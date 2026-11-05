# tests/test_setup_launcher.py
import os
import sys
import tempfile
import zipfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication

# اطمینان از وجود نمونه QApplication در تست‌های کیوت
app = QApplication.instance() or QApplication(sys.argv)

from setup_launcher import (
    ExtractionWorker,
    SetupLauncherWindow,
    get_system_ram_gb,
    is_running_as_admin,
)


class TestSetupLauncher(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_system_ram_detection(self):
        ram = get_system_ram_gb()
        self.assertIsInstance(ram, float)
        self.assertGreater(ram, 0)

    def test_admin_detection(self):
        admin = is_running_as_admin()
        self.assertIsInstance(admin, bool)

    def test_extraction_worker_zip(self):
        # ساخت یک فایل zip تستی
        test_zip = self.temp_path / "test_payload.zip"
        target_dir = self.temp_path / "extracted"

        with zipfile.ZipFile(test_zip, "w") as zf:
            zf.writestr("test1.txt", "Hello Sepehryar 1" * 100)
            zf.writestr("sub/test2.txt", "Hello Sepehryar 2" * 100)

        worker = ExtractionWorker(test_zip, target_dir)
        progress_events = []
        finish_events = []

        worker.sig_progress.connect(lambda *args: progress_events.append(args))
        worker.sig_finished.connect(lambda *args: finish_events.append(args))

        worker.run()

        self.assertTrue((target_dir / "test1.txt").exists())
        self.assertTrue((target_dir / "sub" / "test2.txt").exists())
        self.assertTrue(len(finish_events) > 0)
        self.assertTrue(finish_events[0][0])  # success == True

    def test_extraction_worker_cancel(self):
        test_zip = self.temp_path / "test_cancel.zip"
        target_dir = self.temp_path / "extracted_cancel"

        with zipfile.ZipFile(test_zip, "w") as zf:
            for i in range(10):
                zf.writestr(f"file_{i}.dat", b"0" * 1024)

        worker = ExtractionWorker(test_zip, target_dir)
        worker.cancel()
        finish_events = []
        worker.sig_finished.connect(lambda *args: finish_events.append(args))

        worker.run()

        self.assertTrue(len(finish_events) > 0)
        self.assertFalse(finish_events[0][0])  # success should be False due to cancellation
        self.assertIn("لغو", finish_events[0][1])

    def test_setup_launcher_window_init(self):
        win = SetupLauncherWindow()
        self.assertIsNotNone(win)
        self.assertEqual(win.stack.count(), 3)
        self.assertEqual(win.stack.currentIndex(), 0)
        self.assertTrue(win.txt_extract_path.text().strip() != "")
        win.close()


if __name__ == "__main__":
    unittest.main()
