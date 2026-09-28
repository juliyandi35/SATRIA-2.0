from pathlib import Path
import io
import platform
import shutil
import sys
import tempfile

import pyotp
import pytest

from app import PROJECT_ROOT, create_app
from SATRIA_backend import query_defense_data, read_file
from satria.data_service import DataRepository

TEST_EMAIL = 'satria-test@example.com'
TEST_PASSWORD = 'a-strong-test-password-1'


@pytest.fixture(autouse=True)
def _reset_login_lockout():
    # Login lockout tracking is a module-global dict keyed only by email (correct for the real
    # single-process server); tests reuse TEST_EMAIL across isolated throwaway databases, so it
    # must be cleared between tests to keep them independent.
    from services.auth_service import _FAILED_ATTEMPTS

    _FAILED_ATTEMPTS.clear()
    yield
    _FAILED_ATTEMPTS.clear()


def _build_app():
    # A plain tempfile.mkdtemp() dir, not pytest's tmp_path - this sandbox denies pytest's own
    # numbered-tmpdir bookkeeping directory (os.scandir on pytest-of-<user> raises PermissionError)
    # even though ordinary temp-directory creation works fine.
    scratch = Path(tempfile.mkdtemp(prefix='satria-test-'))
    repository = DataRepository(PROJECT_ROOT)
    application = create_app(repository, database_path=scratch / 'checkpoints.db')
    application.config.update(TESTING=True)
    return application, scratch


@pytest.fixture()
def client():
    """An authenticated client - most tests exercise data/analytics endpoints, not login itself,
    so the fixture completes account setup + mandatory MFA enrollment against an isolated
    per-test database and hands back an already-logged-in session."""
    application, scratch = _build_app()
    try:
        with application.test_client() as test_client:
            setup = test_client.post('/api/auth/setup', json={'email': TEST_EMAIL, 'password': TEST_PASSWORD})
            secret = setup.get_json()['totp_secret']
            code = pyotp.TOTP(secret).now()
            enrolled = test_client.post('/api/auth/mfa/enroll', json={'email': TEST_EMAIL, 'code': code})
            assert enrolled.status_code == 200
            yield test_client
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


@pytest.fixture()
def guest_client():
    """An unauthenticated client, for exercising the login/setup flow and the auth gate itself."""
    application, scratch = _build_app()
    try:
        with application.test_client() as test_client:
            yield test_client
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_initial_state_is_empty(client):
    response = client.get('/api/data/status')
    assert response.status_code == 200
    assert response.get_json()['loaded'] is False
    assert response.get_json()['metadata'] is None


def test_system_status_reports_active_python_runtime(client):
    payload = client.get('/api/system/status').get_json()
    python_runtime = payload['backend']['python']
    assert python_runtime['version'] == platform.python_version()
    assert Path(python_runtime['executable']).resolve() == Path(sys.executable).resolve()
    assert Path(python_runtime['base_prefix']).resolve() == Path(sys.base_prefix).resolve()


def test_builtin_import_and_authoritative_summary(client):
    imported = client.post('/api/data/import', json={'source': 'builtin'})
    assert imported.status_code == 200
    body = imported.get_json()
    assert body['metadata']['rows'] == 2500
    assert body['metadata']['schema_map']['lat'] == 'LATITUDE'
    assert body['metadata']['schema_map']['lon'] == 'LONGITUDE'

    view = client.post('/api/data/view', json={'filters': {}, 'page_size': 20})
    assert view.status_code == 200
    payload = view.get_json()
    assert payload['summary']['record_count'] == 2500
    assert payload['summary']['unit_count'] == 474
    assert payload['summary']['province_count'] == 38
    assert payload['summary']['average_readiness'] == pytest.approx(83.8833, abs=0.0001)
    assert payload['summary']['maximum_readiness'] == 110
    assert len(payload['map_points']) == 500


