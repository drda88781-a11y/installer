# ui/pages/page_update.py
"""
صفحه اختصاصی تعیین مسیر و پکیج آخرین به‌روزرسانی سپهریار:
- دریافت مسیر فایل .rar، .zip یا اسکریپت پچ .sql آخرین آپدیت
- ممیزی و بازرسی بلادرنگ محتوای آرشیو (تعداد فایل‌ها، MDFها، اسکریپت‌ها)
- استخراج چندلایه بدون نیاز به WinRAR در سیستم‌های مختلف
- امکان صرف‌نظر و ادامه نصب نسخه پایه بدون پکیج آپدیت
"""

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from config.settings import THEME_COLORS
from utils.archive_extractor import inspect_archive, ArchiveInspectionResult
from utils.icon_factory import IconFactory
from utils.win_helpers import format_bytes
from file_manager.update_engine import validate_update_archive


class UpdatePackagePage(QWidget):
    """
    صفحه اختصاصی تعیین مسیر و پکیج آخرین به‌روزرسانی
    """
    selection_changed = Signal(bool)  # is_valid_or_skipped
    update_applied = Signal(object)   # UpdateResult
    update_skipped = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_dir: Optional[Path] = None
        self.selected_product_ids: List[str] = []
        self.install_mode: str = "server"
        self.sql_version: str = "2019"
        self.server_target: str = ""
        self.archive_path: Optional[Path] = None
        self.inspection_result: Optional[ArchiveInspectionResult] = None
        self._init_ui()

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(16)

        # ۱. سربرگ صفحه
        self.title_lbl = QLabel("مسیر بسته یا اسکریپت آخرین به‌روزرسانی سپهریار", container)
        self.title_lbl.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 24px; font-weight: bold;")
        main_layout.addWidget(self.title_lbl)

        self.sub_lbl = QLabel(
            "بسته ZIP دارای شناسنامه یا پچ SQL همراه شناسنامه را انتخاب کنید. محصول، نسخه و سلامت فایل‌ها پیش از نصب بررسی می‌شوند. انتخاب آپدیت اختیاری است.",
            container
        )
        self.sub_lbl.setWordWrap(True)
        self.sub_lbl.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 13.5px; line-height: 1.5;")
        main_layout.addWidget(self.sub_lbl)

        # ۲. کارت انتخاب فایل مسیر آپدیت
        self.file_card = QFrame(container)
        self.file_card.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 10px;
                padding: 6px;
            }}
        """)
        file_layout = QVBoxLayout(self.file_card)
        file_layout.setContentsMargins(16, 14, 16, 14)
        file_layout.setSpacing(12)

        lbl_file_head = QLabel("مسیر فایل فشرده (.zip / .rar) یا اسکریپت دیتابیس (.sql):", self.file_card)
        lbl_file_head.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 13px; font-weight: bold;")
        file_layout.addWidget(lbl_file_head)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)

        self.txt_path = QLineEdit(self.file_card)
        self.txt_path.setPlaceholderText("مسیر فایل ZIP، RAR یا SQL پچ را انتخاب یا وارد نمایید...")
        self.txt_path.textChanged.connect(self._on_path_text_changed)
        self.txt_path.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0E1015;
                color: #FFFFFF;
                border: 1px solid {THEME_COLORS['border_medium']};
                border-radius: 6px;
                padding: 9px 12px;
                font-size: 12.5px;
            }}
            QLineEdit:focus {{
                border-color: {THEME_COLORS['gold_primary']};
            }}
            QLineEdit:disabled {{
                background-color: #1A1D24;
                color: #555555;
                border-color: #282D3A;
            }}
        """)
        input_layout.addWidget(self.txt_path, stretch=1)

        self.btn_browse = QPushButton("انتخاب فایل...", self.file_card)
        self.btn_browse.setProperty("class", "GoldSecondary")
        self.btn_browse.setIcon(IconFactory.get_icon("folder", size=16))
        self.btn_browse.setFixedHeight(36)
        self.btn_browse.clicked.connect(self._browse_archive)
        input_layout.addWidget(self.btn_browse)

        file_layout.addLayout(input_layout)

        # نوار وضعیت فایل انتخابی
        self.lbl_status = QLabel("اختیاری: فایل آپدیت را انتخاب نمایید یا از چک‌باکس زیر صرف‌نظر کنید.", self.file_card)
        self.lbl_status.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 12px;")
        file_layout.addWidget(self.lbl_status)

        # پنل پیش‌نمایش جزئیات پکیج آپدیت
        self.preview_card = QFrame(self.file_card)
        self.preview_card.setVisible(False)
        self.preview_card.setStyleSheet("""
            QFrame {
                background-color: #12141C;
                border: 1px solid #232938;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        preview_layout = QHBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(10, 8, 10, 8)
        preview_layout.setSpacing(14)

        self.lbl_pkg_badge = QLabel(self.preview_card)
        self.lbl_pkg_badge.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(216, 168, 78, 0.18);
                color: {THEME_COLORS['gold_hover']};
                border: 1px solid {THEME_COLORS['gold_primary']};
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)
        preview_layout.addWidget(self.lbl_pkg_badge)

        self.lbl_pkg_info = QLabel(self.preview_card)
        self.lbl_pkg_info.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12px;")
        preview_layout.addWidget(self.lbl_pkg_info, stretch=1)

        file_layout.addWidget(self.preview_card)
        main_layout.addWidget(self.file_card)

        # ۳. گزینه صرف‌نظر از آپدیت
        self.chk_skip = QCheckBox("صرف‌نظر از پکیج به‌روزرسانی در این مرحله (نصب نسخه پایه بدون آپدیت)", container)
        self.chk_skip.setStyleSheet(f"""
            QCheckBox {{
                color: {THEME_COLORS['text_primary']};
                font-size: 13px;
                font-weight: 500;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {THEME_COLORS['border_medium']};
                border-radius: 4px;
                background-color: #151820;
            }}
            QCheckBox::indicator:checked {{
                background-color: {THEME_COLORS['gold_primary']};
                border-color: {THEME_COLORS['gold_hover']};
            }}
        """)
        self.chk_skip.toggled.connect(self._on_skip_toggled)
        main_layout.addWidget(self.chk_skip)

        # ۴. کارت راهنمای اقدامات در صورت اعمال آپدیت
        self.info_card = QFrame(container)
        self.info_card.setStyleSheet(f"""
            QFrame {{
                background-color: #12141D;
                border: 1px solid #242938;
                border-radius: 10px;
                padding: 6px;
            }}
        """)
        info_layout = QVBoxLayout(self.info_card)
        info_layout.setContentsMargins(16, 14, 16, 14)
        info_layout.setSpacing(10)

        lbl_actions_title = QLabel("اقدامات خودکار در صورت انتخاب پکیج به‌روزرسانی:", self.info_card)
        lbl_actions_title.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 13px; font-weight: bold;")
        info_layout.addWidget(lbl_actions_title)

        self.info_rows_container = QWidget(self.info_card)
        self.info_rows_layout = QVBoxLayout(self.info_rows_container)
        self.info_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.info_rows_layout.setSpacing(8)
        info_layout.addWidget(self.info_rows_container)

        self._refresh_info_card(True)
        main_layout.addWidget(self.info_card)

        main_layout.addStretch()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    def _refresh_info_card(self, needs_sql: bool):
        while self.info_rows_layout.count():
            item = self.info_rows_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        if needs_sql:
            steps_text = [
                ("📁", "استخراج و کپی هوشمند فایل‌های آپدیت بدون قفل شدن پروسه‌ها"),
                ("🗄️", "انتقال فایل‌های دیتابیس (.mdf/.ldf) به پوشه داده‌ها (SEPEHRYAR.Data)"),
                ("⚡", "اتچ خودکار پایگاه داده در SQL Server فعال (SEPEHRYAR2019 / SEPEHRYAR2014)"),
                ("📜", "اجرای خودکار پچ‌های اسکریپتی دیتابیس (.sql) در صورت وجود"),
                ("🖥️", "ایجاد و بازسازی میانبر فایل اجرایی نرم‌افزار روی دسکتاپ ویندوز"),
            ]
        else:
            steps_text = [
                ("📁", "استخراج و کپی هوشمند فایل‌های آپدیت بر روی پوشه نرم‌افزار"),
                ("🗄️", "انتقال فایل‌های پوشه data به پوشه داده‌ها (SEPEHRYAR.Data)"),
                ("🖥️", "ایجاد و بازسازی میانبر فایل اجرایی نرم‌افزار روی دسکتاپ ویندوز"),
                ("🛡️", "عدم نیاز به اتچ پایگاه داده محلی (سیستم‌های فروش، کلاینت یا مودیان)"),
            ]

        for icon, text in steps_text:
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl_ico = QLabel(icon, self.info_card)
            lbl_ico.setFixedWidth(22)
            lbl_t = QLabel(text, self.info_card)
            lbl_t.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12.5px;")
            row.addWidget(lbl_ico)
            row.addWidget(lbl_t, stretch=1)
            self.info_rows_layout.addLayout(row)

    def set_context(
        self,
        root_dir: Optional[Path] = None,
        selected_product_ids: Optional[List[str]] = None,
        install_mode: str = "server",
        sql_version: str = "2019",
        server_target: str = "",
        sql_instance: str = "",
    ):
        """تنظیم مشخصات و پیش‌نیازها قبل از ورود به صفحه"""
        from config.settings import requires_sql
        self.root_dir = root_dir
        self.selected_product_ids = selected_product_ids or []
        self.install_mode = install_mode
        self.sql_version = str(sql_version)
        self.server_target = str(server_target)
        self.sql_instance = str(sql_instance)

        needs_sql = requires_sql(self.selected_product_ids, install_mode)
        self._refresh_info_card(needs_sql)

    def _browse_archive(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "انتخاب بسته یا اسکریپت آخرین به‌روزرسانی سپهریار",
            str(Path.home()),
            "بسته‌های دارای شناسنامه (*.zip *.sql);;بسته ZIP (*.zip);;پچ SQL (*.sql)"
        )
        if filepath:
            self.txt_path.setText(filepath)

    def _on_path_text_changed(self, text: str):
        clean_text = text.strip().strip('"').strip("'")
        if not clean_text:
            self.archive_path = None
            self.preview_card.setVisible(False)
            if not self.chk_skip.isChecked():
                self.lbl_status.setText("اختیاری: فایل آپدیت را انتخاب نمایید یا از چک‌باکس زیر صرف‌نظر کنید.")
                self.lbl_status.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 12px;")
            self.selection_changed.emit(True)
            return

        p = Path(clean_text)
        is_valid = p.exists() and p.is_file()
        if is_valid:
            report = validate_update_archive(p)
            if not report.is_valid:
                self.archive_path = None
                self.preview_card.setVisible(False)
                self.lbl_status.setText(f"✕ {report.error_message}")
                self.selection_changed.emit(False)
                return
            self.archive_path = p
            # بررسی محتوای فایل با موتور ارزیابی
            insp = inspect_archive(p)
            self.inspection_result = insp

            self.preview_card.setVisible(True)
            self.lbl_pkg_badge.setText(insp.file_type)

            size_str = format_bytes(insp.total_size_bytes)
            details = [f"حجم: {size_str}"]
            if insp.total_files_count > 0:
                details.append(f"تعداد {insp.total_files_count} فایل")
            if insp.mdf_files:
                details.append(f"{len(insp.mdf_files)} دیتابیس (MDF)")
            if insp.sql_files:
                details.append(f"{len(insp.sql_files)} اسکریپت SQL")

            self.lbl_pkg_info.setText(" | ".join(details))
            self.lbl_status.setText(f"✓ سلامت بسته تأیید شد: {p.name} — نسخه {report.package_version}")
            self.lbl_status.setStyleSheet(f"color: {THEME_COLORS['success']}; font-size: 12.5px; font-weight: bold;")
            self.selection_changed.emit(True)
        else:
            self.archive_path = None
            self.preview_card.setVisible(False)
            self.lbl_status.setText("✕ فایل انتخابی یافت نشد یا معتبر نیست.")
            self.lbl_status.setStyleSheet(f"color: {THEME_COLORS['error']}; font-size: 12px;")
            self.selection_changed.emit(False)

    def _on_skip_toggled(self, checked: bool):
        self.txt_path.setEnabled(not checked)
        self.btn_browse.setEnabled(not checked)
        if checked:
            self.preview_card.setVisible(False)
            self.lbl_status.setText("⚪ در صورت ادامه، نصب پایه بدون اعمال پکیج آپدیت انجام خواهد شد.")
            self.lbl_status.setStyleSheet(f"color: {THEME_COLORS['warning']}; font-size: 12px;")
            self.selection_changed.emit(True)
        else:
            self._on_path_text_changed(self.txt_path.text())

    def get_archive_path(self) -> Optional[Path]:
        """بازگرداندن مسیر فایل فشرده آپدیت در صورت انتخاب"""
        if self.chk_skip.isChecked():
            return None
        return self.archive_path

    def is_skipped(self) -> bool:
        """بررسی اینکه آیا پکیج آپدیت صرف‌نظر شده یا خالی است"""
        return self.chk_skip.isChecked() or not self.txt_path.text().strip()
