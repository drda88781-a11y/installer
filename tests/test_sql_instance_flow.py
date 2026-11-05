# tests/test_sql_instance_flow.py
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from config.settings import SQL_2019_INSTANCE_NAME, SQL_2014_INSTANCE_NAME
from sql.sql_detector import (
    get_all_installed_sql_instances,
    get_sql_service_name_for_instance,
    is_sql_instance_installed,
)
from sql.sql_installer import SQLServerInstaller
from verification.final_verifier import FinalVerifier
from core.install_plan import create_install_plan


class TestSQLInstanceFlow(unittest.TestCase):
    def test_service_name_for_default_instance(self):
        self.assertEqual(get_sql_service_name_for_instance("MSSQLSERVER"), "MSSQLSERVER")
        self.assertEqual(get_sql_service_name_for_instance(""), "MSSQLSERVER")
        self.assertEqual(get_sql_service_name_for_instance("."), "MSSQLSERVER")
        self.assertEqual(get_sql_service_name_for_instance("SEPEHRYAR2019"), "MSSQL$SEPEHRYAR2019")
        self.assertEqual(get_sql_service_name_for_instance("SQLEXPRESS"), "MSSQL$SQLEXPRESS")

    def test_sql_installer_accepts_custom_instance(self):
        installer = SQLServerInstaller(instance_name="CUSTOM_INSTANCE", sql_version="2019")
        self.assertEqual(installer.instance_name, "CUSTOM_INSTANCE")

    def test_sql_installer_defaults_to_version_instance(self):
        installer_2019 = SQLServerInstaller(sql_version="2019")
        self.assertEqual(installer_2019.instance_name, SQL_2019_INSTANCE_NAME)

        installer_2014 = SQLServerInstaller(sql_version="2014")
        self.assertEqual(installer_2014.instance_name, SQL_2014_INSTANCE_NAME)

    def test_create_install_plan_includes_custom_instance(self):
        plan = create_install_plan(
            drive="D:",
            products=["SEPEHRYAR.Hesabdari"],
            mode="server",
            sql_version="2019",
            sql_instance="MY_TEST_INSTANCE",
        )
        self.assertIn("MY_TEST_INSTANCE", plan.sql_description)

    def test_final_verifier_uses_custom_instance(self):
        verifier = FinalVerifier(
            root_install_dir=Path("D:/SEPEHRYAR"),
            selected_product_ids=["SEPEHRYAR.Hesabdari"],
            install_mode="server",
            sql_version="2019",
            instance_name="CUSTOM_INSTANCE",
        )
        self.assertEqual(verifier.instance_name, "CUSTOM_INSTANCE")

    @patch("sql.sql_detector.winreg")
    @patch("sql.sql_detector.psutil")
    def test_get_all_installed_sql_instances(self, mock_psutil, mock_winreg):
        # شبیه‌سازی وجود اینستنس‌های رجیستری
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        mock_winreg.EnumValue.side_effect = [
            ("SEPEHRYAR2019", "MSSQL15.SEPEHRYAR2019", 1),
            ("SQLEXPRESS", "MSSQL15.SQLEXPRESS", 1),
            OSError("No more data"),
        ]
        mock_psutil.win_service_iter.return_value = []

        instances = get_all_installed_sql_instances()
        self.assertIn("SEPEHRYAR2019", instances)
        self.assertIn("SQLEXPRESS", instances)


    def test_sql_installer_force_new_instance_flag(self):
        installer = SQLServerInstaller(instance_name="BRAND_NEW_INST", force_new_instance=True)
        self.assertTrue(installer.force_new_instance)
        self.assertTrue(installer.has_custom_instance)
        self.assertEqual(installer.instance_name, "BRAND_NEW_INST")

    def test_update_all_connect_files_in_folder_recursive(self):
        import tempfile
        import shutil
        from utils.connect_config import update_all_connect_files_in_folder

        temp_dir = Path(tempfile.mkdtemp())
        try:
            sub = temp_dir / "SubLevel1" / "SubLevel2"
            sub.mkdir(parents=True)
            nested_xml = sub / "conect.xml"
            nested_xml.write_bytes(
                '<?xml version="1.0" encoding="utf-16"?><Connection>Data Source=OLD_HOST\\OLD_INST;Initial Catalog=TestDB;</Connection>'.encode("utf-16")
            )
            count = update_all_connect_files_in_folder(temp_dir, ".\\NEW_INSTANCE")
            self.assertEqual(count, 1)
            content = nested_xml.read_bytes().decode("utf-16")
            self.assertIn("Data Source=.\\NEW_INSTANCE;", content)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

