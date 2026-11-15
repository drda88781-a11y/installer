# ui/dialogs/password_dialog.py
"""
دیالوگ امنیتی احراز هویت و ورود به نصاب سپهریار
پشتیبانی از تفکیک دسترسی مدیر کل (admin / 55219100) و کارشناس بازرگانی (1 / 1)
Security Login & Role Authentication Dialog for SEPEHRYAR Installer
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
    پنجره مدال و لوکس مشکی-طلایی جهت ورود و تعیین سطح دسترسی کاربر
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("احراز هویت نصاب سپهریار")
        self.setFixedSize(500, 360)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {THEME_COLORS['bg_main']};
                color: {THEME_COLORS['text_primary']};
            }}
        """)
        self.user_role = "admin"
        self.username = "admin"
        self._init_ui()

    def get_user_role(self) -> str:
        """بازگرداندن نقش کاربر: 'admin' یا 'commercial'"""
        return self.user_role

    def get_username(self) -> str:
        """بازگرداندن نام کاربری وارد شده"""
        return self.username

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 22, 28, 20)
        main_layout.setSpacing(14)

        # کارت اصلی هدر
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        icon_shield = QLabel(self)
        icon_shield.setPixmap(IconFactory.get_icon("technician", size=38, color_override=THEME_COLORS["gold_primary"]).pixmap(38, 38))
        header_layout.addWidget(icon_shield)

        v_head = QVBoxLayout()
        v_head.setSpacing(4)
        lbl_title = QLabel("ورود به سیستم استقرار سپهریار", self)
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {THEME_COLORS['gold_primary']};")
        v_head.addWidget(lbl_title)

        lbl_desc = QLabel("لطفاً نام کاربری و رمز عبور اختصاصی نصاب را وارد فرمایید.", self)
        lbl_desc.setStyleSheet(f"font-size: 11.5px; color: {THEME_COLORS['text_secondary']};")
        v_head.addWidget(lbl_desc)

        header_layout.addLayout(v_head, stretch=1)
        main_layout.addLayout(header_layout)

        # خط جداکننده
        sep = QFrame(self)
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {THEME_COLORS['border_medium']};")
        main_layout.addWidget(sep)

        # ۱. کادر نام کاربری
        user_card = QFrame(self)
        user_card.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 8px;
            }}
            QFrame:focus-within {{
                border: 1px solid {THEME_COLORS['gold_primary']};
            }}
        """)
        user_layout = QHBoxLayout(user_card)
        user_layout.setContentsMargins(10, 4, 10, 4)
        user_layout.setSpacing(8)

        lbl_user_icon = QLabel("👤", user_card)
        lbl_user_icon.setStyleSheet("font-size: 15px;")
        user_layout.addWidget(lbl_user_icon)

        self.txt_username = QLineEdit(user_card)
        self.txt_username.setPlaceholderText("نام کاربری (مثلاً admin یا 1)")
        self.txt_username.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                color: #FFFFFF;
                border: none;
                font-size: 13px;
                padding: 6px;
                font-family: Consolas, "Courier New", monospace;
            }
        """)
        self.txt_username.returnPressed.connect(lambda: self.txt_password.setFocus())
        user_layout.addWidget(self.txt_username, stretch=1)
        main_layout.addWidget(user_card)

        # ۲. کادر ورود رمز عبور با دکمه نمایش/مخفی
        pass_card = QFrame(self)
        pass_card.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 8px;
            }}
            QFrame:focus-within {{
                border: 1px solid {THEME_COLORS['gold_primary']};
            }}
        """)
        pass_layout = QHBoxLayout(pass_card)
        pass_layout.setContentsMargins(10, 4, 10, 4)
        pass_layout.setSpacing(8)

        lbl_lock = QLabel("🔒", pass_card)
        lbl_lock.setStyleSheet("font-size: 15px;")
        pass_layout.addWidget(lbl_lock)

        self.txt_password = QLineEdit(pass_card)
        self.txt_password.setEchoMode(QLineEdit.Password)
        self.txt_password.setPlaceholderText("رمز عبور...")
        self.txt_password.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                color: #FFFFFF;
                border: none;
                font-size: 13px;
                padding: 6px;
                font-family: Consolas, "Courier New", monospace;
            }
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

        # پیام خطای ورود نادرست
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

        # فوکوس اولیه روی نام کاربری
        self.txt_username.setFocus()

    def _toggle_password_visibility(self):
        if self.txt_password.echoMode() == QLineEdit.Password:
            self.txt_password.setEchoMode(QLineEdit.Normal)
        else:
            self.txt_password.setEchoMode(QLineEdit.Password)

    def _validate_and_submit(self):
        username = self.txt_username.text().strip()
        password = self.txt_password.text().strip()

        # ۱. ورود مدیر کل با دسترسی کامل به همه پکیج‌ها
        if (username.lower() == "admin" and password == "55219100") or (password == INSTALLER_ACCESS_PASSWORD):
            self.user_role = "admin"
            self.username = "admin"
            logger.log("AUTH", "LOGIN", "SUCCESS", "ورود کاربر ارشد (admin) با دسترسی کامل به تمامی نرم‌افزارها تایید شد.")
            self.accept()
            return

        # ۲. ورود کارشناس حسابداری بازرگانی با دسترسی اختصاصی و محدود
        if username == "1" and password == "1":
            self.user_role = "commercial"
            self.username = "1"
            logger.log("AUTH", "LOGIN", "SUCCESS", "ورود کاربر محدود (1) با دسترسی اختصاصی به حسابداری بازرگانی تایید شد.")
            self.accept()
            return

        # ۳. خطا در صورت عدم تطابق
        logger.log("AUTH", "LOGIN", "FAILED", f"نام کاربری یا رمز عبور نامعتبر برای کاربر: {username}")
        self.lbl_error.setText("⚠️ نام کاربری یا رمز عبور وارد شده نادرست است.")
        self.lbl_error.setVisible(True)
        self.txt_password.selectAll()
        self.txt_password.setFocus()
