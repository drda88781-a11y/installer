"""Persisted installer progress. Completed copy stages are rechecked before reuse."""

import hashlib
import json
from pathlib import Path

from config.settings import APP_VERSION
from utils.durable_state import atomic_json, contained_path, sha256_file


def request_identity(products, install_mode, sql_version, server_target, update_path):
    return {"app_version": APP_VERSION, "products": sorted(products), "install_mode": install_mode,
            "sql_version": str(sql_version), "server_target": server_target,
            "update_path": str(update_path.resolve()) if update_path else None,
            "update_sha256": sha256_file(update_path) if update_path and update_path.is_file() else None}


def source_identity(paths):
    digest = hashlib.sha256()
    for path in sorted(paths, key=str):
        if not path.exists():
            digest.update(f"missing:{path}".encode())
            continue
        for file in ([path] if path.is_file() else sorted(path.rglob("*"))):
            if file.is_file():
                info = file.stat()
                digest.update(f"{file}:{info.st_size}:{info.st_mtime_ns}".encode())
    return digest.hexdigest()


class InstallCheckpoint:
    def __init__(self, path, request, source_digest, resume=True):
        self.path = Path(path)
        self.root = self.path.parent.parent
        self.state = {"schema_version": 1, "request": request, "source_digest": source_digest,
                      "status": "running", "completed": [], "artifacts": {}, "active_stage": None,
                      "sql_version": request["sql_version"]}
        if resume and self.path.is_file():
            existing = json.loads(self.path.read_text(encoding="utf-8"))
            if (existing.get("schema_version") == 1 and existing.get("request") == request
                    and existing.get("source_digest") == source_digest and existing.get("status") != "complete"):
                self.state = existing

    def save(self):
        atomic_json(self.path, self.state)

    def start(self, stage):
        self.state.update(active_stage=stage, status="running")
        self.save()

    def completed(self, stage, files=(), sql_version=None):
        evidence = []
        for file in sorted(set(files)):
            if not file.is_file():
                continue
            relative = file.resolve().relative_to(self.root.resolve()).as_posix()
            evidence.append({"path": relative, "sha256": sha256_file(file)})
        self.state["artifacts"][stage] = evidence
        if stage not in self.state["completed"]:
            self.state["completed"].append(stage)
        if stage == "apply_update":
            self.state["artifacts"]["copy_app"] = evidence
        self.state.update(active_stage=None, sql_version=sql_version or self.state["sql_version"])
        if stage == "verify":
            self.state["status"] = "complete"
        self.save()

    def skipped(self, stage):
        if "skipped" not in self.state:
            self.state["skipped"] = []
        if stage not in self.state["skipped"]:
            self.state["skipped"].append(stage)
        self.state.update(active_stage=None, status="running")
        self.save()

    def valid_files(self, stage):
        evidence = self.state["artifacts"].get(stage, [])
        if stage in ("copy_setup", "copy_app", "apply_update") and not evidence:
            return False
        for item in evidence:
            file = contained_path(self.root, item["path"])
            if not file.is_file() or sha256_file(file) != item["sha256"]:
                return False
        return True

    def invalidate_from(self, stage, ordered_stages):
        invalid = set(ordered_stages[ordered_stages.index(stage):])
        self.state["completed"] = [item for item in self.state["completed"] if item not in invalid]
        self.state["artifacts"] = {key: value for key, value in self.state["artifacts"].items() if key not in invalid}
        self.save()