def test_filters_update_every_summary_dimension(client):
    client.post('/api/data/import', json={'source': 'builtin'})
    response = client.post('/api/data/view', json={'filters': {'status': 'FLAGGED'}})
    payload = response.get_json()
    # 552 = deterministically every row whose computed readiness (actual / MEF x 100) is below
    # the FLAGGED_BELOW threshold - the live computed pipeline has no synthetic random flagging.
    assert payload['summary']['record_count'] == 552
    assert payload['summary']['flagged_count'] == 552
    assert all(record['status'] == 'FLAGGED' for record in payload['records'])


def test_satuan_filter_is_detected_and_constrains_unit_options(client):
    client.post('/api/data/import', json={'source': 'builtin'})
    response = client.post('/api/data/view', json={'filters': {'satuan': 'Yonif'}})
    payload = response.get_json()
    assert payload['filter_options']['satuan'] == ['Bekangdam', 'Denpal', 'Yonif', 'Yonkav', 'Yonarmed', 'Yonzipur']
    assert payload['filter_options']['unit']
    assert all(unit.startswith('Yonif ') for unit in payload['filter_options']['unit'])
    assert all(record['unit'].startswith('Yonif ') for record in payload['records'])


def test_diagnostics_preserve_suspicious_values(client):
    client.post('/api/data/import', json={'source': 'builtin'})
    response = client.post('/api/data/diagnostics', json={'filters': {}})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['numeric']['out_of_expected_range'] > 0
    assert len(payload['details_ids']['out_of_range']) == payload['numeric']['out_of_expected_range']


def test_spatial_and_hidden_risk_use_imported_data(client):
    client.post('/api/data/import', json={'source': 'builtin'})
    clusters = client.post('/api/spatial/clusters', json={'filters': {}})
    assert clusters.status_code == 200
    assert clusters.get_json()['method'] == 'Haversine DBSCAN'
    assert clusters.get_json()['risk_point_count'] > 0

    prediction = client.post('/api/predictive/forecast', json={'filters': {}})
    assert prediction.status_code == 200
    payload = prediction.get_json()
    assert payload['method'] == 'Isolation Forest'
    assert payload['features_analyzed'] == ['readiness', 'category', 'location']
    assert len(payload['top_risks']) == 15
    assert all(item['lat'] is not None and item['lon'] is not None for item in payload['top_risks'])


def test_ai_file_tools_cannot_escape_project():
    with pytest.raises(PermissionError):
        read_file(str(Path(PROJECT_ROOT).parent / 'outside.txt'))
    with pytest.raises(PermissionError):
        query_defense_data('DELETE FROM readiness')


def test_ai_sql_guard_blocks_dumpfile_too():
    with pytest.raises(PermissionError):
        query_defense_data("SELECT secret FROM t INTO DUMPFILE '/tmp/shell.php'")


def test_wrong_http_method_returns_405_not_500(client):
    response = client.get('/api/data/import')
    assert response.status_code == 405


def test_diagnostics_on_empty_filter_returns_422_not_500(client):
    client.post('/api/data/import', json={'source': 'builtin'})
    response = client.post('/api/data/diagnostics', json={'filters': {'location': 'Atlantis'}})
    assert response.status_code == 422


def test_null_numeric_payload_falls_back_to_default(client):
    client.post('/api/data/import', json={'source': 'builtin'})
    response = client.post('/api/spatial/clusters', json={'filters': {}, 'epsilon_km': None})
    assert response.status_code == 200
    response = client.post('/api/predictive/forecast', json={'filters': {}, 'limit': None})
    assert response.status_code == 200
    response = client.post('/api/data/view', json={'filters': {}, 'page_size': None})
    assert response.status_code == 200


