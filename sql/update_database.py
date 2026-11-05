"""Database operations for verified update backups and recovery."""

from pathlib import Path
import re

from file_manager.update_package import validate_database_name


def identifier(name):
    return "[" + validate_database_name(name).replace("]", "]]") + "]"


def literal(value):
    return "N'" + str(value).replace("'", "''") + "'"


class UpdateDatabase:
    def __init__(self, instance):
        if not instance:
            raise ValueError("اینستنس پایگاه داده مشخص نشده است.")
        self.instance = instance

    def _connect(self):
        from file_manager.update_engine import get_sql_connection
        connection = get_sql_connection(self.instance, timeout=15)
        if connection is None:
            raise RuntimeError(f"اتصال به SQL Server {self.instance} برقرار نشد.")
        connection.timeout = 600
        return connection

    def _execute(self, sql, parameters=(), fetch=False):
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(sql, parameters)
            return cursor.fetchone() if fetch else None
        finally:
            connection.close()

    def exists(self, name):
        validate_database_name(name)
        row = self._execute("SELECT state_desc FROM sys.databases WHERE name = ?", (name,), fetch=True)
        if row and row[0] != "ONLINE":
            raise RuntimeError(f"پایگاه داده {name} آماده استفاده نیست: {row[0]}")
        return row is not None

    def version(self):
        row = self._execute("SELECT CAST(SERVERPROPERTY('ProductMajorVersion') AS int)", fetch=True)
        return {12: "2014", 15: "2019"}.get(int(row[0]), str(row[0]))

    def backup(self, name, destination: Path):
        self._execute(f"BACKUP DATABASE {identifier(name)} TO DISK = {literal(destination)} WITH COPY_ONLY, INIT, CHECKSUM;")
        self._execute(f"RESTORE VERIFYONLY FROM DISK = {literal(destination)} WITH CHECKSUM;")
        if not destination.is_file() or destination.stat().st_size == 0:
            raise RuntimeError(f"فایل بک‌آپ تأییدشده {name} در مسیر محلی در دسترس نیست.")

    def restore(self, name, backup: Path):
        self._execute(f"RESTORE VERIFYONLY FROM DISK = {literal(backup)} WITH CHECKSUM;")
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(f"IF DB_ID({literal(name)}) IS NOT NULL ALTER DATABASE {identifier(name)} SET SINGLE_USER WITH ROLLBACK IMMEDIATE;")
            try:
                cursor.execute(f"RESTORE DATABASE {identifier(name)} FROM DISK = {literal(backup)} WITH REPLACE, CHECKSUM;")
            finally:
                cursor.execute(f"IF DB_ID({literal(name)}) IS NOT NULL ALTER DATABASE {identifier(name)} SET MULTI_USER;")
        finally:
            connection.close()
        self.verify(name)

    def drop_created(self, name):
        self._execute(f"IF DB_ID({literal(name)}) IS NOT NULL BEGIN ALTER DATABASE {identifier(name)} SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE {identifier(name)}; END;")

    def attach(self, name, mdf, ldf=None):
        paths = f"(FILENAME = {literal(mdf)})"
        if ldf:
            paths += f", (FILENAME = {literal(ldf)})"
        self._execute(f"CREATE DATABASE {identifier(name)} ON {paths} FOR {'ATTACH' if ldf else 'ATTACH_REBUILD_LOG'};")

    def execute_script(self, name, script: Path):
        raw = script.read_bytes()
        encoding = "utf-16" if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else "utf-8-sig"
        text = raw.decode(encoding)
        # Package scripts run in the declared database. Reject explicit context changes
        # to another database and server/database administration in patch files.
        stripped = re.sub(r"/\*.*?\*/|--[^\n]*", "", text, flags=re.S)
        if re.search(r"\b(?:CREATE|ALTER|DROP|RESTORE|BACKUP)\s+DATABASE\b|\bUSE\b|^\s*:", stripped, re.I | re.M):
            raise ValueError("پچ باید فقط تغییرات داخل دیتابیس اعلام‌شده را شامل شود؛ USE و مدیریت دیتابیس مجاز نیست.")
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(f"USE {identifier(name)}")
            for batch in re.split(r"(?im)^\s*GO\s*(?:--[^\n]*)?$", text):
                if batch.strip():
                    cursor.execute(batch)
                    while cursor.nextset():
                        pass
        finally:
            connection.close()

    def verify(self, name):
        if not self.exists(name):
            raise RuntimeError(f"پایگاه داده {name} پس از آپدیت موجود نیست.")
