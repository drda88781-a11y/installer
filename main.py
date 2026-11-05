# main.py
"""
نقطه ورود رسمی و اصلی اینستالر نرم‌افزار حسابداری سپهریار
Official Entry Point for SEPEHRYAR Professional Windows Installer
"""

import os
import sys
from pathlib import Path

# ایمن‌سازی خروجی کنسول ویندوز برای متون فارسی
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

# افزودن مسیر ریشه برنامه به sys.path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))


def _global_exception_hook(exctype, value, tb):
    """مدیریت خطاهای کنترل‌نشده برای ثبت در لاگ و نمایش پیام شفاف به کاربر"""
    import traceback
    import tempfile
    crash_trace = "".join(traceback.format_exception(exctype, value, tb))
    
    # ثبت در فایل لاگ کراش در Temp
    crash_file = Path(tempfile.gettempdir()) / "sepehryar_installer_crash.log"
    try:
        crash_file.write_text(crash_trace, encoding="utf-8")
    except Exception:
        pass

    # نمایش دیالوگ خطای بومی ویندوز
    try:
        import ctypes
        msg = (
            f"خطایی در اجرای نصاب سپهریار رخ داد:\n\n{value}\n\n"
            f"جزئیات کامل خطا در مسیر زیر ذخیره شد:\n{crash_file}"
        )
        ctypes.windll.user32.MessageBoxW(0, msg, "خطای راه‌اندازی نصاب سپهریار", 0x10)
    except Exception:
        pass

    sys.__excepthook__(exctype, value, tb)


sys.excepthook = _global_exception_hook

# فعال‌سازی مقیاس‌بندی وضوح بالا (High-DPI) برای مانیتورهای مدرن و 4K
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QDialog

from config.settings import (
    APP_NAME_FA,
    APP_NAME_EN,
    APP_VERSION,
    ORGANIZATION_NAME,
    APP_ICON_PNG,
    APP_ICON_ICO,
)
from app_logging.app_logger import logger
from ui.dialogs.password_dialog import PasswordDialog
from ui.main_window import MainWindow
from ui.theme import get_application_stylesheet, load_application_fonts


def main():
    logger.log("APP", "STARTUP", "INITIALIZING", f"راه‌اندازی {APP_NAME_EN} نسخه {APP_VERSION}")

    # ایجاد اپلیکیشن Qt
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME_EN)
    app.setApplicationDisplayName(APP_NAME_FA)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORGANIZATION_NAME)

    # فعال‌سازی رسمی جهت چیدمان راست‌به‌چپ (RTL Persian)
    app.setLayoutDirection(Qt.RightToLeft)

    # تنظیم آیکون رسمی برنامه در ویندوز و تسک‌بار
    if APP_ICON_PNG.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PNG)))
    elif APP_ICON_ICO.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_ICO)))

    # بارگذاری فونت رسمی آراد یا فال‌بک
    font_family = load_application_fonts()
    app_font = QFont(font_family, 10)
    app_font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(app_font)

    # اعمال تم مشکی و طلایی پریمیوم (Black + Premium Gold)
    stylesheet = get_application_stylesheet(font_family)
    app.setStyleSheet(stylesheet)

    # ۱. احراز هویت با رمز عبور امنیتی قبل از باز شدن پنجره اصلی
    auth_dialog = PasswordDialog()
    if auth_dialog.exec() != QDialog.Accepted:
        logger.log("APP", "STARTUP", "CANCELLED", "ورود توسط کاربر لغو شد.")
        sys.exit(0)

    # ۲. ایجاد و نمایش پنجره اصلی پس از ورود موفق رمز عبور
    window = MainWindow()
    window.show()

    logger.log("APP", "STARTUP", "RUNNING", "پنجره اصلی با موفقیت به کاربر نمایش داده شد.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
