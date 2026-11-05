# tests/test_skip_stage_flow.py
import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication

from ui.dialogs.error_dialog import ErrorDialog
from ui.pages.page_progress import ProgressDashboardPage
from core.worker import InstallWorker
from core.install_checkpoint import InstallCheckpoint


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_error_dialog_has_skip_signal(qapp):
    dlg = ErrorDialog(stage_title="تست مرحله", error_details="خطای آزمایشی", can_retry=True, can_skip=True)
    assert hasattr(dlg, "skip_requested")

    received = []
    dlg.skip_requested.connect(lambda: received.append(True))
    dlg._on_skip()
    assert len(received) == 1
    dlg.deleteLater()


def test_progress_dashboard_set_stage_skipped(qapp):
    dashboard = ProgressDashboardPage()
    dashboard.configure_stages(["SEPEHRYAR.Hesabdari"], install_mode="server")
    dashboard.set_stage_skipped(0, "صرف‌نظر شد")
    dashboard.deleteLater()


def test_worker_skip_current_stage():
    worker = InstallWorker(
        selected_drive="D:",
        selected_product_ids=["SEPEHRYAR.Hesabdari"],
        install_mode="server",
    )
    worker.retry_from_stage_idx = 1
    worker.skip_current_stage(1)
    
    assert 1 in worker.stages or len(worker.stages) > 1
    stage_id = worker.stages[1].id
    assert stage_id in worker.skipped_stage_ids
    assert worker.retry_from_stage_idx == 2


def test_checkpoint_skipped_state(tmp_path):
    ckpt_file = tmp_path / "checkpoint.json"
    request = {"app_version": "1.0", "products": [], "install_mode": "server", "sql_version": "2019", "server_target": "", "update_path": None, "update_sha256": None}
    ckpt = InstallCheckpoint(ckpt_file, request, "digest", resume=False)
    ckpt.skipped("prerequisites")
    assert "prerequisites" in ckpt.state["skipped"]

    # Re-reading checkpoint should preserve skipped
    ckpt2 = InstallCheckpoint(ckpt_file, request, "digest", resume=True)
    assert "prerequisites" in ckpt2.state.get("skipped", [])
