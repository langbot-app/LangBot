from langbot.pkg.platform import credential_setup


def test_dingtalk_registration_source_defaults_to_allowlisted_value(monkeypatch):
    monkeypatch.delenv('DINGTALK_REGISTRATION_SOURCE', raising=False)
    assert credential_setup.dingtalk_registration_source() == 'DING_DWS_CLAW'


def test_dingtalk_registration_source_env_override(monkeypatch):
    monkeypatch.setenv('DINGTALK_REGISTRATION_SOURCE', '  LANGBOT_CUSTOM  ')
    assert credential_setup.dingtalk_registration_source() == 'LANGBOT_CUSTOM'


def test_dingtalk_registration_source_blank_env_falls_back(monkeypatch):
    monkeypatch.setenv('DINGTALK_REGISTRATION_SOURCE', '   ')
    assert credential_setup.dingtalk_registration_source() == 'DING_DWS_CLAW'
