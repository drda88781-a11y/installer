# ui/dialogs/log_dialog.py
"""
دیالوگ پیشرفته و شیک مشاهده زنده گزارش نصب و لاگ‌های سیستم
Advanced real-time log viewer modal dialog with export and filter capabilities
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QFileDialog,
)
from config.settings import THEME_COLORS
from app_logging.app_logger import logger
from utils.icon_factory import IconFactory


class LogViewerDialog(QDialog):
    """
    پنجره مدال لاگ با قابلیت کپی، خروجی و رفرش خودکار
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("گزارش وقایع و لاگ نصب سپهریار")
        self.resize(800, 520)
        self._init_ui()
        self.refresh_log()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # سربرگ دیالوگ
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        icon_lbl = QLabel(self)
        icon_pix = IconFactory.get_icon("log", size=24).pixmap(24, 24)
        icon_lbl.setPixmap(icon_pix)
        header_layout.addWidget(icon_lbl)

        title_lbl = QLabel("گزارش زنده عملیات نصب و بررسی سیستم", self)
        title_lbl.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title_lbl, stretch=1)

        layout.addLayout(header_layout)

        # متن لاگ
        self.log_text = QPlainTextEdit(self)
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text, stretch=1)

        # دکمه‌های پایینی
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_export = QPushButton("ذخیره در فایل...", self)
        self.btn_export.setProperty("class", "GoldSecondary")
        self.btn_export.clicked.connect(self._export_log)
        btn_layout.addWidget(self.btn_export)

        self.btn_copy = QPushButton("کپی در کلیپ‌بورد", self)
        self.btn_copy.setProperty("class", "GoldSecondary")
        self.btn_copy.clicked.connect(self._copy_log)
        btn_layout.addWidget(self.btn_copy)

        btn_layout.addStretch()

        self.btn_close = QPushButton("بستن", self)
        self.btn_close.setProperty("class", "GoldPrimary")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def refresh_log(self):
        txt = logger.get_full_text()
        self.log_text.setPlainText(txt)
        # اسکرول به انتها
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def _copy_log(self):
        self.log_text.selectAll()
        self.log_text.copy()
        self.btn_copy.setText("کپی شد! ✓")

    def _export_log(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "ذخیره لاگ نصب",
            "SEPEHRYAR_Install_Log.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.log_text.toPlainText())
