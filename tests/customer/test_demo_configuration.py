"""Private demo issuance rejects unsupported Windows ACL semantics before IO."""
from types import SimpleNamespace
import pytest
from returnops_api import demo

@pytest.mark.parametrize('version',[(3,12,0),(3,12,3)])
def test_old_windows_issuance_rejected_before_path_or_secret_generation(monkeypatch,version):
    monkeypatch.setattr(demo,'os',SimpleNamespace(name='nt'))
    monkeypatch.setattr(demo,'sys',SimpleNamespace(version_info=version))
    def forbidden(*a,**kw): raise AssertionError('Unsupported runtime performed an output or secret action')
    monkeypatch.setattr(demo,'Path',forbidden);monkeypatch.setattr(demo.secrets,'token_bytes',forbidden)
    with pytest.raises(ValueError) as error:
        demo.provision('PRIVATE_PATH_MARKER',store='store_demo',customer_one='customer_one',customer_two='customer_two',founder='founder_demo')
    assert '3.12.4' in str(error.value) and 'PRIVATE_PATH_MARKER' not in str(error.value)

@pytest.mark.parametrize('platform,version',[('nt',(3,12,4)),('nt',(3,12,9)),('posix',(3,12,0))])
def test_supported_directory_privacy_semantics_pass_runtime_guard(monkeypatch,platform,version):
    monkeypatch.setattr(demo,'os',SimpleNamespace(name=platform))
    monkeypatch.setattr(demo,'sys',SimpleNamespace(version_info=version))
    demo._require_private_output_runtime()
