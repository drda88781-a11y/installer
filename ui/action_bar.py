# ui/action_bar.py
"""
نوار اقدامات پایینی اینستالر (Action Bar) شامل دکمه‌های ناوبری، لاگ و خروج
Bottom action bar with Gold primary and secondary navigation buttons
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QWidget,
)
from utils.icon_factory import IconFactory


class ActionBar(QWidget):
    """
    نوار اقدامات پایین صفحه با استایل راست‌به‌چپ (RTL)
    """
    next_clicked = Signal()
    prev_clicked = Signal()
    cancel_clicked = Signal()
    log_clicked = Signal()
    troubleshoot_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ActionBarWidget")
        self.setFixedHeight(72)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        # دکمه مشاهده لاگ
        self.btn_log = QPushButton("مشاهده لاگ", self)
        self.btn_log.setProperty("class", "GoldSecondary")
        self.btn_log.setIcon(IconFactory.get_icon("log", size=16))
        self.btn_log.clicked.connect(self.log_clicked.emit)
        layout.addWidget(self.btn_log)

        # دکمه عیب‌یابی و تأمین کسری‌ها (Troubleshooting Panel)
        self.btn_troubleshoot = QPushButton("عیب‌یابی و تأمین کسری‌ها (F12)", self)
        self.btn_troubleshoot.setProperty("class", "GoldSecondary")
        self.btn_troubleshoot.setIcon(IconFactory.get_icon("gear", size=16))
        self.btn_troubleshoot.clicked.connect(self.troubleshoot_clicked.emit)
        layout.addWidget(self.btn_troubleshoot)

        layout.addStretch()

        # دکمه انصراف
        self.btn_cancel = QPushButton("انصراف", self)
        self.btn_cancel.setProperty("class", "GoldSecondary")
        self.btn_cancel.clicked.connect(self.cancel_clicked.emit)
        layout.addWidget(self.btn_cancel)

        # دکمه قبلی
        self.btn_prev = QPushButton("مرحله قبلی", self)
        self.btn_prev.setProperty("class", "GoldSecondary")
        self.btn_prev.clicked.connect(self.prev_clicked.emit)
        layout.addWidget(self.btn_prev)

        # دکمه اصلی (بعدی / شروع نصب / اتمام)
        self.btn_next = QPushButton("ادامه", self)
        self.btn_next.setProperty("class", "GoldPrimary")
        self.btn_next.clicked.connect(self.next_clicked.emit)
        layout.addWidget(self.btn_next)

    def set_next_enabled(self, enabled: bool):
        self.btn_next.setEnabled(enabled)

    def set_next_text(self, text: str):
        self.btn_next.setText(text)

    def set_prev_visible(self, visible: bool):
        self.btn_prev.setVisible(visible)

    def set_cancel_visible(self, visible: bool):
        self.btn_cancel.setVisible(visible)

    def set_log_visible(self, visible: bool):
        self.btn_log.setVisible(visible)
