# app_logging/__init__.py
"""
سیستم لاگینگ ساختاریافته اینستالر سپهریار
"""
from .app_logger import logger, LogEntry, InstallerLogger

__all__ = ["logger", "LogEntry", "InstallerLogger"]
