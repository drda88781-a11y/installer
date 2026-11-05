# logging/app_logger.py
"""
سیستم لاگینگ جامع، ساختاریافته و Thread-Safe اینستالر سپهریار
Structured, multi-channel and thread-safe logging for SEPEHRYAR Installer
"""

import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional
from dataclasses import dataclass

# ایمن‌سازی خروجی استاندارد کنسول در ویندوز برای یونیکد و متون فارسی
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


@dataclass
class LogEntry:
    timestamp: str
    stage: str
    operation: str
    status: str
    message: str
    file_path: Optional[str] = None
    exit_code: Optional[int] = None
    sql_instance: Optional[str] = None
    error: Optional[str] = None

    def to_formatted_string(self) -> str:
        lines = [f"[{self.timestamp}] [{self.stage}] [{self.operation}] {self.status}"]
        if self.message:
            lines.append(f"  پیام: {self.message}")
        if self.sql_instance:
            lines.append(f"  اس‌کیو‌ال اینستنس: {self.sql_instance}")
        if self.file_path:
            lines.append(f"  مسیر فایل: {self.file_path}")
        if self.exit_code is not None:
            lines.append(f"  کد خروج: {self.exit_code}")
        if self.error:
            lines.append(f"  خطا: {self.error}")
        return "\n".join(lines)


class InstallerLogger:
    """
    لاگر مرکزی اینستالر که لاگ‌ها را در فایل و در حافظه (جهت نمایش در UI) ثبت می‌کند.
    """
    _instance: Optional["InstallerLogger"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "InstallerLogger":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(InstallerLogger, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.lock = threading.Lock()
        self.entries: List[LogEntry] = []
        self.listeners: List[Callable[[LogEntry], None]] = []
        
        # مسیر اولیه لاگ محلی
        self.local_log_dir = Path.home() / ".sepehryar_installer" / "logs"
        self.local_log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.local_log_file = self.local_log_dir / f"install_{timestamp_str}.log"
        self.setup_target_log_file: Optional[Path] = None
        
        # نوشتن سربرگ اولیه
        self._write_to_file(
            f"============================================================\n"
            f"SEPEHRYAR INSTALLER LOG SESSION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"============================================================\n",
            self.local_log_file
        )

    def set_target_dir(self, setup_dir: Path):
        """
        تعیین مسیر مقصد در [Drive]:\\SEPEHRYAR\\SEPEHRYAR.Setup جهت ذخیره دائمی لاگ‌ها
        """
        with self.lock:
            try:
                setup_dir.mkdir(parents=True, exist_ok=True)
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.setup_target_log_file = setup_dir / f"install_{timestamp_str}.log"
                
                # انتقال لاگ‌های قبلی به فایل مقصد
                with open(self.setup_target_log_file, "a", encoding="utf-8") as f:
                    f.write(
                        f"============================================================\n"
                        f"SEPEHRYAR PROFESSIONAL WINDOWS INSTALLER LOG\n"
                        f"تاریخ شروع: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"مسیر نصب: {setup_dir.parent}\n"
                        f"============================================================\n\n"
                    )
                    for entry in self.entries:
                        f.write(entry.to_formatted_string() + "\n\n")
            except Exception as ex:
                print(f"[Logger Warning] Could not initialize target log file: {ex}", file=sys.stderr)

    def add_listener(self, callback: Callable[[LogEntry], None]):
        """افزودن شنونده برای آپدیت زنده در UI"""
        with self.lock:
            if callback not in self.listeners:
                self.listeners.append(callback)

    def remove_listener(self, callback: Callable[[LogEntry], None]):
        with self.lock:
            if callback in self.listeners:
                self.listeners.remove(callback)

    def log(
        self,
        stage: str,
        operation: str,
        status: str,
        message: str = "",
        file_path: Optional[str] = None,
        exit_code: Optional[int] = None,
        sql_instance: Optional[str] = None,
        error: Optional[str] = None,
    ) -> LogEntry:
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = LogEntry(
            timestamp=timestamp,
            stage=stage,
            operation=operation,
            status=status,
            message=message,
            file_path=file_path,
            exit_code=exit_code,
            sql_instance=sql_instance,
            error=error,
        )

        with self.lock:
            self.entries.append(entry)
            formatted = entry.to_formatted_string() + "\n\n"
            
            # ثبت در فایل محلی
            self._write_to_file(formatted, self.local_log_file)
            
            # ثبت در فایل مقصد در صورت آماده بودن
            if self.setup_target_log_file:
                self._write_to_file(formatted, self.setup_target_log_file)
            
            # چاپ در کنسول جهت مانیتورینگ
            try:
                print(f"[{entry.timestamp}] [{entry.stage}] [{entry.operation}] -> {entry.status} {entry.message}")
            except UnicodeEncodeError:
                safe_msg = entry.message.encode("ascii", errors="backslashreplace").decode("ascii")
                print(f"[{entry.timestamp}] [{entry.stage}] [{entry.operation}] -> {entry.status} {safe_msg}")
            except Exception:
                pass

            if entry.error:
                try:
                    print(f"   [ERROR] {entry.error}", file=sys.stderr)
                except Exception:
                    pass

            # اطلاع‌رسانی به شنونده‌های UI
            for listener in list(self.listeners):
                try:
                    listener(entry)
                except Exception as ex:
                    print(f"[Logger Listener Error] {ex}", file=sys.stderr)

        return entry

    def _write_to_file(self, content: str, target_file: Path):
        try:
            with open(target_file, "a", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass

    def get_all_entries(self) -> List[LogEntry]:
        with self.lock:
            return list(self.entries)

    def get_full_text(self) -> str:
        with self.lock:
            return "\n\n".join(e.to_formatted_string() for e in self.entries)


# نمونه سینگلتون سراسری
logger = InstallerLogger()
