"""The /api/auth/* routes, as a Flask Blueprint - split out of app.py purely to keep that
file's line count sane as the auth surface grew (setup, MFA enrollment, login, account
settings, add/remove account). AuthError is handled by the app-level error handler
registered in app.py, which applies across all blueprints, so routes here just raise it."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request, session

from services.auth_service import (
    account_status,
    add_account,
    authenticate,
    change_email,
    change_password,
    create_account,
    enroll_mfa,
    list_accounts,
    remove_account,
)

AUTH_EXEMPT_PATHS = {
    "/api/auth/status",
    "/api/auth/setup",
    "/api/auth/mfa/enroll",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/session",
}


def _payload() -> dict[str, Any]:
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else {}


def build_auth_blueprint(auth_db_path: Path) -> Blueprint:
    audit = logging.getLogger("satria.audit")
    bp = Blueprint("auth", __name__, url_prefix="/api/auth")

    @bp.get("/status")
    def auth_status():
        return jsonify(account_status(auth_db_path))

    @bp.get("/session")
    def auth_session():
        return jsonify({"authenticated": bool(session.get("authenticated")), "email": session.get("email")})

    @bp.post("/setup")
    def auth_setup():
        payload = _payload()
        result = create_account(auth_db_path, str(payload.get("email", "")), str(payload.get("password", "")))
        audit.info("AUTH SETUP email=%s", result["email"])
        return jsonify({"status": "success", **result})

    @bp.post("/mfa/enroll")
    def auth_mfa_enroll():
        payload = _payload()
        email = str(payload.get("email", "")).strip().lower()
        enroll_mfa(auth_db_path, email, str(payload.get("code", "")))
        # Only log the caller in as the enrolled account when they weren't already signed in
        # (first-run setup, or a teammate finishing enrollment from the login screen). An
        # already-authenticated admin completing a teammate's enrollment from account
        # management keeps their own session - enrolling someone else must not hijack it.
        if not session.get("authenticated"):
            session["authenticated"] = True
            session["email"] = email
            # "Ingat saya" on the login screen: unchecked (default) leaves the session cookie
            # non-permanent, so it expires the moment the browser closes and the app always
            # demands a fresh login. Checked makes it survive a browser restart.
            session.permanent = bool(payload.get("remember", False))
        audit.info("AUTH MFA ENROLLED email=%s", email)
        return jsonify({"status": "success", "email": email})

    @bp.post("/login")
    def auth_login():
        payload = _payload()
        result = authenticate(
            auth_db_path,
            str(payload.get("email", "")),
            str(payload.get("password", "")),
            str(payload.get("totp_code", "")),
        )
        session["authenticated"] = True
        session["email"] = result["email"]
        session.permanent = bool(payload.get("remember", False))
        audit.info("AUTH LOGIN email=%s", result["email"])
        return jsonify({"status": "success", "email": result["email"]})

    @bp.post("/logout")
    def auth_logout():
        email = session.get("email")
        session.clear()
        if email:
            audit.info("AUTH LOGOUT email=%s", email)
        return jsonify({"status": "success"})

    @bp.post("/change-password")
    def auth_change_password():
        payload = _payload()
        change_password(
            auth_db_path,
            str(session.get("email", "")),
            str(payload.get("current_password", "")),
            str(payload.get("new_password", "")),
        )
        audit.info("AUTH PASSWORD CHANGED email=%s", session.get("email"))
        return jsonify({"status": "success"})

    @bp.post("/change-email")
    def auth_change_email():
        payload = _payload()
        new_email = change_email(
            auth_db_path,
            str(session.get("email", "")),
            str(payload.get("current_password", "")),
            str(payload.get("new_email", "")),
        )
        session["email"] = new_email
        audit.info("AUTH EMAIL CHANGED email=%s", new_email)
        return jsonify({"status": "success", "email": new_email})

    @bp.get("/accounts")
    def auth_accounts():
        return jsonify({"accounts": list_accounts(auth_db_path)})

    @bp.post("/accounts/add")
    def auth_accounts_add():
        payload = _payload()
        result = add_account(
            auth_db_path,
            str(session.get("email", "")),
            str(payload.get("current_password", "")),
            str(payload.get("new_email", "")),
            str(payload.get("new_password", "")),
        )
        audit.info("AUTH ACCOUNT ADDED by=%s new_email=%s", session.get("email"), result["email"])
        return jsonify({"status": "success", **result})

    @bp.post("/accounts/remove")
    def auth_accounts_remove():
        payload = _payload()
        target_email = str(payload.get("target_email", ""))
        remove_account(auth_db_path, str(session.get("email", "")), str(payload.get("current_password", "")), target_email)
        audit.info("AUTH ACCOUNT REMOVED by=%s target_email=%s", session.get("email"), target_email)
        removed_self = target_email.strip().lower() == str(session.get("email", "")).strip().lower()
        if removed_self:
            session.clear()
        return jsonify({"status": "success", "removed_self": removed_self})

    return bp