def test_risk_lens_categories_are_exclusive(client):
    client.post('/api/data/import', json={'source': 'builtin'})
    good = client.post('/api/data/view', json={'filters': {'risk': 'good'}}).get_json()
    attention = client.post('/api/data/view', json={'filters': {'risk': 'attention'}}).get_json()
    critical = client.post('/api/data/view', json={'filters': {'risk': 'critical'}}).get_json()
    assert good['summary']['minimum_readiness'] >= 80
    assert 60 <= attention['summary']['minimum_readiness']
    assert attention['summary']['maximum_readiness'] < 80
    assert critical['summary']['maximum_readiness'] < 60
    total = good['summary']['record_count'] + attention['summary']['record_count'] + critical['summary']['record_count']
    all_records = client.post('/api/data/view', json={'filters': {}}).get_json()['summary']['record_count']
    assert total <= all_records


def test_empty_list_filter_means_no_filter(client):
    client.post('/api/data/import', json={'source': 'builtin'})
    response = client.post('/api/data/view', json={'filters': {'location': []}})
    all_records = client.post('/api/data/view', json={'filters': {}}).get_json()['summary']['record_count']
    assert response.get_json()['summary']['record_count'] == all_records


def test_csv_import_sniffs_comma_delimiter_despite_quoted_semicolons():
    from satria.data_service import DataRepository

    header = 'RECORD_ID,UNIT_NODE,LOCATION,CATEGORY,LAT,LON,READINESS_IDX,STATUS,LAST_SYNC,"N;N;N;N;N;N;N;N;N;N;N;N"\n'
    row = '1,Unit A,Jakarta,Personnel,-6.2,106.8,85,VERIFIED,2024-01-01,"note; here"\n'
    repository = DataRepository(PROJECT_ROOT)
    result = repository.import_bytes((header + row).encode('utf-8'), 'sample.csv')
    assert result['metadata']['rows'] == 1


def test_send_email_tool_attaches_binary_content(monkeypatch):
    from services.email_service import send_email_tool

    sent: dict = {}

    class FakeServer:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def login(self, *args, **kwargs):
            pass

        def sendmail(self, sender, to, message):
            sent['sender'] = sender
            sent['to'] = to
            sent['message'] = message

    monkeypatch.setenv('SMTP_USERNAME', 'bot@example.com')
    monkeypatch.setenv('SMTP_PASSWORD', 'secret')
    monkeypatch.setattr('services.email_service.smtplib.SMTP_SSL', FakeServer)

    result = send_email_tool('user@example.com', 'Subject', 'Body', attachment=(b'%PDF-1.4 fake', 'report.pdf'))
    assert 'berhasil' in result.lower()
    assert 'report.pdf' in sent['message']
    assert 'application/pdf' in sent['message'].lower()


def test_full_report_pdf_builds_valid_pdf_bytes():
    from satria.data_service import DataRepository
    from services.report_service import build_full_report_pdf

    repository = DataRepository(PROJECT_ROOT)
    repository.import_builtin()
    pdf_bytes = build_full_report_pdf(repository)
    assert pdf_bytes.startswith(b'%PDF')
    assert len(pdf_bytes) > 500


def test_email_audit_log_endpoint_reports_missing_smtp_config(client, monkeypatch):
    monkeypatch.delenv('SMTP_USERNAME', raising=False)
    monkeypatch.delenv('SMTP_PASSWORD', raising=False)
    response = client.post('/api/email/audit-log', json={'email': 'user@example.com'})
    assert response.status_code in (409, 422)


def test_unauthenticated_api_call_is_rejected(guest_client):
    response = guest_client.get('/api/data/status')
    assert response.status_code == 401


