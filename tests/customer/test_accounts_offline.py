"""Password hashing, the private credentials file, the limiter and route wiring (31 October 2026).

No database: create_app is only composed, never started. FR-001, FR-012; NFR-009.
"""
import json
from types import SimpleNamespace
import pytest
from returnops_api import accounts, demo
from returnops_api.main import create_app
from returnops_domain.errors import FlowError


def test_hash_verifies_only_the_same_password_and_never_contains_it():
    stored = accounts.hash_password('correct horse battery')
    assert stored.startswith('scrypt$16384$8$1$') and 'correct horse' not in stored
    assert accounts.verify_password('correct horse battery', stored)
    assert not accounts.verify_password('correct horse batterY', stored)
    assert accounts.hash_password('correct horse battery') != stored  # a new salt each time
    for broken in ('', 'scrypt$1$8$1$AA==$AA==', 'bcrypt$x', 'scrypt$16384$8$1$!!$AA==', None):
        assert not accounts.verify_password('correct horse battery', broken)


def test_credentials_file_adds_once_removes_and_keeps_its_shape(tmp_path):
    path = tmp_path / 'credentials.json'
    accounts.new_credentials_file(path, 'store_demo', {'founder_demo': 'founder-secret-1'})
    with pytest.raises(FileExistsError):
        accounts.new_credentials_file(path, 'store_demo', {})
    store = accounts.CredentialStore(path)
    assert store.store_id == 'store_demo' and accounts.verify_password('founder-secret-1', store.hash_for('founder_demo'))
    store.add('customer_new', accounts.hash_password('customer-secret-1'))
    with pytest.raises(FlowError):
        store.add('customer_new', accounts.hash_password('other-secret-1'))
    # A name taken in another letter case is taken too: no look-alike of the Founder's ID.
    for look_alike in ('Customer_New', 'FOUNDER_DEMO', 'Founder_Demo', 'founder-demo', 'founderdemo'):
        with pytest.raises(FlowError):
            store.add(look_alike, accounts.hash_password('other-secret-1'))
    assert accounts.verify_password('customer-secret-1', store.hash_for('customer_new'))
    assert store.taken('Customer-New') and not store.taken('customer_other')
    store.remove('customer_new')
    assert store.hash_for('customer_new') is None and store.hash_for('nobody') is None
    text = path.read_text(encoding='utf-8')
    assert 'secret' not in text and set(json.loads(text)) == {'version', 'store_id', 'accounts'}
    assert [p.name for p in tmp_path.iterdir()] == ['credentials.json']  # no temporary file left


def test_credentials_file_must_be_absolute_and_well_formed(tmp_path):
    with pytest.raises(ValueError):
        accounts.CredentialStore('credentials.json')
    path = tmp_path / 'credentials.json'
    for document in ({'version': 1, 'accounts': {}}, {'version': 2, 'store_id': 'store_demo', 'accounts': {}},
                     {'version': 1, 'store_id': 'bad store', 'accounts': {}}, [1]):
        path.write_text(json.dumps(document), encoding='utf-8')
        with pytest.raises((ValueError, FlowError)):
            accounts.CredentialStore(path)


def test_limiter_counts_per_key_inside_its_window():
    now = [100.0]
    limiter = accounts.AttemptLimiter(2, 60, clock=lambda: now[0])
    assert limiter.take('a') and limiter.take('a')
    assert not limiter.take('a') and limiter.take('b')
    now[0] += 61
    assert limiter.take('a')
    limiter.clear('a')
    assert limiter.take('a') and limiter.take('a')


# Review of 31 October 2026, finding 2: every failed name used to stay in memory forever.
def test_limiter_holds_a_bounded_number_of_keys():
    now = [100.0]
    limiter = accounts.AttemptLimiter(5, 60, max_keys=3, clock=lambda: now[0])
    assert all(limiter.take(key) for key in ('a', 'b', 'c'))
    # Runtime review (31 October 2026): a full limiter lets the oldest key give way, so a
    # flood of made-up names cannot lock out a real one; the size stays bounded.
    assert limiter.take('d') and limiter.size() == 3
    assert limiter._events.keys() == {'b', 'c', 'd'}
    for _ in range(4):
        assert limiter.take('b')
    assert not limiter.take('b')  # a live key still counts
    now[0] += 61
    assert limiter.take('e') and limiter.size() == 1


