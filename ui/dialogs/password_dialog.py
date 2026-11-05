# ui/dialogs/password_dialog.py
"""
دیالوگ امنیتی احراز هویت و دریافت رمز عبور جهت ورود به نصاب سپهریار
Security Password Dialog for Authenticating Access to SEPEHRYAR Installer
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from app_logging.app_logger import logger
from config.settings import THEME_COLORS, APP_NAME_FA
from utils.icon_factory import IconFactory

INSTALLER_ACCESS_PASSWORD = "sepehr@yar@system"


class PasswordDialog(QDialog):
    """
    پنجره مدال و لوکس مشکی-طلایی جهت دریافت رمز عبور ورود به برنامه
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("احراز هویت نصاب سپهریار")
        self.setFixedSize(480, 290)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {THEME_COLORS['bg_main']};
                color: {THEME_COLORS['text_primary']};
            }}
        """)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 20)
        main_layout.setSpacing(16)

        # کارت اصلی هدر
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        icon_shield = QLabel(self)
        icon_shield.setPixmap(IconFactory.get_icon("technician", size=36, color_override=THEME_COLORS["gold_primary"]).pixmap(36, 36))
        header_layout.addWidget(icon_shield)

        v_head = QVBoxLayout()
        v_head.setSpacing(4)
        lbl_title = QLabel("ورود به سیستم استقرار سپهریار", self)
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {THEME_COLORS['gold_primary']};")
        v_head.addWidget(lbl_title)

        lbl_desc = QLabel("لطفاً جهت دسترسی به منوهای نصب، رمز عبور اختصاصی را وارد نمایید.", self)
        lbl_desc.setStyleSheet(f"font-size: 11.5px; color: {THEME_COLORS['text_secondary']};")
        v_head.addWidget(lbl_desc)

        header_layout.addLayout(v_head, stretch=1)
        main_layout.addLayout(header_layout)

        # خط جداکننده
        sep = QFrame(self)
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {THEME_COLORS['border_medium']};")
        main_layout.addWidget(sep)

        # کادر ورود رمز عبور با دکمه نمایش/مخفی
        pass_card = QFrame(self)
        pass_card.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 8px;
            }}
        """)
        pass_layout = QHBoxLayout(pass_card)
        pass_layout.setContentsMargins(10, 4, 10, 4)
        pass_layout.setSpacing(8)

        lbl_lock = QLabel("🔒", pass_card)
        lbl_lock.setStyleSheet("font-size: 16px;")
        pass_layout.addWidget(lbl_lock)

        self.txt_password = QLineEdit(pass_card)
        self.txt_password.setEchoMode(QLineEdit.Password)
        self.txt_password.setPlaceholderText("رمز عبور امنیتی را وارد کنید...")
        self.txt_password.setStyleSheet(f"""
            QLineEdit {{
                background-color: transparent;
                color: #FFFFFF;
                border: none;
                font-size: 13px;
                padding: 6px;
                font-family: Consolas, "Courier New", monospace;
            }}
        """)
        self.txt_password.returnPressed.connect(self._validate_and_submit)
        pass_layout.addWidget(self.txt_password, stretch=1)

        self.btn_toggle_eye = QPushButton("👁", pass_card)
        self.btn_toggle_eye.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_eye.setToolTip("نمایش / مخفی‌سازی رمز")
        self.btn_toggle_eye.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 15px;
                color: #A0A7B5;
                padding: 4px;
            }
            QPushButton:hover {
                color: #FFFFFF;
            }
        """)
        self.btn_toggle_eye.clicked.connect(self._toggle_password_visibility)
        pass_layout.addWidget(self.btn_toggle_eye)

        main_layout.addWidget(pass_card)

        # پیام خطای رمز نادرست
        self.lbl_error = QLabel("", self)
        self.lbl_error.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: bold;")
        self.lbl_error.setVisible(False)
        main_layout.addWidget(self.lbl_error)

        main_layout.addStretch(1)

        # دکمه‌های تایید و انصراف
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_cancel = QPushButton("انصراف و خروج", self)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME_COLORS['card_bg']};
                color: {THEME_COLORS['text_secondary']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                border-color: #EF4444;
                color: #EF4444;
                background-color: {THEME_COLORS['card_hover']};
            }}
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_submit = QPushButton("تأیید و ورود >", self)
        self.btn_submit.setCursor(Qt.PointingHandCursor)
        self.btn_submit.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {THEME_COLORS['gold_primary']}, stop:1 {THEME_COLORS['gold_dark']});
                color: #0E1015;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-size: 12.5px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {THEME_COLORS['gold_hover']};
            }}
        """)
        self.btn_submit.clicked.connect(self._validate_and_submit)
        btn_layout.addWidget(self.btn_submit)

        main_layout.addLayout(btn_layout)

        # فوکوس پیش‌فرض روی اینپوت
        self.txt_password.setFocus()

    def _toggle_password_visibility(self):
        if self.txt_password.echoMode() == QLineEdit.Password:
            self.txt_password.setEchoMode(QLineEdit.Normal)
        else:
            self.txt_password.setEchoMode(QLineEdit.Password)

    def _validate_and_submit(self):
        entered = self.txt_password.text().strip()
        if entered == INSTALLER_ACCESS_PASSWORD:
            logger.log("AUTH", "LOGIN", "SUCCESS", "احراز هویت کارشناس نصب با موفقیت تایید شد.")
            self.accept()
        else:
            logger.log("AUTH", "LOGIN", "FAILED", "رمز عبور وارد شده نادرست است.")
            self.lbl_error.setText("⚠️ رمز عبور وارد شده نادرست است. لطفاً مجدداً بررسی فرمایید.")
            self.lbl_error.setVisible(True)
            self.txt_password.selectAll()
            self.txt_password.setFocus()
