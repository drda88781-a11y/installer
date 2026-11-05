# ui/pages/page_product_select.py
"""
صفحه ۳: انتخاب محصولات و پکیج‌های نرم‌افزار حسابداری سپهریار
Page 3: SEPEHRYAR Software Products Multi-Selection
"""

from typing import List, Set
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from config.settings import THEME_COLORS, requires_sql
from packages.product_catalog import get_available_products, ProductItem
from ui.components.gold_card import SelectableProductCard


class ProductSelectPage(QWidget):
    """
    صفحه انتخاب چندگانه محصولات سپهریار با کارت‌های لوکس
    """
    selection_changed = Signal(list, bool)  # selected_ids, is_valid

    def __init__(self, parent=None):
        super().__init__(parent)
        self.products: List[ProductItem] = []
        self.card_widgets: List[SelectableProductCard] = []
        self.selected_ids: Set[str] = set()
        self.install_mode: str = "server"
        self.sql_version: str = "2019"
        self.sql_instance_name: str = ""
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 24)
        main_layout.setSpacing(14)

        # سربرگ صفحه
        self.title_lbl = QLabel("انتخاب محصول سپهریار", self)
        self.title_lbl.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 24px; font-weight: bold;")
        main_layout.addWidget(self.title_lbl)

        self.sub_lbl = QLabel(
            "محصولات مورد نظر خود را جهت نصب انتخاب نمایید. می‌توانید یک یا چند نرم‌افزار را به صورت همزمان نصب کنید.",
            self
        )
        self.sub_lbl.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 14px;")
        main_layout.addWidget(self.sub_lbl)

        # ناحیه اسکرول کارت‌های محصولات
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

        # نوار وضعیت نیاز به SQL Server بر اساس انتخاب محصولات
        self.sql_notice_lbl = QLabel(self)
        main_layout.addWidget(self.sql_notice_lbl)

        # نوار پایین: وضعیت انتخاب و دکمه‌های انتخاب همه / عدم انتخاب
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(12)

        self.selection_summary_lbl = QLabel("۰ محصول انتخاب شده است", self)
        self.selection_summary_lbl.setStyleSheet(f"color: {THEME_COLORS['text_primary']}; font-size: 14px; font-weight: bold;")
        bottom_bar.addWidget(self.selection_summary_lbl, stretch=1)

        btn_select_all = QPushButton("انتخاب همه", self)
        btn_select_all.setProperty("class", "GoldSecondary")
        btn_select_all.clicked.connect(self.select_all)
        bottom_bar.addWidget(btn_select_all)

        btn_clear_all = QPushButton("لغو انتخاب‌ها", self)
        btn_clear_all.setProperty("class", "GoldSecondary")
        btn_clear_all.clicked.connect(self.clear_all)
        bottom_bar.addWidget(btn_clear_all)

        main_layout.addLayout(bottom_bar)

    def set_sql_version(self, version: str):
        """تنظیم نسخه انتخابی SQL Server"""
        self.sql_version = str(version)

    def get_selected_sql_version(self) -> str:
        """بازگرداندن نسخه انتخابی SQL Server"""
        return self.sql_version

    def set_sql_instance_name(self, inst_name: str, force_new: bool = False):
        """تنظیم نام اینستنس انتخابی SQL Server"""
        self.sql_instance_name = str(inst_name).strip()
        self.force_new_sql_instance = force_new

    def get_selected_sql_instance_name(self) -> str:
        """بازگرداندن نام اینستنس انتخابی SQL Server"""
        return getattr(self, "sql_instance_name", "")

    def is_force_new_sql_instance(self) -> bool:
        return getattr(self, "force_new_sql_instance", False)

    def set_install_mode(self, mode: str):
        """تنظیم حالت نصب قبل از بارگذاری محصولات"""
        self.install_mode = mode

    def load_products(self):
        """
        بارگذاری مشخصات محصولات از کاتالوگ و نمایش کارت‌ها بر اساس حالت سرور یا کلاینت
        """
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.card_widgets.clear()
        self.products = get_available_products()
        self.selected_ids.clear()

        is_client = (self.install_mode == "client")
        if is_client:
            self.title_lbl.setText("انتخاب محصول سپهریار (حالت کلاینت)")
            self.sub_lbl.setText(
                "در حالت کلاینت، نرم‌افزار مکانیزه فروش سپهریار (Client) همراه با کلیه فایل‌های Setup، فونت‌ها و گزارش‌سازها بدون نیاز به پایگاه داده SQL Server نصب می‌گردد."
            )
        else:
            self.title_lbl.setText("انتخاب محصول سپهریار (حالت سرور)")
            self.sub_lbl.setText(
                "محصولات مورد نظر خود را جهت نصب روی سرور انتخاب نمایید. در صورت انتخاب حسابداری یا صنعتی، پایگاه داده SQL Server نصب خواهد شد."
            )

        for p in self.products:
            if is_client:
                # در حالت کلاینت، پیش‌فرض سیستم فروش (Client) انتخاب می‌شود
                default_checked = (p.id == "SEPEHRYAR.Client")
            else:
                # در حالت سرور، بدون انتخاب پیش‌فرض تا کاربر محصول مد نظر خود را آگاهانه انتخاب کند
                default_checked = False

            if default_checked:
                self.selected_ids.add(p.id)

            card = SelectableProductCard(p, is_checked=default_checked, parent=self.cards_container)
            card.toggled.connect(self._on_card_toggled)
            self.cards_layout.addWidget(card)
            self.card_widgets.append(card)

        self.cards_layout.addStretch()
        self._update_summary()

    def _on_card_toggled(self, product_id: str, checked: bool):
        if checked:
            self.selected_ids.add(product_id)
        else:
            self.selected_ids.discard(product_id)
        self._update_summary()

    def select_all(self):
        for card in self.card_widgets:
            card.checkbox.setChecked(True)

    def clear_all(self):
        for card in self.card_widgets:
            card.checkbox.setChecked(False)

    def _update_summary(self):
        count = len(self.selected_ids)
        is_valid = (count > 0)
        if is_valid:
            self.selection_summary_lbl.setText(f"✓ تعداد {count} محصول برای نصب انتخاب شده است.")
            self.selection_summary_lbl.setStyleSheet(f"color: {THEME_COLORS['success']}; font-size: 14px; font-weight: bold;")

            # بررسی نیاز به پایگاه داده SQL Server
            needs_sql = requires_sql(self.selected_ids, self.install_mode)
            if needs_sql:
                self.sql_notice_lbl.setText(f"⚡ شامل نرم‌افزار حسابداری یا صنعتی: نیازمند پایگاه داده Microsoft SQL Server {self.sql_version} (پایگاه داده نصب خواهد شد)")
                self.sql_notice_lbl.setStyleSheet(f"""
                    QLabel {{
                        background-color: rgba(216, 168, 78, 0.15);
                        color: #FCD34D;
                        border: 1px solid rgba(216, 168, 78, 0.5);
                        border-radius: 8px;
                        padding: 8px 14px;
                        font-size: 13px;
                        font-weight: bold;
                    }}
                """)
            else:
                self.sql_notice_lbl.setText("🛡️ فاقد حسابداری و صنعتی (فروش / رستوران / مودیان): نیازی به SQL Server ندارند و به هیچ عنوان SQL Server نصب نمی‌شود.")
                self.sql_notice_lbl.setStyleSheet("""
                    QLabel {{
                        background-color: rgba(34, 197, 94, 0.15);
                        color: #4ADE80;
                        border: 1px solid rgba(34, 197, 94, 0.5);
                        border-radius: 8px;
                        padding: 8px 14px;
                        font-size: 13px;
                        font-weight: bold;
                    }}
                """)
            self.sql_notice_lbl.setVisible(True)
        else:
            self.selection_summary_lbl.setText("✕ لطفاً حداقل یک محصول را جهت نصب انتخاب نمایید.")
            self.selection_summary_lbl.setStyleSheet(f"color: {THEME_COLORS['error']}; font-size: 14px; font-weight: bold;")
            self.sql_notice_lbl.setVisible(False)

        self.selection_changed.emit(list(self.selected_ids), is_valid)

    def get_selected_products(self) -> List[str]:
        return list(self.selected_ids)
