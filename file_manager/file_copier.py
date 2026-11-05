# file_manager/file_copier.py
"""
ماژول کپی واقعی، ایمن و بایت‌به‌بایت فایل‌ها و ایجاد ساختار پوشه‌های سپهریار
Safe, real, and chunked byte-by-byte file copier with progress reporting
"""

import os
import shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from config.settings import INSTALL_ROOT_DIR_NAME, SUBFOLDERS
from app_logging.app_logger import logger


def create_sepehryar_root_structure(selected_drive: str, needs_setup: bool = True) -> Dict[str, Path]:
    """
    ایجاد ساختار ریشه در درایو انتخابی بدون حذف یا تغییر داده‌های قبلی:
    [SelectedDrive]:\\SEPEHRYAR\\
        SEPEHRYAR.Setup\\ (فقط در صورت انتخاب حسابداری یا صنعتی)
        SEPEHRYAR.Data\\
        SEPEHRYAR.Backup\\
        SEPEHRYAR.Update\\
    """
    drive_letter = selected_drive.strip().rstrip("\\/").upper()
    if not drive_letter.endswith(":"):
        drive_letter += ":"

    root_path = Path(f"{drive_letter}\\") / INSTALL_ROOT_DIR_NAME
    logger.log("FILE_MANAGER", "CREATE_ROOT", "RUNNING", f"ایجاد ساختار اصلی در: {root_path}")

    # ساخت پوشه ریشه در صورت عدم وجود (بدون حذف فایل‌های قبلی)
    root_path.mkdir(parents=True, exist_ok=True)

    folder_paths: Dict[str, Path] = {"root": root_path}

    subfolders = ["SEPEHRYAR.Data", "SEPEHRYAR.Backup", "SEPEHRYAR.Update"]
    if needs_setup:
        subfolders.insert(0, "SEPEHRYAR.Setup")

    for sub in subfolders:
        sub_path = root_path / sub
        sub_path.mkdir(parents=True, exist_ok=True)
        folder_paths[sub] = sub_path
        logger.log("FILE_MANAGER", "MKDIR", "SUCCESS", f"آماده‌سازی پوشه: {sub_path}")

    # تنظیم مسیر هدف لاگر
    if "SEPEHRYAR.Setup" in folder_paths:
        logger.set_target_dir(folder_paths["SEPEHRYAR.Setup"])
    else:
        log_dir = root_path / "Logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.set_target_dir(log_dir)

    return folder_paths


