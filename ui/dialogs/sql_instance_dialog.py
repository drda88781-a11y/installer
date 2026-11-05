# ui/dialogs/sql_instance_dialog.py
"""
دیالوگ دریافت و تأیید نام اینستنس پایگاه داده Microsoft SQL Server
SQL Server Instance Selection & Confirmation Modal Dialog
"""

from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)
from config.settings import THEME_COLORS, get_sql_instance_name
from sql.sql_detector import get_all_installed_sql_instances
from sql.sql_verifier import verify_sql_connection
from utils.icon_factory import IconFactory


class SQLInstancePromptDialog(QDialog):
    """
    فرم وسط صفحه جهت دریافت نام اینستنس از کاربر در صورت وجود اس‌کیو‌ال سرور روی سیستم
    یا انتخاب و ورود نام اینستنس دلخواه
    """
    def __init__(
        self,
        current_instance: str = "",
        detected_instances: Optional[List[str]] = None,
        sql_version: str = "2019",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("تنظیم و انتخاب اینستنس SQL Server")
        self.resize(600, 430)
        self.setModal(True)
        self.setLayoutDirection(Qt.RightToLeft)

        self.sql_version = str(sql_version)
        self.detected_instances = detected_instances if detected_instances is not None else get_all_installed_sql_instances()
        default_inst = current_instance or (self.detected_instances[0] if self.detected_instances else get_sql_instance_name(self.sql_version))
        self.selected_instance: str = default_inst
        self.use_existing: bool = bool(self.detected_instances)

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
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)

        # ۱. سربرگ دیالوگ
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        icon_header = QLabel(self)
        icon_pix = IconFactory.get_icon("database", size=36, color_override=THEME_COLORS["gold_primary"]).pixmap(36, 36)
        icon_header.setPixmap(icon_pix)
        header_layout.addWidget(icon_header)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(4)

        dlg_title = QLabel("پایگاه داده SQL Server در سیستم شناسایی شد", self)
        dlg_title.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 17px; font-weight: bold;")
        title_vbox.addWidget(dlg_title)

        if self.detected_instances:
            inst_list_str = "، ".join(self.detected_instances)
            sub_text = f"اینستنس‌های شناسایی‌شده در ویندوز: <b>{inst_list_str}</b><br>می‌توانید یکی از موارد بالا را انتخاب کرده یا نام دلخواه خود را تایپ نمایید:"
        else:
            sub_text = "لطفاً نام اینستنس مورد نظر خود را جهت اتصال یا نصب نرم‌افزار سپهریار وارد نمایید:"

        dlg_sub = QLabel(sub_text, self)
        dlg_sub.setWordWrap(True)
        dlg_sub.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12.5px; line-height: 1.4;")
        title_vbox.addWidget(dlg_sub)

        header_layout.addLayout(title_vbox, stretch=1)
        layout.addLayout(header_layout)

        # ۲. کادر دریافت و انتخاب اینستنس
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
        form_layout.setContentsMargins(16, 12, 16, 12)
        form_layout.setSpacing(10)

        lbl_inst = QLabel("نام اینستنس SQL Server (انتخاب یا تایپ دستی):", form_frame)
        lbl_inst.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 12.5px; font-weight: bold;")
        form_layout.addWidget(lbl_inst)

        # کمبوباکس قابل ویرایش برای نام اینستنس
        combo_layout = QHBoxLayout()
        combo_layout.setSpacing(10)

        self.cmb_instance = QComboBox(form_frame)
        self.cmb_instance.setEditable(True)
        self.cmb_instance.setStyleSheet(f"""
            QComboBox {{
                background-color: #0E1015;
                color: #FFFFFF;
                border: 1px solid {THEME_COLORS['border_medium']};
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13.5px;
                font-weight: bold;
            }}
            QComboBox:focus {{
                border-color: {THEME_COLORS['gold_primary']};
            }}
            QComboBox QAbstractItemView {{
                background-color: #141720;
                color: #FFFFFF;
                selection-background-color: {THEME_COLORS['gold_primary']};
                selection-color: #0E1015;
            }}
        """)

        # بارگذاری اینستنس‌های کشف‌شده
        added_set = set()
        for inst in self.detected_instances:
            if inst and inst not in added_set:
                self.cmb_instance.addItem(inst)
                added_set.add(inst)

        # اضافه کردن اینستنس‌های پیشنهادی سپهریار در صورت عدم وجود
        for rec in ["SEPEHRYAR2019", "SEPEHRYAR2014", "MSSQLSERVER"]:
            if rec not in added_set:
                self.cmb_instance.addItem(rec)
                added_set.add(rec)

        if self.selected_instance:
            self.cmb_instance.setEditText(self.selected_instance)

        combo_layout.addWidget(self.cmb_instance, stretch=1)

        # دکمه تست اتصال زنده به اینستنس
        self.btn_test = QPushButton("🔍 تست اتصال", form_frame)
        self.btn_test.setProperty("class", "GoldSecondary")
        self.btn_test.setStyleSheet("padding: 7px 14px; font-size: 12px; font-weight: bold;")
        self.btn_test.clicked.connect(self._test_connection)
        combo_layout.addWidget(self.btn_test)

        form_layout.addLayout(combo_layout)

        # برچسب وضعیت تست اتصال
        self.lbl_test_result = QLabel(form_frame)
        self.lbl_test_result.setWordWrap(True)
        self.lbl_test_result.setVisible(False)
        form_layout.addWidget(self.lbl_test_result)

        # گزینه‌های نحوه برخورد با اینستنس
        opts_vbox = QVBoxLayout()
        opts_vbox.setSpacing(6)

        self.radio_use_existing = QRadioButton("استفاده از اینستنس موجود (تأمین خودکار کم و کسری‌ها بدون نصب مجدد)", form_frame)
        self.radio_use_existing.setStyleSheet(f"color: {THEME_COLORS['text_primary']}; font-size: 12px;")
        self.radio_use_existing.setChecked(True)
        opts_vbox.addWidget(self.radio_use_existing)

        self.radio_install_new = QRadioButton("نصب یک اینستنس جدید مجزا با همین نام (توسط اینستالر)", form_frame)
        self.radio_install_new.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 12px;")
        opts_vbox.addWidget(self.radio_install_new)

        form_layout.addLayout(opts_vbox)
        layout.addWidget(form_frame)

        # اتصال تغییر متن برای انتخاب هوشمند رادیوباتن
        self.cmb_instance.currentTextChanged.connect(self._on_instance_text_changed)
        self._on_instance_text_changed(self.cmb_instance.currentText())

        # نوار دکمه‌های پایین
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        info_lbl = QLabel("با کلیک روی «تأیید»، اینستنس انتخابی شما در تمامی مراحل نصب اعمال خواهد شد.", self)
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 11px;")
        btn_layout.addWidget(info_lbl, stretch=1)

        btn_confirm = QPushButton("تأیید و ذخیره اینستنس", self)
        btn_confirm.setProperty("class", "GoldPrimary")
        btn_confirm.setIcon(IconFactory.get_icon("check", size=16, color_override="#000000"))
        btn_confirm.setFixedSize(160, 38)
        btn_confirm.clicked.connect(self._on_confirm)
        btn_layout.addWidget(btn_confirm)

        btn_cancel = QPushButton("انصراف", self)
        btn_cancel.setProperty("class", "GoldSecondary")
        btn_cancel.setFixedSize(90, 38)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def _test_connection(self):
        """تست زنده اتصال به اینستنس تایپ‌شده یا انتخابی کاربر"""
        inst_name = self.cmb_instance.currentText().strip()
        if not inst_name:
            self.lbl_test_result.setText("⚠️ لطفاً نام اینستنس را وارد نمایید.")
            self.lbl_test_result.setStyleSheet("color: #F59E0B; font-size: 11.5px;")
            self.lbl_test_result.setVisible(True)
            return

        self.btn_test.setEnabled(False)
        self.btn_test.setText("در حال تست...")
        self.lbl_test_result.setText(f"در حال تلاش برای اتصال به {inst_name}...")
        self.lbl_test_result.setStyleSheet("color: #38BDF8; font-size: 11.5px;")
        self.lbl_test_result.setVisible(True)
        self.repaint()

        try:
            res = verify_sql_connection(instance_name=inst_name)
            if res.is_connected:
                ver_text = f" ({res.sql_version})" if res.sql_version else ""
                self.lbl_test_result.setText(
                    f"✓ اتصال زنده به اینستنس <b>{inst_name}</b> با موفقیت برقرار شد ({res.auth_method}){ver_text}."
                )
                self.lbl_test_result.setStyleSheet(f"""
                    QLabel {{
                        background-color: rgba(16, 185, 129, 0.15);
                        color: {THEME_COLORS['success']};
                        border: 1px solid {THEME_COLORS['success']};
                        border-radius: 6px;
                        padding: 6px 10px;
                        font-size: 11.5px;
                    }}
                """)
                self.radio_use_existing.setChecked(True)
            else:
                self.lbl_test_result.setText(
                    f"⚠️ اتصال مستقیم به {inst_name} برقرار نشد ({res.error_message}). در صورت لزوم می‌توانید نصب یا راه‌اندازی سرویس را انجام دهید."
                )
                self.lbl_test_result.setStyleSheet(f"""
                    QLabel {{
                        background-color: rgba(245, 158, 11, 0.12);
                        color: #F59E0B;
                        border: 1px solid rgba(245, 158, 11, 0.35);
                        border-radius: 6px;
                        padding: 6px 10px;
                        font-size: 11.5px;
                    }}
                """)
        except Exception as ex:
            self.lbl_test_result.setText(f"خطا در آزمون اتصال: {ex}")
            self.lbl_test_result.setStyleSheet("color: #EF4444; font-size: 11.5px;")
        finally:
            self.btn_test.setEnabled(True)
            self.btn_test.setText("🔍 تست اتصال")

    def _on_confirm(self):
        inst = self.cmb_instance.currentText().strip()
        if not inst:
            self.lbl_test_result.setText("⚠️ لطفاً نام اینستنس را مشخص نمایید.")
            self.lbl_test_result.setVisible(True)
            return
        self.selected_instance = inst
        self.use_existing = self.radio_use_existing.isChecked()
        self.accept()

    def get_selected_instance(self) -> str:
        return self.selected_instance

    def _on_instance_text_changed(self, text: str):
        inst = text.strip()
        is_detected = any(inst.lower() == d.lower() for d in self.detected_instances)
        if is_detected:
            self.radio_use_existing.setChecked(True)
        else:
            self.radio_install_new.setChecked(True)

    def is_use_existing_instance(self) -> bool:
        return self.use_existing

