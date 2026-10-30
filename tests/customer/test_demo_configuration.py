"""Private demo issuance rejects unsupported Windows ACL semantics before IO."""
from types import SimpleNamespace
import pytest
from returnops_api import demo


def _provision_argv(directory, founder='synthetic_founder'):
    return ['provision', '--private-dir', str(directory), '--store', 'synthetic_au_store', '--customer-one',
            'synthetic_customer_a', '--customer-two', 'synthetic_customer_b', '--founder', founder]


@pytest.mark.parametrize('case', ['existing_directory', 'duplicate_principals'])
def test_cli_prints_the_safe_reason_for_configuration_errors(tmp_path, monkeypatch, capsys, case):
    monkeypatch.setattr(demo.sys, 'version_info', (3, 12, 9))
    monkeypatch.delenv('DATABASE_URL', raising=False)
    existing = tmp_path / 'already-there'
    existing.mkdir()
    argv = _provision_argv(existing) if case == 'existing_directory' else _provision_argv(tmp_path / 'fresh', 'synthetic_customer_a')
    assert demo.cli(argv) == 1
    printed = capsys.readouterr().out
    assert printed.startswith('Demo setup or startup failed: ') and 'No credentials are printed.' in printed
    expected = 'Use a new absolute private output directory.' if case == 'existing_directory' else 'Use three distinct demo principal IDs.'
    assert expected in printed and str(tmp_path) not in printed
    assert not (tmp_path / 'fresh').exists()


def test_cli_names_the_id_rule_for_an_invalid_id(tmp_path, monkeypatch, capsys):
    # 31 October 2026 review: an invalid ID used to print the generic sentence.
    monkeypatch.setattr(demo.sys, 'version_info', (3, 12, 9))
    argv = _provision_argv(tmp_path / 'fresh')
    argv[argv.index('--store') + 1] = 'bad store'
    assert demo.cli(argv) == 1
    printed = capsys.readouterr().out
    assert 'Store and principal IDs must be 3 to 80 letters, digits, - or _' in printed
    assert not (tmp_path / 'fresh').exists()


def test_cli_keeps_the_generic_sentence_for_unexpected_errors(monkeypatch, capsys):
    def explode(argv=None):
        raise RuntimeError('private detail dsn=postgresql://user:secret@host/db')
    monkeypatch.setattr(demo, 'main', explode)
    assert demo.cli(['provision']) == 1
    printed = capsys.readouterr().out
    assert printed.strip() == demo.GENERIC_FAILURE and 'secret' not in printed


@pytest.mark.parametrize('flag,expected', [([], False), (['--founder-manual'], True)])
def test_provision_passes_the_explicit_founder_manual_flag(monkeypatch, tmp_path, capsys, flag, expected):
    # docs/45 S3: the manual-handling authority is granted only when asked for.
    seen = {}
    monkeypatch.setattr(demo, 'provision', lambda directory, **options: seen.update(options))
    demo.main(_provision_argv(tmp_path / 'fresh') + flag)
    assert seen['founder_manual'] is expected
    assert seen['order_investigation'] is False and seen['fixed_proposal'] is False
    assert 'Private synthetic demo registration completed.' in capsys.readouterr().out


def test_cli_returns_zero_when_main_succeeds(monkeypatch, capsys):
    monkeypatch.setattr(demo, 'main', lambda argv=None: None)
    assert demo.cli(['provision']) == 0 and capsys.readouterr().out == ''

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
