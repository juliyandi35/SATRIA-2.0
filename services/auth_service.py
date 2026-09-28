from __future__ import annotations

import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyotp
from werkzeug.security import check_password_hash, generate_password_hash

_LOCK = threading.RLock()
_FAILED_ATTEMPTS: dict[str, list[float]] = {}
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300


class AuthError(ValueError):
    """A login/setup error safe to show in the interface, with an HTTP status to report."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _migrate_legacy_single_account_schema(connection: sqlite3.Connection) -> None:
    """Early SATRIA databases pinned users.id to 1 (CHECK id = 1) - back when exactly one
    account could ever exist. Rebuild the table without that constraint, once, keeping the
    existing account's data intact, so multiple accounts can be added."""
    row = connection.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'").fetchone()
    if row is None or "CHECK" not in (row[0] or ""):
        return
    connection.execute(
        """CREATE TABLE users_migrated (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            totp_secret TEXT NOT NULL,
            mfa_enabled INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )"""
    )
    connection.execute(
        "INSERT INTO users_migrated (email, password_hash, totp_secret, mfa_enabled, created_at) "
        "SELECT email, password_hash, totp_secret, mfa_enabled, created_at FROM users"
    )
    connection.execute("DROP TABLE users")
    connection.execute("ALTER TABLE users_migrated RENAME TO users")
    connection.commit()


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path, timeout=5)
    connection.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            totp_secret TEXT NOT NULL,
            mfa_enabled INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )"""
    )
    connection.execute("CREATE TABLE IF NOT EXISTS app_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    _migrate_legacy_single_account_schema(connection)
    return connection


def get_secret_key(db_path: Path) -> str:
    """Return the Flask session-signing key, generating and persisting one on first run."""
    with _LOCK:
        connection = _connect(db_path)
        try:
            row = connection.execute("SELECT value FROM app_config WHERE key = 'secret_key'").fetchone()
            if row:
                return row[0]
            key = secrets.token_hex(32)
            connection.execute("INSERT INTO app_config (key, value) VALUES ('secret_key', ?)", (key,))
            connection.commit()
            return key
        finally:
            connection.close()


def account_status(db_path: Path) -> dict[str, Any]:
    """Whether any account exists yet - used only to decide between the first-run bootstrap
    screen and the normal login screen, so it deliberately says nothing about which account."""
    with _LOCK:
        connection = _connect(db_path)
        try:
            exists = connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None
        finally:
            connection.close()
    return {"configured": exists}


def list_accounts(db_path: Path) -> list[dict[str, Any]]:
    with _LOCK:
        connection = _connect(db_path)
        try:
            rows = connection.execute(
                "SELECT email, mfa_enabled, created_at FROM users ORDER BY created_at"
            ).fetchall()
        finally:
            connection.close()
    return [{"email": row[0], "mfa_enabled": bool(row[1]), "created_at": row[2]} for row in rows]


def _validate_email(email: str) -> str:
    email = str(email).strip().lower()
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise AuthError("Alamat e-mail tidak valid.")
    return email


def _validate_password(password: str) -> str:
    if len(password) < 10:
        raise AuthError("Kata sandi minimal 10 karakter.")
    return password


def _insert_account(connection: sqlite3.Connection, email: str, password: str) -> str:
    secret = pyotp.random_base32()
    try:
        connection.execute(
            "INSERT INTO users (email, password_hash, totp_secret, mfa_enabled, created_at) VALUES (?, ?, ?, 0, ?)",
            (email, generate_password_hash(password), secret, datetime.now(timezone.utc).isoformat()),
        )
    except sqlite3.IntegrityError:
        raise AuthError("E-mail tersebut sudah terdaftar.", 409) from None
    connection.commit()
    return secret


def create_account(db_path: Path, email: str, password: str) -> dict[str, Any]:
    """First-run bootstrap only: with zero accounts in the database, anyone reaching this
    endpoint may create the first one. Once an account exists, further accounts can only be
    added by an already-authenticated operator via add_account - never anonymously."""
    email = _validate_email(email)
    _validate_password(password)

    with _LOCK:
        connection = _connect(db_path)
        try:
            if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise AuthError("Sudah ada akun terdaftar. Masuk lalu tambahkan akun baru dari menu Kendali sistem.", 409)
            secret = _insert_account(connection, email, password)
        finally:
            connection.close()

    uri = pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="SATRIA 2.0")
    return {"email": email, "totp_secret": secret, "provisioning_uri": uri}


def add_account(db_path: Path, requester_email: str, requester_password: str, new_email: str, new_password: str) -> dict[str, Any]:
    """An authenticated operator provisions a teammate's account. The new account starts with
    MFA disabled - the teammate completes their own enrollment via enroll_mfa using the secret
    shared with them here, exactly like the first-run bootstrap flow."""
    new_email = _validate_email(new_email)
    _validate_password(new_password)
    with _LOCK:
        connection = _connect(db_path)
        try:
            requester = _find_by_email(connection, requester_email)
            if not check_password_hash(requester[1], requester_password):
                raise AuthError("Kata sandi saat ini salah.", 401)
            secret = _insert_account(connection, new_email, new_password)
        finally:
            connection.close()

    uri = pyotp.TOTP(secret).provisioning_uri(name=new_email, issuer_name="SATRIA 2.0")
    return {"email": new_email, "totp_secret": secret, "provisioning_uri": uri}


def remove_account(db_path: Path, requester_email: str, requester_password: str, target_email: str) -> None:
    """The last remaining account can never be removed, to avoid permanently locking everyone
    out of the command center - delete the whole database instead if that is truly the intent."""
    target_email = str(target_email).strip().lower()
    with _LOCK:
        connection = _connect(db_path)
        try:
            requester = _find_by_email(connection, requester_email)
            if not check_password_hash(requester[1], requester_password):
                raise AuthError("Kata sandi saat ini salah.", 401)
            if not connection.execute("SELECT 1 FROM users WHERE email = ?", (target_email,)).fetchone():
                raise AuthError("Akun tidak ditemukan.", 404)
            total = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if total <= 1:
                raise AuthError("Tidak dapat menghapus satu-satunya akun yang tersisa.", 409)
            connection.execute("DELETE FROM users WHERE email = ?", (target_email,))
            connection.commit()
        finally:
            connection.close()
    _FAILED_ATTEMPTS.pop(target_email, None)


def enroll_mfa(db_path: Path, email: str, code: str) -> None:
    """Finish setup: the account only becomes usable once one real TOTP code is verified,
    proving the authenticator app was actually enrolled - MFA here is mandatory, not optional."""
    email = str(email).strip().lower()
    with _LOCK:
        connection = _connect(db_path)
        try:
            row = connection.execute(
                "SELECT email, totp_secret, mfa_enabled FROM users WHERE email = ?", (email,)
            ).fetchone()
            if row is None:
                raise AuthError("Akun tidak ditemukan.", 404)
            if row[2]:
                raise AuthError("MFA sudah aktif untuk akun ini.", 409)
            if not pyotp.TOTP(row[1]).verify(str(code).strip(), valid_window=1):
                raise AuthError("Kode verifikasi salah atau kedaluwarsa.")
            connection.execute("UPDATE users SET mfa_enabled = 1 WHERE email = ?", (email,))
            connection.commit()
        finally:
            connection.close()


def _check_lockout(email: str) -> None:
    now = time.monotonic()
    attempts = [attempt for attempt in _FAILED_ATTEMPTS.get(email, []) if now - attempt < LOCKOUT_SECONDS]
    _FAILED_ATTEMPTS[email] = attempts
    if len(attempts) >= MAX_ATTEMPTS:
        raise AuthError("Terlalu banyak percobaan gagal. Coba lagi dalam beberapa menit.", 429)


def authenticate(db_path: Path, email: str, password: str, totp_code: str) -> dict[str, Any]:
    """Password (knowledge factor) and TOTP code (possession factor) are required together -
    genuine multi-factor authentication, not a password check with an optional extra step."""
    email = str(email).strip().lower()
    with _LOCK:
        _check_lockout(email)
        connection = _connect(db_path)
        try:
            row = connection.execute(
                "SELECT email, password_hash, totp_secret, mfa_enabled FROM users WHERE email = ?", (email,)
            ).fetchone()
        finally:
            connection.close()

        valid = bool(row) and check_password_hash(row[1], password)
        if valid and row[3]:
            valid = bool(totp_code) and pyotp.TOTP(row[2]).verify(str(totp_code).strip(), valid_window=1)
        elif valid and not row[3]:
            raise AuthError("Penyiapan MFA belum selesai. Selesaikan pendaftaran verifikator terlebih dahulu.", 409)

        if not valid:
            _register_failure(email)
            raise AuthError("E-mail, kata sandi, atau kode verifikasi salah.", 401)

        _FAILED_ATTEMPTS.pop(email, None)
        return {"email": row[0]}


def _register_failure(email: str) -> None:
    _FAILED_ATTEMPTS.setdefault(email, []).append(time.monotonic())


def _find_by_email(connection: sqlite3.Connection, email: str) -> tuple[str, str, str, int]:
    row = connection.execute(
        "SELECT email, password_hash, totp_secret, mfa_enabled FROM users WHERE email = ?",
        (str(email).strip().lower(),),
    ).fetchone()
    if row is None:
        raise AuthError("Akun tidak ditemukan.", 404)
    return row


def change_password(db_path: Path, email: str, current_password: str, new_password: str) -> None:
    """Requires the current password - proves the caller is the account owner, not just an
    already-open session, before a new credential can be set."""
    _validate_password(new_password)
    with _LOCK:
        connection = _connect(db_path)
        try:
            row = _find_by_email(connection, email)
            if not check_password_hash(row[1], current_password):
                raise AuthError("Kata sandi saat ini salah.", 401)
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE email = ?",
                (generate_password_hash(new_password), row[0]),
            )
            connection.commit()
        finally:
            connection.close()


def change_email(db_path: Path, email: str, current_password: str, new_email: str) -> str:
    """Requires the current password for the same reason as change_password."""
    new_email = _validate_email(new_email)
    with _LOCK:
        connection = _connect(db_path)
        try:
            row = _find_by_email(connection, email)
            if not check_password_hash(row[1], current_password):
                raise AuthError("Kata sandi saat ini salah.", 401)
            try:
                connection.execute("UPDATE users SET email = ? WHERE email = ?", (new_email, row[0]))
            except sqlite3.IntegrityError:
                raise AuthError("E-mail tersebut sudah dipakai akun lain.", 409) from None
            connection.commit()
        finally:
            connection.close()
    return new_email
