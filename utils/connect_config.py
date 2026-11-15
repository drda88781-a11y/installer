# utils/connect_config.py
"""
ماژول تنظیم و پیکربندی خودکار فایل‌های اتصال به پایگاه داده (conect.xml / CONNECT)
Automated configuration for client connection files (conect.xml)
"""

import re
import socket
from pathlib import Path
from typing import Optional, Tuple
from app_logging.app_logger import logger


def test_server_connection(host_or_target: str, default_port: int = 1433, timeout: float = 3.0) -> Tuple[bool, str]:
    """
    بررسی برقراری ارتباط شبکه با آدرس سرور و پورت SQL Server
    """
    clean_host = host_or_target.strip()
    if "\\" in clean_host:
        clean_host = clean_host.split("\\")[0]
    if "," in clean_host:
        parts = clean_host.split(",")
        clean_host = parts[0].strip()
        try:
            default_port = int(parts[1].strip())
        except ValueError:
            pass

    if not clean_host:
        return False, "آدرس سرور خالی است."

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((clean_host, default_port))
        sock.close()
        return True, f"ارتباط با {clean_host}:{default_port} با موفقیت برقرار شد."
    except socket.timeout:
        return False, f"عدم پاسخ از {clean_host} در پورت {default_port} (Timeout)."
    except Exception as ex:
        return False, f"خطا در اتصال به {clean_host}:{default_port} - {ex}"


def update_connect_xml(file_path: Path, server_target: str, db_name: Optional[str] = None) -> bool:
    """
    به‌روزرسانی رشته اتصال در فایل XML بدون دستکاری بقیه مقادیر (نظیر پسورد رمزگذاری‌شده)
    در صورت عدم وجود فایل، ساخت مستقیم آن با فرمت UTF-16 استاندارد
    """
    if not file_path.exists():
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            init_cat = f";Initial Catalog={db_name}" if db_name else ""
            content = f'<?xml version="1.0" encoding="utf-16"?>\n<Connection>Data Source={server_target}{init_cat};Integrated Security=True</Connection>'
            file_path.write_bytes(content.encode("utf-16"))
            logger.log("CONNECT_CONFIG", "CREATE", "SUCCESS", f"فایل {file_path.name} با Data Source={server_target} و Initial Catalog={db_name} ایجاد شد.")
            return True
        except Exception as ex:
            logger.log("CONNECT_CONFIG", "CREATE_ERROR", "ERROR", f"خطا در ایجاد فایل {file_path.name}: {ex}")
            return False

    raw = file_path.read_bytes()
    # تشخیص انکودینگ: UTF-16LE یا UTF-8
    is_utf16 = (raw[:2] == b"\xff\xfe" or (len(raw) > 4 and b"\x00" in raw[:10]))
    encoding = "utf-16" if is_utf16 else "utf-8"

    try:
        content = raw.decode(encoding)
    except Exception:
        try:
            content = raw.decode("utf-8-sig")
            encoding = "utf-8"
        except Exception as ex:
            logger.log("CONNECT_CONFIG", "DECODE_ERROR", "ERROR", f"خطا در خواندن فایل {file_path.name}: {ex}")
            return False

    # الگوی جایگزینی Data Source
    # مثال: Data Source=DESKTOP-U9RO2AT; یا Data Source=.\spnd2014;
    ds_pattern = r"(Data\s*Source\s*=\s*)([^;]+)(;?)"
    if re.search(ds_pattern, content, re.IGNORECASE):
        new_content = re.sub(
            ds_pattern,
            lambda m: f"{m.group(1)}{server_target}{m.group(3)}",
            content,
            count=1,
            flags=re.IGNORECASE
        )
    else:
        # در صورتی که Data Source نبود اما تگ Connection بود
        conn_pattern = r"(<Connection\b[^>]*>)(.*?)(</Connection>)"
        if re.search(conn_pattern, content, re.IGNORECASE):
            new_content = re.sub(
                conn_pattern,
                lambda m: f"{m.group(1)}Data Source={server_target};{m.group(2)}{m.group(3)}",
                content,
                count=1,
                flags=re.IGNORECASE
            )
        else:
            new_content = f"<Connection>Data Source={server_target};Integrated Security=True</Connection>"

    # در صورتی که نام دیتابیس نیز مشخص شده باشد
    if db_name:
        cat_pattern = r"(Initial\s*Catalog\s*=\s*)([^;]+)(;?)"
        if re.search(cat_pattern, new_content, re.IGNORECASE):
            new_content = re.sub(
                cat_pattern,
                lambda m: f"{m.group(1)}{db_name}{m.group(3)}",
                new_content,
                count=1,
                flags=re.IGNORECASE
            )

    try:
        out_bytes = new_content.encode(encoding)
        file_path.write_bytes(out_bytes)
        logger.log("CONNECT_CONFIG", "UPDATE", "SUCCESS", f"فایل {file_path.name} با Data Source={server_target} به‌روز شد.")
        return True
    except Exception as ex:
        logger.log("CONNECT_CONFIG", "WRITE_ERROR", "ERROR", f"خطا در نوشتن فایل {file_path.name}: {ex}")
        return False


