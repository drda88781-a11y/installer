# ui/dialogs/sql_version_dialog.py
"""
دیالوگ انتخاب نسخه پایگاه داده Microsoft SQL Server (2014 یا 2019) با تشخیص خودکار اینستنس‌های نصب‌شده
Modal Dialog for choosing SQL Server Version (2014 vs 2019) with auto-detection badges
"""

from typing import Optional, Dict
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from config.settings import THEME_COLORS
from utils.icon_factory import IconFactory


class SQLOptionCard(QFrame):
    """کارت بزرگ و خوانا برای انتخاب نسخه در دیالوگ همراه با بج وضعیت نصب"""
    clicked = Signal(str)

    def __init__(
        self,
        version: str,
        title: str,
        time_badge: str,
        features: list,
        is_active: bool = False,
        is_installed: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.version = version
        self.title_text = title
        self.time_badge_text = time_badge
        self.features = features
        self.is_active = is_active
        self.is_installed = is_installed
        self.setCursor(Qt.PointingHandCursor)
        self._init_ui()
        self.set_active(is_active)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # ردیف بالا: آیکون، عنوان و بج زمان
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)

        self.icon_lbl = QLabel(self)
        top_layout.addWidget(self.icon_lbl)

        self.lbl_title = QLabel(self.title_text, self)
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        top_layout.addWidget(self.lbl_title, stretch=1)

        # بج نصب بودن در سیستم
        if self.is_installed:
            lbl_installed = QLabel("✓ نصب است", self)
            lbl_installed.setStyleSheet(f"""
                QLabel {{
                    background-color: {THEME_COLORS['success_bg']};
                    color: {THEME_COLORS['success']};
                    border: 1px solid {THEME_COLORS['success']};
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }}
            """)
            top_layout.addWidget(lbl_installed)

        # بج زمان
        self.lbl_time = QLabel(self.time_badge_text, self)
        self.lbl_time.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(216, 168, 78, 0.12);
                color: {THEME_COLORS['gold_hover']};
                border: 1px solid rgba(216, 168, 78, 0.35);
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11.5px;
                font-weight: bold;
            }}
        """)
        top_layout.addWidget(self.lbl_time)

        # نشانگر انتخاب (تیک)
        self.badge_lbl = QLabel(self)
        self.badge_lbl.setAlignment(Qt.AlignCenter)
        self.badge_lbl.setFixedSize(24, 24)
        top_layout.addWidget(self.badge_lbl)

        layout.addLayout(top_layout)

        # جداکننده نازک
        sep = QFrame(self)
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {THEME_COLORS['card_border']}; max-height: 1px;")
        layout.addWidget(sep)

        # لیست ویژگی‌ها
        features_layout = QVBoxLayout()
        features_layout.setSpacing(6)
        for feat in self.features:
            f_lbl = QLabel(feat, self)
            f_lbl.setWordWrap(True)
            f_lbl.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12px; line-height: 1.4;")
            features_layout.addWidget(f_lbl)
        layout.addLayout(features_layout)

    def set_active(self, active: bool):
        self.is_active = active
        c = THEME_COLORS
        if active:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: #1A1E29;
                    border: 2px solid {c['gold_primary']};
                    border-radius: 12px;
                }}
            """)
            self.lbl_title.setStyleSheet(f"color: {c['gold_hover']}; font-size: 15px; font-weight: bold;")
            icon_pix = IconFactory.get_icon("database", size=28, color_override=c["gold_primary"]).pixmap(28, 28)
            self.icon_lbl.setPixmap(icon_pix)
            self.badge_lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: {c['gold_primary']};
                    color: #0E1015;
                    font-size: 13px;
                    font-weight: bold;
                    border-radius: 12px;
                }}
            """)
            self.badge_lbl.setText("✓")
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {c['card_bg']};
                    border: 1px solid {c['card_border']};
                    border-radius: 12px;
                }}
                QFrame:hover {{
                    background-color: {c['card_hover']};
                    border-color: #4A5060;
                }}
            """)
            self.lbl_title.setStyleSheet(f"color: {c['text_primary']}; font-size: 15px; font-weight: bold;")
            icon_pix = IconFactory.get_icon("database", size=28, color_override=c["text_muted"]).pixmap(28, 28)
            self.icon_lbl.setPixmap(icon_pix)
            self.badge_lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: #1A1D24;
                    border: 1px solid #3A4050;
                    border-radius: 12px;
                }}
            """)
            self.badge_lbl.setText("")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.version)
        super().mousePressEvent(event)


class SQLVersionDialog(QDialog):
    """
    فرم وسط صفحه برای انتخاب نسخه Microsoft SQL Server
    """
    def __init__(
        self,
        current_version: str = "2019",
        installed_versions: Optional[Dict[str, bool]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("انتخاب نسخه پایگاه داده Microsoft SQL Server")
        self.selected_version = str(current_version)
        self.installed_versions = installed_versions or {}
        self.resize(740, 450)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #12141A;
                border: 1px solid {THEME_COLORS['gold_primary']};
                border-radius: 14px;
            }}
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        # سربرگ دیالوگ
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        icon_header = QLabel(self)
        icon_pix = IconFactory.get_icon("database", size=36, color_override=THEME_COLORS["gold_primary"]).pixmap(36, 36)
        icon_header.setPixmap(icon_pix)
        header_layout.addWidget(icon_header)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(4)

        dlg_title = QLabel("انتخاب نسخه پایگاه داده Microsoft SQL Server", self)
        dlg_title.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 18px; font-weight: bold;")
        title_vbox.addWidget(dlg_title)

        dlg_sub = QLabel(
            "<b>توجه مهم:</b> در صورتی که یکی از اینستنس‌ها قبلاً روی ویندوز نصب باشد، اینستالر آن را به صورت خودکار شناسایی کرده و کم و کسری‌های آن را تأمین خواهد کرد (بدون نیاز به نصب مجدد).",
            self
        )
        dlg_sub.setWordWrap(True)
        dlg_sub.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(216, 168, 78, 0.1);
                color: #FCD34D;
                border: 1px solid rgba(216, 168, 78, 0.35);
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                line-height: 1.4;
            }}
        """)
        title_vbox.addWidget(dlg_sub)

        header_layout.addLayout(title_vbox, stretch=1)
        layout.addLayout(header_layout)

        # کارت‌های انتخاب دو نسخه (در کنار هم)
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        is_2014_inst = self.installed_versions.get("2014", False)
        is_2019_inst = self.installed_versions.get("2019", False)

        # کارت SQL 2014
        self.card_2014 = SQLOptionCard(
            version="2014",
            title="SQL Server 2014 Enterprise",
            time_badge="⚡ ۴ تا ۷ دقیقه",
            features=[
                "⚡ سرعت نصب بسیار بالا و سبک",
                "✓ ابزار مدیریتی (SSMS) درون بسته موجود است",
                "✓ نیازی به دانلود یا نصب مجزای Management Studio ندارد",
                "✓ مناسب برای سیستم‌های کاری متوسط و سریع"
            ],
            is_active=(self.selected_version == "2014"),
            is_installed=is_2014_inst,
            parent=self
        )
        self.card_2014.clicked.connect(self._select_version)
        cards_layout.addWidget(self.card_2014)

        # کارت SQL 2019
        self.card_2019 = SQLOptionCard(
            version="2019",
            title="SQL Server 2019 Enterprise",
            time_badge="⏳ ۱۰ تا ۱۵ دقیقه",
            features=[
                "🚀 نسخه کامل و پیشرفته سازمانی",
                "✓ به همراه دانلود و نصب آخرین نسخه SSMS",
                "✓ ابزار کامل مدیریتی مایکروسافت",
                "✓ پشتیبانی از پردازش‌های سنگین و سازمانی"
            ],
            is_active=(self.selected_version == "2019"),
            is_installed=is_2019_inst,
            parent=self
        )
        self.card_2019.clicked.connect(self._select_version)
        cards_layout.addWidget(self.card_2019)

        layout.addLayout(cards_layout)

        # نوار دکمه‌های پایین
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(14)

        info_lbl = QLabel("با کلیک روی هر کارت می‌توانید نسخه را انتخاب نمایید.", self)
        info_lbl.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 11.5px;")
        btn_layout.addWidget(info_lbl, stretch=1)

        btn_confirm = QPushButton("تأیید و ادامه", self)
        btn_confirm.setProperty("class", "GoldPrimary")
        btn_confirm.setIcon(IconFactory.get_icon("check", size=16, color_override="#000000"))
        btn_confirm.setFixedSize(140, 38)
        btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(btn_confirm)

        btn_cancel = QPushButton("انصراف", self)
        btn_cancel.setProperty("class", "GoldSecondary")
        btn_cancel.setFixedSize(100, 38)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def _select_version(self, version: str):
        self.selected_version = str(version)
        self.card_2014.set_active(self.selected_version == "2014")
        self.card_2019.set_active(self.selected_version == "2019")

    def get_selected_version(self) -> str:
        return self.selected_version
