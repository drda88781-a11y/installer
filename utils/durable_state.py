"""Atomic state files and a process lock shared by installer and updater."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import tempfile


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def relative_path(value: str) -> str:
    """Reject paths which Windows normalizes outside or onto another file."""
    if not isinstance(value, str) or not value:
        raise ValueError("مسیر فایل در شناسنامه خالی است.")
    value = value.replace("\\", "/")
    parts = value.split("/")
    devices = {"CON", "PRN", "AUX", "NUL"} | {f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)}
    if PureWindowsPath(value).drive or value.startswith("/"):
        raise ValueError(f"مسیر مطلق مجاز نیست: {value}")
    for part in parts:
        if (part in ("", ".", "..") or part.rstrip(" .") != part
                or any(ord(c) < 32 or c in ':<>"|?*' for c in part)
                or part.split(".")[0].upper() in devices):
            raise ValueError(f"مسیر فایل مجاز نیست: {value}")
    return value


def contained_path(root: Path, relative: str) -> Path:
    path = root / relative_path(relative)
    path.resolve().relative_to(root.resolve())
    return path


@contextmanager
def installation_lock(root: Path):
    """The OS releases this lock after process termination, including a crash."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".sepehryar-operation.lock").open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("نصب یا آپدیت دیگری روی همین مسیر در حال اجرا است.") from exc
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError("Another installation is using this directory") from exc
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)
