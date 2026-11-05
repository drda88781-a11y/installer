# utils/elevation.py
"""
مدیریت سطح دسترسی Administrator و فراخوانی UAC در صورت لزوم
Administrator detection and on-demand UAC elevation handler
"""

import ctypes
import os
import sys
import subprocess


def is_admin() -> bool:
    """بررسی دسترسی ادمینستریتور فعلی پروسس"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def request_admin_elevation():
    """
    اجرای مجدد برنامه جاری با سطح دسترسی Admin از طریق UAC
    """
    if is_admin():
        return True

    params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
    try:
        # ShellExecuteEx با runas
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            f'"{sys.argv[0]}" {params}',
            None,
            1  # SW_SHOWNORMAL
        )
        if ret > 32:
            sys.exit(0)
            return True
    except Exception:
        pass
    return False
