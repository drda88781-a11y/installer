# ai/troubleshooting_plan.py
"""
موتور هوشمند تولید پلن عیب‌یابی و حل مسئله عملیاتی برای تکنسین‌های استقرار سپهریar
Intelligent Troubleshooting Plan & Auto-Remediation Engine for SEPEHRYAR Deployment
"""

from dataclasses import dataclass, field
from pathlib import Path
import subprocess
from typing import Callable, List, Optional, Tuple

from app_logging.app_logger import logger


@dataclass
class TroubleshootingPlan:
    stage_id: str
    error_summary: str
    root_cause_fa: str
    action_steps: List[str]
    powershell_commands: List[str] = field(default_factory=list)
    can_auto_repair: bool = False
    repair_action_title: str = "تلاش برای رفع خودکار مشکل"


class TroubleshootingPlanEngine:
    """
    تولید داینامیک پلن حل مشکل متناسب با مرحله و متن خطای رخ داده
    """
    @staticmethod
    def generate_plan(stage_id: str, error_details: str, context: Optional[dict] = None) -> TroubleshootingPlan:
        err_lower = (error_details or "").lower()
        ctx = context or {}
        sql_ver = ctx.get("sql_version", "2019")
        inst_name = f"SEPEHRYAR{sql_ver}"

        # =====================================================================
        # ۱. خطاهای پایگاه داده SQL Server
        # =====================================================================
        if stage_id in ["sql_server", "sql_config"] or "sql" in err_lower:
            # الف) عدم اتصال ODBC / سرویس متوقف است
            if any(k in err_lower for k in ["login failed", "named pipes", "cannot open connection", "server does not exist", "timeout", "08001"]):
                return TroubleshootingPlan(
                    stage_id=stage_id,
                    error_summary="عدم امکان اتصال به سرویس SQL Server",
                    root_cause_fa=(
                        f"سرویس پایگاه داده MSSQL${inst_name} متوقف است یا پورت شبکه فعال نیست و یا دسترسی احراز هویت Mixed Mode نیازمند بازنشانی است."
                    ),
                    action_steps=[
                        f"۱. بررسی وضعیت سرویس: دستور 'Start-Service -Name MSSQL${inst_name}' را در PowerShell اجرا فرمایید.",
                        "۲. فعال‌سازی سرویس جستجوی دیتابیس: سرویس SQLBrowser را در Services.msc در حالت Running قرار دهید.",
                        "۳. بررسی دسترسی فایروال ویندوز: پورت ۱۴۳۳ و ۱۴۳۴ را در Windows Firewall باز کنید.",
                        "۴. اجرای نصاب با Run as Administrator: برنامه نصاب را ببندید و حتماً با راست‌کلیک و Run as Administrator اجرا فرمایید.",
                    ],
                    powershell_commands=[
                        f"Start-Service -Name 'MSSQL${inst_name}'; Start-Service -Name 'SQLBrowser'",
                        f"netsh advfirewall firewall add rule name='SQL Server' dir=in action=allow protocol=TCP localport=1433",
                    ],
                    can_auto_repair=True,
                    repair_action_title="راه‌اندازی سرویس‌های SQL و تلاش مجدد",
                )

            # ب) خطای ستاپ یا فایل نصب ISO/RAR
            if any(k in err_lower for k in ["unrar", "iso", "setup.exe", "mount", "exit code"]):
                return TroubleshootingPlan(
                    stage_id=stage_id,
                    error_summary="خطا در آماده‌سازی یا اجرای ستاپ SQL Server",
                    root_cause_fa=(
                        "فایل نصاب SQL Server به دلیل کمبود دسترسی ادمینستریتور، مسدود بودن توسط آنتی‌ویروس یا آسیب‌دیدگی پکیج قابل راه‌اندازی نیست."
                    ),
                    action_steps=[
                        "۱. غیرفعال‌سازی موقت آنتی‌ویروس ویندوز (Windows Defender Real-time Protection) در حین نصب.",
                        "۲. اطمینان از دسترسی کامل ادمینستریتور (Run as Administrator).",
                        f"۳. بررسی سلامت پکیج Setup در پوشه SETUP/SQL یا دانلود مجدد آرشیو SQL Server {sql_ver}.",
                        "۴. ری‌استارت سیستم: در صورت معلق بودن آپدیت‌های ویندوز، یک‌بار سیستم را Restart نمایید.",
                    ],
                    powershell_commands=[
                        "Get-Process -Name '*setup*' | Stop-Process -Force -ErrorAction SilentlyContinue",
                    ],
                    can_auto_repair=True,
                    repair_action_title="آزادسازی منابع و تلاش مجدد",
                )

        # =====================================================================
        # ۲. خطاهای به‌روزرسانی (Update / Extract / Copy)
        # =====================================================================
        if stage_id in ["apply_update", "copy_app", "copy_setup"] or "update" in err_lower or "extract" in err_lower:
            # الف) قفل بودن پروسه‌های در حال اجرا (WinError 32)
            if any(k in err_lower for k in ["being used by another process", "permissionerror", "winerror 32", "access is denied"]):
                return TroubleshootingPlan(
                    stage_id=stage_id,
                    error_summary="فایل‌های نرم‌افزار توسط یک برنامه باز قفل شده‌اند",
                    root_cause_fa=(
                        "یکی از نسخه‌های حسابداری، رستوران یا کلاینت سپهریار در پس‌زمینه ویندوز باز است و اجازه جایگزینی فایل‌های DLL و EXE را نمی‌دهد."
                    ),
                    action_steps=[
                        "۱. کلیه پنجره‌های باز حسابداری، رستوران و کلاینت را ببندید.",
                        "۲. در تسک‌منیجر ویندوز (Task Manager) پروسه‌های Hesabdari.exe، SepandResturan.exe و ClientSepand.exe را End Task کنید.",
                        "۳. روی دکمه «تلاش برای رفع خودکار» در زیر کلیک کنید تا تمام پروسه‌ها خودکار بسته شوند.",
                    ],
                    powershell_commands=[
                        "Stop-Process -Name 'Hesabdari','SepandResturan','ClientSepand','SepandYar_TaxGov' -Force -ErrorAction SilentlyContinue",
                    ],
                    can_auto_repair=True,
                    repair_action_title="بستن خودکار کلیه پروسه‌های سپهریار و تلاش مجدد",
                )

            # ب) ابزار اکسترکت یافت نشد
            if any(k in err_lower for k in ["unrar", "7-zip", "zip", "استخراج"]):
                return TroubleshootingPlan(
                    stage_id=stage_id,
                    error_summary="عدم شناسایی ابزار استخراج آرشیو",
                    root_cause_fa=(
                        "فایل آپدیت به فرمت RAR است اما نرم‌افزار WinRAR در سیستم نصب نیست، یا آرشیو ZIP دچار خرابی (CRC Error) می‌باشد."
                    ),
                    action_steps=[
                        "۱. پکیج به‌روزرسانی را به صورت فایل استاندارد ZIP فشرده کنید تا بدون نیاز به نرم‌افزار جانبی استخراج شود.",
                        "۲. نرم‌افزار WinRAR یا 7-Zip را روی ویندوز نصب فرمایید.",
                        "۳. از سالم بودن و کامل دانلود شدن فایل فشرده اطمینان حاصل کنید.",
                    ],
                    powershell_commands=[
                        "winget install --id RARLab.WinRAR -e --silent",
                    ],
                    can_auto_repair=False,
                )

        # =====================================================================
        # ۳. خطاهای پیش‌نیازها و گزارش‌سازها (Prerequisites)
        # =====================================================================
        if stage_id == "prerequisites" or "crystal" in err_lower or "stimulsoft" in err_lower:
            return TroubleshootingPlan(
                stage_id=stage_id,
                error_summary="خطا در نصب پیش‌نیازها یا گزارش‌سازها",
                root_cause_fa=(
                    "سرویس نصب‌کننده ویندوز (Windows Installer Service) درگیر نصب برنامه دیگری است یا یک راه‌اندازی مجدد (Pending Reboot) معلق مانده است."
                ),
                action_steps=[
                    "۱. اطمینان از بسته بودن سایر نصاب‌های باز در تسک‌بار یا Task Manager.",
                    "۲. استارت سرویس msiserver در ویندوز با دستور 'net start msiserver'.",
                    "۳. نصب دستی بسته‌های کریستال و استیمول‌سافت از پوشه SETUP.",
                ],
                powershell_commands=[
                    "Start-Service -Name 'msiserver'",
                ],
                can_auto_repair=True,
                repair_action_title="راه‌اندازی سرویس Windows Installer و تلاش مجدد",
            )

        # =====================================================================
        # ۴. پلن عمومی برای سایر خطاها
        # =====================================================================
        return TroubleshootingPlan(
            stage_id=stage_id,
            error_summary="خطای عملیاتی غیرمنتظره در حین اجرای مرحله",
            root_cause_fa=(
                f"عملیات مرحله {stage_id} با پیام '{error_details}' متوقف شد. این خطا معمولاً ناشی از محدودیت دسترسی کاربری یا فضای دیسک است."
            ),
            action_steps=[
                "۱. اجرای مجدد اینستالر با دسترسی Administrator (راست‌کلیک > Run as administrator).",
                "۲. بررسی فضای خالی درایو محل نصب.",
                "۳. بررسی لاگ تفصیلی اینستالر از طریق دکمه «مشاهده لاگ».",
            ],
            powershell_commands=[
                f"# مرحله {stage_id}: لطفاً لاگ تفصیلی را بررسی نمایید.",
            ],
            can_auto_repair=True,
            repair_action_title="تلاش مجدد خودکار",
        )

    @staticmethod
    def execute_auto_repair(plan: TroubleshootingPlan, context: Optional[dict] = None) -> Tuple[bool, str]:
        """
        اجرای عملیات تعمیر خودکار بر اساس پلن تولید شده
        """
        logger.log("AUTO_REPAIR", "START", "RUNNING", f"شروع تلاش برای تعمیر خودکار مرحله {plan.stage_id}")
        ctx = context or {}
        sql_ver = ctx.get("sql_version", "2019")
        inst_name = f"SEPEHRYAR{sql_ver}"

        # ۱. بستن پروسه‌های قفل‌کننده
        if plan.stage_id in ["apply_update", "copy_app", "copy_setup"]:
            from utils.archive_extractor import close_running_sepehryar_processes
            count, names = close_running_sepehryar_processes()
            if count > 0:
                return True, f"تعداد {count} پروسه باز بسته شد: {', '.join(names)}. اکنون می‌توانید مجدداً تلاش نمایید."
            return True, "پروسه باز دیگری یافت نشد. آماده تلاش مجدد."

        # ۲. راه‌اندازی سرویس‌های SQL
        if plan.stage_id in ["sql_server", "sql_config"]:
            svc_name = f"MSSQL${inst_name}"
            subprocess.run(["net", "start", svc_name], capture_output=True, timeout=20)
            subprocess.run(["net", "start", "SQLBrowser"], capture_output=True, timeout=20)
            return True, f"دستور راه‌اندازی سرویس‌های {svc_name} و SQLBrowser صادر شد."

        # ۳. راه‌اندازی msiserver
        if plan.stage_id == "prerequisites":
            subprocess.run(["net", "start", "msiserver"], capture_output=True, timeout=15)
            return True, "سرویس Windows Installer فعال گردید."

        return True, "تنظیمات اولیه آماده تلاش مجدد است."
