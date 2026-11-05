from typing import Any
# system_check/hardware_checker.py
"""
ماژول بررسی جامع و واقعی شرایط سخت‌افزاری و نرم‌افزاری سیستم جهت نصب سپهریار
Comprehensive and real system requirements checker for SEPEHRYAR Installer
"""

import ctypes
import os
import platform
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional
import psutil

from config.settings import (
    MIN_RAM_GB,
    MIN_RAM_TOLERANCE_GB,
    MIN_CPU_GENERATION,
    MIN_FREE_SPACE_GB,
    MIN_CLIENT_RAM_GB,
    MIN_CLIENT_RAM_TOLERANCE_GB,
    MIN_CLIENT_FREE_SPACE_GB,
    REQUIRED_ARCH,
    DEV_ALLOW_LOW_SPACE,
)
from app_logging.app_logger import logger


@dataclass
class RequirementItem:
    key: str
    title_fa: str
    icon_name: str
    detected_value: str
    required_value: str
    passed: bool
    status_text: str
    failure_reason: Optional[str] = None
    is_critical: bool = True


@dataclass
class SystemCheckResult:
    all_passed: bool
    can_proceed: bool
    items: List[RequirementItem]
    admin_detected: bool


def is_admin() -> bool:
    """بررسی دسترسی ادمینستریتور"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def get_physical_ram_gb() -> float:
    """
    تشخیص رم فیزیکی نصب‌شده روی مادربورد از طریق WMI یا psutil
    """
    try:
        import subprocess
        cmd = 'Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum | Select-Object -ExpandProperty Sum'
        output = subprocess.check_output(['powershell', '-NoProfile', '-Command', cmd], text=True, timeout=5).strip()
        if output.isdigit():
            bytes_total = int(output)
            return round(bytes_total / (1024 ** 3), 2)
    except Exception:
        pass

    # فال‌بک با psutil
    mem = psutil.virtual_memory()
    return round(mem.total / (1024 ** 3), 2)


def get_cpu_info() -> Dict[str, any]:
    """دریافت نام، تعداد هسته و نسل پردازنده"""
    cpu_name = platform.processor() or "Unknown CPU"
    cores = psutil.cpu_count(logical=False) or 1
    threads = psutil.cpu_count(logical=True) or 1

    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        if name:
            cpu_name = name.strip()
    except Exception:
        pass

    # تشخیص نسل پردازنده
    # مثال: i5-8365U یا i7-10700 یا Ryzen 5 3600
    gen_passed = False
    details = f"{cpu_name} ({cores} هسته / {threads} رشته)"

    intel_match = re.search(r'i[3579]-(\d{1,2})\d{2,3}', cpu_name, re.IGNORECASE)
    if intel_match:
        gen = int(intel_match.group(1))
        if gen >= MIN_CPU_GENERATION:
            gen_passed = True
    elif "ryzen" in cpu_name.lower():
        ryzen_match = re.search(r'ryzen\s+[3579]\s+(\d)', cpu_name, re.IGNORECASE)
        if ryzen_match:
            r_gen = int(ryzen_match.group(1))
            if r_gen >= 2:
                gen_passed = True
        else:
            gen_passed = True
    elif cores >= 4 and threads >= 8:
        # پردازنده‌های چند هسته‌ای قدرتمند معادل (Xeon، Core Ultra و غیره)
        gen_passed = True
    elif cores >= 4:
        gen_passed = True

    return {
        "name": cpu_name,
        "cores": cores,
        "threads": threads,
        "details": details,
        "passed": gen_passed,
    }


def get_windows_info(install_mode: str = "server", sql_version: str = "2019") -> Dict[str, any]:
    """بررسی سیستم‌عامل ویندوز متناسب با حالت نصب و نسخه SQL Server"""
    is_win = platform.system() == "Windows"
    win_release = platform.release()  # e.g. "10", "11", "7", "8.1"
    win_version = platform.version()  # e.g. "10.0.19045"
    
    passed = False
    reason = None
    display = f"Windows {win_release} (بیلد {win_version})"

    if not is_win:
        passed = False
        reason = "سیستم‌عامل ویندوز نیست."
    elif win_release in ["10", "11"]:
        passed = True
    elif "server" in platform.platform().lower():
        passed = True
    elif win_release in ["7", "8", "8.1"]:
        if install_mode == "client" or str(sql_version) == "2014":
            passed = True
            display = f"Windows {win_release} (سازگار با کلاینت و SQL 2014)"
        else:
            # در حالت سرور و SQL 2019، پیشنهاد نسخه 2014 داده می‌شود اما اجازه ادامه با هشدار داده می‌شود
            passed = True
            reason = "برای این نسخه ویندوز، استفاده از SQL Server 2014 توصیه می‌شود."
            display = f"Windows {win_release} (پیشنهاد: SQL 2014)"
    else:
        passed = True
        display = f"Windows {win_release}"

    return {
        "display": display,
        "passed": passed,
        "reason": reason,
    }


def get_storage_info(min_space_gb: float = MIN_FREE_SPACE_GB) -> Dict[str, any]:
    """بررسی فضای درایوهای غیر C سیستم متناسب با نوع نصب"""
    non_c_drives = []
    max_free_gb = 0.0
    best_drive = None

    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts or part.fstype == "":
            continue
        mount = part.mountpoint
        drive_letter = mount[:2].upper()
        if drive_letter == "C:":
            continue
        try:
            usage = psutil.disk_usage(mount)
            free_gb = round(usage.free / (1024 ** 3), 1)
            total_gb = round(usage.total / (1024 ** 3), 1)
            non_c_drives.append((drive_letter, free_gb, total_gb))
            if free_gb > max_free_gb:
                max_free_gb = free_gb
                best_drive = drive_letter
        except Exception:
            pass

    passed = max_free_gb >= min_space_gb
    reason = None

    if not non_c_drives:
        # بررسی درایو C به عنوان فال‌بک برای سیستم‌های تک‌پارتیشن (POS / لپ‌تاپ‌های تک SSD)
        try:
            c_usage = psutil.disk_usage("C:\\")
            c_free = round(c_usage.free / (1024 ** 3), 1)
            display = f"درایو C با {c_free} GB فضای آزاد (سیستم تک‌پارتیشن)"
            passed = c_free >= 15.0  # حداقل ۱۵ گیگابایت برای سیستم‌های تک‌درایوه
            best_drive = "C:"
            max_free_gb = c_free
            if not passed:
                reason = f"سیستم فقط درایو C دارد و فضای آزاد آن ({c_free} GB) کمتر از حد نصاب است."
            else:
                reason = None
        except Exception:
            passed = False
            display = "هیچ درایوی یافت نشد"
            reason = "عدم امکان خواندن درایوهای ذخیره‌سازی سیستم."
    else:
        display = f"درایو {best_drive} با {max_free_gb} GB فضای آزاد"
        if not passed:
            reason = f"حداقل فضای موردنیاز {int(min_space_gb)} گیگابایت است. بیشترین فضای آزاد: {max_free_gb} گیگابایت."

    # اگر در حالت تست/توسعه هستیم و فضای درایو کمتر است، اجازه عبور داده می‌شود
    if not passed and DEV_ALLOW_LOW_SPACE:
        display += " (حالت مجاز تست: تأیید)"
        passed = True
        reason = None

    return {
        "display": display,
        "max_free_gb": max_free_gb,
        "best_drive": best_drive,
        "passed": passed,
        "reason": reason,
        "drives": non_c_drives,
    }


def check_all_system_requirements(install_mode: str = "server", sql_version: str = "2019") -> SystemCheckResult:
    """
    اجرای تمامی بررسی‌های پنج‌گانه مرحله System Check متناسب با نوع نصب (سرور یا کلاینت) و نسخه SQL
    """
    logger.log("SYSTEM_CHECK", "START", "RUNNING", f"شروع بررسی پیش‌نیازها در حالت: {install_mode} (SQL: {sql_version})")
    items: List[RequirementItem] = []
    all_critical_passed = True

    is_client = (install_mode == "client")
    required_ram_tol = MIN_CLIENT_RAM_TOLERANCE_GB if is_client else MIN_RAM_TOLERANCE_GB
    required_ram_gb = MIN_CLIENT_RAM_GB if is_client else MIN_RAM_GB
    required_space_gb = MIN_CLIENT_FREE_SPACE_GB if is_client else MIN_FREE_SPACE_GB

    # 1. RAM Check
    ram_gb = get_physical_ram_gb()
    ram_passed = ram_gb >= required_ram_tol
    ram_display = f"{ram_gb} GB"
    ram_status = "✓ مناسب" if ram_passed else "✕ نامناسب"
    ram_reason = None if ram_passed else f"میزان رم سیستم ({ram_gb} GB) کمتر از {required_ram_gb} گیگابایت مورد نیاز است."
    if not ram_passed:
        all_critical_passed = False

    items.append(RequirementItem(
        key="ram",
        title_fa="حافظه رم (RAM)",
        icon_name="ram",
        detected_value=ram_display,
        required_value=f"حداقل {required_ram_gb} گیگابایت ({required_ram_gb} GB)",
        passed=ram_passed,
        status_text=ram_status,
        failure_reason=ram_reason,
        is_critical=True,
    ))
    logger.log("SYSTEM_CHECK", "RAM", "PASS" if ram_passed else "FAIL", f"RAM: {ram_display} (Passed: {ram_passed})")

    # 2. CPU Check
    cpu_info = get_cpu_info()
    cpu_passed = cpu_info["passed"]
    cpu_status = "✓ مناسب" if cpu_passed else "✕ نامناسب"
    cpu_reason = None if cpu_passed else "پردازنده باید حداقل Intel Core i5 نسل ۸ یا معادل ۴ هسته/۸ رشته باشد."
    if not cpu_passed:
        all_critical_passed = False

    items.append(RequirementItem(
        key="cpu",
        title_fa="پردازنده (CPU)",
        icon_name="cpu",
        detected_value=cpu_info["details"],
        required_value="Intel Core i5 نسل ۸ یا معادل",
        passed=cpu_passed,
        status_text=cpu_status,
        failure_reason=cpu_reason,
        is_critical=True,
    ))
    logger.log("SYSTEM_CHECK", "CPU", "PASS" if cpu_passed else "FAIL", f"CPU: {cpu_info['details']}")

    # 3. Architecture Check
    machine = platform.machine().lower()
    is_64bit = sys.maxsize > 2**32 or "64" in machine
    arch_display = "64-bit (x64)" if is_64bit else "32-bit (x86)"
    arch_passed = is_64bit
    arch_status = "✓ مناسب" if arch_passed else "✕ نامناسب"
    arch_reason = None if arch_passed else "معماری ۳۲ بیتی پشتیبانی نمی‌شود. سیستم‌عامل ۶۴ بیتی الزامی است."
    if not arch_passed:
        all_critical_passed = False

    items.append(RequirementItem(
        key="arch",
        title_fa="معماری سیستم (Architecture)",
        icon_name="arch",
        detected_value=arch_display,
        required_value=REQUIRED_ARCH,
        passed=arch_passed,
        status_text=arch_status,
        failure_reason=arch_reason,
        is_critical=True,
    ))
    logger.log("SYSTEM_CHECK", "ARCH", "PASS" if arch_passed else "FAIL", f"Arch: {arch_display}")

    # 4. Storage Check
    storage_info = get_storage_info(min_space_gb=required_space_gb)
    storage_passed = storage_info["passed"]
    storage_status = "✓ مناسب" if storage_passed else "✕ نامناسب"
    if not storage_passed:
        all_critical_passed = False

    req_storage_str = f"حداقل {required_space_gb} گیگابایت در درایو غیر C"
    items.append(RequirementItem(
        key="storage",
        title_fa="فضای ذخیره‌سازی دیسک (Storage)",
        icon_name="storage",
        detected_value=storage_info["display"],
        required_value=req_storage_str,
        passed=storage_passed,
        status_text=storage_status,
        failure_reason=storage_info["reason"],
        is_critical=True,
    ))
    logger.log("SYSTEM_CHECK", "STORAGE", "PASS" if storage_passed else "FAIL", f"Storage: {storage_info['display']}")

    # 5. Windows Compatibility Check
    win_info = get_windows_info(install_mode=install_mode, sql_version=sql_version)
    win_passed = win_info["passed"]
    win_status = "✓ مناسب" if win_passed else "✕ نامناسب"
    if not win_passed:
        all_critical_passed = False

    items.append(RequirementItem(
        key="windows",
        title_fa="سیستم‌عامل ویندوز (OS)",
        icon_name="windows",
        detected_value=win_info["display"],
        required_value="ویندوز ۱۰ یا ۱۱ نسخه ۶۴ بیتی",
        passed=win_passed,
        status_text=win_status,
        failure_reason=win_info["reason"],
        is_critical=True,
    ))
    logger.log("SYSTEM_CHECK", "OS", "PASS" if win_passed else "FAIL", f"OS: {win_info['display']}")

    # Administrator status (Non-critical informational item)
    admin_active = is_admin()
    admin_display = "مدیر سیستم (Administrator)" if admin_active else "کاربر استاندارد (ارتقا در صورت نیاز)"
    items.append(RequirementItem(
        key="admin",
        title_fa="سطح دسترسی کاربری",
        icon_name="shield",
        detected_value=admin_display,
        required_value="اختیاری در مرحله بررسی (ارتقا در زمان نصب)",
        passed=True,
        status_text="✓ تأیید شده" if admin_active else "ℹ اطلاع‌رسانی",
        failure_reason=None,
        is_critical=False,
    ))

    logger.log(
        "SYSTEM_CHECK",
        "SUMMARY",
        "COMPLETED",
        f"نتیجه نهایی بررسی سیستم ({install_mode}): {'پذیرفته شد' if all_critical_passed else 'رد شد'}"
    )

    return SystemCheckResult(
        all_passed=all_critical_passed,
        can_proceed=all_critical_passed,
        items=items,
        admin_detected=admin_active,
    )