def update_all_connect_files_in_folder(folder_path: Path, server_target: str, db_name: Optional[str] = None) -> int:
    """
    جستجو و به‌روزرسانی کلیه فایل‌های conect*.xml و connect*.xml در یک پوشه
    """
    if not folder_path.exists() or not folder_path.is_dir():
        return 0

    updated_count = 0
    # جستجوی عمیق و غیرحساس به حروف فایل‌های conect*.xml و connect*.xml در پوشه و تمام زیرپوشه‌ها
    candidates = [
        f for f in folder_path.rglob("*")
        if f.is_file() and ("conect" in f.name.lower() or "connect" in f.name.lower()) and f.suffix.lower() == ".xml"
    ]
    for f in candidates:
        if update_connect_xml(f, server_target, db_name):
            updated_count += 1

    return updated_count


def configure_hesabdari_connection(
    root_dir: Path,
    server_target: str,
    db_name: str = "Sepehr_Main_1405"
) -> bool:
    """
    تنظیم کامل و تضمین اتصال پوشه حسابداری بازرگانی (SEPEHRYAR.Hesabdari)
    به اینستنس SQL Server و دیتابیس اتچ شده
    """
    clean_srv = (server_target or "").strip()
    if not clean_srv or clean_srv.upper() in ("MSSQLSERVER", "(DEFAULT)", "DEFAULT", ".\\MSSQLSERVER"):
        clean_srv = "."

    hesabdari_dir = root_dir / "SEPEHRYAR.Hesabdari"
    if not hesabdari_dir.exists():
        hesabdari_dir.mkdir(parents=True, exist_ok=True)

    nested_hesabdari_dir = hesabdari_dir / "SEPEHRYAR.Hesabdari"
    if not nested_hesabdari_dir.exists():
        nested_hesabdari_dir.mkdir(parents=True, exist_ok=True)

    # به‌روزرسانی کلیه فایل‌های کانکت موجود
    count = update_all_connect_files_in_folder(hesabdari_dir, clean_srv, db_name)

    # ایجاد و تضمین حضور همزمان هر دو نام conect.xml و connect.xml در پوشه اصلی و زیرپوشه
    target_locations = [
        hesabdari_dir / "conect.xml",
        hesabdari_dir / "connect.xml",
        nested_hesabdari_dir / "conect.xml",
        nested_hesabdari_dir / "connect.xml",
    ]

    for loc in target_locations:
        if update_connect_xml(loc, clean_srv, db_name):
            count += 1

    logger.log("CONNECT_CONFIG", "HESABDARI", "SUCCESS", f"تعداد {count} فایل اتصال حسابداری با سرور {clean_srv} و دیتابیس {db_name} تنظیم گردید.")
    return True

