# ui/dialogs/client_connect_dialog.py
"""
دیالوگ تنظیم مشخصات اتصال به سرور مرکزی در حالت کلاینت (تنظیم فایل CONNECT)
Dialog for configuring remote SQL Server IP/instance in Client mode
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from config.settings import THEME_COLORS
from utils.connect_config import test_server_connection
from utils.icon_factory import IconFactory


class ClientConnectDialog(QDialog):
    """
    فرم دریافت آدرس سرور مرکزی و اینستنس جهت تنظیم فایل‌های CONNECT کلاینت
    """
    def __init__(self, current_target: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("تنظیم اتصال به سرور مرکزی (فایل CONNECT)")
        self.resize(580, 390)
        self.setModal(True)

        self.server_ip = ""
        self.instance_name = "SEPEHRYAR2019"

        if current_target:
            if "\\" in current_target:
                parts = current_target.split("\\", 1)
                self.server_ip = parts[0].strip()
                self.instance_name = parts[1].strip()
            else:
                self.server_ip = current_target.strip()

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
        layout.setSpacing(16)

        # سربرگ دیالوگ
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        icon_header = QLabel(self)
        icon_pix = IconFactory.get_icon("server", size=36, color_override=THEME_COLORS["gold_primary"]).pixmap(36, 36)
        icon_header.setPixmap(icon_pix)
        header_layout.addWidget(icon_header)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(4)

        dlg_title = QLabel("تنظیم اتصال کلاینت به سرور مرکزی", self)
        dlg_title.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 17px; font-weight: bold;")
        title_vbox.addWidget(dlg_title)

        dlg_sub = QLabel("مشخصات سرور را جهت ثبت خودکار در فایل‌های CONNECT وارد فرمایید:", self)
        dlg_sub.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12.5px;")
        title_vbox.addWidget(dlg_sub)

        header_layout.addLayout(title_vbox, stretch=1)
        layout.addLayout(header_layout)

        # کادر فیلدها
        form_frame = QFrame(self)
        form_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 10px;
                padding: 6px;
            }}
        """)
        form_layout = QVBoxLayout(form_frame)
        form_layout.setContentsMargins(16, 14, 16, 14)
        form_layout.setSpacing(12)

        # فیلد ۱: IP یا نام کامپیوتر سرور
        lbl_ip = QLabel("آدرس IP یا نام کامپیوتر سرور مرکزی:", form_frame)
        lbl_ip.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 12.5px; font-weight: bold;")
        form_layout.addWidget(lbl_ip)

        self.txt_server_ip = QLineEdit(form_frame)
        self.txt_server_ip.setPlaceholderText("مثال: 192.168.1.100 یا SERVER-PC")
        self.txt_server_ip.setText(self.server_ip)
        self.txt_server_ip.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0E1015;
                color: #FFFFFF;
                border: 1px solid {THEME_COLORS['border_medium']};
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {THEME_COLORS['gold_primary']};
            }}
        """)
        form_layout.addWidget(self.txt_server_ip)

        # فیلد ۲: نام اینستنس پایگاه داده
        lbl_inst = QLabel("اینستنس SQL Server در سرور (اختیاری):", form_frame)
        lbl_inst.setStyleSheet(f"color: {THEME_COLORS['text_primary']}; font-size: 12px; font-weight: bold;")
        form_layout.addWidget(lbl_inst)

        self.cmb_instance = QComboBox(form_frame)
        self.cmb_instance.setEditable(True)
        self.cmb_instance.addItems(["SEPEHRYAR2019", "SEPEHRYAR2014", "بدون اینستنس (Default)"])
        if self.instance_name:
            self.cmb_instance.setEditText(self.instance_name)
        self.cmb_instance.setStyleSheet(f"""
            QComboBox {{
                background-color: #0E1015;
                color: #FFFFFF;
                border: 1px solid {THEME_COLORS['border_medium']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12.5px;
            }}
            QComboBox:focus {{
                border-color: {THEME_COLORS['gold_primary']};
            }}
        """)
        form_layout.addWidget(self.cmb_instance)

        layout.addWidget(form_frame)

        # ردیف تست اتصال
        test_layout = QHBoxLayout()
        test_layout.setSpacing(10)

        self.btn_test = QPushButton("تست اتصال شبکه به سرور", self)
        self.btn_test.setProperty("class", "GoldSecondary")
        self.btn_test.setIcon(IconFactory.get_icon("refresh", size=15))
        self.btn_test.clicked.connect(self._on_test_clicked)
        test_layout.addWidget(self.btn_test)

        self.lbl_test_result = QLabel("", self)
        self.lbl_test_result.setStyleSheet("font-size: 12px;")
        test_layout.addWidget(self.lbl_test_result, stretch=1)

        layout.addLayout(test_layout)

        # راهنما
        tip_lbl = QLabel(
            "💡 این آدرس به عنوان Data Source در فایل‌های conect.xml و ConectClient.xml ذخیره می‌شود.",
            self
        )
        tip_lbl.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 11px;")
        layout.addWidget(tip_lbl)

        # دکمه‌های اقدام
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        btn_confirm = QPushButton("تأیید و ذخیره", self)
        btn_confirm.setProperty("class", "GoldPrimary")
        btn_confirm.setIcon(IconFactory.get_icon("check", size=16, color_override="#000000"))
        btn_confirm.setFixedSize(130, 38)
        btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(btn_confirm)

        btn_cancel = QPushButton("انصراف", self)
        btn_cancel.setProperty("class", "GoldSecondary")
        btn_cancel.setFixedSize(100, 38)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def _on_test_clicked(self):
        host = self.txt_server_ip.text().strip()
        if not host:
            self.lbl_test_result.setText("✕ لطفاً آدرس IP یا نام سرور را وارد کنید.")
            self.lbl_test_result.setStyleSheet(f"color: {THEME_COLORS['error']}; font-weight: bold;")
            return

        self.lbl_test_result.setText("در حال تست ارتباط با پورت 1433...")
        self.lbl_test_result.setStyleSheet(f"color: {THEME_COLORS['gold_hover']};")
        self.repaint()

        ok, msg = test_server_connection(host, default_port=1433, timeout=2.5)
        if ok:
            self.lbl_test_result.setText(f"✓ {msg}")
            self.lbl_test_result.setStyleSheet(f"color: {THEME_COLORS['success']}; font-weight: bold;")
        else:
            self.lbl_test_result.setText(f"✕ {msg}")
            self.lbl_test_result.setStyleSheet(f"color: {THEME_COLORS['error']};")

    def get_server_target(self) -> str:
        """
        بازگرداندن رشته Data Source به فرمت Server\\Instance یا Server
        """
        host = self.txt_server_ip.text().strip()
        if not host:
            return ""
        inst = self.cmb_instance.currentText().strip()
        if inst and "بدون اینستنس" not in inst:
            return f"{host}\\{inst}"
        return host