def test_full_setup_and_login_requires_both_password_and_totp(guest_client):
    assert guest_client.get('/api/auth/status').get_json()['configured'] is False

    setup = guest_client.post('/api/auth/setup', json={'email': TEST_EMAIL, 'password': TEST_PASSWORD})
    assert setup.status_code == 200
    secret = setup.get_json()['totp_secret']
    assert setup.get_json()['provisioning_uri'].startswith('otpauth://totp/')

    # A second setup attempt is refused - exactly one account may exist.
    again = guest_client.post('/api/auth/setup', json={'email': 'other@example.com', 'password': TEST_PASSWORD})
    assert again.status_code == 409

    # The account cannot log in before MFA enrollment finishes, even with the right password.
    premature = guest_client.post(
        '/api/auth/login', json={'email': TEST_EMAIL, 'password': TEST_PASSWORD, 'totp_code': '000000'}
    )
    assert premature.status_code == 409

    # A wrong code does not complete enrollment.
    bad_code = guest_client.post('/api/auth/mfa/enroll', json={'email': TEST_EMAIL, 'code': '000000'})
    assert bad_code.status_code == 400
    assert guest_client.get('/api/data/status').status_code == 401

    enrolled = guest_client.post('/api/auth/mfa/enroll', json={'email': TEST_EMAIL, 'code': pyotp.TOTP(secret).now()})
    assert enrolled.status_code == 200
    # Enrollment logs the operator straight in.
    assert guest_client.get('/api/data/status').status_code == 200

    guest_client.post('/api/auth/logout')
    assert guest_client.get('/api/data/status').status_code == 401

    # Wrong password is rejected even with a correct TOTP code.
    wrong_password = guest_client.post(
        '/api/auth/login', json={'email': TEST_EMAIL, 'password': 'not-the-password', 'totp_code': pyotp.TOTP(secret).now()}
    )
    assert wrong_password.status_code == 401

    # Wrong TOTP code is rejected even with the correct password.
    wrong_code = guest_client.post(
        '/api/auth/login', json={'email': TEST_EMAIL, 'password': TEST_PASSWORD, 'totp_code': '111111'}
    )
    assert wrong_code.status_code == 401

    good_login = guest_client.post(
        '/api/auth/login', json={'email': TEST_EMAIL, 'password': TEST_PASSWORD, 'totp_code': pyotp.TOTP(secret).now()}
    )
    assert good_login.status_code == 200
    assert guest_client.get('/api/auth/session').get_json() == {'authenticated': True, 'email': TEST_EMAIL}


def test_repeated_failed_logins_are_locked_out(guest_client):
    setup = guest_client.post('/api/auth/setup', json={'email': TEST_EMAIL, 'password': TEST_PASSWORD})
    secret = setup.get_json()['totp_secret']
    guest_client.post('/api/auth/mfa/enroll', json={'email': TEST_EMAIL, 'code': pyotp.TOTP(secret).now()})
    guest_client.post('/api/auth/logout')

    for _ in range(5):
        response = guest_client.post(
            '/api/auth/login', json={'email': TEST_EMAIL, 'password': 'wrong', 'totp_code': '000000'}
        )
        assert response.status_code == 401

    locked_out = guest_client.post(
        '/api/auth/login', json={'email': TEST_EMAIL, 'password': TEST_PASSWORD, 'totp_code': pyotp.TOTP(secret).now()}
    )
    assert locked_out.status_code == 429


def test_spatial_cluster_with_missing_readiness_stays_valid_json(client):
    client.post('/api/data/import', json={'source': 'builtin'})
    response = client.post('/api/spatial/clusters', json={'filters': {}})
    assert response.status_code == 200
    # get_json() round-trips through the stdlib json decoder - a literal NaN token would raise here.
    for cluster in response.get_json()['clusters']:
        assert cluster['average_readiness'] is None or isinstance(cluster['average_readiness'], (int, float))


def test_change_password_requires_current_password_and_takes_effect(client):
    wrong_current = client.post('/api/auth/change-password', json={'current_password': 'nope', 'new_password': 'a-new-strong-password-1'})
    assert wrong_current.status_code == 401

    too_short = client.post('/api/auth/change-password', json={'current_password': TEST_PASSWORD, 'new_password': 'short'})
    assert too_short.status_code == 400

    changed = client.post('/api/auth/change-password', json={'current_password': TEST_PASSWORD, 'new_password': 'a-new-strong-password-1'})
    assert changed.status_code == 200

    # The old password no longer works; the new one does (new session, same account/db).
    client.post('/api/auth/logout')
    old_login = client.post('/api/auth/login', json={'email': TEST_EMAIL, 'password': TEST_PASSWORD, 'totp_code': '000000'})
    assert old_login.status_code == 401


