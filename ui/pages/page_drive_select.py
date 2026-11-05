# ui/pages/page_drive_select.py
"""
صفحه ۲: اسکن، ارزیابی و انتخاب درایو نصب با اعمال ممنوعیت درایو C
Page 2: Drive Scan and Selection with Drive C Prohibited and Space Validation
"""

from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from config.settings import THEME_COLORS, DEV_ALLOW_LOW_SPACE
from file_manager.drive_scanner import scan_drives, DriveInfo
from ui.components.gold_card import SelectableDriveCard
from utils.icon_factory import IconFactory


class DriveSelectPage(QWidget):
    """
    صفحه انتخاب درایو نصب با بررسی محدودیت‌ها
    """
    drive_selected = Signal(str, bool)  # drive_letter, is_valid

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drives: List[DriveInfo] = []
        self.card_widgets: List[SelectableDriveCard] = []
        self.selected_drive_letter: Optional[str] = None
        self.dev_mode = DEV_ALLOW_LOW_SPACE
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 24)
        main_layout.setSpacing(18)

        # عنوان و زیرعنوان
        title_lbl = QLabel("انتخاب درایو نصب سپهریار", self)
        title_lbl.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 24px; font-weight: bold;")
        main_layout.addWidget(title_lbl)

        sub_lbl = QLabel(
            "لطفاً درایو مورد نظر برای استقرار فایل‌های سپهریار و پایگاه داده را انتخاب نمایید (نصب روی درایو C مجاز نیست).",
            self
        )
        sub_lbl.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 14px;")
        main_layout.addWidget(sub_lbl)

        # ناحیه اسکرول کارت‌های درایو
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 8, 0, 8)
        self.cards_layout.setSpacing(12)

        scroll.setWidget(self.cards_container)
        main_layout.addWidget(scroll, stretch=1)

        # کادر پیش‌نمایش مسیر ساختار SEPEHRYAR
        preview_frame = QFrame(self)
        preview_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #12141A;
                border: 1px dashed {THEME_COLORS['border_medium']};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setSpacing(4)

        self.path_preview_lbl = QLabel("مسیر نهایی نصب: در انتظار انتخاب درایو...", preview_frame)
        self.path_preview_lbl.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 13px; font-weight: bold;")
        preview_layout.addWidget(self.path_preview_lbl)

        folders_preview = QLabel(
            "ساختار ایجاد شونده: SEPEHRYAR\\ (شامل SEPEHRYAR.Setup | SEPEHRYAR.Data | SEPEHRYAR.Backup | SEPEHRYAR.Update)",
            preview_frame
        )
        folders_preview.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 11px;")
        preview_layout.addWidget(folders_preview)

        main_layout.addWidget(preview_frame)

        # کلید تست حالت کمبود فضا (جهت سیستم‌های توسعه و تستی)
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(12)

        self.chk_dev_mode = QCheckBox("صرف‌نظر از الزام ۱۰۰ گیگابایت فضای خالی (مخصوص ماشین تست فعلی)", self)
        self.chk_dev_mode.setChecked(self.dev_mode)
        self.chk_dev_mode.setStyleSheet(f"color: {THEME_COLORS['text_muted']}; font-size: 12px;")
        self.chk_dev_mode.toggled.connect(self._on_dev_mode_toggled)
        bottom_bar.addWidget(self.chk_dev_mode)

        bottom_bar.addStretch()

        btn_rescan = QPushButton("اسکن مجدد درایوها", self)
        btn_rescan.setProperty("class", "GoldSecondary")
        btn_rescan.setIcon(IconFactory.get_icon("refresh", size=16))
        btn_rescan.clicked.connect(self.scan)
        bottom_bar.addWidget(btn_rescan)

        main_layout.addLayout(bottom_bar)

    def _on_dev_mode_toggled(self, checked: bool):
        self.dev_mode = checked
        self.scan()

    def scan(self):
        """
        اسکن درایوها و نمایش کارت‌های درایو
        """
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.card_widgets.clear()
        self.drives = scan_drives(dev_allow_low_space=self.dev_mode)

        eligible_drive_found = False
        first_eligible = None

        for d in self.drives:
            card = SelectableDriveCard(d, is_selected=False, parent=self.cards_container)
            card.clicked.connect(self._on_card_clicked)
            self.cards_layout.addWidget(card)
            self.card_widgets.append(card)

            if d.is_eligible and not first_eligible:
                first_eligible = d.letter
                eligible_drive_found = True

        self.cards_layout.addStretch()

        # انتخاب خودکار اولین درایو مناسب
        if first_eligible:
            self._select_drive(first_eligible)
        else:
            self.selected_drive_letter = None
            self.path_preview_lbl.setText("مسیر نهایی نصب: هیچ درایو واجد شرایطی یافت نشد.")
            self.drive_selected.emit("", False)

    def _on_card_clicked(self, letter: str):
        self._select_drive(letter)

    def _select_drive(self, letter: str):
        self.selected_drive_letter = letter
        for card in self.card_widgets:
            card.set_selected(card.drive_info.letter == letter)

        preview_text = f"مسیر نهایی نصب: <b style='color:#FFFFFF'>{letter}\\SEPEHRYAR\\</b>"
        self.path_preview_lbl.setText(preview_text)
        self.drive_selected.emit(letter, True)

    def get_selected_drive(self) -> Optional[str]:
        return self.selected_drive_letter
