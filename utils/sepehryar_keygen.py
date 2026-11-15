# utils/sepehryar_keygen.py
"""
ماژول اختصاصی محاسبه کد فعال‌سازی و اتوماسیون بازگشایی قفل نرم‌افزاری سپهریار
بر پایه مهندسی معکوس و دیکامپایل الگوریتم رسمی SepehryarKeygen / cod.exe
SEPEHRYAR Software Lock Automated Activation & Keygen Engine
"""

import ctypes
import hashlib
import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple

from app_logging.app_logger import logger

KEYGEN_MASTER_PASSWORD = "kvlhtchvsepandhlh"


def generate_activation_code(serial: str, password: str = KEYGEN_MASTER_PASSWORD) -> str:
    """
    تولید کد فعال‌سازی دقیقاً مطابق با الگوریتم SepehryarKeygen.exe:
    1. اعتبارسنجی رمز عبور با kvlhtchvsepandhlh
    2. الحاق رشته: 'sepand' + serial + 'amapardazesh'
    3. محاسبه هش MD5 روی کاراکترهای ASCII
    4. تبدیل بایت‌های هش با فرمت x (بدون لیدینگ زیرو برای بایت‌های تک‌رقمی)
    5. تفکیک ۱۲ کاراکتر اول به قالب ۳ بلوک ۴تایی: XXXX-XXXX-XXXX
    """
    if password.strip().lower() != KEYGEN_MASTER_PASSWORD.lower():
        raise ValueError("رمز عبور کیجن نادرست است.")

    clean_serial = serial.strip()
    if not clean_serial:
        raise ValueError("کد سریال/قفل نرم‌افزاری نباید خالی باشد.")

    raw = f"sepand{clean_serial}amapardazesh"
    md5 = hashlib.md5(raw.encode("ascii")).digest()
    hex_str = "".join(format(b, "x") for b in md5)

    part1 = hex_str[0:4]
    part2 = hex_str[4:8]
    part3 = hex_str[8:12]
    return f"{part1}-{part2}-{part3}".upper()


def set_clipboard_text(text: str) -> bool:
    """کپی متن در کلیپ‌بورد ویندوز به صورت بومی و بدون وابستگی"""
    try:
        from PySide6.QtWidgets import QApplication
        cb = QApplication.clipboard()
        if cb:
            cb.setText(text)
            return True
    except Exception:
        pass

    try:
        subprocess.run(["clip.exe"], input=text.encode("utf-16"), check=True, timeout=3)
        return True
    except Exception:
        pass

    return False


def get_clipboard_text() -> str:
    """دریافت متن از کلیپ‌بورد ویندوز"""
    try:
        from PySide6.QtWidgets import QApplication
        cb = QApplication.clipboard()
        if cb:
            return cb.text()
    except Exception:
        pass

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True,
            text=True,
            timeout=4
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass

    return ""


def find_window_by_titles(titles_keywords: list) -> Optional[int]:
    """یافتن هندل پنجره بر اساس کلمات کلیدی عنوان"""
    user32 = ctypes.windll.user32
    found_hwnd = None

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def enum_windows_callback(hwnd, lParam):
        nonlocal found_hwnd
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.lower()
            for kw in titles_keywords:
                if kw.lower() in title:
                    found_hwnd = hwnd
                    return False
        return True

    user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
    return found_hwnd


