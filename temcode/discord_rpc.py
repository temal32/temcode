from __future__ import annotations

import json
import os
import struct
import time
import uuid
from typing import BinaryIO, Callable


class DiscordRpcClient:
    _OP_HANDSHAKE = 0
    _OP_FRAME = 1
    _PIPE_PATH_TEMPLATE = r"\\?\pipe\discord-ipc-{index}"
    _PIPE_INDEX_LIMIT = 10
    _CONNECT_RETRY_INTERVAL_SECONDS = 4.0
    _CONNECT_LOG_INTERVAL_SECONDS = 30.0

    def __init__(
        self,
        client_id: str,
        *,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        self._client_id = client_id.strip()
        self._logger = logger
        self._process_id = os.getpid()
        self._pipe: BinaryIO | None = None
        self._pipe_path: str | None = None
        self._last_connect_attempt_at = 0.0
        self._last_connect_log_at = 0.0

    @property
    def is_connected(self) -> bool:
        return self._pipe is not None

    def set_client_id(self, client_id: str) -> None:
        normalized = client_id.strip()
        if normalized == self._client_id:
            return
        self._client_id = normalized
        self.close(clear_activity=True)

    def connect(self, *, force: bool = False) -> bool:
        if self._pipe is not None:
            return True
        if not self._client_id:
            return False

        now = time.monotonic()
        if not force and (now - self._last_connect_attempt_at) < self._CONNECT_RETRY_INTERVAL_SECONDS:
            return False
        self._last_connect_attempt_at = now

        for pipe_index in range(self._PIPE_INDEX_LIMIT):
            pipe_path = self._PIPE_PATH_TEMPLATE.format(index=pipe_index)
            try:
                pipe = open(pipe_path, "r+b", buffering=0)
                self._write_frame(
                    pipe,
                    self._OP_HANDSHAKE,
                    {
                        "v": 1,
                        "client_id": self._client_id,
                    },
                )
            except OSError:
                continue

            self._pipe = pipe
            self._pipe_path = pipe_path
            self._log(f"[discord] Connected to Discord IPC ({pipe_path}).")
            return True

        if (now - self._last_connect_log_at) >= self._CONNECT_LOG_INTERVAL_SECONDS:
            self._last_connect_log_at = now
            self._log("[discord] Discord IPC is unavailable. Is Discord running?")
        return False

    def set_activity(self, activity: dict[str, object] | None) -> bool:
        if not self.connect():
            return False

        payload = {
            "cmd": "SET_ACTIVITY",
            "args": {
                "pid": self._process_id,
                "activity": activity,
            },
            "nonce": uuid.uuid4().hex,
        }
        if self._send_frame(payload):
            return True

        if not self.connect(force=True):
            return False
        return self._send_frame(payload)

    def clear_activity(self) -> bool:
        return self.set_activity(None)

    def close(self, *, clear_activity: bool = False) -> None:
        if self._pipe is None:
            return

        if clear_activity:
            try:
                self._send_frame(
                    {
                        "cmd": "SET_ACTIVITY",
                        "args": {
                            "pid": self._process_id,
                            "activity": None,
                        },
                        "nonce": uuid.uuid4().hex,
                    }
                )
            except OSError:
                pass

        self._close_pipe()

    def _send_frame(self, payload: dict[str, object]) -> bool:
        if self._pipe is None:
            return False
        try:
            self._write_frame(self._pipe, self._OP_FRAME, payload)
            return True
        except OSError:
            self._close_pipe()
            return False

    def _close_pipe(self) -> None:
        pipe = self._pipe
        self._pipe = None
        self._pipe_path = None
        if pipe is not None:
            try:
                pipe.close()
            except OSError:
                pass

    @staticmethod
    def _write_frame(pipe: BinaryIO, opcode: int, payload: dict[str, object]) -> None:
        payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        header = struct.pack("<II", int(opcode), len(payload_bytes))
        pipe.write(header + payload_bytes)
        pipe.flush()

    def _log(self, message: str) -> None:
        if self._logger is not None:
            self._logger(message)
