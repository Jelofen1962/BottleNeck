from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data = tmp_path / "data"
    monkeypatch.setattr(main, "DB_PATH", data / "bottleneck.sqlite3")
    monkeypatch.setattr(main, "UPLOAD_DIR", data / "uploads")
    monkeypatch.setattr(main, "AVATAR_DIR", data / "uploads" / "avatars")
    monkeypatch.setattr(main, "SHARED_DIR", data / "shared")
    monkeypatch.setattr(main, "CHAT_DIR", data / "chat_uploads")
    monkeypatch.setattr(main, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(main, "SERVER_LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(main, "SERVER_LOG_PATH", tmp_path / "logs" / "server.log")
    with TestClient(main.app) as test_client:
        yield test_client
