# ui/components/status_badge.py
"""
نشان (Badge) وضعیت مدرن و مینیمال برای نمایش تأیید، خطا یا هشدار
Minimalist status badge component for pass, fail, warning, and info
"""

from enum import Enum
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel
from typing import Optional
from config.settings import THEME_COLORS
from utils.icon_factory import IconFactory


class BadgeType(Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class StatusBadge(QFrame):
    """
    بج وضعیت با استایل شیک و حاشیه رنگی متناسب
    """
    def __init__(self, text: str, badge_type: BadgeType = BadgeType.SUCCESS, parent=None):
        super().__init__(parent)
        self.badge_type = badge_type
        self._init_ui(text)

    def _init_ui(self, text: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        c = THEME_COLORS
        if self.badge_type == BadgeType.SUCCESS:
            color = c["success"]
            bg = c["success_bg"]
            icon_name = "check"
        elif self.badge_type == BadgeType.ERROR:
            color = c["error"]
            bg = c["error_bg"]
            icon_name = "cross"
        elif self.badge_type == BadgeType.WARNING:
            color = c["warning"]
            bg = c["warning_bg"]
            icon_name = "warning"
        else:
            color = c["gold_primary"]
            bg = c["gold_glow"]
            icon_name = "shield"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid {color};
                border-radius: 6px;
            }}
        """)

        # آیکون
        icon_label = QLabel(self)
        icon_pix = IconFactory.get_icon(icon_name, size=14, color_override=color).pixmap(14, 14)
        icon_label.setPixmap(icon_pix)
        icon_label.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(icon_label)

        # متن
        self.text_label = QLabel(text, self)
        self.text_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        layout.addWidget(self.text_label)

    def set_text(self, text: str, badge_type: Optional[BadgeType] = None):
        if badge_type:
            self.badge_type = badge_type
        self.text_label.setText(text)