def auto_unlock_sepehryar_app(
    exe_path: Optional[Path] = None,
    timeout_sec: int = 20,
    password: str = KEYGEN_MASTER_PASSWORD
) -> Tuple[bool, str, Optional[str]]:
    """
    اتوماسیون هوشمند بازگشایی قفل نرم‌افزاری حسابداری سپهریار:
    ۱. در صورت بسته بودن، اجرای فایل اجرایی حسابداری
    ۲. مانیتورینگ و شناسایی پنجره فعال‌سازی قفل
    ۳. استخراج کد قفل سیستم یا دریافت از کلیپ‌بورد/کنترل‌ها
    ۴. محاسبه کد فعال‌سازی با الگوریتم رسمی
    ۵. تزریق کد در نرم‌افزار و کپی در کلیپ‌بورد
    """
    proc = None
    if exe_path and exe_path.exists():
        logger.log("KEYGEN", "AUTO_UNLOCK", "RUNNING", f"راه‌اندازی برنامه جهت فعال‌سازی: {exe_path.name}")
        try:
            proc = subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
        except Exception as ex:
            return False, f"خطا در اجرای برنامه: {ex}", None

    keywords = ["ثبت", "فعال", "قفل", "سریال", "کد", "سپند", "سپهریار", "activation", "register", "lock"]
    start_time = time.time()
    lock_hwnd = None

    while time.time() - start_time < timeout_sec:
        lock_hwnd = find_window_by_titles(keywords)
        if lock_hwnd:
            break
        time.sleep(1)

    user32 = ctypes.windll.user32
    WM_GETTEXT = 0x000D
    WM_SETTEXT = 0x000C
    WM_GETTEXTLENGTH = 0x000E
    BM_CLICK = 0x00F5

    detected_serial = ""
    edit_hwnds = []
    button_hwnds = []

    if lock_hwnd:
        # جستجوی کنترل‌های درون پنجره قفل
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def enum_child_callback(hwnd, lParam):
            class_buff = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd, class_buff, 128)
            c_name = class_buff.value.lower()

            length = user32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)
            text_buff = ctypes.create_unicode_buffer(length + 1)
            user32.SendMessageW(hwnd, WM_GETTEXT, length + 1, ctypes.byref(text_buff))
            ctrl_text = text_buff.value.strip()

            if "edit" in c_name or "textbox" in c_name:
                edit_hwnds.append((hwnd, ctrl_text))
            elif "button" in c_name:
                button_hwnds.append((hwnd, ctrl_text))

            return True

        user32.EnumChildWindows(lock_hwnd, WNDENUMPROC(enum_child_callback), 0)

        # استخراج سریال از تکست‌باکس‌های دارای محتوا
        for h, txt in edit_hwnds:
            if txt and len(txt) >= 4 and not txt.startswith("-"):
                detected_serial = txt
                break

    # اگر از کنترل‌ها پیدا نشد، بررسی کلیپ‌بورد (چون برنامه معمولاً کد قفل را در کلیپ‌بورد کپی می‌کند)
    if not detected_serial:
        cb = get_clipboard_text()
        if cb and len(cb) >= 4:
            detected_serial = cb

    if not detected_serial:
        msg = "پنجره نرم‌افزار اجرا شد. لطفاً کد قفل را در پنجره کیجن وارد کنید یا اجازه دهید به صورت خودکار خوانده شود."
        logger.log("KEYGEN", "AUTO_UNLOCK", "WARN", msg)
        return False, msg, None

    # محاسبه کد فعال‌سازی
    try:
        active_code = generate_activation_code(detected_serial, password=password)
        set_clipboard_text(active_code)
        logger.log("KEYGEN", "AUTO_UNLOCK", "SUCCESS", f"کد فعال‌سازی با سریال {detected_serial} محاسبه شد: {active_code}")

        # اگر تکست‌باکس دومی برای کد فعال‌سازی وجود داشت، تزریق کن
        if len(edit_hwnds) >= 2:
            target_edit = edit_hwnds[1][0]
            buff = ctypes.create_unicode_buffer(active_code)
            user32.SendMessageW(target_edit, WM_SETTEXT, 0, ctypes.byref(buff))

            # کلیک روی دکمه ثبت / تایید در صورت وجود
            if button_hwnds:
                for b_h, b_txt in button_hwnds:
                    if any(w in b_txt for w in ["ثبت", "تایید", "فعال", "ok", "register"]):
                        user32.SendMessageW(b_h, BM_CLICK, 0, 0)
                        break

        return True, f"کد فعال‌سازی با موفقیت تولید و در کلیپ‌بورد کپی شد:\n{active_code}", active_code

    except Exception as ex:
        err = f"خطا در تولید کد فعال‌سازی: {ex}"
        logger.log("KEYGEN", "AUTO_UNLOCK", "ERROR", err)
        return False, err, None

