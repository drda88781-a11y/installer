# packages/product_catalog.py
"""
کاتالوگ، مدیریت و تفکیک پکیج‌های ۵ گانه نرم‌افزار حسابداری سپهریار
Product catalog and package resolver for SEPEHRYAR accounting suite
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import EXE_FULL_DIR, PRODUCTS_CONFIG
from app_logging.app_logger import logger


@dataclass
class ProductItem:
    id: str                 # e.g. "SEPEHRYAR.Hesabdari"
    title: str              # e.g. "حسابداری"
    icon_symbol: str        # e.g. "🧾"
    folder_name: str        # e.g. "SEPEHRYAR.Hesabdari"
    main_exe: str           # e.g. "Hesabdari.exe"
    shortcut_name: str      # e.g. "سپهریار - حسابداری"
    description: str        # توضیحات کوتاه
    is_available: bool      # آیا در پوشه exe full وجود دارد؟
    file_count: int         # تعداد فایل‌های موجود در پکیج
    size_bytes: int         # مجموع حجم پکیج


def resolve_product_source_dir(product_id: str) -> Optional[Path]:
    """
    یافتن پوشه مبدأ واقعی پکیج محصول در exe full
    در صورت وجود ساب‌فولدر همنام (نظیر SEPEHRYAR.Hesabdari/SEPEHRYAR.Hesabdari)، پوشه حاوی فایل‌های اجرایی انتخاب می‌شود.
    """
    cfg = PRODUCTS_CONFIG.get(product_id)
    if not cfg:
        return None

    folder_name = cfg["folder_name"]
    base_target = EXE_FULL_DIR / folder_name

    if not base_target.exists():
        return None

    # بررسی ساختار تو در تو (Nested)
    nested_target = base_target / folder_name
    if nested_target.exists() and nested_target.is_dir():
        # اگر در پوشه داخلی فایل‌های اجرایی باشد
        if (nested_target / cfg["main_exe"]).exists():
            return nested_target

    # اگر مستقیماً در پوشه پایه باشد
    if (base_target / cfg["main_exe"]).exists():
        return base_target

    # در صورت وجود فایل‌های دیگر در پوشه پایه
    return base_target


def resolve_installed_exe_path(root_install_dir: Path, product_id: str) -> Optional[Path]:
    """
    یافتن فایل اجرایی اصلی پس از کپی در مسیر نصب
    [SelectedDrive]:\\SEPEHRYAR\\[ProductFolder]\\[MainExe]
    """
    cfg = PRODUCTS_CONFIG.get(product_id)
    if not cfg:
        return None

    folder_name = cfg["folder_name"]
    main_exe = cfg["main_exe"]
    expected_path = root_install_dir / folder_name / main_exe

    if expected_path.exists():
        return expected_path

    # بررسی حالت‌های احتمالی دیگر
    alt_path = root_install_dir / folder_name / folder_name / main_exe
    if alt_path.exists():
        return alt_path

    return expected_path


def get_available_products() -> List[ProductItem]:
    """
    دریافت مشخصات کامل و وضعیت ۵ محصول رسمی سپهریار
    """
    items: List[ProductItem] = []

    for pid, cfg in PRODUCTS_CONFIG.items():
        src_dir = resolve_product_source_dir(pid)
        is_available = src_dir is not None and src_dir.exists()
        file_count = 0
        size_bytes = 0

        if is_available:
            try:
                for f in src_dir.rglob("*"):
                    if f.is_file():
                        file_count += 1
                        size_bytes += f.stat().st_size
            except Exception as ex:
                logger.log("PACKAGE", pid, "WARN", f"خطا در محاسبه حجم پکیج {pid}: {ex}")

        item = ProductItem(
            id=pid,
            title=cfg["title"],
            icon_symbol=cfg["icon_symbol"],
            folder_name=cfg["folder_name"],
            main_exe=cfg["main_exe"],
            shortcut_name=cfg["shortcut_name"],
            description=cfg["description"],
            is_available=is_available,
            file_count=file_count,
            size_bytes=size_bytes,
        )
        items.append(item)

    return items


def get_product_by_id(product_id: str) -> Optional[ProductItem]:
    for p in get_available_products():
        if p.id == product_id:
            return p
    return None
