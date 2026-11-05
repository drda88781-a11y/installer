# config/settings.py
"""
تنظیمات سراسری، ثوابت، مسیرها و پیکربندی امن اینستالر سپهریار
Global settings, constants, paths, and secure configuration for SEPEHRYAR Installer
"""

import os
import sys
from pathlib import Path


def get_bundle_dir() -> Path:
    """مسیر فایل‌های باندل شده در PyInstaller یا سورس"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def get_app_dir() -> Path:
    """مسیر فولدری که فایل EXE یا اسکریپت در آن قرار دارد"""
    if getattr(sys, "frozen", False):
        return Path(os.path.dirname(sys.executable))
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_bundle_dir()
APP_DIR = get_app_dir()

# نام و نسخه نرم‌افزار
APP_NAME_FA = "نصب‌کننده نرم‌افزار حسابداری سپهریار"
APP_NAME_EN = "SEPEHRYAR Professional Windows Installer"
APP_VERSION = "2026.1 Enterprise"
ORGANIZATION_NAME = "SEPEHRYAR Software Group"

# پوشه‌های اصلی و جانبی
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
ICONS_DIR = ASSETS_DIR / "icons"
IMAGES_DIR = ASSETS_DIR / "images"


def resolve_setup_dir() -> Path:
    """شناسایی پوشه Setup (با بررسی کنار فایل EXE، باندل و پوشه جاری)"""
    candidates = [
        APP_DIR / "setup",
        APP_DIR / "SETUP",
        BASE_DIR / "setup",
        BASE_DIR / "SETUP",
        Path.cwd() / "setup",
        Path.cwd() / "SETUP",
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return APP_DIR / "SETUP"


def resolve_exe_full_dir() -> Path:
    """شناسایی پوشه exe full (با بررسی کنار فایل EXE، باندل و پوشه جاری)"""
    candidates = [
        APP_DIR / "exe full",
        BASE_DIR / "exe full",
        Path.cwd() / "exe full",
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return APP_DIR / "exe full"


SETUP_DIR = resolve_setup_dir()
EXE_FULL_DIR = resolve_exe_full_dir()

# مسیر فایل فونت
ARAD_FONT_PATH = FONTS_DIR / "Arad.ttf"
ARAD_VF_FONT_PATH = FONTS_DIR / "AradVF.ttf"

# مسیر فایل‌های لوگو و آیکون رسمی سپهریار
APP_ICON_ICO = ICONS_DIR / "app_icon.ico"
APP_ICON_PNG = ICONS_DIR / "app_icon.png"
APP_LOGO_PNG = IMAGES_DIR / "logo.png"
APP_LOGO_CIRCLE_PNG = IMAGES_DIR / "logo_circle.png"
APP_LOGO_REPORT_PNG = IMAGES_DIR / "logo_report.png"


# پیش‌نیازهای بررسی سیستم (System Check)
MIN_RAM_GB = 8
MIN_RAM_TOLERANCE_GB = 7.5  # به دلیل حافظه رزرو شده سخت‌افزاری در رم‌های ۸ گیگ
MIN_CPU_GENERATION = 8      # نسل ۸ یا معادل آن
MIN_FREE_SPACE_GB = 100     # حداقل ۱۰۰ گیگابایت فضای خالی
REQUIRED_ARCH = "64-bit (x64)"

# حالت توسعه / صرف‌نظر از چک ۱۰۰ گیگابایت برای ماشین تست
DEV_ALLOW_LOW_SPACE = True

# ساختار ریشه نصب سپهریار در درایو انتخابی
INSTALL_ROOT_DIR_NAME = "SEPEHRYAR"
SUBFOLDERS = [
    "SEPEHRYAR.Setup",
    "SEPEHRYAR.Data",
    "SEPEHRYAR.Backup",
    "SEPEHRYAR.Update",
]

# محصولات سپهریار
PRODUCTS_CONFIG = {
    "SEPEHRYAR.Resturan": {
        "title": "رستوران",
        "icon_symbol": "🍽",
        "folder_name": "SEPEHRYAR.Resturan",
        "source_folder": "SEPEHRYAR.Resturan",
        "main_exe": "SepandResturan.exe",
        "shortcut_name": "سپهریار - رستوران",
        "description": "سیستم جامع مدیریت و صندوق مکانیزه رستوران و فست‌فود",
    },
    "SEPEHRYAR.Hesabdari": {
        "title": "حسابداری",
        "icon_symbol": "🧾",
        "folder_name": "SEPEHRYAR.Hesabdari",
        "source_folder": "SEPEHRYAR.Hesabdari",
        "main_exe": "Hesabdari.exe",
        "shortcut_name": "سپهریار - حسابداری",
        "description": "نرم‌افزار جامع مالی، بازرگانی، خزانه‌داری و حسابداری",
    },
    "SEPEHRYAR.Sanati": {
        "title": "صنعتی",
        "icon_symbol": "🏭",
        "folder_name": "SEPEHRYAR.Sanati",
        "source_folder": "SEPEHRYAR.Sanati",
        "main_exe": "Hesabdari.exe",
        "shortcut_name": "سپهریار - صنعتی",
        "description": "نرم‌افزار حسابداری صنعتی، بهای تمام‌شده و تولید",
    },
    "SEPEHRYAR.Client": {
        "title": "فروش (کلاینت)",
        "icon_symbol": "🛒",
        "folder_name": "SEPEHRYAR.Client",
        "source_folder": "SEPEHRYAR.Client",
        "main_exe": "ClientSepand.exe",
        "shortcut_name": "سپهریار - فروش",
        "description": "سیستم جامع مکانیزه فروش، صندوق و ایستگاه کاری کلاینت متصل به سرور",
    },
    "SEPEHRYAR.TaxGov": {
        "title": "مالیاتی و سامانه مودیان",
        "icon_symbol": "🏛",
        "folder_name": "SEPEHRYAR.TaxGov",
        "source_folder": "SEPEHRYAR.TaxGov",
        "main_exe": "SepandYar_TaxGov.exe",
        "shortcut_name": "سپهریار - سامانه مودیان",
        "description": "ارسال مستقیم و هوشمند صورت‌حساب به سامانه مودیان مالیاتی",
    },
}

# حداقل‌های سخت‌افزاری متناسب با حالت کلاینت
MIN_CLIENT_RAM_GB = 4
MIN_CLIENT_RAM_TOLERANCE_GB = 3.5
MIN_CLIENT_FREE_SPACE_GB = 20

# محصولاتی که در حالت سرور نیاز به SQL Server و پایگاه داده دارند
SQL_REQUIRED_PRODUCTS = {"SEPEHRYAR.Hesabdari", "SEPEHRYAR.Sanati"}

# برنامه‌های کلاینت که به هیچ عنوان نباید SQL Server برای آن‌ها نصب شود
SQL_EXCLUDED_PRODUCTS = {"SEPEHRYAR.Client", "SEPEHRYAR.Resturan", "SEPEHRYAR.TaxGov"}


def requires_sql(selected_product_ids, install_mode: str = "server") -> bool:
    """
    بررسی دقیق نیاز به نصب SQL Server:
    - در صورتی که فقط برنامه‌های کلاینت (فروش، رستوران، مودیان) انتخاب شده باشند: به هیچ عنوان SQL Server نصب نمی‌شود.
    - در صورتی که حسابداری (یا صنعتی) همراه با هر برنامه‌ای انتخاب شده باشد: نیاز به SQL Server دارد.
    - در حالت کلاینت (client): به هیچ عنوان SQL نصب نمی‌شود.
    """
    if install_mode == "client":
        return False
    # اگر حسابداری یا صنعتی در محصولات انتخابی باشد، نیاز به SQL Server دارد
    return bool(set(selected_product_ids) & SQL_REQUIRED_PRODUCTS)


def requires_sql_and_setup(selected_product_ids, install_mode: str = "server") -> bool:
    """سازگاری با فراخوانی‌های قبلی"""
    return requires_sql(selected_product_ids, install_mode=install_mode)


# پیکربندی SQL Server (پشتیبانی از نسخه‌های ۲۰۱۴ و ۲۰۱۹)
DEFAULT_SQL_VERSION = "2019"
SQL_2014_INSTANCE_NAME = "SEPEHRYAR2014"
SQL_2019_INSTANCE_NAME = "SEPEHRYAR2019"
SQL_INSTANCE_NAME = SQL_2019_INSTANCE_NAME  # مقدار پیش‌فرض برای سازگاری عقب‌رو
SQL_SERVICE_NAME = f"MSSQL${SQL_INSTANCE_NAME}"
SQL_AGENT_SERVICE_NAME = f"SQLAgent${SQL_INSTANCE_NAME}"
SQL_FEATURES = "SQLEngine"
SQL_ARCHIVE_NAME = "Microsoft.SQL.Server.2019.Enterprise.x64.rar"
SQL_ARCHIVE_PASS = "soft98.ir"
SQL_SA_USER = "sa"
SQL_SA_PASSWORD = "sepandyar@123"

SQL_VERSIONS_CONFIG = {
    "2014": {
        "title": "Microsoft SQL Server 2014 Enterprise (SP3)",
        "instance_name": "SEPEHRYAR2014",
        "folder_name": "SQL",
        "features": "SQLEngine,SSMS,ADV_SSMS",
        "needs_ssms_download": False,
    },
    "2019": {
        "title": "Microsoft SQL Server 2019 Enterprise",
        "instance_name": "SEPEHRYAR2019",
        "archive_name": "Microsoft.SQL.Server.2019.Enterprise.x64.rar",
        "archive_pass": "soft98.ir",
        "download_url": "https://dl2.soft98.ir/programing/Microsoft.SQL.Server.2019.Enterprise.x64.rar?1790685163",
        "features": "SQLEngine",
        "needs_ssms_download": True,
    },
}


def get_sql_instance_name(sql_version: str = "2019") -> str:
    """دریافت نام اینستنس متناظر با نسخه SQL"""
    cfg = SQL_VERSIONS_CONFIG.get(sql_version)
    if cfg:
        return cfg["instance_name"]
    return f"SEPEHRYAR{sql_version}"

# پیکربندی SSMS
SSMS_LINK_FILENAME = "LINK DOWNLOAD SQL MANAGEMENT.txt"
SSMS_ALT_LINK_FILENAME = "LINK DOWNLOAD SQL MANAGEMENT"
SSMS_FALLBACK_URL = "https://dl2.soft98.ir/programing/SQL.Server.Management.Studio.18.12.1.x64.rar?1789719194"

# پالت رنگی مشکی و طلایی پریمیوم (Black + Premium Gold الهام‌گرفته از نشان رسمی سپهریار)
THEME_COLORS = {
    "bg_main": "#0E1015",
    "bg_secondary": "#141720",
    "card_bg": "#181B24",
    "card_hover": "#212531",
    "card_border": "#2C3140",
    "card_border_active": "#D8A84E",
    
    "gold_primary": "#D8A84E",
    "gold_hover": "#ECC867",
    "gold_light": "#F7E2A3",
    "gold_dark": "#B98E4A",
    "gold_muted": "#8E6B2C",
    "gold_glow": "rgba(216, 168, 78, 0.22)",
    
    "text_primary": "#F4F6F9",
    "text_secondary": "#A0A7B5",
    "text_muted": "#6E7585",
    "text_dark": "#0E1015",
    
    "success": "#10B981",
    "success_bg": "rgba(16, 185, 129, 0.15)",
    "warning": "#F59E0B",
    "warning_bg": "rgba(245, 158, 11, 0.15)",
    "error": "#EF4444",
    "error_bg": "rgba(239, 68, 68, 0.15)",
    
    "sidebar_bg": "#101217",
    "sidebar_border": "#1D2029",
    "action_bar_bg": "#101217",
    
    "border_subtle": "#1F232D",
    "border_medium": "#2D323F",
}
