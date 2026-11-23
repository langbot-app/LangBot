from __future__ import annotations

import logging
import os
from pathlib import Path
import re
import uuid
import weakref


def validate_instance_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value
    ):
        raise ValueError(
            "Box instance ID must contain 1-128 letters, digits, dots, colons, underscores or hyphens"
        )
    return value


class BoxIdentity:
    def __init__(
        self,
        logger: logging.Logger,
        instance_id: str | None,
        data_dir: str | Path | None,
    ):
        self.logger = logger
        self.data_dir = Path(
            data_dir or os.environ.get("LANGBOT_BOX_DATA_DIR") or "data/box"
        )
        self.persistent = True
        self._release = None
        if instance_id is not None:
            self.instance_id = validate_instance_id(instance_id)
            return
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            identity_path = self.data_dir / "instance-id"
            try:
                with identity_path.open("x", encoding="utf-8") as identity_file:
                    identity_file.write(uuid.uuid4().hex[:12] + "\n")
            except FileExistsError:
                pass
            self.instance_id = validate_instance_id(
                identity_path.read_text(encoding="utf-8").strip()
            )
        except OSError:
            self.instance_id = uuid.uuid4().hex[:12]
            self.persistent = False
            self.logger.warning(
                "Box identity cannot be persisted; using a random ID without orphan cleanup"
            )

    def acquire(self) -> bool:
        if not self.persistent:
            return False
        if self._release is not None:
            raise RuntimeError("Box runtime is already initialized")
        descriptor = None
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(
                self.data_dir / f"{self.instance_id.replace(':', '%3A')}.lock",
                os.O_CREAT | os.O_RDWR,
                0o600,
            )
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError(
                    "Box instance ID is already in use or cannot be locked"
                ) from exc
            self._release = weakref.finalize(self, os.close, descriptor)
            descriptor = None
            return True
        except OSError:
            self.logger.warning(
                "Box identity lock is unavailable; skipping orphan cleanup"
            )
            return False
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def release(self) -> None:
        if self._release is not None:
            self._release()
            self._release = None
