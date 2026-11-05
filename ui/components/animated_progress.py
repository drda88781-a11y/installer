# ui/components/animated_progress.py
"""
ویجت پیشرفته نوار پیشرفت (Progress Bar) لوکس طلایی با نمایش سرعت و درصد
Luxury Gold progress bar widget with stage and percentage labels
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)
from config.settings import THEME_COLORS


class LuxuryProgressBar(QFrame):
    """
    نوار پیشرفت پیشرفته با استایل تیره و نوار طلایی
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ردیف بالای نوار: عنوان عملیات و درصد
        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)

        self.op_label = QLabel("آماده‌سازی فرایند نصب...", self)
        self.op_label.setStyleSheet(f"color: {THEME_COLORS['text_primary']}; font-size: 14px; font-weight: 500;")
        top_layout.addWidget(self.op_label, stretch=1)

        self.percent_label = QLabel("0%", self)
        self.percent_label.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 18px; font-weight: bold;")
        top_layout.addWidget(self.percent_label)

        layout.addLayout(top_layout)

        # نوار پروگرس بار
        self.pbar = QProgressBar(self)
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        self.pbar.setTextVisible(False)
        self.pbar.setFixedHeight(12)
        self.pbar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #121419;
                border: 1px solid {THEME_COLORS['border_subtle']};
                border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                  stop:0 {THEME_COLORS['gold_dark']},
                                                  stop:1 {THEME_COLORS['gold_primary']});
                border-radius: 5px;
            }}
        """)
        layout.addWidget(self.pbar)

        # جزئیات تکمیلی (فایل در حال کپی، بایت‌ها و ...)
        self.detail_label = QLabel("", self)
        self.detail_label.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 12px;")
        layout.addWidget(self.detail_label)

    def set_progress(self, percent: int, operation_text: str = "", detail_text: str = ""):
        p = max(0, min(percent, 100))
        self.pbar.setValue(p)
        self.percent_label.setText(f"{p}%")
        if operation_text:
            self.op_label.setText(operation_text)
        if detail_text:
            self.detail_label.setText(detail_text)
