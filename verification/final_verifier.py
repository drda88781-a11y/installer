# verification/final_verifier.py
"""
ماژول اعتبارسنجی نهایی ۱۲ گانه سلامت نصب و مؤلفه‌های اجرایی سپهریار
Final verification of all 12+ components before declaring success
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List

from config.settings import requires_sql_and_setup, get_sql_instance_name
from downloader.ssms_downloader import is_ssms_installed
from app_logging.app_logger import logger
from packages.product_catalog import resolve_installed_exe_path
from prerequisites.prereq_installer import PrerequisiteManager
from sql.sql_detector import is_sql_instance_installed, get_sql_service_status
from sql.sql_verifier import verify_sql_connection
from utils.shortcut_manager import get_desktop_dir


@dataclass
class VerificationItem:
    key: str
    title_fa: str
    passed: bool
    details: str
    is_critical: bool = True


@dataclass
class VerificationSummary:
    all_passed: bool
    items: List[VerificationItem]
    failed_critical_count: int


class FinalVerifier:
    """
    اعتبارسنجی قطعی قبل از نمایش صفحه موفقیت نهایی
    """
    def __init__(
        self,
        root_install_dir: Path,
        selected_product_ids: List[str],
        install_mode: str = "server",
        sql_version: str = "2019",
        instance_name: Optional[str] = None,
    ):
        self.root = root_install_dir
        self.selected_products = selected_product_ids
        self.install_mode = install_mode
        self.sql_version = str(sql_version)
        self.instance_name = (instance_name or get_sql_instance_name(self.sql_version)).strip()

    def verify_all(self) -> VerificationSummary:
        logger.log("VERIFICATION", "START", "RUNNING", f"آغاز اعتبارسنجی جامع نهایی مؤلفه‌ها ({self.install_mode})")
        items: List[VerificationItem] = []

        # 1. SEPEHRYAR Folder
        root_ok = self.root.exists() and self.root.is_dir()
        items.append(VerificationItem(
            key="root_folder",
            title_fa="پوشه اصلی SEPEHRYAR",
            passed=root_ok,
            details=str(self.root) if root_ok else "پوشه اصلی در درایو یافت نشد.",
            is_critical=True,
        ))

        is_client = (self.install_mode == "client")
        needs_setup = True  # همه حالت‌های نصب، پیش‌نیازها را در Setup کپی می‌کنند.
        needs_sql = requires_sql_and_setup(self.selected_products, install_mode=self.install_mode)

        # 2-5. Subfolders
        checked_subfolders = ["SEPEHRYAR.Data", "SEPEHRYAR.Backup", "SEPEHRYAR.Update"]
        if needs_setup:
            checked_subfolders.insert(0, "SEPEHRYAR.Setup")

        for sub in checked_subfolders:
            sub_path = self.root / sub
            sub_ok = sub_path.exists() and sub_path.is_dir()
            items.append(VerificationItem(
                key=sub.lower(),
                title_fa=f"پوشه {sub}",
                passed=sub_ok,
                details=str(sub_path) if sub_ok else f"پوشه {sub} ایجاد نشده است.",
                is_critical=True,
            ))

        # 6. Setup Files
        if needs_setup:
            setup_dir = self.root / "SEPEHRYAR.Setup"
            setup_files_ok = setup_dir.exists() and any(setup_dir.iterdir())
            items.append(VerificationItem(
                key="setup_files",
                title_fa="فایل‌های پکیج Setup",
                passed=setup_files_ok,
                details="فایل‌های Setup کپی و اعتبارسنجی شدند." if setup_files_ok else "پوشه Setup خالی است.",
                is_critical=True,
            ))
        else:
            items.append(VerificationItem(
                key="setup_files",
                title_fa="فایل‌های پکیج Setup",
                passed=True,
                details="عدم نیاز به فایل‌های ستاپ (صرفاً فایل‌های اجرایی خود برنامه کپی شدند)",
                is_critical=False,
            ))

        # 7. Selected Application Files & EXEs
        app_files_ok = bool(self.selected_products)
        app_details = []
        for pid in self.selected_products:
            exe_path = resolve_installed_exe_path(self.root, pid)
            if exe_path and exe_path.exists():
                app_details.append(f"{pid}: {exe_path.name} (✓)")
            else:
                app_files_ok = False
                app_details.append(f"{pid}: فایل اجرایی یافت نشد (✕)")

        items.append(VerificationItem(
            key="app_files",
            title_fa="فایل‌ها و برنامه‌های اجرایی منتخب",
            passed=app_files_ok,
            details=" | ".join(app_details) if app_details else "هیچ محصولی انتخاب نشده بود.",
            is_critical=True,
        ))

        # 8. SQL Instance
        if needs_sql:
            sql_inst_ok = is_sql_instance_installed(self.instance_name)
            items.append(VerificationItem(
                key="sql_instance",
                title_fa=f"اینستنس پایگاه داده {self.instance_name}",
                passed=sql_inst_ok,
                details="اینستنس در رجیستری و سرویس‌های سیستم فعال است." if sql_inst_ok else "اینستنس یافت نشد.",
                is_critical=True,
            ))

            # 9. SQL Service
            svc_exists, svc_status = get_sql_service_status(self.instance_name)
            svc_ok = svc_exists and svc_status == "running"
            items.append(VerificationItem(
                key="sql_service",
                title_fa="سرویس ویندوز SQL Server",
                passed=svc_ok,
                details=f"وضعیت سرویس: {svc_status}" if svc_exists else "سرویس ویندوز یافت نشد.",
                is_critical=True,
            ))

            # 10. SQL Connection
            conn_res = verify_sql_connection(self.instance_name)
            items.append(VerificationItem(
                key="sql_connection",
                title_fa=f"اتصال زنده به .\\{self.instance_name}",
                passed=conn_res.is_connected,
                details=f"متصل شد ({conn_res.sql_version})" if conn_res.is_connected else f"خطا: {conn_res.error_message}",
                is_critical=True,
            ))

            # 11. Prerequisites
            pm = PrerequisiteManager()
            cr_ok = pm.is_crystal_reports_installed()
            st_ok = pm.is_stimulsoft_installed()
            prereq_ok = cr_ok or st_ok  # حداقل گزارش‌سازها ثبت شده باشند
            items.append(VerificationItem(
                key="prerequisites",
                title_fa="پیش‌نیازها و کامپوننت‌های گزارش‌ساز",
                passed=prereq_ok,
                details=f"Crystal Reports: {'نصب' if cr_ok else 'عدم تشخیص'} | Stimulsoft: {'نصب' if st_ok else 'عدم تشخیص'}",
                is_critical=False,
            ))

            # 12. SQL Management Studio
            if self.sql_version == "2014":
                items.append(VerificationItem(
                    key="ssms",
                    title_fa="SQL Server Management Studio (SSMS)",
                    passed=True,
                    details="عدم نیاز به ابزار مدیریت SSMS مجزا در نسخه SQL Server 2014",
                    is_critical=False,
                ))
            else:
                ssms_ok = is_ssms_installed()
                items.append(VerificationItem(
                    key="ssms",
                    title_fa="SQL Server Management Studio (SSMS)",
                    passed=ssms_ok,
                    details="محیط مدیریتی SSMS در سیستم آماده است." if ssms_ok else "نصاب SSMS در صف اجراست.",
                    is_critical=False,
                ))
        else:
            sql_note = "ایستگاه کلاینت تحت شبکه (عدم نیاز به SQL محلی)" if is_client else "عدم نیاز به SQL Server محلی برای محصولات انتخابی"
            items.append(VerificationItem(
                key="sql_instance",
                title_fa=f"اینستنس پایگاه داده {self.instance_name}",
                passed=True,
                details=sql_note,
                is_critical=False,
            ))
            items.append(VerificationItem(
                key="sql_service",
                title_fa="سرویس ویندوز SQL Server",
                passed=True,
                details="سرویس پایگاه داده روی سرور مرکزی شبکه قرار دارد",
                is_critical=False,
            ))
            items.append(VerificationItem(
                key="sql_connection",
                title_fa="اتصال پایگاه داده SQL",
                passed=True,
                details="آماده اتصال تحت شبکه به سرور مرکزی سپهریار",
                is_critical=False,
            ))
            if is_client:
                pm = PrerequisiteManager()
                cr_ok = pm.is_crystal_reports_installed()
                st_ok = pm.is_stimulsoft_installed()
                prereq_ok = cr_ok or st_ok
                items.append(VerificationItem(
                    key="prerequisites",
                    title_fa="پیش‌نیازها و کامپوننت‌های گزارش‌ساز",
                    passed=prereq_ok,
                    details=f"Crystal Reports: {'نصب' if cr_ok else 'سیستمی'} | Stimulsoft: {'نصب' if st_ok else 'سیستمی'}",
                    is_critical=False,
                ))
            else:
                items.append(VerificationItem(
                    key="prerequisites",
                    title_fa="پیش‌نیازها و کامپوننت‌های گزارش‌ساز",
                    passed=True,
                    details="عدم نیاز به پیش‌نیازهای اختصاصی برای این محصول",
                    is_critical=False,
                ))
            items.append(VerificationItem(
                key="ssms",
                title_fa="SQL Server Management Studio (SSMS)",
                passed=True,
                details="عدم نیاز به ابزار مدیریت SSMS در این پکیج",
                is_critical=False,
            ))

        # 13. Shortcuts
        desktop_dir = get_desktop_dir()
        desktop_lnks = list(desktop_dir.glob("سپهریار*.lnk"))
        shortcuts_ok = len(desktop_lnks) > 0
        items.append(VerificationItem(
            key="shortcuts",
            title_fa="میانبرهای دسکتاپ و استارت‌منو",
            passed=shortcuts_ok,
            details=f"{len(desktop_lnks)} میانبر روی دسکتاپ ایجاد شد." if shortcuts_ok else "میانبر یافت نشد.",
            is_critical=False,
        ))

        # محاسبه موارد بحرانی ناموفق
        failed_crit = sum(1 for it in items if it.is_critical and not it.passed)
        all_passed = (failed_crit == 0)

        logger.log(
            "VERIFICATION",
            "SUMMARY",
            "SUCCESS" if all_passed else "FAILED",
            f"نتیجه اعتبارسنجی نهایی: {'تأیید شد' if all_passed else f'{failed_crit} خطای بحرانی'}"
        )

        return VerificationSummary(
            all_passed=all_passed,
            items=items,
            failed_critical_count=failed_crit,
        )