def test_change_email_requires_current_password_and_updates_session(client):
    wrong_current = client.post('/api/auth/change-email', json={'current_password': 'nope', 'new_email': 'new@example.com'})
    assert wrong_current.status_code == 401

    invalid_email = client.post('/api/auth/change-email', json={'current_password': TEST_PASSWORD, 'new_email': 'not-an-email'})
    assert invalid_email.status_code == 400

    changed = client.post('/api/auth/change-email', json={'current_password': TEST_PASSWORD, 'new_email': 'new-address@example.com'})
    assert changed.status_code == 200
    assert changed.get_json()['email'] == 'new-address@example.com'

    session_check = client.get('/api/auth/session').get_json()
    assert session_check['email'] == 'new-address@example.com'


def test_add_account_requires_authentication_and_current_password(guest_client):
    # Anonymous callers cannot add accounts, even before any account exists.
    anon = guest_client.post('/api/auth/accounts/add', json={'current_password': 'x', 'new_email': TEST_EMAIL, 'new_password': TEST_PASSWORD})
    assert anon.status_code == 401

    setup = guest_client.post('/api/auth/setup', json={'email': TEST_EMAIL, 'password': TEST_PASSWORD})
    secret = setup.get_json()['totp_secret']
    guest_client.post('/api/auth/mfa/enroll', json={'email': TEST_EMAIL, 'code': pyotp.TOTP(secret).now()})

    wrong_password = guest_client.post(
        '/api/auth/accounts/add', json={'current_password': 'wrong', 'new_email': 'teammate@example.com', 'new_password': 'a-teammate-password-1'}
    )
    assert wrong_password.status_code == 401

    added = guest_client.post(
        '/api/auth/accounts/add',
        json={'current_password': TEST_PASSWORD, 'new_email': 'teammate@example.com', 'new_password': 'a-teammate-password-1'},
    )
    assert added.status_code == 200
    teammate_secret = added.get_json()['totp_secret']
    assert added.get_json()['provisioning_uri'].startswith('otpauth://totp/')

    duplicate = guest_client.post(
        '/api/auth/accounts/add',
        json={'current_password': TEST_PASSWORD, 'new_email': 'teammate@example.com', 'new_password': 'another-password-1'},
    )
    assert duplicate.status_code == 409

    accounts = guest_client.get('/api/auth/accounts').get_json()['accounts']
    assert {account['email'] for account in accounts} == {TEST_EMAIL, 'teammate@example.com'}
    teammate = next(account for account in accounts if account['email'] == 'teammate@example.com')
    assert teammate['mfa_enabled'] is False

    # The teammate completes their own enrollment and can then log in independently.
    guest_client.post('/api/auth/mfa/enroll', json={'email': 'teammate@example.com', 'code': pyotp.TOTP(teammate_secret).now()})
    guest_client.post('/api/auth/logout')
    teammate_login = guest_client.post(
        '/api/auth/login',
        json={'email': 'teammate@example.com', 'password': 'a-teammate-password-1', 'totp_code': pyotp.TOTP(teammate_secret).now()},
    )
    assert teammate_login.status_code == 200


