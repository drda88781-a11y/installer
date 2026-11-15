# ui/dialogs/keygen_dialog.py
"""
دیالوگ هوشمند فعال‌سازی و کیجن نرم‌افزار حسابداری سپهریار
پشتیبانی از تولید خودکار کد فعال‌سازی، تزریق در برنامه و کپی سریع
Keygen & Software Lock Activation Dialog for SEPEHRYAR Accounting
"""

from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from config.settings import THEME_COLORS
from utils.icon_factory import IconFactory
from utils.sepehryar_keygen import (
    KEYGEN_MASTER_PASSWORD,
    auto_unlock_sepehryar_app,
    generate_activation_code,
    get_clipboard_text,
    set_clipboard_text,
)


class KeygenDialog(QDialog):
    """
    دیالوگ لوکس مشکی-طلایی کیجن و بازگشایی قفل نرم‌افزاری سپهریار
    """
    def __init__(self, exe_path: Optional[Path] = None, parent=None):
        super().__init__(parent)
        self.exe_path = exe_path
        self.setWindowTitle("دستیار هوشمند فعال‌سازی قفل نرم‌افزاری سپهریار")
        self.setFixedSize(540, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {THEME_COLORS['bg_main']};
                color: {THEME_COLORS['text_primary']};
            }}
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(12)

        # ۱. سربرگ
        head_layout = QHBoxLayout()
        head_layout.setSpacing(12)

        icon_key = QLabel(self)
        icon_key.setPixmap(IconFactory.get_icon("key", size=36, color_override=THEME_COLORS["gold_primary"]).pixmap(36, 36))
        head_layout.addWidget(icon_key)

        v_head = QVBoxLayout()
        v_head.setSpacing(2)
        lbl_title = QLabel("فعال‌سازی قفل نرم‌افزاری سپهریار", self)
        lbl_title.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 16px; font-weight: bold;")
        v_head.addWidget(lbl_title)

        lbl_desc = QLabel("تولید آنی کد فعال‌سازی و بازگشایی قفل نرم‌افزار حسابداری بازرگانی", self)
        lbl_desc.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 11.5px;")
        v_head.addWidget(lbl_desc)

        head_layout.addLayout(v_head, stretch=1)
        layout.addLayout(head_layout)

        # خط جداکننده
        sep = QFrame(self)
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {THEME_COLORS['border_medium']};")
        layout.addWidget(sep)

        # ۲. فیلد رمز کیجن
        lbl_pass = QLabel("رمز عبور امنیتی کیجن:", self)
        lbl_pass.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(lbl_pass)

        self.txt_pass = QLineEdit(self)
        self.txt_pass.setText(KEYGEN_MASTER_PASSWORD)
        self.txt_pass.setEchoMode(QLineEdit.Password)
        self.txt_pass.setReadOnly(True)
        self.txt_pass.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME_COLORS['card_bg']};
                color: #FFFFFF;
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }}
        """)
        layout.addWidget(self.txt_pass)

        # ۳. فیلد کد قفل / سریال برنامه
        lbl_serial = QLabel("کد قفل نمایش‌داده‌شده در نرم‌افزار (Serial / Lock Code):", self)
        lbl_serial.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 12px; font-weight: bold;")
        layout.addWidget(lbl_serial)

        serial_box = QHBoxLayout()
        serial_box.setSpacing(8)

        self.txt_serial = QLineEdit(self)
        self.txt_serial.setPlaceholderText("کد قفل برنامه را اینجا وارد یا پیست کنید...")
        self.txt_serial.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME_COLORS['card_bg']};
                color: #FFFFFF;
                border: 1px solid {THEME_COLORS['gold_primary']};
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13px;
                font-weight: bold;
                font-family: Consolas, monospace;
            }}
        """)
        self.txt_serial.textChanged.connect(self._on_serial_changed)
        serial_box.addWidget(self.txt_serial, stretch=1)

        btn_paste = QPushButton("📋 پیست", self)
        btn_paste.setCursor(Qt.PointingHandCursor)
        btn_paste.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME_COLORS['card_bg']};
                color: {THEME_COLORS['gold_primary']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11.5px;
            }}
            QPushButton:hover {{
                border-color: {THEME_COLORS['gold_primary']};
            }}
        """)
        btn_paste.clicked.connect(self._paste_serial)
        serial_box.addWidget(btn_paste)

        layout.addLayout(serial_box)

        # ۴. فیلد کد فعال‌سازی تولیدشده
        lbl_code = QLabel("کد فعال‌سازی محاسبه‌شده (Activation Code):", self)
        lbl_code.setStyleSheet(f"color: {THEME_COLORS['success']}; font-size: 12px; font-weight: bold;")
        layout.addWidget(lbl_code)

        code_box = QHBoxLayout()
        code_box.setSpacing(8)

        self.txt_code = QLineEdit(self)
        self.txt_code.setReadOnly(True)
        self.txt_code.setPlaceholderText("XXXX-XXXX-XXXX")
        self.txt_code.setStyleSheet(f"""
            QLineEdit {{
                background-color: #121820;
                color: #4ADE80;
                border: 1px solid {THEME_COLORS['success']};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 15px;
                font-weight: bold;
                font-family: Consolas, monospace;
                letter-spacing: 2px;
            }}
        """)
        code_box.addWidget(self.txt_code, stretch=1)

        self.btn_copy = QPushButton("کپی کد", self)
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME_COLORS['success']};
                color: #0E1015;
                border: none;
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #22C55E;
            }}
        """)
        self.btn_copy.clicked.connect(self._copy_code)
        code_box.addWidget(self.btn_copy)

        layout.addLayout(code_box)

        # وضعیت
        self.lbl_status = QLabel("", self)
        self.lbl_status.setStyleSheet("font-size: 11.5px; color: #A0A7B5;")
        layout.addWidget(self.lbl_status)

        layout.addStretch(1)

        # دکمه‌های اکشن
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_auto_unlock = QPushButton("⚡ بازگشایی خودکار قفل برنامه", self)
        self.btn_auto_unlock.setCursor(Qt.PointingHandCursor)
        self.btn_auto_unlock.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {THEME_COLORS['gold_primary']}, stop:1 {THEME_COLORS['gold_dark']});
                color: #0E1015;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 12.5px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {THEME_COLORS['gold_hover']};
            }}
        """)
        self.btn_auto_unlock.clicked.connect(self._run_auto_unlock)
        btn_layout.addWidget(self.btn_auto_unlock, stretch=1)

        btn_close = QPushButton("بستن", self)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME_COLORS['card_bg']};
                color: {THEME_COLORS['text_secondary']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                color: #FFFFFF;
                border-color: {THEME_COLORS['border_medium']};
            }}
        """)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

        # بررسی کلیپ‌بورد برای پیست خودکار سریال در بدو باز شدن
        self._auto_detect_from_clipboard()

    def _auto_detect_from_clipboard(self):
        cb_text = get_clipboard_text().strip()
        if cb_text and len(cb_text) >= 4 and not cb_text.startswith("-") and cb_text != KEYGEN_MASTER_PASSWORD:
            self.txt_serial.setText(cb_text)

    def _paste_serial(self):
        cb_text = get_clipboard_text().strip()
        if cb_text:
            self.txt_serial.setText(cb_text)

    def _on_serial_changed(self, text: str):
        clean = text.strip()
        if not clean:
            self.txt_code.clear()
            self.lbl_status.setText("")
            return

        pwd = self.txt_pass.text().strip() or KEYGEN_MASTER_PASSWORD
        try:
            code = generate_activation_code(clean, password=pwd)
            self.txt_code.setText(code)
            self.lbl_status.setText("✓ کد فعال‌سازی با موفقیت محاسبه گردید و آماده کپی است.")
            self.lbl_status.setStyleSheet("color: #4ADE80; font-size: 11.5px;")
        except Exception as ex:
            self.txt_code.clear()
            self.lbl_status.setText(f"خطا: {ex}")
            self.lbl_status.setStyleSheet("color: #EF4444; font-size: 11.5px;")

    def _copy_code(self):
        code = self.txt_code.text().strip()
        if code:
            set_clipboard_text(code)
            self.lbl_status.setText("✓ کد فعال‌سازی در کلیپ‌بورد کپی شد (آماده پیست در نرم‌افزار).")
            self.lbl_status.setStyleSheet("color: #4ADE80; font-size: 11.5px; font-weight: bold;")
            QMessageBox.information(self, "کپی موفق", f"کد فعال‌سازی در کلیپ‌بورد کپی شد:\n\n{code}")

    def _run_auto_unlock(self):
        self.lbl_status.setText("در حال بررسی و بازگشایی پنجره قفل نرم‌افزار...")
        self.lbl_status.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 11.5px;")
        ok, msg, code = auto_unlock_sepehryar_app(exe_path=self.exe_path, timeout_sec=15)
        if ok and code:
            self.txt_code.setText(code)
            self.lbl_status.setText(f"✓ {msg}")
            self.lbl_status.setStyleSheet("color: #4ADE80; font-size: 11.5px; font-weight: bold;")
            QMessageBox.information(self, "فعال‌سازی قفل", msg)
        else:
            self.lbl_status.setText(msg)
            self.lbl_status.setStyleSheet(f"color: {THEME_COLORS['warning']}; font-size: 11.5px;")
            # اگر سریال در کادر بود، دستی محاسبه کن
            if self.txt_serial.text().strip():
                self._on_serial_changed(self.txt_serial.text())

