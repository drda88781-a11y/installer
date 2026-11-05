# ui/sidebar.py
"""
سایدبار عمودی مراحل نصب سپهریار با استایل طلایی و راست‌به‌چپ (RTL)
Vertical installation steps sidebar with Gold active/completed indicators
"""

from typing import List
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from config.settings import THEME_COLORS, APP_VERSION, APP_LOGO_CIRCLE_PNG, APP_LOGO_PNG
from utils.icon_factory import IconFactory


class SidebarStepItem(QFrame):
    """
    ردیف نمایش هر یک از مراحل اصلی اینستالر
    """
    def __init__(self, step_number: int, title: str, parent=None):
        super().__init__(parent)
        self.step_number = step_number
        self.title = title
        self.is_active = False
        self.is_completed = False
        self._init_ui()
        self.update_state(False, False)

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # نشانگر آیکون یا شماره مرحله
        self.indicator = QLabel(str(self.step_number), self)
        self.indicator.setFixedSize(28, 28)
        self.indicator.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.indicator)

        # عنوان مرحله
        self.title_lbl = QLabel(self.title, self)
        self.title_lbl.setStyleSheet("font-size: 14px; font-weight: 500;")
        layout.addWidget(self.title_lbl, stretch=1)

    def update_state(self, is_active: bool, is_completed: bool):
        self.is_active = is_active
        self.is_completed = is_completed
        c = THEME_COLORS

        if is_completed:
            # مرحله تکمیل‌شده: نشانگر چک مارک طلایی
            self.indicator.setText("")
            pix = IconFactory.get_icon("check", size=16, color_override=c["gold_primary"]).pixmap(16, 16)
            self.indicator.setPixmap(pix)
            self.indicator.setStyleSheet(f"""
                QLabel {{
                    background-color: {c['gold_glow']};
                    border: 1.5px solid {c['gold_primary']};
                    border-radius: 14px;
                }}
            """)
            self.title_lbl.setStyleSheet(f"color: {c['gold_hover']}; font-size: 14px; font-weight: 600;")
            self.setStyleSheet(f"QFrame {{ background: transparent; border-right: 3px solid {c['gold_primary']}; }}")

        elif is_active:
            # مرحله در حال اجرا / فعال: دایره متالیک طلایی لوکس
            self.indicator.setPixmap(QPixmap())
            self.indicator.setText(str(self.step_number))
            self.indicator.setStyleSheet(f"""
                QLabel {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                stop:0 {c['gold_light']}, stop:0.4 {c['gold_primary']}, stop:1 {c['gold_dark']});
                    color: #0E1015;
                    font-size: 13px;
                    font-weight: bold;
                    border: 1px solid {c['gold_hover']};
                    border-radius: 14px;
                }}
            """)
            self.title_lbl.setStyleSheet(f"color: {c['text_primary']}; font-size: 14px; font-weight: bold;")
            self.setStyleSheet(f"QFrame {{ background-color: #161922; border-right: 3px solid {c['gold_primary']}; border-radius: 6px; }}")

        else:
            # مرحله در انتظار (Pending): خاکستری تیره و غیرفعال
            self.indicator.setPixmap(QPixmap())
            self.indicator.setText(str(self.step_number))
            self.indicator.setStyleSheet(f"""
                QLabel {{
                    background-color: #1A1D24;
                    color: {c['text_muted']};
                    font-size: 12px;
                    font-weight: bold;
                    border: 1px solid #282D3A;
                    border-radius: 14px;
                }}
            """)
            self.title_lbl.setStyleSheet(f"color: {c['text_muted']}; font-size: 14px; font-weight: normal;")
            self.setStyleSheet("QFrame {{ background: transparent; border-right: 3px solid transparent; }}")


class InstallerSidebar(QWidget):
    """
    سایدبار یکپارچه با فهرست گام‌های اینستالر
    """
    STEPS = [
        (1, "بررسی آمادگی سیستم"),
        (2, "انتخاب درایو نصب"),
        (3, "انتخاب محصول سپهریار"),
        (4, "مسیر بسته به‌روزرسانی"),
        (5, "داشبورد و فرایند نصب"),
        (6, "پایان و راه‌اندازی"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidebarWidget")
        self.setFixedWidth(280)
        self.step_widgets: List[SidebarStepItem] = []
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 24, 16, 24)
        main_layout.setSpacing(10)

        # برندینگ و لوگوی رسمی سپهریار
        brand_frame = QFrame(self)
        brand_layout = QHBoxLayout(brand_frame)
        brand_layout.setContentsMargins(8, 8, 8, 16)
        brand_layout.setSpacing(12)

        # نشان و لوگوی اختصاصی زرین سپهریار
        logo_lbl = QLabel(brand_frame)
        logo_lbl.setFixedSize(46, 46)
        if APP_LOGO_CIRCLE_PNG.exists():
            pix = QPixmap(str(APP_LOGO_CIRCLE_PNG)).scaled(
                46, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            logo_lbl.setPixmap(pix)
        elif APP_LOGO_PNG.exists():
            pix = QPixmap(str(APP_LOGO_PNG)).scaled(
                46, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            logo_lbl.setPixmap(pix)
        else:
            logo_pix = IconFactory.get_icon("database", size=32).pixmap(32, 32)
            logo_lbl.setPixmap(logo_pix)
        brand_layout.addWidget(logo_lbl)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

        name_lbl = QLabel("سـپـهـریـار", brand_frame)
        name_lbl.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 18px; font-weight: bold; letter-spacing: 1px;")
        title_layout.addWidget(name_lbl)

        ver_lbl = QLabel(f"اینستالر نسخه {APP_VERSION}", brand_frame)
        ver_lbl.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 11px;")
        title_layout.addWidget(ver_lbl)

        brand_layout.addLayout(title_layout)
        main_layout.addWidget(brand_frame)

        # خط جداکننده افقی ظریف
        sep = QFrame(self)
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {THEME_COLORS['border_subtle']}; max-height: 1px; margin-bottom: 12px;")
        main_layout.addWidget(sep)

        # مراحل ۵ گانه
        for num, title in self.STEPS:
            item = SidebarStepItem(num, title, self)
            self.step_widgets.append(item)
            main_layout.addWidget(item)

        main_layout.addStretch()

        # پانوشت سایدبار
        footer_lbl = QLabel("سیستم نصب مکانیزه و امن", self)
        footer_lbl.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 11px; padding: 8px;")
        footer_lbl.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(footer_lbl)

    def set_current_step(self, step_idx: int):
        """
        به‌روزرسانی وضعیت مراحل (0 تا 4)
        """
        for i, item in enumerate(self.step_widgets):
            if i < step_idx:
                item.update_state(is_active=False, is_completed=True)
            elif i == step_idx:
                item.update_state(is_active=True, is_completed=False)
            else:
                item.update_state(is_active=False, is_completed=False)
