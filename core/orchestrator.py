# core/orchestrator.py
"""
مدیریت زنجیره مراحل نصب، پایپ‌لاین و کنترل وضعیت کلی اینستالر سپهریار
Installation pipeline orchestrator and state machine for SEPEHRYAR Installer
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import SETUP_DIR, requires_sql, requires_sql_and_setup
from downloader.ssms_downloader import SSMSDownloader
from file_manager.file_copier import FileCopier, create_sepehryar_root_structure
from app_logging.app_logger import logger
from packages.product_catalog import (
    get_product_by_id,
    resolve_installed_exe_path,
    resolve_product_source_dir,
)
from prerequisites.prereq_installer import PrerequisiteManager
from sql.sql_installer import SQLServerInstaller
from utils.shortcut_manager import create_shortcuts_for_product
from verification.final_verifier import FinalVerifier, VerificationSummary


@dataclass
class InstallStage:
    id: str
    title_fa: str
    status: str = "pending"
    progress: int = 0
    message: str = ""
    error_details: str = ""


@dataclass
class InstallState:
    selected_drive: str = ""
    selected_products: List[str] = field(default_factory=list)
    install_mode: str = "server"  # "server" or "client"
    root_dir: Optional[Path] = None
    setup_dir: Optional[Path] = None
    sql_version: str = "2019"
    update_archive_path: Optional[Path] = None
    stages: List[InstallStage] = field(default_factory=list)
    current_stage_idx: int = 0
    overall_progress: int = 0
    stage_progress: int = 0
    status_text: str = ""
    is_completed: bool = False
    has_error: bool = False
    error_message: str = ""
    verification_summary: Optional[VerificationSummary] = None


def get_install_stages_for_products(
    selected_product_ids: List[str],
    install_mode: str = "server",
    sql_version: str = "2019",
    has_update: bool = False,
) -> List[InstallStage]:
    """
    تولید داینامیک لیست مراحل نصب بر مبنای محصولات انتخابی، نوع استقرار و نسخه SQL:
    - در صورتی که فقط برنامه‌های کلاینت (فروش، رستوران، مودیان) انتخاب شوند: به هیچ عنوان SQL نصب نمی‌شود.
    - در صورتی که حسابداری (یا صنعتی) انتخاب شده باشد: در حالت سرور مراحل کامل SQL Server اجرا می‌گردد.
    - برای نسخه ۲۰۱۴: مرحله SSMS حذف می‌شود.
    - برای نسخه ۲۰۱۹: مرحله دانلود و نصب SSMS اجرا می‌گردد.
    - در صورت انتخاب پکیج آپدیت: مرحله اعمال به‌روزرسانی و اتصال دیتابیس به زنجیره اضافه می‌شود.
    """
    stages = [
        InstallStage("create_folders", "ساخت پوشه‌ها و ساختار SEPEHRYAR"),
        InstallStage("copy_setup", "کپی فایل‌های پکیج Setup"),
        InstallStage("prerequisites", "نصب پیش‌نیازها و فونت‌های سیستم"),
    ]

    needs_sql = requires_sql(selected_product_ids, install_mode=install_mode)

    if needs_sql:
        stages.extend([
            InstallStage("sql_server", f"نصب و بررسی SQL Server {sql_version}"),
            InstallStage("sql_config", "تنظیمات و تست اتصال پایگاه داده"),
        ])
        if str(sql_version) != "2014":
            stages.append(InstallStage("ssms", "دریافت و نصب SQL Management Studio"))

    stages.append(InstallStage("copy_app", "کپی فایل‌های اجرایی پکیج منتخب"))

    if has_update:
        stages.append(InstallStage("apply_update", "اعمال بسته به‌روزرسانی و اتصال دیتابیس"))

    stages.extend([
        InstallStage("shortcuts", "ایجاد میانبرهای دسکتاپ و منوی استارت"),
        InstallStage("verify", "بررسی و اعتبارسنجی نهایی"),
    ])

    return stages


def get_default_install_stages(sql_version: str = "2019", has_update: bool = False) -> List[InstallStage]:
    return get_install_stages_for_products(["SEPEHRYAR.Hesabdari"], install_mode="server", sql_version=sql_version, has_update=has_update)


class InstallationOrchestrator:
    """
    هماهنگ‌کننده وضعیت و پایپ‌لاین مراحل نصب
    """
    def __init__(
        self,
        selected_drive: str = "",
        selected_products: Optional[List[str]] = None,
        install_mode: str = "server",
        sql_version: str = "2019",
        update_archive_path: Optional[Path] = None,
    ):
        prods = selected_products or []
        has_upd = bool(update_archive_path and update_archive_path.exists())
        self.state = InstallState(
            selected_drive=selected_drive,
            selected_products=prods,
            install_mode=install_mode,
            sql_version=sql_version,
            update_archive_path=update_archive_path,
            stages=get_install_stages_for_products(prods, install_mode=install_mode, sql_version=sql_version, has_update=has_upd),
        )

    def get_stages(self) -> List[InstallStage]:
        return self.state.stages

    def reset(self):
        has_upd = bool(self.state.update_archive_path and self.state.update_archive_path.exists())
        self.state.stages = get_install_stages_for_products(
            self.state.selected_products,
            install_mode=self.state.install_mode,
            sql_version=self.state.sql_version,
            has_update=has_upd,
        )
        self.state.current_stage_idx = 0
        self.state.overall_progress = 0
        self.state.is_completed = False
        self.state.has_error = False