# Finding 7: parallel requests must not all pass the check before any is counted.
def test_limiter_checks_and_counts_in_one_step():
    import threading
    limiter = accounts.AttemptLimiter(5, 60)
    passed = []
    barrier = threading.Barrier(40)

    def attempt():
        barrier.wait()
        passed.append(limiter.take('founder'))

    threads = [threading.Thread(target=attempt) for _ in range(40)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert passed.count(True) == 5


def test_look_alike_names_share_one_canonical_form():
    from returnops_domain.registry import canonical_id
    assert canonical_id('Synthetic-Founder') == canonical_id('synthetic_founder') == canonical_id('SYNTHETICFOUNDER')
    assert canonical_id('synthetic_f0under') != canonical_id('synthetic_founder')


def test_routes_exist_only_with_a_credentials_file(tmp_path, monkeypatch):
    monkeypatch.delenv('RETURNOPS_ACCOUNTS_FILE', raising=False)
    monkeypatch.delenv('RETURNOPS_AUTH_FILE', raising=False)
    def auth_paths(app):
        return sorted(route.path for route in app.routes if getattr(route, 'path', '').startswith('/v1/auth/'))
    assert auth_paths(create_app(engine=object(), enable_processor=False)) == []
    path = tmp_path / 'credentials.json'
    accounts.new_credentials_file(path, 'store_demo', {})
    app = create_app(engine=object(), enable_processor=False, accounts_file=str(path.resolve()))
    assert auth_paths(app) == ['/v1/auth/login', '/v1/auth/register']
    with pytest.raises(ValueError, match='credentials file'):
        create_app(engine=object(), enable_processor=False, accounts_file=str((tmp_path / 'missing.json').resolve()))


def test_the_customer_case_list_is_served_only_with_a_credentials_file(tmp_path, monkeypatch):
    monkeypatch.delenv('RETURNOPS_ACCOUNTS_FILE', raising=False)
    monkeypatch.delenv('RETURNOPS_AUTH_FILE', raising=False)
    def case_list(app):
        return [route for route in app.routes if getattr(route, 'path', '') == '/v1/cases' and 'GET' in route.methods]
    assert case_list(create_app(engine=object(), enable_processor=False)) == []
    path = tmp_path / 'credentials.json'
    accounts.new_credentials_file(path, 'store_demo', {})
    assert len(case_list(create_app(engine=object(), enable_processor=False, accounts_file=str(path.resolve())))) == 1


def test_provision_writes_private_passwords_and_matching_hashes(tmp_path, monkeypatch):
    class Registry:
        def __init__(self, engine):
            pass

        def provision(self, principals, sessions):
            pass

    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://demo:demo-distinct-pw@localhost/returnops_f02_accounts')
    monkeypatch.setattr(demo, 'build_engine', lambda settings: SimpleNamespace(dispose=lambda: None))
    monkeypatch.setattr(demo, 'TrustedRegistry', Registry)
    directory = tmp_path / 'shop'
    demo.provision(directory, store='store_demo', customer_one='customer_one', customer_two='customer_two', founder='founder_demo')
    passwords = json.loads((directory / 'passwords.json').read_text(encoding='utf-8'))
    assert set(passwords) == {'customer_one', 'customer_two', 'founder_demo'} and len(set(passwords.values())) == 3
    store = accounts.CredentialStore(directory / 'credentials.json')
    assert store.store_id == 'store_demo'
    assert all(accounts.verify_password(value, store.hash_for(name)) for name, value in passwords.items())
    assert not any(value in (directory / 'credentials.json').read_text(encoding='utf-8') for value in passwords.values())


def test_serve_names_the_credentials_file_only_with_accounts(monkeypatch, tmp_path):
    # demo.main writes these into os.environ; set them first so monkeypatch restores them.
    for name in ('RETURNOPS_AUTH_FILE', 'RETURNOPS_FIXED_PROPOSAL_DEMO', 'RETURNOPS_FOUNDER_DECISIONS',
                 'RETURNOPS_MODEL_SHOWCASE', 'RETURNOPS_ACCOUNTS_FILE'):
        monkeypatch.setenv(name, 'placeholder')
    seen = {}
    monkeypatch.setitem(__import__('sys').modules, 'uvicorn', SimpleNamespace(run=lambda *a, **k: seen.update(
        accounts=__import__('os').environ.get('RETURNOPS_ACCOUNTS_FILE'))))
    auth = str((tmp_path / 'shop' / 'auth.json').resolve())
    demo.main(['serve', '--auth-file', auth, '--accounts'])
    assert seen['accounts'] == str((tmp_path / 'shop' / 'credentials.json').resolve())
    demo.main(['serve', '--auth-file', auth])
    assert seen['accounts'] is None


def _provision_with(tmp_path, monkeypatch, chosen):
    class Registry:
        def __init__(self, engine):
            pass

        def provision(self, principals, sessions):
            pass

    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://demo:demo-distinct-pw@localhost/returnops_f02_accounts')
    if chosen is None:
        monkeypatch.delenv('RETURNOPS_DEMO_PASSWORD', raising=False)
    else:
        monkeypatch.setenv('RETURNOPS_DEMO_PASSWORD', chosen)
    monkeypatch.setattr(demo, 'build_engine', lambda settings: SimpleNamespace(dispose=lambda: None))
    monkeypatch.setattr(demo, 'TrustedRegistry', Registry)
    directory = tmp_path / 'shop'
    demo.provision(directory, store='store_demo', customer_one='customer_one', customer_two='customer_two', founder='founder')
    return json.loads((directory / 'passwords.json').read_text(encoding='utf-8')), accounts.CredentialStore(directory / 'credentials.json')


# 31 October 2026: the presenter types one password the lead chose, set only as a service variable.
def test_a_chosen_demo_password_is_the_password_of_all_three_people(tmp_path, monkeypatch):
    passwords, store = _provision_with(tmp_path, monkeypatch, 'Shop-Demo-2026')
    assert set(passwords.values()) == {'Shop-Demo-2026'}
    assert all(accounts.verify_password('Shop-Demo-2026', store.hash_for(name)) for name in passwords)


def test_an_unacceptable_chosen_password_falls_back_to_generated_ones(tmp_path, monkeypatch, capsys):
    passwords, _ = _provision_with(tmp_path, monkeypatch, 'short')
    assert len(set(passwords.values())) == 3 and 'short' not in passwords.values()
    out = capsys.readouterr().out
    assert 'RETURNOPS_DEMO_PASSWORD' in out and 'short' not in out.replace('RETURNOPS_DEMO_PASSWORD', '')
    (tmp_path / 'again').mkdir()
    generated, _ = _provision_with(tmp_path / 'again', monkeypatch, None)
    assert len(set(generated.values())) == 3


def test_a_chosen_password_nobody_could_type_falls_back_to_generated_ones(capsys):
    # Runtime review (31 October 2026): `"pw" | railway variable set ... --stdin` in Windows
    # PowerShell stores a trailing line break, and a space at either end is invisible.
    people = ['founder', 'customer_a']
    for chosen in ('a-password\r\n', ' a-password', 'a-password ', 'a-pass\tword'):
        passwords = demo._demo_passwords(people, chosen)
        assert chosen not in passwords.values() and len(set(passwords.values())) == 2
    assert 'RETURNOPS_DEMO_PASSWORD' in capsys.readouterr().out
    assert set(demo._demo_passwords(people, 'a-pass word').values()) == {'a-pass word'}

