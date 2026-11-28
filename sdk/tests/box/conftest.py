import pytest


@pytest.fixture(autouse=True)
def isolated_box_identity(monkeypatch, tmp_path):
    monkeypatch.setenv("LANGBOT_BOX_DATA_DIR", str(tmp_path / "runtime-data"))
    monkeypatch.delenv("LANGBOT_BOX_INSTANCE_ID", raising=False)
