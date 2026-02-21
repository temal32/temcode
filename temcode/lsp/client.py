from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from urllib.request import url2pathname

from PySide6.QtCore import QObject, QProcess, Signal


ResponseCallback = Callable[[object | None, dict[str, object] | None], None]


def path_to_uri(path: str) -> str:
    return Path(os.path.abspath(path)).as_uri()


def uri_to_path(uri: str) -> str | None:
    parsed = urlparse(uri)
    if parsed.scheme.lower() != "file":
        return None

    resolved_path = url2pathname(parsed.path)
    if parsed.netloc and parsed.netloc.lower() not in {"", "localhost"}:
        resolved_path = f"//{parsed.netloc}{resolved_path}"

    if os.name == "nt" and resolved_path.startswith("\\") and len(resolved_path) > 2 and resolved_path[2] == ":":
        resolved_path = resolved_path.lstrip("\\")

    if not resolved_path:
        return None
    return os.path.abspath(resolved_path)


class LspClient(QObject):
    ready_changed = Signal(bool, str)
    diagnostics_published = Signal(str, object)
    log_message = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._root_path: str | None = None
        self._command: list[str] = []
        self._server_capabilities: dict[str, object] = {}
        self._is_ready = False

        self._buffer = bytearray()
        self._expected_content_length: int | None = None
        self._next_request_id = 1
        self._pending_requests: dict[int, ResponseCallback] = {}

        self._opened_document_versions: dict[str, int] = {}
        self._pending_document_sync: dict[str, tuple[str, str]] = {}

    def is_ready(self) -> bool:
        return self._is_ready

    def root_path(self) -> str | None:
        return self._root_path

    def ensure_started(self, root_path: str) -> bool:
        normalized_root = os.path.abspath(root_path)
        if not os.path.isdir(normalized_root):
            normalized_root = os.getcwd()

        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            if self._root_path and os.path.normcase(self._root_path) == os.path.normcase(normalized_root):
                return True
            self.stop()

        return self._start_process(normalized_root)

    def stop(self) -> None:
        process = self._process
        self._process = None

        previously_ready = self._is_ready
        self._is_ready = False
        self._server_capabilities = {}
        self._root_path = None
        self._command = []
        self._pending_requests.clear()
        self._opened_document_versions.clear()
        self._pending_document_sync.clear()
        self._buffer.clear()
        self._expected_content_length = None

        if previously_ready:
            self.ready_changed.emit(False, "stopped")

        if process is None:
            return

        if process.state() != QProcess.ProcessState.NotRunning:
            try:
                self._send_message(
                    {
                        "jsonrpc": "2.0",
                        "id": self._next_request_id,
                        "method": "shutdown",
                        "params": {},
                    },
                    process=process,
                )
                self._next_request_id += 1
                self._send_message({"jsonrpc": "2.0", "method": "exit", "params": {}}, process=process)
            except RuntimeError:
                pass

            process.terminate()
            if not process.waitForFinished(1200):
                process.kill()
                process.waitForFinished(1200)

        process.deleteLater()

    def open_or_change_document(self, file_path: str, text: str, language_id: str = "python") -> bool:
        absolute_path = os.path.abspath(file_path)
        uri = path_to_uri(absolute_path)

        if not self._is_ready:
            self._pending_document_sync[uri] = (text, language_id)
            return False

        version = self._opened_document_versions.get(uri)
        if version is None:
            self._opened_document_versions[uri] = 1
            self._send_notification(
                "textDocument/didOpen",
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": language_id,
                        "version": 1,
                        "text": text,
                    }
                },
            )
            return True

        next_version = version + 1
        self._opened_document_versions[uri] = next_version
        self._send_notification(
            "textDocument/didChange",
            {
                "textDocument": {"uri": uri, "version": next_version},
                "contentChanges": [{"text": text}],
            },
        )
        return True

    def close_document(self, file_path: str) -> None:
        uri = path_to_uri(file_path)
        self._pending_document_sync.pop(uri, None)
        if uri not in self._opened_document_versions:
            return

        self._opened_document_versions.pop(uri, None)
        if not self._is_ready:
            return

        self._send_notification("textDocument/didClose", {"textDocument": {"uri": uri}})

    def request_completion(self, file_path: str, line: int, character: int, callback: ResponseCallback) -> bool:
        if not self._is_ready:
            callback(None, {"message": "Language server is not ready."})
            return False

        self._send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": path_to_uri(file_path)},
                "position": {"line": max(0, int(line)), "character": max(0, int(character))},
                "context": {"triggerKind": 1},
            },
            callback,
        )
        return True

    def request_definition(self, file_path: str, line: int, character: int, callback: ResponseCallback) -> bool:
        if not self._is_ready:
            callback(None, {"message": "Language server is not ready."})
            return False

        self._send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": path_to_uri(file_path)},
                "position": {"line": max(0, int(line)), "character": max(0, int(character))},
            },
            callback,
        )
        return True

    def request_rename(
        self,
        file_path: str,
        line: int,
        character: int,
        new_name: str,
        callback: ResponseCallback,
    ) -> bool:
        if not self._is_ready:
            callback(None, {"message": "Language server is not ready."})
            return False

        self._send_request(
            "textDocument/rename",
            {
                "textDocument": {"uri": path_to_uri(file_path)},
                "position": {"line": max(0, int(line)), "character": max(0, int(character))},
                "newName": new_name,
            },
            callback,
        )
        return True

    def _start_process(self, root_path: str) -> bool:
        for candidate in self._python_server_candidates():
            if not candidate:
                continue

            program = candidate[0]
            args = candidate[1:]
            if not self._is_executable_candidate(program, args):
                continue

            process = QProcess(self)
            process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
            process.setWorkingDirectory(root_path)
            process.readyReadStandardOutput.connect(self._on_stdout_ready)
            process.readyReadStandardError.connect(self._on_stderr_ready)
            process.finished.connect(self._on_process_finished)
            process.errorOccurred.connect(self._on_process_error)

            process.start(program, args)
            if not process.waitForStarted(2000):
                process.deleteLater()
                continue

            self._process = process
            self._root_path = root_path
            self._command = candidate
            self._buffer.clear()
            self._expected_content_length = None
            self._next_request_id = 1
            self._pending_requests.clear()
            self._opened_document_versions.clear()
            self._pending_document_sync.clear()
            self._server_capabilities = {}
            self._is_ready = False

            self.log_message.emit(f"Starting Python LSP server: {' '.join(candidate)}")
            self._send_initialize_request()
            self.ready_changed.emit(False, "initializing")
            return True

        self.ready_changed.emit(False, "server not found")
        self.log_message.emit(
            "No Python LSP server found. Install one of: python-lsp-server (pylsp), pyright-langserver, or jedi-language-server."
        )
        return False

    def _is_executable_candidate(self, program: str, args: list[str]) -> bool:
        normalized = os.path.basename(program).lower()
        if program == sys.executable:
            return True
        if normalized in {"python", "python.exe"} and args[:1] == ["-m"]:
            return True
        if os.path.isabs(program):
            return os.path.exists(program)
        return shutil.which(program) is not None

    def _python_server_candidates(self) -> list[list[str]]:
        candidates: list[list[str]] = []
        override = os.environ.get("TEMCODE_PYTHON_LSP_COMMAND", "").strip()
        if override:
            try:
                parsed = shlex.split(override, posix=False)
                if parsed:
                    candidates.append(parsed)
            except ValueError:
                self.log_message.emit("Invalid TEMCODE_PYTHON_LSP_COMMAND value; ignoring override.")

        candidates.extend(
            [
                ["pylsp"],
                [sys.executable, "-m", "pylsp"],
                ["pyright-langserver", "--stdio"],
                ["jedi-language-server"],
            ]
        )
        return candidates

    def _send_initialize_request(self) -> None:
        if self._process is None or self._root_path is None:
            return

        root_uri = path_to_uri(self._root_path)
        params: dict[str, object] = {
            "processId": os.getpid(),
            "clientInfo": {"name": "Temcode"},
            "rootUri": root_uri,
            "workspaceFolders": [{"uri": root_uri, "name": os.path.basename(self._root_path) or self._root_path}],
            "capabilities": {
                "workspace": {"workspaceEdit": {"documentChanges": True}},
                "textDocument": {
                    "completion": {"completionItem": {"snippetSupport": True}},
                    "definition": {},
                    "rename": {"dynamicRegistration": False},
                    "publishDiagnostics": {"relatedInformation": True},
                    "synchronization": {"didSave": True},
                },
            },
        }
        self._send_request("initialize", params, self._on_initialize_response)

    def _on_initialize_response(self, result: object | None, error: dict[str, object] | None) -> None:
        if error is not None:
            self.log_message.emit(f"LSP initialize failed: {error}")
            self.ready_changed.emit(False, "initialize failed")
            return

        if isinstance(result, dict):
            capabilities = result.get("capabilities")
            if isinstance(capabilities, dict):
                self._server_capabilities = capabilities

        self._send_notification("initialized", {})
        self._is_ready = True
        command_label = " ".join(self._command) if self._command else "unknown"
        self.ready_changed.emit(True, f"ready ({command_label})")
        self.log_message.emit(f"LSP initialized with server: {command_label}")
        self._flush_pending_document_sync()

    def _flush_pending_document_sync(self) -> None:
        if not self._is_ready or not self._pending_document_sync:
            return
        pending_items = list(self._pending_document_sync.items())
        self._pending_document_sync.clear()
        for uri, (text, language_id) in pending_items:
            path = uri_to_path(uri)
            if not path:
                continue
            self.open_or_change_document(path, text, language_id=language_id)

    def _send_request(self, method: str, params: dict[str, object], callback: ResponseCallback) -> None:
        request_id = self._next_request_id
        self._next_request_id += 1
        self._pending_requests[request_id] = callback
        self._send_message(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )

    def _send_notification(self, method: str, params: dict[str, object]) -> None:
        self._send_message({"jsonrpc": "2.0", "method": method, "params": params})

    def _send_response(self, request_id: int, result: object) -> None:
        self._send_message({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _send_message(self, payload: dict[str, object], process: QProcess | None = None) -> None:
        target = process or self._process
        if target is None or target.state() != QProcess.ProcessState.Running:
            return

        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(encoded)}\r\n\r\n".encode("ascii")
        target.write(header + encoded)

    def _on_stdout_ready(self) -> None:
        if self._process is None:
            return

        self._buffer.extend(bytes(self._process.readAllStandardOutput()))
        while True:
            if self._expected_content_length is None:
                header_end = self._buffer.find(b"\r\n\r\n")
                if header_end < 0:
                    return

                raw_headers = bytes(self._buffer[:header_end]).decode("ascii", errors="replace")
                del self._buffer[: header_end + 4]

                content_length = None
                for line in raw_headers.split("\r\n"):
                    if line.lower().startswith("content-length:"):
                        try:
                            content_length = int(line.split(":", 1)[1].strip())
                        except ValueError:
                            content_length = None
                        break
                if content_length is None:
                    continue
                self._expected_content_length = max(0, content_length)

            if len(self._buffer) < self._expected_content_length:
                return

            payload_bytes = bytes(self._buffer[: self._expected_content_length])
            del self._buffer[: self._expected_content_length]
            self._expected_content_length = None

            try:
                message = json.loads(payload_bytes.decode("utf-8"))
            except json.JSONDecodeError as exc:
                self.log_message.emit(f"LSP parse error: {exc}")
                continue
            self._handle_message(message)

    def _on_stderr_ready(self) -> None:
        if self._process is None:
            return

        raw = bytes(self._process.readAllStandardError())
        if not raw:
            return
        text = raw.decode("utf-8", errors="replace").strip()
        if text:
            self.log_message.emit(f"[server] {text}")

    def _handle_message(self, message: object) -> None:
        if not isinstance(message, dict):
            return

        message_id = message.get("id")
        if message_id is not None and ("result" in message or "error" in message):
            try:
                numeric_id = int(message_id)
            except (TypeError, ValueError):
                numeric_id = -1
            callback = self._pending_requests.pop(numeric_id, None)
            if callback is not None:
                result = message.get("result")
                error = message.get("error")
                callback(result, error if isinstance(error, dict) else None)
            return

        method = message.get("method")
        if not isinstance(method, str):
            return
        params = message.get("params")
        params_dict = params if isinstance(params, dict) else {}

        if method == "textDocument/publishDiagnostics":
            uri = params_dict.get("uri")
            diagnostics = params_dict.get("diagnostics", [])
            if isinstance(uri, str) and isinstance(diagnostics, list):
                self.diagnostics_published.emit(uri, diagnostics)
            return

        if method in {"window/logMessage", "window/showMessage"}:
            msg = params_dict.get("message")
            if isinstance(msg, str) and msg.strip():
                self.log_message.emit(msg.strip())
            return

        if message_id is None:
            return

        try:
            numeric_id = int(message_id)
        except (TypeError, ValueError):
            return
        if method == "workspace/configuration":
            items = params_dict.get("items")
            count = len(items) if isinstance(items, list) else 0
            self._send_response(numeric_id, [{} for _ in range(count)])
            return

        if method in {"client/registerCapability", "client/unregisterCapability", "window/workDoneProgress/create"}:
            self._send_response(numeric_id, None)
            return

        if method == "workspace/applyEdit":
            self._send_response(
                numeric_id,
                {
                    "applied": False,
                    "failureReason": "Temcode applies workspace edits from direct request results only.",
                },
            )
            return

        self._send_response(numeric_id, None)

    def _on_process_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        was_ready = self._is_ready
        self._is_ready = False
        self._pending_requests.clear()
        self._opened_document_versions.clear()
        self._pending_document_sync.clear()
        self._buffer.clear()
        self._expected_content_length = None
        self.log_message.emit(f"LSP process exited with code {exit_code}.")
        self.ready_changed.emit(False, "server exited")
        if self._process is not None:
            self._process.deleteLater()
            self._process = None
        if was_ready:
            self._server_capabilities = {}

    def _on_process_error(self, error: QProcess.ProcessError) -> None:
        self.log_message.emit(f"LSP process error: {error}")
