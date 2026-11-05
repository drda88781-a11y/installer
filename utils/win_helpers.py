# utils/win_helpers.py
"""
توابع کمکی فرمت‌بندی، تبدیل بایت‌ها، مسیرها و متن‌های دوزبانه
Helper functions for byte formatting, path safety, and bilingual RTL support
"""

from pathlib import Path


def format_bytes(bytes_count: int) -> str:
    """تبدیل بایت‌ها به واحد خوانا (GB, MB, KB)"""
    if bytes_count <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_idx = 0
    val = float(bytes_count)
    while val >= 1024.0 and unit_idx < len(units) - 1:
        val /= 1024.0
        unit_idx += 1
    return f"{val:.1f} {units[unit_idx]}"


def sanitize_path(path_str: str) -> Path:
    """اعتبارسنجی و ایمن‌سازی مسیر"""
    p = Path(path_str).resolve()
    return p
