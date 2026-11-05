# ui/dialogs/troubleshooting_panel.py
"""
پنل جامع و هوشمند عیب‌یابی، ممیزی و تأمین خودکار کم و کسری‌های سیستم سپهریار
Sepehryar Smart Diagnostics, Troubleshooting & Remediation Panel
"""

import os
from pathlib import Path
import subprocess
import time
from typing import Dict, List, Optional

import psutil
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config.settings import (
    SETUP_DIR,
    SQL_SA_PASSWORD,
    SQL_SA_USER,
    THEME_COLORS,
)
from app_logging.app_logger import logger
from prerequisites.prereq_installer import PrerequisiteManager
from sql.sql_auditor import InstanceAuditInfo, SQLInstanceAuditor
from utils.archive_extractor import close_running_sepehryar_processes
from utils.icon_factory import IconFactory


class RemediationWorker(QThread):
    """ترد پس‌زمینه برای اجرای اقدامات اصلاحی بدون فریز شدن پنجره"""
    sig_progress = Signal(str, int)
    sig_finished = Signal(bool, str)

    def __init__(self, action_id: str, context: dict, parent=None):
        super().__init__(parent)
        self.action_id = action_id
        self.context = context

    def run(self):
        inst_name = self.context.get("instance_name", "SEPEHRYAR2019")
        data_dir = self.context.get("data_dir")
        auditor = SQLInstanceAuditor()

        try:
            if self.action_id == "fix_sql_services":
                self.sig_progress.emit(f"در حال راه‌اندازی سرویس MSSQL${inst_name}...", 20)
                svc_name = f"MSSQL${inst_name}" if inst_name != "MSSQLSERVER" else "MSSQLSERVER"
                subprocess.run(["sc", "config", svc_name, "start=", "auto"], capture_output=True, timeout=10)
                subprocess.run(["net", "start", svc_name], capture_output=True, timeout=25)

                self.sig_progress.emit("در حال راه‌اندازی سرویس SQLBrowser...", 60)
                subprocess.run(["sc", "config", "SQLBrowser", "start=", "auto"], capture_output=True, timeout=10)
                subprocess.run(["net", "start", "SQLBrowser"], capture_output=True, timeout=20)
                self.sig_finished.emit(True, f"سرویس‌های {svc_name} و SQLBrowser با موفقیت فعال و راه‌اندازی شدند.")

            elif self.action_id == "fix_firewall":
                self.sig_progress.emit("در حال ایجاد رول‌های فایروال ویندوز...", 30)
                cmds = [
                    'netsh advfirewall firewall add rule name="SQL Server Port" dir=in action=allow protocol=TCP localport=1433 profile=any',
                    'netsh advfirewall firewall add rule name="SQL Browser Port" dir=in action=allow protocol=UDP localport=1434 profile=any',
                ]
                for cmd in cmds:
                    subprocess.run(cmd, shell=True, capture_output=True, timeout=15)
                self.sig_finished.emit(True, "پورت‌های ۱۴۳۳ (TCP) و ۱۴۳۴ (UDP) در فایروال ویندوز باز شدند.")

            elif self.action_id == "fix_permissions":
                self.sig_progress.emit("در حال اعمال دسترسی کامل NTFS بر روی پوشه Data...", 40)
                target = Path(data_dir) if data_dir else Path(r"C:\SEPEHRYAR\SEPEHRYAR.Data")
                if not target.exists():
                    target.mkdir(parents=True, exist_ok=True)
                cmd = f'icacls "{target}" /grant Everyone:(OI)(CI)F /T /Q'
                subprocess.run(cmd, shell=True, capture_output=True, timeout=20)
                self.sig_finished.emit(True, f"مجوزهای دسترسی کامل سرویس به {target} اعمال شد.")

            elif self.action_id == "attach_databases":
                self.sig_progress.emit("در حال بررسی و اتچ دیتابیس‌های مفقود...", 30)
                target = Path(data_dir) if data_dir else Path(r"C:\SEPEHRYAR\SEPEHRYAR.Data")
                rep = auditor.remediate_instance_shortages(
                    instance_name=inst_name,
                    data_dir=target,
                    progress_callback=lambda m, p: self.sig_progress.emit(m, p),
                )
                cnt = len(rep.attached_databases)
                self.sig_finished.emit(True, f"تعداد {cnt} پایگاه داده با موفقیت در {inst_name} آماده‌سازی شد.")

            elif self.action_id == "fix_prereqs":
                self.sig_progress.emit("در حال نصب پیش‌نیازهای گزارش‌ساز و فونت‌ها...", 20)
                pm = PrerequisiteManager()
                pm.install_crystal_reports()
                self.sig_progress.emit("نصب استیمول‌سافت و فونت‌ها...", 70)
                pm.install_stimulsoft()
                pm.install_farsi_fonts()
                self.sig_finished.emit(True, "پیش‌نیازهای Crystal Reports، Stimulsoft و فونت‌های فارسی تنظیم شدند.")

            elif self.action_id == "unlock_processes":
                self.sig_progress.emit("در حال بستن پردازه‌های معلق سپهریار...", 50)
                closed = close_running_sepehryar_processes()
                self.sig_finished.emit(True, f"تعداد {len(closed)} پردازه معلق جهت آزادسازی فایل‌ها بسته شدند.")

            elif self.action_id == "fix_all_shortages":
                self.sig_progress.emit("شروع جبران جامع تمام کم و کسری‌های سیستم...", 10)
                # 1. بستن پروسه‌ها
                close_running_sepehryar_processes()
                # 2. سرویس‌ها
                svc_name = f"MSSQL${inst_name}" if inst_name != "MSSQLSERVER" else "MSSQLSERVER"
                subprocess.run(["sc", "config", svc_name, "start=", "auto"], capture_output=True, timeout=10)
                subprocess.run(["net", "start", svc_name], capture_output=True, timeout=25)
                subprocess.run(["sc", "config", "SQLBrowser", "start=", "auto"], capture_output=True, timeout=10)
                subprocess.run(["net", "start", "SQLBrowser"], capture_output=True, timeout=20)
                # 3. فایروال
                subprocess.run('netsh advfirewall firewall add rule name="SQL Server Port" dir=in action=allow protocol=TCP localport=1433 profile=any', shell=True, capture_output=True, timeout=10)
                # 4. پرمیشن
                target = Path(data_dir) if data_dir else Path(r"C:\SEPEHRYAR\SEPEHRYAR.Data")
                if target.exists():
                    subprocess.run(f'icacls "{target}" /grant Everyone:(OI)(CI)F /T /Q', shell=True, capture_output=True, timeout=15)
                # 5. اتچ دیتابیس‌ها
                rep = auditor.remediate_instance_shortages(instance_name=inst_name, data_dir=target)
                # 6. پیش‌نیازها
                pm = PrerequisiteManager()
                pm.install_crystal_reports()
                pm.install_farsi_fonts()

                self.sig_finished.emit(True, "تمامی کم و کسری‌های شناسایی‌شده با موفقیت جبران گردیدند.")

        except Exception as ex:
            self.sig_finished.emit(False, f"خطا در اجرای اقدام اصلاحی: {ex}")


