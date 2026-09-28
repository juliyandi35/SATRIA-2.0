from __future__ import annotations

import mimetypes
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def email_configuration_status() -> dict[str, object]:
    configured = bool(os.getenv("SMTP_USERNAME") and os.getenv("SMTP_PASSWORD"))
    return {
        "configured": configured,
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "465")),
        "sender_configured": bool(os.getenv("SMTP_FROM") or os.getenv("SMTP_USERNAME")),
    }


def send_email_tool(
    to_email: str,
    subject: str,
    body: str,
    *,
    attachment: tuple[bytes, str] | None = None,
) -> str:
    """Send an email only when SMTP credentials are explicitly configured.

    attachment, if given, is (content_bytes, filename); its MIME type is guessed from the filename.
    """
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", username or "")
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "465"))
    if not username or not password or not sender:
        raise RuntimeError("Layanan email belum dikonfigurasi melalui environment variables.")
    if "@" not in to_email or len(to_email) > 254:
        raise ValueError("Alamat email penerima tidak valid.")

    if attachment:
        content, filename = attachment
        guessed_type, _ = mimetypes.guess_type(filename)
        maintype, subtype = (guessed_type or "application/octet-stream").split("/", 1)
        message = MIMEMultipart()
        message.attach(MIMEText(body, "plain", "utf-8"))
        part = MIMEBase(maintype, subtype)
        part.set_payload(content)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        message.attach(part)
    else:
        message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to_email
    try:
        with smtplib.SMTP_SSL(host, port, timeout=15) as server:
            server.login(username, password)
            server.sendmail(sender, [to_email], message.as_string())
    except smtplib.SMTPException as exc:
        raise RuntimeError(f"Gagal mengirim email: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"Gagal terhubung ke server SMTP {host}:{port}: {exc}") from exc
    return "Email berhasil dikirim."
