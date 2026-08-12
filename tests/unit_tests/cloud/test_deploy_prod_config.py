from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_RECOVERY_SPACE_REF = '1c31172dee7aa912ce807d899018de27ff29054f'


def test_production_build_pins_recovered_cloud_adapter_revision():
    workflow = (_REPO_ROOT / '.github' / 'workflows' / 'deploy-prod.yml').read_text(encoding='utf-8')

    assert f'SPACE_REF: {_RECOVERY_SPACE_REF}' in workflow