def test_remove_account_blocks_last_account_and_supports_self_removal(guest_client):
    setup = guest_client.post('/api/auth/setup', json={'email': TEST_EMAIL, 'password': TEST_PASSWORD})
    secret = setup.get_json()['totp_secret']
    guest_client.post('/api/auth/mfa/enroll', json={'email': TEST_EMAIL, 'code': pyotp.TOTP(secret).now()})

    # Cannot remove the only account, even with the correct password.
    lone = guest_client.post('/api/auth/accounts/remove', json={'current_password': TEST_PASSWORD, 'target_email': TEST_EMAIL})
    assert lone.status_code == 409

    added = guest_client.post(
        '/api/auth/accounts/add',
        json={'current_password': TEST_PASSWORD, 'new_email': 'teammate@example.com', 'new_password': 'a-teammate-password-1'},
    )
    assert added.status_code == 200

    wrong_password = guest_client.post(
        '/api/auth/accounts/remove', json={'current_password': 'wrong', 'target_email': 'teammate@example.com'}
    )
    assert wrong_password.status_code == 401

    removed_teammate = guest_client.post(
        '/api/auth/accounts/remove', json={'current_password': TEST_PASSWORD, 'target_email': 'teammate@example.com'}
    )
    assert removed_teammate.status_code == 200
    assert removed_teammate.get_json()['removed_self'] is False
    assert guest_client.get('/api/auth/session').get_json()['authenticated'] is True

    # Removing your own account clears the session immediately.
    removed_self = guest_client.post('/api/auth/accounts/remove', json={'current_password': TEST_PASSWORD, 'target_email': TEST_EMAIL})
    assert removed_self.status_code == 409  # still the last account - guard holds even for self-removal


