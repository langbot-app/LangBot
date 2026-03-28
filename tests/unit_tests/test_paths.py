from pathlib import Path

from src.langbot.pkg.utils import paths


def test_get_data_root_uses_source_root_in_repo_checkout():
    data_root = Path(paths.get_data_root())
    repo_root = Path(__file__).resolve().parents[2]

    assert data_root == repo_root / 'data'


def test_get_data_path_joins_under_data_root():
    data_path = Path(paths.get_data_path('skills', 'demo-skill'))
    repo_root = Path(__file__).resolve().parents[2]

    assert data_path == repo_root / 'data' / 'skills' / 'demo-skill'


def test_get_data_root_honors_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv('LANGBOT_DATA_ROOT', str(tmp_path / 'custom-data'))

    assert Path(paths.get_data_root()) == (tmp_path / 'custom-data').resolve()
