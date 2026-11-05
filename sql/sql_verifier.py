# sql/sql_verifier.py
"""
ماژول تست اتصال زنده و اعتبارسنجی پایگاه داده SQL Server اینستنس SEPEHRYAR2019
Live ODBC connection testing and database instance verification
"""

import time
from dataclasses import dataclass
from typing import List, Optional
import pyodbc

from config.settings import SQL_INSTANCE_NAME, SQL_SA_USER, SQL_SA_PASSWORD
from app_logging.app_logger import logger


@dataclass
class SQLVerificationResult:
    is_connected: bool
    instance_name: str
    target_server: str
    sql_version: str
    auth_method: str
    databases: List[str]
    error_message: Optional[str] = None


def verify_sql_connection(
    instance_name: str = SQL_INSTANCE_NAME,
    sql_user: Optional[str] = SQL_SA_USER,
    sql_password: Optional[str] = SQL_SA_PASSWORD,
    retries: int = 3,
    delay: float = 2.0,
) -> SQLVerificationResult:
    """
    تست اتصال زنده به اینستنس target: .\\SEPEHRYAR2019
    ابتدا با Trusted_Connection (Windows Auth) و در صورت نیاز با SQL Login (sa)
    """
    target_server = f".\\{instance_name}"
    logger.log("SQL", "CONNECTION_TEST", "RUNNING", f"شروع تست اتصال زنده به {target_server}", sql_instance=instance_name)

    drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
    if not drivers:
        err = "هیچ درایور ODBC برای SQL Server در ویندوز یافت نشد."
        logger.log("SQL", "CONNECTION_TEST", "FAILED", err, sql_instance=instance_name, error=err)
        return SQLVerificationResult(
            is_connected=False,
            instance_name=instance_name,
            target_server=target_server,
            sql_version="",
            auth_method="None",
            databases=[],
            error_message=err,
        )

    preferred_driver = "SQL Server"
    for d in ["ODBC Driver 17 for SQL Server", "SQL Server Native Client 11.0", "SQL Server"]:
        if d in drivers:
            preferred_driver = d
            break

    last_error = ""

    for attempt in range(1, retries + 1):
        # 1. تست با Windows Authentication
        conn_str_trusted = f"Driver={{{preferred_driver}}};Server={target_server};Trusted_Connection=yes;"
        try:
            conn = pyodbc.connect(conn_str_trusted, timeout=10)
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            ver_row = cursor.fetchone()
            sql_version = ver_row[0].split("\n")[0] if ver_row else "SQL Server 2019"

            cursor.execute("SELECT name FROM sys.databases WHERE state_desc = 'ONLINE'")
            dbs = [row[0] for row in cursor.fetchall()]
            conn.close()

            logger.log(
                "SQL",
                "CONNECTION_TEST",
                "SUCCESS",
                f"اتصال موفق به {target_server} از طریق Windows Authentication",
                sql_instance=instance_name
            )
            return SQLVerificationResult(
                is_connected=True,
                instance_name=instance_name,
                target_server=target_server,
                sql_version=sql_version,
                auth_method="Windows Authentication (Trusted)",
                databases=dbs,
                error_message=None,
            )
        except Exception as ex:
            last_error = str(ex)

        # 2. در صورت ارسال credential تست با SQL Authentication
        if sql_user and sql_password:
            conn_str_sql = f"Driver={{{preferred_driver}}};Server={target_server};UID={sql_user};PWD={sql_password};"
            try:
                conn = pyodbc.connect(conn_str_sql, timeout=10)
                cursor = conn.cursor()
                cursor.execute("SELECT @@VERSION")
                ver_row = cursor.fetchone()
                sql_version = ver_row[0].split("\n")[0] if ver_row else "SQL Server 2019"

                cursor.execute("SELECT name FROM sys.databases WHERE state_desc = 'ONLINE'")
                dbs = [row[0] for row in cursor.fetchall()]
                conn.close()

                logger.log(
                    "SQL",
                    "CONNECTION_TEST",
                    "SUCCESS",
                    f"اتصال موفق به {target_server} از طریق SQL Authentication ({sql_user})",
                    sql_instance=instance_name
                )
                return SQLVerificationResult(
                    is_connected=True,
                    instance_name=instance_name,
                    target_server=target_server,
                    sql_version=sql_version,
                    auth_method=f"SQL Authentication ({sql_user})",
                    databases=dbs,
                    error_message=None,
                )
            except Exception as ex:
                last_error = str(ex)

        if attempt < retries:
            time.sleep(delay)

    logger.log(
        "SQL",
        "CONNECTION_TEST",
        "FAILED",
        f"عدم امکان اتصال به {target_server}: {last_error}",
        sql_instance=instance_name,
        error=last_error
    )
    return SQLVerificationResult(
        is_connected=False,
        instance_name=instance_name,
        target_server=target_server,
        sql_version="",
        auth_method="Failed",
        databases=[],
        error_message=last_error,
    )
