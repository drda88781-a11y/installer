"""Regression tests using real Qt threads and temporary files, without installing software.

Run: python -B -m unittest discover -s tests -v
External processes and database connections are blocked unless a test supplies a mock.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import typing
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOCAL_DEPS = ROOT / "scratch" / "test_dependencies"
if LOCAL_DEPS.is_dir():
    sys.path.insert(0, str(LOCAL_DEPS))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Importing the real logger creates a log under the user's profile.
log_module = types.ModuleType("app_logging.app_logger")
log_module.logger = Mock()
log_module.LogEntry = Mock
log_module.InstallerLogger = Mock
sys.modules["app_logging.app_logger"] = log_module

from PySide6.QtWidgets import QApplication, QMessageBox
import pyodbc

from config import settings
from core import worker as worker_module
from core.orchestrator import InstallStage
from core.worker import InstallWorker
from file_manager import update_manager as update_module
from file_manager.update_manager import UpdateManager
from prerequisites import prereq_installer as prereq_module
from prerequisites.prereq_installer import PrerequisiteManager
from sql.sql_verifier import SQLVerificationResult
from ui.main_window import MainWindow
from verification import final_verifier as verifier_module
from verification.final_verifier import FinalVerifier, VerificationSummary

APP = QApplication.instance() or QApplication([])
PRODUCT = "SEPEHRYAR.Hesabdari"


class SafeTestCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="installer_regression_")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for name in ("run", "check_output", "check_call", "Popen"):
            blocker = patch.object(subprocess, name, side_effect=AssertionError("External command blocked in tests"))
            blocker.start()
            self.addCleanup(blocker.stop)
        blocker = patch.object(pyodbc, "connect", side_effect=AssertionError("Live SQL blocked in tests"))
        blocker.start()
        self.addCleanup(blocker.stop)
        log_module.logger.reset_mock()

    def patched(self, target, attribute, **kwargs):
        patcher = patch.object(target, attribute, **kwargs)
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def worker(self):
        worker = InstallWorker("D:", [PRODUCT])
        worker.root_path = self.root
        return worker

    def product_source(self):
        source = self.root / "source" / PRODUCT
        source.mkdir(parents=True)
        (source / "Hesabdari.exe").write_bytes(b"test application")
        self.patched(worker_module, "resolve_product_source_dir", return_value=source)
        self.patched(worker_module, "get_product_by_id", return_value=types.SimpleNamespace(folder_name=PRODUCT))
        self.patched(settings, "EXE_FULL_DIR", new=source.parent)
        return source.parent


class WorkerTests(SafeTestCase):
    def test_type_annotations_resolve(self):
        self.assertEqual(typing.get_type_hints(InstallWorker._step_create_folders)["return"], typing.Tuple[bool, str])

    def test_retry_resumes_failed_stage_without_recopying(self):
        worker = self.worker()
        worker.stages = [InstallStage("copy_setup", "copy"), InstallStage("prerequisites", "prereq")]
        worker._step_copy_setup = Mock(return_value=(True, "copied"))
        worker._step_prerequisites = Mock(side_effect=[(False, "failed"), (True, "installed")])
        results = []
        worker.sig_finished.connect(lambda ok, summary: results.append(ok))
        worker.run()
        self.assertEqual(worker.retry_from_stage_idx, 1)
        worker.run()
        self.assertEqual(results, [False, True])
        self.assertEqual(worker._step_copy_setup.call_count, 1)

    def test_failed_verification_never_reports_success_or_100_percent(self):
        worker = self.worker()
        worker.stages = [InstallStage("verify", "verify")]
        summary = VerificationSummary(False, [], 1)
        worker._step_verify = Mock(return_value=(False, "SQL unavailable", summary))
        progress, errors, results = [], [], []
        worker.sig_progress.connect(lambda *args: progress.append(args))
        worker.sig_error.connect(lambda *args: errors.append(args))
        worker.sig_finished.connect(lambda *args: results.append(args))
        worker.run()
        self.assertTrue(all(value[0] < 100 for value in progress))
        self.assertEqual(errors, [("verify", "SQL unavailable", True)])
        self.assertEqual(results, [(False, summary)])
        self.assertEqual(worker.retry_from_stage_idx, 0)

    def test_cancel_during_stage_cannot_report_success(self):
        worker = self.worker()
        worker.stages = [InstallStage("prerequisites", "prereq")]
        def cancel_during_stage():
            worker.cancel()
            return True, "done"
        worker._step_prerequisites = cancel_during_stage
        results = []
        worker.sig_finished.connect(lambda ok, summary: results.append(ok))
        worker.run()
        self.assertEqual(results, [False])

    def test_cancel_is_forwarded_to_active_copy(self):
        worker = self.worker()
        copier = Mock()
        worker._active_copier = copier
        worker.cancel()
        copier.request_cancel.assert_called_once_with()

    def test_verify_without_root_returns_failure_summary(self):
        worker = self.worker()
        worker.root_path = None
        ok, _, summary = worker._step_verify()
        self.assertFalse(ok)
        self.assertEqual(summary.failed_critical_count, 1)

    def test_failed_prerequisite_stops_installation(self):
        pm = self.patched(worker_module, "PrerequisiteManager").return_value
        pm.install_crystal_reports.return_value = False
        pm.install_stimulsoft.return_value = True
        pm.install_farsi_fonts.return_value = True
        ok, message = self.worker()._step_prerequisites()
        self.assertFalse(ok)
        self.assertIn("Crystal Reports", message)

    def test_setup_copy_errors_are_not_success(self):
        copier = self.patched(worker_module, "FileCopier").return_value
        copier.calculate_total_size.return_value = (2, 20)
        copier.copy_directory_contents.return_value = (10, 1, 1)
        worker = self.worker()
        worker.setup_target_dir = self.root / "setup"
        self.assertFalse(worker._step_copy_setup(0, 3)[0])

    def test_missing_product_is_not_silently_skipped(self):
        self.patched(worker_module, "resolve_product_source_dir", return_value=None)
        self.assertFalse(self.worker()._step_copy_app(0, 3)[0])

    def test_product_copy_errors_are_not_success(self):
        self.product_source()
        copier = self.patched(worker_module, "FileCopier").return_value
        copier.calculate_total_size.return_value = (1, 10)
        copier.copy_directory_contents.return_value = (0, 0, 1)
        self.assertFalse(self.worker()._step_copy_app(0, 3)[0])

    def make_shared_package(self, name="connect.xml", content=None):
        bundle = self.product_source()
        shared = bundle / "_shared"
        shared.mkdir()
        if content is not None:
            (shared / name).write_text(content, encoding="utf-8")
        manifest = {"products": {PRODUCT: {"shared_files": [{"shared_name": name, "relative_path": name}]}}}
        (bundle / "shared_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return bundle

    def test_missing_shared_file_fails_installation(self):
        self.make_shared_package()
        self.assertFalse(self.worker()._step_copy_app(0, 3)[0])

    def test_corrupt_shared_manifest_fails_installation(self):
        bundle = self.make_shared_package()
        (bundle / "shared_manifest.json").write_text("broken JSON")
        self.assertFalse(self.worker()._step_copy_app(0, 3)[0])

    def test_shared_connection_file_is_configured_after_copy(self):
        self.make_shared_package(content="<Connection>Data Source=OLD;Initial Catalog=Accounting;</Connection>")
        worker = self.worker()
        worker.server_target = r"SERVER\SEPEHRYAR2014"
        self.assertTrue(worker._step_copy_app(0, 3)[0])
        self.assertIn(worker.server_target, (self.root / PRODUCT / "connect.xml").read_text())

    def test_reinstall_refreshes_shared_dll(self):
        self.make_shared_package(name="common.dll", content="new library")
        destination = self.root / PRODUCT
        destination.mkdir()
        (destination / "common.dll").write_text("old library")
        self.assertTrue(self.worker()._step_copy_app(0, 3)[0])
        self.assertEqual((destination / "common.dll").read_text(), "new library")

    def test_existing_sql_version_is_used_in_later_steps(self):
        installer = self.patched(worker_module, "SQLServerInstaller").return_value
        installer.sql_version = "2014"
        result = SQLVerificationResult(True, "SEPEHRYAR2014", r".\SEPEHRYAR2014", "2014", "Windows", [])
        installer.execute_flow.return_value = (True, result)
        worker = self.worker()
        self.assertTrue(worker._step_sql_server(0, 5)[0])
        from sql import sql_verifier
        verify = self.patched(sql_verifier, "verify_sql_connection", return_value=result)
        self.assertTrue(worker._step_sql_config()[0])
        self.assertEqual(verify.call_args.kwargs["instance_name"], "SEPEHRYAR2014")
        self.assertEqual(worker.sql_version, "2014")

    def test_missing_selected_update_fails(self):
        worker = self.worker()
        worker.update_archive_path = self.root / "removed.zip"
        self.assertFalse(worker._step_apply_update(0, 5)[0])


class VerificationTests(SafeTestCase):
    def prepare_installation(self):
        for name in settings.SUBFOLDERS:
            (self.root / name).mkdir()
        (self.root / "SEPEHRYAR.Setup" / "runtime.msi").write_bytes(b"fixture")
        exe = self.root / "Hesabdari.exe"
        exe.write_bytes(b"fixture")
        self.patched(verifier_module, "resolve_installed_exe_path", return_value=exe)
        self.patched(verifier_module, "get_desktop_dir", return_value=self.root)
        pm = self.patched(verifier_module, "PrerequisiteManager").return_value
        pm.is_crystal_reports_installed.return_value = True
        pm.is_stimulsoft_installed.return_value = True

    def test_2014_is_verified_instead_of_default_2019(self):
        self.prepare_installation()
        detect = self.patched(verifier_module, "is_sql_instance_installed", return_value=True)
        service = self.patched(verifier_module, "get_sql_service_status", return_value=(True, "running"))
        verify = self.patched(verifier_module, "verify_sql_connection", return_value=types.SimpleNamespace(is_connected=True, sql_version="2014"))
        summary = FinalVerifier(self.root, [PRODUCT], sql_version="2014").verify_all()
        self.assertTrue(summary.all_passed)
        for operation in (detect, service, verify):
            operation.assert_called_once_with("SEPEHRYAR2014")

    def test_client_never_requires_local_sql(self):
        self.prepare_installation()
        detect = self.patched(verifier_module, "is_sql_instance_installed")
        verify = self.patched(verifier_module, "verify_sql_connection")
        self.assertTrue(FinalVerifier(self.root, [PRODUCT], install_mode="client").verify_all().all_passed)
        detect.assert_not_called()
        verify.assert_not_called()


class UpdateTests(SafeTestCase):
    def manager(self, mode="server"):
        manager = UpdateManager(self.root, [PRODUCT], install_mode=mode)
        manager._grant_folder_permissions = Mock()
        manager.refresh_desktop_shortcuts = Mock(return_value=[])
        return manager

    def pipeline(self):
        archive = self.root / "update.zip"
        archive.write_bytes(b"mock archive")
        manager = self.manager()
        manager.extract_archive = Mock(return_value=(True, "extracted"))
        manager.copy_update_files = Mock(return_value=(True, "copied", 1))
        manager.copy_data_files = Mock(return_value=(True, "data", []))
        manager.attach_databases = Mock(return_value=(True, "attached", []))
        manager.execute_sql_patch_scripts = Mock(return_value=(True, "patched", []))
        return manager, archive

    def test_pipeline_stops_at_each_failed_operation(self):
        operations = ["copy_update_files", "copy_data_files", "attach_databases", "execute_sql_patch_scripts"]
        for index, operation in enumerate(operations):
            with self.subTest(operation=operation):
                manager, archive = self.pipeline()
                getattr(manager, operation).return_value = (False, "failure", 0 if index == 0 else [])
                result = manager.execute_update_pipeline(archive)
                self.assertFalse(result.success)
                self.assertEqual(result.error_details, "failure")
                for later in operations[index + 1:]:
                    getattr(manager, later).assert_not_called()
                manager.refresh_desktop_shortcuts.assert_not_called()

    def test_update_extraction_does_not_reuse_stale_files(self):
        manager, archive = self.pipeline()
        stale = manager.update_dir / "Extracted"
        stale.mkdir(parents=True)
        (stale / "obsolete.sql").write_text("old patch")
        self.assertTrue(manager.execute_update_pipeline(archive).success)
        first = manager.extract_archive.call_args.args[1]
        self.assertTrue(manager.execute_update_pipeline(archive).success)
        second = manager.extract_archive.call_args.args[1]
        self.assertNotEqual(first, second)
        self.assertFalse((first / "obsolete.sql").exists())

    def test_client_sql_patch_cannot_touch_local_database(self):
        script = self.root / "patch.sql"
        script.write_text("SELECT 1")
        self.assertFalse(self.manager(mode="client").execute_update_pipeline(script).success)
        pyodbc.connect.assert_not_called()

    def test_update_copy_reports_locked_files(self):
        source = self.root / "Files"
        source.mkdir()
        (source / "Hesabdari.exe").write_bytes(b"new exe")
        (self.root / PRODUCT).mkdir()
        self.patched(update_module, "get_product_by_id", return_value=types.SimpleNamespace(folder_name=PRODUCT))
        self.patched(update_module, "close_running_sepehryar_processes")
        self.patched(update_module.shutil, "copy2", side_effect=PermissionError("locked"))
        self.assertFalse(self.manager().copy_update_files(self.root)[0])

    def test_existing_customer_database_is_preserved(self):
        manager = self.manager()
        source = self.root / "package" / "Data"
        source.mkdir(parents=True)
        manager.data_dir.mkdir()
        (source / "customer.mdf").write_bytes(b"empty template")
        (manager.data_dir / "customer.mdf").write_bytes(b"customer records")
        ok, _, files = manager.copy_data_files(source.parent)
        self.assertTrue(ok)
        self.assertEqual((manager.data_dir / "customer.mdf").read_bytes(), b"customer records")
        self.assertEqual(len(files), 1)

    def test_failed_data_copy_is_reported(self):
        source = self.root / "package" / "Data"
        source.mkdir(parents=True)
        (source / "customer.mdf").write_bytes(b"database")
        self.patched(update_module.shutil, "copy2", side_effect=OSError("disk full"))
        self.assertFalse(self.manager().copy_data_files(source.parent)[0])

    def test_attach_connection_failure_is_not_success_or_wrong_instance(self):
        mdf = self.root / "customer.mdf"
        mdf.write_bytes(b"database")
        self.patched(pyodbc, "drivers", return_value=["SQL Server"])
        connect = self.patched(pyodbc, "connect", side_effect=RuntimeError("unavailable"))
        self.assertFalse(self.manager().attach_databases([mdf])[0])
        self.assertEqual(connect.call_count, 2)
        for call in connect.call_args_list:
            self.assertIn(r"Server=.\SEPEHRYAR2019;", call.args[0])

    def test_attach_failure_closes_connection_and_reports_error(self):
        mdf = self.root / "customer.mdf"
        mdf.write_bytes(b"database")
        self.patched(pyodbc, "drivers", return_value=["SQL Server"])
        connection = self.patched(pyodbc, "connect").return_value
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = None
        cursor.execute.side_effect = [None, RuntimeError("invalid database")]
        self.assertFalse(self.manager().attach_databases([mdf])[0])
        connection.close.assert_called_once()

    def test_patch_failure_stops_following_scripts(self):
        for name in ["01.sql", "02.sql", "03.sql"]:
            (self.root / name).write_text("SELECT 1")
        from sql import sql_auditor
        auditor = self.patched(sql_auditor, "SQLInstanceAuditor").return_value
        auditor.execute_sql_script.side_effect = [(True, "ok"), (False, "bad SQL")]
        ok, _, executed = self.manager().execute_sql_patch_scripts(self.root)
        self.assertFalse(ok)
        self.assertEqual(executed, ["01.sql"])
        self.assertEqual(auditor.execute_sql_script.call_count, 2)


class PrerequisiteTests(SafeTestCase):
    def test_one_failed_crystal_architecture_is_not_hidden_by_other_success(self):
        manager = PrerequisiteManager()
        manager._get_crystal_msi_files = Mock(return_value=[self.root / "x86.msi", self.root / "x64.msi"])
        manager.is_crystal_reports_installed = Mock(return_value=False)
        self.patched(subprocess, "run", side_effect=[types.SimpleNamespace(returncode=1603), types.SimpleNamespace(returncode=0)])
        self.assertFalse(manager.install_crystal_reports())

    def test_missing_fonts_are_not_reported_installed(self):
        self.patched(prereq_module, "SETUP_DIR", new=self.root)
        self.patched(prereq_module, "BASE_DIR", new=self.root)
        with patch.object(prereq_module.ctypes, "windll", Mock()):
            self.assertFalse(PrerequisiteManager().install_farsi_fonts())

    def test_failed_font_copy_is_not_registered_or_reported_successful(self):
        self.patched(prereq_module, "SETUP_DIR", new=self.root)
        self.patched(prereq_module, "BASE_DIR", new=self.root)
        (self.root / "AradVF.ttf").write_bytes(b"font fixture")
        registry = self.patched(prereq_module.winreg, "OpenKey")
        self.patched(prereq_module.shutil, "copy2", side_effect=PermissionError("access denied"))
        with patch.dict(os.environ, {"WINDIR": str(self.root / "windows")}), patch.object(prereq_module.ctypes, "windll", Mock()):
            self.assertFalse(PrerequisiteManager().install_farsi_fonts())
        registry.assert_not_called()


class WindowTests(SafeTestCase):
    def test_all_installer_pages_can_be_constructed(self):
        from ui.pages.page_system_check import SystemCheckPage
        with patch.object(SystemCheckPage, "run_check"):
            window = MainWindow()
        self.addCleanup(window.deleteLater)
        self.assertEqual(window.stack.count(), 7)
        self.assertEqual(window.stack.currentIndex(), 0)

    def window(self):
        def fake_ui(window):
            window.page_progress = Mock()
            window.page_system_check = Mock()
            window.stack = Mock()
            window.stack.currentIndex.return_value = 4
            window.action_bar = Mock()
        with patch.object(MainWindow, "_init_ui", fake_ui), patch.object(MainWindow, "_connect_signals"):
            window = MainWindow()
        self.addCleanup(window.deleteLater)
        return window

    def test_retry_after_real_qthread_finish_keeps_failed_stage_and_logging(self):
        window = self.window()
        worker = self.worker()
        worker.stages = [InstallStage("copy_setup", "copy"), InstallStage("prerequisites", "prereq")]
        worker._step_copy_setup = Mock(return_value=(True, "copied"))
        worker._step_prerequisites = Mock(side_effect=[(False, "failure"), (True, "installed")])
        window.worker = worker
        window._show_installation_error = Mock()
        window._go_to_final_page = Mock()
        worker.sig_error.connect(window._on_worker_error)
        worker.sig_finished.connect(window._on_worker_finished)
        worker.finished.connect(window._on_worker_thread_finished)
        worker.start()
        self.assertTrue(worker.wait(2000))
        APP.processEvents()
        window._show_installation_error.assert_called_once_with("prerequisites", "failure", True)
        window._retry_current_stage()
        self.assertTrue(worker.wait(2000))
        APP.processEvents()
        window._go_to_final_page.assert_called_once()
        self.assertEqual(worker._step_copy_setup.call_count, 1)
        log_module.logger.add_listener.assert_called_with(window._on_new_log_entry)

    def test_close_defers_destruction_until_thread_has_finished(self):
        window = self.window()
        window.worker = Mock()
        window.worker.isRunning.return_value = True
        event = Mock()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            window.closeEvent(event)
        event.ignore.assert_called_once()
        event.accept.assert_not_called()
        window.worker.cancel.assert_called_once()
        self.assertTrue(window._close_when_finished)
        window.close = Mock()
        window.worker.isRunning.return_value = False
        window._on_worker_thread_finished()
        window.close.assert_called_once()

    def test_copy_data_files_copies_mdf_ndf_ldf_and_permission(self):
        import tempfile
        from file_manager.update_manager import UpdateManager
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manager = UpdateManager(root_dir=root, selected_product_ids=["SEPEHRYAR.Hesabdari"], install_mode="server")
            source = root / "update_pkg" / "Data"
            source.mkdir(parents=True)
            (source / "Sepehr_Main_1405.mdf").write_bytes(b"MDF_DATA")
            (source / "Sepehr_Main_1405.ndf").write_bytes(b"NDF_DATA")
            (source / "Sepehr_Main_1405.ldf").write_bytes(b"LDF_DATA")
            (source / "Permission.cmd").write_text("icacls *", encoding="utf-8")

            ok, msg, mdfs = manager.copy_data_files(source.parent)
            self.assertTrue(ok)
            self.assertTrue((manager.data_dir / "Sepehr_Main_1405.mdf").exists())
            self.assertTrue((manager.data_dir / "Sepehr_Main_1405.ndf").exists())
            self.assertTrue((manager.data_dir / "Sepehr_Main_1405.ldf").exists())
            self.assertTrue((manager.data_dir / "Permission.cmd").exists())
            self.assertEqual((manager.data_dir / "Sepehr_Main_1405.ndf").read_bytes(), b"NDF_DATA")

    def test_configure_hesabdari_creates_both_xml_variants(self):
        import tempfile
        from utils.connect_config import configure_hesabdari_connection
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "SEPEHRYAR"
            root.mkdir(parents=True)
            ok = configure_hesabdari_connection(root, ".", "Sepehr_Main_1405")
            self.assertTrue(ok)
            h_dir = root / "SEPEHRYAR.Hesabdari"
            self.assertTrue((h_dir / "conect.xml").exists())
            self.assertTrue((h_dir / "connect.xml").exists())
            self.assertTrue((h_dir / "SEPEHRYAR.Hesabdari" / "conect.xml").exists())
            self.assertTrue((h_dir / "SEPEHRYAR.Hesabdari" / "connect.xml").exists())
            content = (h_dir / "conect.xml").read_bytes().decode("utf-16")
            self.assertIn("Initial Catalog=Sepehr_Main_1405", content)
            self.assertIn("Data Source=.", content)

    def test_keygen_dialog_password_field_is_masked(self):
        from ui.dialogs.keygen_dialog import KeygenDialog
        from PySide6.QtWidgets import QLineEdit
        dlg = KeygenDialog(parent=None)
        self.assertEqual(dlg.txt_pass.echoMode(), QLineEdit.Password)
        self.assertTrue(dlg.txt_pass.isReadOnly())


if __name__ == "__main__":
    unittest.main()
