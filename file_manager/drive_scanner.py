# file_manager/drive_scanner.py
"""
ماژول اسکن و بررسی درایوهای ذخیره‌سازی ویندوز و اعمال محدودیت‌های نصب
Windows storage drives scanner and installation constraints validator
"""

from dataclasses import dataclass
from typing import List
import psutil

from config.settings import MIN_FREE_SPACE_GB, DEV_ALLOW_LOW_SPACE
from app_logging.app_logger import logger


@dataclass
class DriveInfo:
    letter: str                 # e.g. "D:"
    mount_point: str            # e.g. "D:\\"
    total_gb: float
    used_gb: float
    free_gb: float
    is_c_drive: bool
    is_eligible: bool
    status_text: str
    status_reason: str


def scan_drives(dev_allow_low_space: bool = DEV_ALLOW_LOW_SPACE) -> List[DriveInfo]:
    """
    اسکن تمام درایوهای متصل به سیستم و بررسی شرایط انتخاب برای نصب سپهریار:
    ۱. نصب روی درایو C ممنوع است.
    ۲. حداقل فضای آزاد باید ۱۰۰ گیگابایت باشد (مگر در حالت تست/توسعه).
    """
    logger.log("DRIVE_SCAN", "START", "RUNNING", "اسکن درایوهای فعال سیستم جهت انتخاب مسیر نصب")
    results: List[DriveInfo] = []

    for part in psutil.disk_partitions(all=False):
        # نادیده گرفتن CD-ROM و درایوهای مجازی بدون فایل‌سیستم
        if "cdrom" in part.opts or not part.fstype:
            continue

        mount = part.mountpoint
        letter = mount[:2].upper()
        if not letter.endswith(":"):
            continue

        try:
            usage = psutil.disk_usage(mount)
            total_gb = round(usage.total / (1024 ** 3), 1)
            used_gb = round(usage.used / (1024 ** 3), 1)
            free_gb = round(usage.free / (1024 ** 3), 1)

            is_c = (letter == "C:")
            is_eligible = False
            status_text = ""
            status_reason = ""

            if is_c:
                is_eligible = False
                status_text = "✕ نصب روی درایو C ممنوع است"
                status_reason = "طبق استانداردهای پایگاه داده و نرم‌افزار مالی سپهریار، نصب روی درایو ویندوز (C:) مجاز نمی‌باشد."
            elif free_gb >= MIN_FREE_SPACE_GB:
                is_eligible = True
                status_text = "✓ مناسب"
                status_reason = f"فضای آزاد ({free_gb} GB) بیشتر از حد نصاب ۱۰۰ گیگابایت است."
            else:
                # کمتر از ۱۰۰ گیگابایت
                if dev_allow_low_space:
                    is_eligible = True
                    status_text = "✓ مناسب (حالت تست)"
                    status_reason = f"فضای آزاد {free_gb} GB است (حالت تست فعال است)."
                else:
                    is_eligible = False
                    status_text = "✕ فضای کافی نیست"
                    status_reason = f"حداقل فضای موردنیاز ۱۰۰ گیگابایت است (فضای آزاد: {free_gb} GB)."

            info = DriveInfo(
                letter=letter,
                mount_point=mount,
                total_gb=total_gb,
                used_gb=used_gb,
                free_gb=free_gb,
                is_c_drive=is_c,
                is_eligible=is_eligible,
                status_text=status_text,
                status_reason=status_reason,
            )
            results.append(info)
            logger.log(
                "DRIVE_SCAN",
                letter,
                "ELIGIBLE" if is_eligible else "INELIGIBLE",
                f"Drive {letter} Total={total_gb}GB, Used={used_gb}GB, Free={free_gb}GB -> {status_text}"
            )
        except Exception as e:
            logger.log("DRIVE_SCAN", letter, "ERROR", f"خطا در اسکن درایو {letter}: {e}")

    # اگر هیچ درایو دیگری غیر از C در سیستم نباشد، درایو C به عنوان تنها گزینه مجاز فعال شود
    non_c_exists = any(not d.is_c_drive for d in results)
    if not non_c_exists:
        for d in results:
            if d.is_c_drive and d.free_gb >= 15.0:
                d.is_eligible = True
                d.status_text = "⚪ مجاز (تنها درایو موجود)"
                d.status_reason = "سیستم فاقد درایو ثانویه است؛ نصب روی پوشه C:\\SEPEHRYAR مجاز گردید."

    # سورت کردن درایوها: درایوهای واجد شرایط اول باشند
    results.sort(key=lambda d: (not d.is_eligible, d.letter))
    return results
