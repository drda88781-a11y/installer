# sql/sql_detector.py
"""
ماژول تشخیص اینستنس SQL Server و بررسی وضعیت سرویس‌های ویندوز
Detection of SQL Server instance SEPEHRYAR2019 and Windows service control
"""

import subprocess
import winreg
from typing import Optional, Tuple
import psutil

from config.settings import SQL_INSTANCE_NAME, SQL_SERVICE_NAME, SQL_AGENT_SERVICE_NAME
from app_logging.app_logger import logger


def get_sql_service_name_for_instance(instance_name: str) -> str:
    """دریافت نام دقیق سرویس ویندوز متناظر با اینستنس (MSSQLSERVER برای اینستنس پیش‌فرض)"""
    clean = (instance_name or "").strip()
    if not clean or clean.upper() in ("MSSQLSERVER", "(DEFAULT)", "."):
        return "MSSQLSERVER"
    return f"MSSQL${clean}"


def get_all_installed_sql_instances() -> list[str]:
    """
    شناسایی تمامی اینستنس‌های نصب‌شده Microsoft SQL Server روی ویندوز
    از طریق کلیدهای رسمی رجیستری و سرویس‌های فعال سیستم
    """
    instances = set()
    reg_keys = [
        r"SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL",
        r"SOFTWARE\WOW6432Node\Microsoft\Microsoft SQL Server\Instance Names\SQL",
    ]
    for rpath in reg_keys:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rpath) as key:
                i = 0
                while True:
                    try:
                        name, _, _ = winreg.EnumValue(key, i)
                        if name:
                            instances.add(name.strip())
                        i += 1
                    except OSError:
                        break
        except Exception:
            pass

    # بررسی سرویس‌های ویندوز
    try:
        for s in psutil.win_service_iter():
            s_name = s.name()
            if s_name.upper() == "MSSQLSERVER":
                instances.add("MSSQLSERVER")
            elif s_name.upper().startswith("MSSQL$"):
                inst = s_name[6:]
                if inst:
                    instances.add(inst.strip())
    except Exception:
        pass

    # مرتب‌سازی با اولویت‌بندی اینستنس‌های سپهریار در ابتدا
    return sorted(
        list(instances),
        key=lambda x: (
            0 if "SEPEHRYAR" in x.upper() else 1,
            x.upper()
        )
    )


def is_sql_instance_installed(instance_name: str = SQL_INSTANCE_NAME) -> bool:
    """
    بررسی وجود اینستنس در رجیستری ویندوز یا سرویس‌های فعال
    """
    # 1. بررسی کلید رسمی اینستنس‌های اس‌کیو‌ال سرور در رجیستری
    reg_keys = [
        r"SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL",
        r"SOFTWARE\WOW6432Node\Microsoft\Microsoft SQL Server\Instance Names\SQL",
    ]
    for rpath in reg_keys:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rpath) as key:
                val, _ = winreg.QueryValueEx(key, instance_name)
                if val:
                    logger.log("SQL", "DETECTOR", "FOUND", f"اینستنس {instance_name} در رجیستری یافت شد: {val}")
                    return True
        except Exception:
            pass

    # 2. بررسی از طریق سرویس ویندوز
    target_service = get_sql_service_name_for_instance(instance_name)
    try:
        service = psutil.win_service_get(target_service)
        if service:
            logger.log("SQL", "DETECTOR", "FOUND", f"سرویس {target_service} در ویندوز یافت شد.")
            return True
    except Exception:
        pass

    return False


def get_sql_service_status(instance_name: str = SQL_INSTANCE_NAME) -> Tuple[bool, str]:
    """
    دریافت وضعیت سرویس SQL Server (مثلاً running, stopped, not_installed)
    """
    target_service = get_sql_service_name_for_instance(instance_name)
    try:
        service = psutil.win_service_get(target_service)
        status = service.status()  # e.g. "running", "stopped"
        return True, status
    except Exception:
        return False, "not_installed"


def start_sql_service_if_stopped(instance_name: str = SQL_INSTANCE_NAME) -> bool:
    """
    راه‌اندازی سرویس SQL Server در صورت متوقف بودن
    """
    target_service = get_sql_service_name_for_instance(instance_name)
    logger.log("SQL", "SERVICE_START", "RUNNING", f"بررسی و استارت سرویس {target_service}...")

    exists, status = get_sql_service_status(instance_name)
    if not exists:
        logger.log("SQL", "SERVICE_START", "ERROR", f"سرویس {target_service} اصلاً روی سیستم نصب نیست.")
        return False

    if status == "running":
        logger.log("SQL", "SERVICE_START", "SUCCESS", f"سرویس {target_service} در حال حاضر فعال و در حال اجراست.")
        return True

    # تلاش برای استارت با دستور net start یا sc start
    try:
        res = subprocess.run(["net", "start", target_service], capture_output=True, text=True, timeout=30)
        if res.returncode == 0 or "already started" in res.stdout.lower():
            logger.log("SQL", "SERVICE_START", "SUCCESS", f"سرویس {target_service} با موفقیت استارت شد.")
            return True
    except Exception as ex:
        logger.log("SQL", "SERVICE_START", "WARN", f"خطا در دستور net start: {ex}")

    try:
        # تلاش ثانویه با PowerShell
        cmd = f"Start-Service -Name '{target_service}' -ErrorAction Stop"
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=30)
        _, new_status = get_sql_service_status(instance_name)
        if new_status == "running":
            logger.log("SQL", "SERVICE_START", "SUCCESS", f"سرویس {target_service} با موفقیت فعال گردید.")
            return True
    except Exception as ex:
        logger.log("SQL", "SERVICE_START", "ERROR", f"شکست در استارت سرویس {target_service}: {ex}", error=str(ex))

    return False