class FileCopier:
    """
    موتور کپی فایل‌ها با گزارش درصد واقعی بر مبنای بایت‌های کپی‌شده
    """
    def __init__(
        self,
        progress_callback: Optional[Callable[[int, int, str, int, int], None]] = None,
        log_callback: Optional[Callable[[str, str, str], None]] = None,
    ):
        """
        progress_callback(copied_bytes, total_bytes, current_filename, current_file_idx, total_files)
        """
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.cancel_requested = False

    def request_cancel(self):
        self.cancel_requested = True

    @staticmethod
    def _is_excluded(name: str, patterns: Optional[List[str]]) -> bool:
        if not patterns:
            return False
        name_lower = name.lower()
        for pat in patterns:
            pat_str = pat.strip()
            if pat_str.startswith("^") and pat_str.endswith("$"):
                if name_lower == pat_str[1:-1].lower():
                    return True
            else:
                if pat_str.lower() in name_lower:
                    return True
        return False

    def calculate_total_size(
        self,
        source_paths: List[Path],
        exclude_patterns: Optional[List[str]] = None,
    ) -> Tuple[int, int]:
        """
        محاسبه تعداد کل فایل‌ها و مجموع حجم بایت‌ها با قابلیت فیلتر موارد مستثنی
        """
        total_files = 0
        total_bytes = 0

        for src in source_paths:
            if not src.exists():
                continue
            if src.is_file():
                if self._is_excluded(src.name, exclude_patterns):
                    continue
                total_files += 1
                total_bytes += src.stat().st_size
            elif src.is_dir():
                for root, dirs, files in os.walk(src):
                    if exclude_patterns:
                        dirs[:] = [d for d in dirs if not self._is_excluded(d, exclude_patterns)]
                    for f in files:
                        if self._is_excluded(f, exclude_patterns):
                            continue
                        fp = Path(root) / f
                        try:
                            total_bytes += fp.stat().st_size
                            total_files += 1
                        except Exception:
                            pass

        return total_files, total_bytes

    def copy_directory_contents(
        self,
        source_dir: Path,
        destination_dir: Path,
        stage_name: str = "COPY",
        overall_offset_bytes: int = 0,
        overall_total_bytes: int = 0,
        file_offset_idx: int = 0,
        overall_total_files: int = 0,
        exclude_patterns: Optional[List[str]] = None,
        preserve_existing_config: bool = False,
    ) -> Tuple[int, int, int]:
        """
        کپی تمام محتویات یک پوشه به مقصد با حفظ ساختار درختی و فیلتر موارد مستثنی
        خروجی: (bytes_copied, files_copied, errors_count)
        """
        destination_dir.mkdir(parents=True, exist_ok=True)

        copied_bytes = 0
        copied_files = 0
        errors = 0
        chunk_size = 1024 * 1024  # 1 MB

        if not source_dir.exists():
            logger.log(stage_name, "COPY_DIR", "ERROR", f"پوشه مبدأ یافت نشد: {source_dir}")
            return 0, 0, 1

        for root, dirs, files in os.walk(source_dir):
            if self.cancel_requested:
                break

            if exclude_patterns:
                dirs[:] = [d for d in dirs if not self._is_excluded(d, exclude_patterns)]

            rel_path = Path(root).relative_to(source_dir)
            target_sub_dir = destination_dir / rel_path
            target_sub_dir.mkdir(parents=True, exist_ok=True)

            for file in files:
                if self.cancel_requested:
                    break

                if self._is_excluded(file, exclude_patterns):
                    continue

                src_file = Path(root) / file
                dst_file = target_sub_dir / file
                current_file_idx = file_offset_idx + copied_files + 1

                src_stat = src_file.stat()
                src_size = src_stat.st_size

                if preserve_existing_config and dst_file.exists():
                    from file_manager.transactional_update import PRESERVED_NAMES
                    if file.lower() in PRESERVED_NAMES or dst_file.suffix.lower() in (".config", ".lic", ".license"):
                        copied_files += 1
                        copied_bytes += src_size
                        continue

                # ۲. کپی هوشمند و پرش از فایل‌های تغییرنیافته (Smart Delta Skip)
                if dst_file.exists():
                    try:
                        dst_stat = dst_file.stat()
                        if dst_stat.st_size == src_size and abs(dst_stat.st_mtime - src_stat.st_mtime) < 2.0:
                            # فایل با همین حجم و زمان اصلاح قبلاً موجود است؛ بدون نیاز به نوشتن مجدد بایت‌ها
                            copied_files += 1
                            copied_bytes += src_size
                            continue
                    except OSError:
                        pass

                try:
                    from ai.sepehryar_setup_ai import setup_ai
                    dynamic_chunk, delay = setup_ai.get_dynamic_copy_params()

                    with open(src_file, "rb") as fsrc, open(dst_file, "wb") as fdst:
                        while True:
                            if self.cancel_requested:
                                break

                            chunk = fsrc.read(dynamic_chunk)
                            if not chunk:
                                break
                            fdst.write(chunk)
                            copied_bytes += len(chunk)

                            if delay > 0:
                                import time
                                time.sleep(delay)

                            if self.progress_callback and overall_total_bytes > 0:
                                current_overall = overall_offset_bytes + copied_bytes
                                self.progress_callback(
                                    current_overall,
                                    overall_total_bytes,
                                    file,
                                    current_file_idx,
                                    overall_total_files,
                                )

                    # کپی ویژگی‌های متادیتا (زمان دسترسی/اصلاح)
                    try:
                        shutil.copystat(src_file, dst_file)
                    except Exception:
                        pass

                    copied_files += 1

                except Exception as ex:
                    errors += 1
                    logger.log(
                        stage_name,
                        "COPY_FILE",
                        "ERROR",
                        f"خطا در کپی فایل {file}: {ex}",
                        file_path=str(src_file),
                        error=str(ex),
                    )

        return copied_bytes, copied_files, errors
