# ui/theme.py
"""
استایل‌شیت جامع QSS، تم اختصاصی مشکی و طلایی پریمیوم و تنظیمات تایپوگرافی
Black + Premium Gold QSS stylesheet, theme tokens, and typography
"""

from PySide6.QtGui import QFont, QFontDatabase
from config.settings import ARAD_FONT_PATH, ARAD_VF_FONT_PATH, THEME_COLORS
from app_logging.app_logger import logger


def load_application_fonts() -> str:
    """
    بارگذاری فونت اختصاصی Arad.ttf یا AradVF.ttf و بازگرداندن نام خانواده فونت
    """
    font_candidates = [ARAD_FONT_PATH, ARAD_VF_FONT_PATH]
    loaded_family = None

    for fpath in font_candidates:
        if fpath.exists():
            font_id = QFontDatabase.addApplicationFont(str(fpath))
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    loaded_family = families[0]
                    logger.log("THEME", "FONT", "SUCCESS", f"فونت با موفقیت بارگذاری شد: {loaded_family}")
                    break

    # فال‌بک به فونت‌های استاندارد فارسی
    if not loaded_family:
        available = QFontDatabase.families()
        for fallback in ["Vazirmatn", "IRANSans", "Segoe UI", "Tahoma", "Arial"]:
            if fallback in available:
                loaded_family = fallback
                break

    return loaded_family or "Segoe UI"


def get_application_stylesheet(font_family: str = "Segoe UI") -> str:
    """
    تولید استایل‌شیت جامع با پالت مشکی و طلایی و فونت رسمی
    """
    c = THEME_COLORS
    return f"""
    /* تنظیمات سراسری */
    QWidget {{
        background-color: {c['bg_main']};
        color: {c['text_primary']};
        font-family: "{font_family}", "Segoe UI", "Tahoma", sans-serif;
        font-size: 14px;
        outline: none;
    }}

    QMainWindow {{
        background-color: {c['bg_main']};
    }}

    /* سایدبار مراحل */
    #SidebarWidget {{
        background-color: {c['sidebar_bg']};
        border-left: 1px solid {c['sidebar_border']};
    }}

    /* نوار پایین دکمه‌ها */
    #ActionBarWidget {{
        background-color: {c['action_bar_bg']};
        border-top: 1px solid {c['border_subtle']};
    }}

    /* سربرگ */
    #HeaderWidget {{
        background-color: {c['sidebar_bg']};
        border-bottom: 1px solid {c['border_subtle']};
    }}

    /* دکمه‌های اصلی طلایی با گرادیان متالیک لوکس (الهام از نشان سپهریار) */
    QPushButton.GoldPrimary {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 {c['gold_light']}, stop:0.35 {c['gold_primary']}, stop:1 {c['gold_dark']});
        color: #0E1015;
        font-weight: bold;
        font-size: 14px;
        border: 1px solid {c['gold_hover']};
        border-radius: 8px;
        padding: 10px 24px;
        min-height: 24px;
    }}

    QPushButton.GoldPrimary:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 #FFFFFF, stop:0.35 {c['gold_hover']}, stop:1 {c['gold_primary']});
        border-color: #FFFFFF;
        color: #000000;
    }}

    QPushButton.GoldPrimary:pressed {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 {c['gold_dark']}, stop:0.6 {c['gold_muted']}, stop:1 #4E3B13);
        border-color: {c['gold_muted']};
        color: #000000;
    }}

    QPushButton.GoldPrimary:disabled {{
        background: #232731;
        color: #555C6E;
        border: 1px solid #232731;
    }}

    /* دکمه‌های ثانویه تیره با حاشیه طلایی (Secondary) */
    QPushButton.GoldSecondary {{
        background-color: #141720;
        color: {c['gold_primary']};
        font-weight: 500;
        font-size: 14px;
        border: 1px solid {c['border_medium']};
        border-radius: 8px;
        padding: 10px 20px;
        min-height: 24px;
    }}

    QPushButton.GoldSecondary:hover {{
        background-color: #1D212C;
        border-color: {c['gold_primary']};
        color: {c['gold_light']};
    }}

    QPushButton.GoldSecondary:pressed {{
        background-color: #0E1015;
        border-color: {c['gold_dark']};
        color: {c['gold_hover']};
    }}

    QPushButton.GoldSecondary:disabled {{
        background-color: #12141A;
        color: #4B5262;
        border-color: #1E222B;
    }}

    /* کارت‌های پس‌زمینه زغالی */
    QFrame.GoldCard {{
        background-color: {c['card_bg']};
        border: 1px solid {c['card_border']};
        border-radius: 12px;
        padding: 16px;
    }}

    QFrame.GoldCard:hover {{
        background-color: {c['card_hover']};
        border: 1px solid #3A3F4E;
    }}

    QFrame.GoldCardSelected {{
        background-color: #1B1E26;
        border: 2px solid {c['gold_primary']};
        border-radius: 12px;
        padding: 16px;
    }}

    /* پروگرس‌بار طلایی متالیک */
    QProgressBar {{
        background-color: #161920;
        border: 1px solid {c['border_subtle']};
        border-radius: 6px;
        height: 12px;
        text-align: center;
        color: {c['text_primary']};
        font-size: 11px;
    }}

    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                    stop:0 {c['gold_dark']}, stop:0.5 {c['gold_primary']}, stop:1 {c['gold_light']});
        border-radius: 5px;
    }}

    /* اسکرول‌بار شیک تیره */
    QScrollBar:vertical {{
        background: #0E1015;
        width: 8px;
        margin: 0px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical {{
        background: #2D323E;
        min-height: 24px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {c['gold_primary']};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* تکست ادیت و لاگ */
    QPlainTextEdit, QTextEdit {{
        background-color: #0E1015;
        color: #E2E8F0;
        border: 1px solid {c['border_subtle']};
        border-radius: 8px;
        padding: 10px;
        font-family: "Consolas", "Courier New", monospace;
        font-size: 12px;
        selection-background-color: {c['gold_dark']};
    }}

    /* جداول */
    QTableWidget {{
        background-color: {c['card_bg']};
        border: 1px solid {c['border_subtle']};
        border-radius: 8px;
        gridline-color: #232732;
    }}

    QHeaderView::section {{
        background-color: #12141A;
        color: {c['gold_primary']};
        padding: 8px;
        font-weight: bold;
        border: none;
        border-bottom: 1px solid {c['border_subtle']};
    }}

    /* دیالوگ‌ها */
    QDialog {{
        background-color: {c['bg_main']};
        border: 1px solid {c['border_medium']};
        border-radius: 12px;
    }}

    QLabel {{
        background: transparent;
    }}
    """