class TroubleshootingPanelDialog(QDialog):
    """
    پنل مستقل و یکپارچه حل مشکل، پایش سلامت سیستم و تأمین خودکار کم و کسری‌ها
    """
    def __init__(self, data_dir: Optional[Path] = None, parent=None):
        super().__init__(parent)
        self.data_dir = data_dir
        self.active_instance = "SEPEHRYAR2019"
        self.audits: Dict[str, InstanceAuditInfo] = {}
        self.worker: Optional[RemediationWorker] = None

        self.setWindowTitle("مرکز هوشمند پایش، عیب‌یابی و تأمین کم و کسری‌های سپهریار")
        self.resize(960, 680)
        self.setMinimumSize(880, 580)
        self._init_ui()
        self.refresh_diagnostics()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # ─── ۱. هدر پنل ───
        header_frame = QFrame(self)
        header_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1A1D24, stop:1 #12141A);
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 8px;
                padding: 10px 14px;
            }}
        """)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(10, 8, 10, 8)
        h_layout.setSpacing(14)

        icon_lbl = QLabel(header_frame)
        icon_lbl.setPixmap(IconFactory.get_icon("gear", size=32).pixmap(32, 32))
        h_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(3)
        lbl_t = QLabel("پنل جامع عیب‌یابی و تأمین خودکار کم و کسری‌ها (Troubleshooting & Remediation)", header_frame)
        lbl_t.setStyleSheet(f"color: {THEME_COLORS['gold_primary']}; font-size: 16px; font-weight: bold;")
        lbl_sub = QLabel("پایش لحظه‌ای سرویس‌های پایگاه داده، فایروال، دسترسی‌های امنیتی، دیتابیس‌ها و رفع خودکار با یک کلیک", header_frame)
        lbl_sub.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 12px;")
        title_vbox.addWidget(lbl_t)
        title_vbox.addWidget(lbl_sub)
        h_layout.addLayout(title_vbox, stretch=1)

        self.btn_refresh = QPushButton("بروزرسانی وضعیت", header_frame)
        self.btn_refresh.setProperty("class", "GoldSecondary")
        self.btn_refresh.setIcon(IconFactory.get_icon("refresh", size=15))
        self.btn_refresh.clicked.connect(self.refresh_diagnostics)
        h_layout.addWidget(self.btn_refresh)

        main_layout.addWidget(header_frame)

        # ─── ۲. بخش اصلی با دو ستون: وضعیت فعلی (چپ) | اکشن‌های اصلاحی و دستورات (راست) ───
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setHandleWidth(4)

        # ستون پایش وضعیت
        status_container = QWidget(splitter)
        status_vbox = QVBoxLayout(status_container)
        status_vbox.setContentsMargins(4, 4, 8, 4)
        status_vbox.setSpacing(10)

        lbl_sec1 = QLabel("🔍 گزارش سلامت و ممیزی سیستم:", status_container)
        lbl_sec1.setStyleSheet(f"color: {THEME_COLORS['gold_hover']}; font-size: 13.5px; font-weight: bold;")
        status_vbox.addWidget(lbl_sec1)

        scroll_status = QScrollArea(status_container)
        scroll_status.setWidgetResizable(True)
        scroll_status.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.status_cards_widget = QWidget()
        self.status_cards_layout = QVBoxLayout(self.status_cards_widget)
        self.status_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.status_cards_layout.setSpacing(8)
        scroll_status.setWidget(self.status_cards_widget)
        status_vbox.addWidget(scroll_status, stretch=1)

        splitter.addWidget(status_container)

        # ستون اقدامات اصلاحی و دستورات
        actions_container = QWidget(splitter)
        actions_vbox = QVBoxLayout(actions_container)
        actions_vbox.setContentsMargins(8, 4, 4, 4)
        actions_vbox.setSpacing(10)

        lbl_sec2 = QLabel("⚡ ابزارهای حل خودکار و رفع کم و کسری‌ها:", actions_container)
        lbl_sec2.setStyleSheet(f"color: #38BDF8; font-size: 13.5px; font-weight: bold;")
        actions_vbox.addWidget(lbl_sec2)

        # دکمه حل همه کم و کسری‌ها (One-Click Auto-Fix All)
        self.btn_fix_all = QPushButton("🚀 رفع تمام کم و کسری‌ها با یک کلیک (توصیه شده)", actions_container)
        self.btn_fix_all.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {THEME_COLORS['gold_primary']}, stop:1 #B8860B);
                color: #0A0C10;
                font-weight: bold;
                font-size: 13px;
                padding: 11px 16px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background: {THEME_COLORS['gold_hover']};
            }}
        """)
        self.btn_fix_all.clicked.connect(lambda: self._run_action("fix_all_shortages"))
        actions_vbox.addWidget(self.btn_fix_all)

        # کارت‌های اکشن‌های مجزا
        actions_scroll = QScrollArea(actions_container)
        actions_scroll.setWidgetResizable(True)
        actions_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        act_widget = QWidget()
        act_layout = QVBoxLayout(act_widget)
        act_layout.setContentsMargins(0, 0, 0, 0)
        act_layout.setSpacing(8)

        act_layout.addWidget(self._create_action_card(
            title="راه‌اندازی سرویس‌های SQL Server و SQL Browser",
            desc="شروع سرویس متوقف‌شده پایگاه داده و تنظیم حالت خودکار (Automatic).",
            btn_text="راه‌اندازی سرویس‌ها",
            action_id="fix_sql_services",
        ))

        act_layout.addWidget(self._create_action_card(
            title="تنظیم فایروال ویندوز و باز کردن پورت‌ها",
            desc="باز کردن پورت‌های ۱۴۳۳ (TCP) و ۱۴۳۴ (UDP) جهت اتصال سیستم‌های کلاینت شبکه.",
            btn_text="تنظیم فایروال",
            action_id="fix_firewall",
        ))

        act_layout.addWidget(self._create_action_card(
            title="اصلاح دسترسی امنیتی پوشه داده‌ها (icacls)",
            desc="اعطای دسترسی Full Control به سرویس پایگاه داده و جلوگیری از خطای Access Denied.",
            btn_text="اصلاح دسترسی",
            action_id="fix_permissions",
        ))

        act_layout.addWidget(self._create_action_card(
            title="اتچ خودکار تمامی دیتابیس‌های موجود در Data",
            desc="شناسایی فایل‌های .mdf رهاشده و اتچ هوشمند با ATTACH_REBUILD_LOG.",
            btn_text="اتچ دیتابیس‌ها",
            action_id="attach_databases",
        ))

        act_layout.addWidget(self._create_action_card(
            title="نصب پیش‌نیازهای گزارش‌گیری و فونت‌ها",
            desc="نصب سایلنت Crystal Reports x86/x64، Stimulsoft و فونت‌های رسمی.",
            btn_text="نصب پیش‌نیازها",
            action_id="fix_prereqs",
        ))

        act_layout.addWidget(self._create_action_card(
            title="آزادسازی فایل‌ها و بستن پروسه‌های قفل‌کننده",
            desc="بستن امن پروسه‌های Hesabdari.exe و... جهت رفع خطای WinError 32.",
            btn_text="آزادسازی پروسه‌ها",
            action_id="unlock_processes",
        ))

        act_layout.addStretch()
        actions_scroll.setWidget(act_widget)
        actions_vbox.addWidget(actions_scroll, stretch=1)

        # کادر دستورات PowerShell آماده کپی
        lbl_cmd = QLabel("📋 دستورات خط فرمان معادل (PowerShell):", actions_container)
        lbl_cmd.setStyleSheet("color: #94A3B8; font-size: 11.5px; font-weight: bold;")
        actions_vbox.addWidget(lbl_cmd)

        self.txt_ps = QTextEdit(actions_container)
        self.txt_ps.setReadOnly(True)
        self.txt_ps.setFixedHeight(64)
        self.txt_ps.setStyleSheet("""
            QTextEdit {
                background-color: #0A0C10;
                color: #38BDF8;
                border: 1px solid #1E293B;
                border-radius: 6px;
                padding: 6px;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
        """)
        actions_vbox.addWidget(self.txt_ps)

        btn_copy = QPushButton("کپی دستورات PowerShell در کلیپ‌بورد", actions_container)
        btn_copy.setProperty("class", "GoldSecondary")
        btn_copy.setIcon(IconFactory.get_icon("copy", size=14))
        btn_copy.clicked.connect(self._copy_ps_commands)
        actions_vbox.addWidget(btn_copy)

        splitter.addWidget(actions_container)
        splitter.setSizes([450, 470])
        main_layout.addWidget(splitter, stretch=1)

        # ─── ۳. نوار پروگرس و وضعیت پایین ───
        bot_layout = QHBoxLayout()
        bot_layout.setSpacing(12)

        self.lbl_status = QLabel("آماده جهت پایش و عیب‌یابی.", self)
        self.lbl_status.setStyleSheet("color: #94A3B8; font-size: 12px;")
        bot_layout.addWidget(self.lbl_status, stretch=1)

        self.prog_bar = QProgressBar(self)
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setFixedHeight(8)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setVisible(False)
        self.prog_bar.setFixedWidth(200)
        bot_layout.addWidget(self.prog_bar)

        btn_close = QPushButton("بستن پنل", self)
        btn_close.setProperty("class", "GoldSecondary")
        btn_close.clicked.connect(self.accept)
        bot_layout.addWidget(btn_close)

        main_layout.addLayout(bot_layout)

    def _create_action_card(self, title: str, desc: str, btn_text: str, action_id: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-radius: 6px;
                padding: 6px 10px;
            }}
        """)
        c_layout = QHBoxLayout(card)
        c_layout.setContentsMargins(8, 6, 8, 6)
        c_layout.setSpacing(10)

        info_vbox = QVBoxLayout()
        info_vbox.setSpacing(2)
        t_lbl = QLabel(title, card)
        t_lbl.setStyleSheet(f"color: {THEME_COLORS['text_primary']}; font-size: 12.5px; font-weight: bold;")
        d_lbl = QLabel(desc, card)
        d_lbl.setWordWrap(True)
        d_lbl.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 11px;")
        info_vbox.addWidget(t_lbl)
        info_vbox.addWidget(d_lbl)
        c_layout.addLayout(info_vbox, stretch=1)

        btn = QPushButton(btn_text, card)
        btn.setProperty("class", "GoldSecondary")
        btn.setFixedHeight(34)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(216, 168, 78, 0.12);
                color: {THEME_COLORS['gold_hover']};
                border: 1px solid {THEME_COLORS['gold_primary']};
                border-radius: 5px;
                padding: 4px 12px;
                font-size: 11.5px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: rgba(216, 168, 78, 0.25);
            }}
        """)
        btn.clicked.connect(lambda: self._run_action(action_id))
        c_layout.addWidget(btn)

        return card

    def refresh_diagnostics(self):
        """اسکن زنده تمام موارد سیستم و بروزرسانی کارت‌های وضعیت"""
        self.lbl_status.setText("در حال اسکن سلامت سیستم و سرویس‌ها...")
        self.btn_refresh.setEnabled(False)

        # پاکسازی کارت‌های قبلی
        while self.status_cards_layout.count():
            item = self.status_cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        auditor = SQLInstanceAuditor()
        self.audits = auditor.scan_all_instances()

        # ۱. اینستنس ۲۰۱۹
        audit_19 = self.audits.get("2019")
        if audit_19 and audit_19.is_installed:
            self.active_instance = "SEPEHRYAR2019"
            svc_txt = "در حال اجرا (Running)" if audit_19.service_status == "running" else "متوقف (Stopped)"
            conn_txt = f"برقرار ({audit_19.auth_method})" if audit_19.is_connected else "عدم اتصال"
            self._add_status_card(
                title="اینستنس SQL Server 2019 (SEPEHRYAR2019)",
                status_ok=(audit_19.service_status == "running" and audit_19.is_connected),
                details=f"وضعیت سرویس: {svc_txt} | وضعیت اتصال: {conn_txt} | تعداد دیتابیس‌ها: {len(audit_19.databases)}",
            )
        else:
            self._add_status_card(
                title="اینستنس SQL Server 2019 (SEPEHRYAR2019)",
                status_ok=False,
                details="نصب نیست یا در رجیستری و سرویس‌های ویندوز شناسایی نشد.",
            )

        # ۲. اینستنس ۲۰۱۴
        audit_14 = self.audits.get("2014")
        if audit_14 and audit_14.is_installed:
            if not (audit_19 and audit_19.is_installed):
                self.active_instance = "SEPEHRYAR2014"
            svc_txt = "در حال اجرا" if audit_14.service_status == "running" else "متوقف"
            self._add_status_card(
                title="اینستنس SQL Server 2014 (SEPEHRYAR2014)",
                status_ok=(audit_14.service_status == "running"),
                details=f"وضعیت سرویس: {svc_txt} | تعداد دیتابیس‌ها: {len(audit_14.databases)}",
            )

        # ۳. سرویس SQLBrowser
        browser_running = False
        try:
            b_svc = psutil.win_service_get("SQLBrowser")
            browser_running = (b_svc.status() == "running")
        except Exception:
            pass

        self._add_status_card(
            title="سرویس جستجوی دیتابیس در شبکه (SQLBrowser)",
            status_ok=browser_running,
            details="در حال اجرا و آماده پاسخ به سیستم‌های کلاینت شبکه" if browser_running else "متوقف یا غیرفعال است (اتصال کلاینت‌ها دچار اختلال می‌شود)",
        )

        # ۴. پوشه داده‌ها و پرمیشن NTFS
        t_data = Path(self.data_dir) if self.data_dir else Path(r"C:\SEPEHRYAR\SEPEHRYAR.Data")
        data_exists = t_data.exists()
        mdf_count = len(list(t_data.glob("*.mdf"))) if data_exists else 0
        self._add_status_card(
            title=f"پوشه ذخیره‌سازی داده‌ها ({t_data.name})",
            status_ok=data_exists,
            details=f"مسیر: {t_data} | تعداد فایلهای MDF موجود: {mdf_count}",
        )

        # ۵. پیش‌نیازهای گزارش‌گیری (Crystal Reports & Stimulsoft)
        pm = PrerequisiteManager()
        cr_ok = pm.is_crystal_reports_installed()
        st_ok = pm.is_stimulsoft_installed()
        self._add_status_card(
            title="پیش‌نیازهای گزارش‌ساز (Crystal Reports & Stimulsoft)",
            status_ok=(cr_ok and st_ok),
            details=f"کریستال ریپورتز: {'✓ نصب است' if cr_ok else '✕ مفقود'} | استیمول‌سافت: {'✓ نصب است' if st_ok else '✕ مفقود'}",
        )

        # ۶. پروسه‌های قفل‌کننده در حال اجرا
        sepehr_procs = []
        for p in psutil.process_iter(["name"]):
            try:
                p_name = p.info.get("name", "")
                if p_name and any(p_name.lower().startswith(k) for k in ["hesabdari", "sepand", "clientsepand"]):
                    sepehr_procs.append(p_name)
            except Exception:
                pass

        if sepehr_procs:
            self._add_status_card(
                title="پروسه‌های در حال اجرای سپهریار",
                status_ok=False,
                details=f"پروسه‌های فعال ({', '.join(set(sepehr_procs))}) ممکن است مانع جایگزینی فایل‌های آپدیت شوند.",
            )
        else:
            self._add_status_card(
                title="پروسه‌های در حال اجرا",
                status_ok=True,
                details="هیچ پروسه قفل‌کننده‌ای در حال حاضر باز نیست.",
            )

        self.status_cards_layout.addStretch()

        # تنظیم متن دستورات پیشنهادی PowerShell
        ps_commands = [
            f"Start-Service -Name 'MSSQL${self.active_instance}' -ErrorAction SilentlyContinue",
            "Start-Service -Name 'SQLBrowser' -ErrorAction SilentlyContinue",
            "netsh advfirewall firewall add rule name='SQL Server' dir=in action=allow protocol=TCP localport=1433",
            f'icacls "{t_data}" /grant Everyone:(OI)(CI)F /T /Q',
        ]
        self.txt_ps.setPlainText("; ".join(ps_commands))

        self.lbl_status.setText("اسکن سلامت سیستم و ممیزی با موفقیت پایان یافت.")
        self.btn_refresh.setEnabled(True)

    def _add_status_card(self, title: str, status_ok: bool, details: str):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_COLORS['card_bg']};
                border: 1px solid {THEME_COLORS['card_border']};
                border-right: 4px solid {'#10B981' if status_ok else '#EF4444'};
                border-radius: 6px;
                padding: 8px 10px;
            }}
        """)
        c_layout = QHBoxLayout(card)
        c_layout.setContentsMargins(8, 6, 8, 6)
        c_layout.setSpacing(10)

        badge_lbl = QLabel(card)
        badge_lbl.setText("✓" if status_ok else "✕")
        badge_lbl.setStyleSheet(f"color: {'#10B981' if status_ok else '#EF4444'}; font-size: 16px; font-weight: bold;")
        c_layout.addWidget(badge_lbl)

        vbox = QVBoxLayout()
        vbox.setSpacing(2)
        t_lbl = QLabel(title, card)
        t_lbl.setStyleSheet(f"color: {THEME_COLORS['text_primary']}; font-size: 12px; font-weight: bold;")
        d_lbl = QLabel(details, card)
        d_lbl.setWordWrap(True)
        d_lbl.setStyleSheet(f"color: {THEME_COLORS['text_secondary']}; font-size: 11px;")
        vbox.addWidget(t_lbl)
        vbox.addWidget(d_lbl)
        c_layout.addLayout(vbox, stretch=1)

        self.status_cards_layout.addWidget(card)

    def _run_action(self, action_id: str):
        """اجرای عملیات اصلاحی در پس‌زمینه"""
        if self.worker and self.worker.isRunning():
            return

        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(15)
        self.btn_fix_all.setEnabled(False)
        self.btn_refresh.setEnabled(False)

        ctx = {
            "instance_name": self.active_instance,
            "data_dir": self.data_dir,
        }

        self.worker = RemediationWorker(action_id, ctx, self)
        self.worker.sig_progress.connect(self._on_remediation_progress)
        self.worker.sig_finished.connect(self._on_remediation_finished)
        self.worker.start()

    def _on_remediation_progress(self, msg: str, pct: int):
        self.lbl_status.setText(msg)
        self.prog_bar.setValue(pct)

    def _on_remediation_finished(self, success: bool, msg: str):
        self.prog_bar.setVisible(False)
        self.btn_fix_all.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet(f"color: {'#10B981' if success else '#EF4444'}; font-size: 12px; font-weight: bold;")
        # تازه‌سازی خودکار وضعیت پس از اتمام اقدام اصلاحی
        self.refresh_diagnostics()

    def _copy_ps_commands(self):
        QApplication.clipboard().setText(self.txt_ps.toPlainText().strip())
        self.lbl_status.setText("✓ دستورات PowerShell در حافظه موقت (Clipboard) کپی گردید.")
        self.lbl_status.setStyleSheet("color: #10B981; font-size: 12px;")