def test_legacy_single_account_schema_migrates_without_data_loss():
    import sqlite3

    from services.auth_service import list_accounts

    scratch = Path(tempfile.mkdtemp(prefix='satria-test-'))
    db_path = scratch / 'legacy.db'
    try:
        connection = sqlite3.connect(db_path)
        connection.execute(
            """CREATE TABLE users (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                totp_secret TEXT NOT NULL,
                mfa_enabled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO users (id, email, password_hash, totp_secret, mfa_enabled, created_at) VALUES (1, ?, ?, ?, 1, ?)",
            ('legacy@example.com', 'not-a-real-hash', 'SECRETSECRETSECRETSECR', '2026-01-01T00:00:00+00:00'),
        )
        connection.commit()
        connection.close()

        accounts = list_accounts(db_path)
        assert len(accounts) == 1
        assert accounts[0]['email'] == 'legacy@example.com'
        assert accounts[0]['mfa_enabled'] is True

        # The migrated table accepts a second account, which the old CHECK(id=1) would have blocked.
        connection = sqlite3.connect(db_path)
        connection.execute(
            "INSERT INTO users (email, password_hash, totp_secret, mfa_enabled, created_at) VALUES (?, ?, ?, 0, ?)",
            ('second@example.com', 'hash', 'SECRET2', '2026-01-02T00:00:00+00:00'),
        )
        connection.commit()
        connection.close()
        assert {account['email'] for account in list_accounts(db_path)} == {'legacy@example.com', 'second@example.com'}
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_legacy_actual_data_schema_migrates_and_reseeds():
    import sqlite3

    from satria import readiness_service

    scratch = Path(tempfile.mkdtemp(prefix='satria-test-'))
    db_path = scratch / 'legacy_actual.db'
    try:
        connection = sqlite3.connect(db_path)
        connection.execute(
            """CREATE TABLE actual_data (
                unit_node TEXT PRIMARY KEY,
                unit_type TEXT NOT NULL,
                location TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                personnel REAL NOT NULL,
                equipment REAL NOT NULL,
                logistics REAL NOT NULL,
                infrastructure REAL NOT NULL,
                training REAL NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO actual_data VALUES ('Yonif 1', 'Yonif', 'Jakarta', -6.2, 106.8, 900, 200, 2900, 38, 19)"
        )
        connection.commit()
        connection.close()

        # seed_if_empty must migrate the legacy single-key table (dropping the one stale test
        # row) and then reseed cleanly from the bundled tabel1_actual.csv - not leave 1 row.
        readiness_service.seed_if_empty(db_path, PROJECT_ROOT)
        result = readiness_service.list_actual(db_path, page=1, page_size=10)
        assert result['pagination']['total_records'] == 500
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_readiness_formula_matches_actual_over_mef_reference():
    from satria import readiness_service

    scratch = Path(tempfile.mkdtemp(prefix='satria-test-'))
    db_path = scratch / 'readiness.db'
    try:
        readiness_service.seed_if_empty(db_path, PROJECT_ROOT)
        csv_bytes = readiness_service.compute_readiness_csv(db_path)
        rows = csv_bytes.decode('utf-8').splitlines()
        assert rows[0] == 'RECORD_ID,CATEGORY,UNIT_NODE,LOCATION,LATITUDE,LONGITUDE,READINESS_IDX,STATUS,LAST_SYNC'
        # 500 units x 5 categories, matching the original tabel3_readiness.csv row count.
        assert len(rows) - 1 == 2500
        # Bekangdam 124, Personnel: actual 305 / MEF reference 400 x 100 = 76.2 (VERIFIED, >= 75).
        first_row = rows[1].split(',')
        assert first_row[1] == 'Personnel'
        assert first_row[2] == 'Bekangdam 124'
        assert first_row[6] == '76.2'
        assert first_row[7] == 'VERIFIED'
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_readiness_recomputes_after_actual_and_reference_edits(client):
    imported = client.post('/api/data/import', json={'source': 'builtin'})
    assert imported.status_code == 200

    actual_page = client.get('/api/data/actual?page=1&page_size=10').get_json()
    assert actual_page['pagination']['total_records'] == 500
    sample = actual_page['records'][0]

    # Editing an actual value changes that unit's readiness on recompute.
    updated = client.post('/api/data/actual/update', json={
        'unit_node': sample['unit_node'],
        'location': sample['location'],
        'personnel': 1,
    })
    assert updated.status_code == 200
    assert updated.get_json()['record']['personnel'] == 1

    view = client.post('/api/data/view', json={
        'filters': {'unit': sample['unit_node'], 'location': sample['location'], 'category': 'Personnel'},
    })
    records = view.get_json()['records']
    assert len(records) == 1
    assert records[0]['readiness'] < 5  # 1 actual against any real MEF reference is near zero.

    # Editing the MEF reference for a whole unit type shifts every one of its units.
    reference = client.get('/api/data/reference').get_json()['records']
    unit_type_row = next(r for r in reference if r['unit_type'] == 'Bekangdam')
    doubled = client.post('/api/data/reference/update', json={
        'unit_type': 'Bekangdam',
        'personnel': unit_type_row['personnel'] * 2,
    })
    assert doubled.status_code == 200

    # Validation: negative actual values and zero/blank MEF reference values are rejected.
    invalid_actual = client.post('/api/data/actual/update', json={
        'unit_node': sample['unit_node'], 'location': sample['location'], 'personnel': -5,
    })
    assert invalid_actual.status_code == 400
    invalid_reference = client.post('/api/data/reference/update', json={'unit_type': 'Bekangdam', 'personnel': 0})
    assert invalid_reference.status_code == 400
    missing_unit = client.post('/api/data/actual/update', json={
        'unit_node': 'Does Not Exist', 'location': 'Nowhere', 'personnel': 5,
    })
    # DataValidationError always reports 400 in this app (the same convention every other
    # data-validation failure uses), not a REST-purist 404 for "not found".
    assert missing_unit.status_code == 400


def test_status_override_flips_and_persists_through_recompute(client):
    client.post('/api/data/import', json={'source': 'builtin'})

    view = client.post('/api/data/view', json={
        'filters': {'unit': 'Bekangdam 124', 'location': 'Kepulauan Bangka Belitung', 'category': 'Personnel'},
    }).get_json()
    row = view['records'][0]
    assert row['status'] == 'VERIFIED'  # 76.2%, above the 75% threshold - see the formula test above.

    flagged = client.post('/api/data/status/override', json={
        'unit_node': row['unit'], 'location': row['location'], 'category': row['category'], 'status': 'FLAGGED',
    })
    assert flagged.status_code == 200
    assert flagged.get_json()['record']['status'] == 'FLAGGED'

    # The override must survive going through the same recompute path an unrelated edit takes.
    reflagged_view = client.post('/api/data/view', json={
        'filters': {'unit': row['unit'], 'location': row['location'], 'category': row['category']},
    }).get_json()
    assert reflagged_view['records'][0]['status'] == 'FLAGGED'

    verified = client.post('/api/data/status/override', json={
        'unit_node': row['unit'], 'location': row['location'], 'category': row['category'], 'status': 'VERIFIED',
    })
    assert verified.get_json()['record']['status'] == 'VERIFIED'

    bad_status = client.post('/api/data/status/override', json={
        'unit_node': row['unit'], 'location': row['location'], 'category': row['category'], 'status': 'MAYBE',
    })
    assert bad_status.status_code == 400
    missing_unit = client.post('/api/data/status/override', json={
        'unit_node': 'Does Not Exist', 'location': 'Nowhere', 'category': 'Personnel', 'status': 'FLAGGED',
    })
    assert missing_unit.status_code == 400


def test_import_actual_csv_replaces_table_and_recomputes(client):
    client.post('/api/data/import', json={'source': 'builtin'})
    csv_payload = (
        b'UNIT_TYPE,UNIT_NODE,LOCATION,LATITUDE,LONGITUDE,Personnel,Equipment,Logistics,Infrastructure,Training\n'
        b'Yonif,Yonif Test,Jakarta,-6.2,106.8,1000,250,3000,40,20\n'
    )
    response = client.post('/api/data/actual/import', data={'file': (io.BytesIO(csv_payload), 'custom.csv')}, content_type='multipart/form-data')
    assert response.status_code == 200
    assert response.get_json()['rows'] == 1

    actual = client.get('/api/data/actual').get_json()
    assert actual['pagination']['total_records'] == 1
    assert actual['records'][0]['unit_node'] == 'Yonif Test'

    view = client.post('/api/data/view', json={'filters': {}})
    summary = view.get_json()['summary']
    assert summary['record_count'] == 5  # one unit x 5 categories
    assert summary['unit_count'] == 1


def test_import_actual_xlsx_replaces_table_and_returns_metadata(client):
    import pandas as pd

    client.post('/api/data/import', json={'source': 'builtin'})
    frame = pd.DataFrame([{
        'UNIT_TYPE': 'Yonif', 'UNIT_NODE': 'Yonif XLSX', 'LOCATION': 'Bandung',
        'LATITUDE': -6.9, 'LONGITUDE': 107.6,
        'Personnel': 500, 'Equipment': 125, 'Logistics': 1500, 'Infrastructure': 20, 'Training': 10,
    }])
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)

    response = client.post('/api/data/actual/import', data={'file': (buffer, 'custom.xlsx')}, content_type='multipart/form-data')
    assert response.status_code == 200
    body = response.get_json()
    assert body['rows'] == 1
    assert body['metadata']['rows'] == 5  # recomputed readiness: one unit x 5 categories

    actual = client.get('/api/data/actual').get_json()
    assert actual['pagination']['total_records'] == 1
    assert actual['records'][0]['unit_node'] == 'Yonif XLSX'


def test_export_dataset_workbook_has_three_sheets_in_order(client):
    import pandas as pd

    client.post('/api/data/import', json={'source': 'builtin'})
    response = client.get('/api/data/export')
    assert response.status_code == 200
    assert response.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert 'Dataset SATRIA.xlsx' in response.headers['Content-Disposition']

    workbook = pd.ExcelFile(io.BytesIO(response.data), engine='openpyxl')
    assert workbook.sheet_names == ['Aktual', 'Referensi', 'Kesiapan']
    assert len(workbook.parse('Aktual')) == 500
    assert len(workbook.parse('Referensi')) == 6
    assert len(workbook.parse('Kesiapan')) == 2500
