from __future__ import annotations

import imaplib
import os
import smtplib
import sqlite3
from email.message import EmailMessage


def test_smtp(account: sqlite3.Row) -> tuple[bool, str]:
    password = os.getenv(account["password_env_name"], "")
    if not password:
        return False, f"Missing password environment variable: {account['password_env_name']}"
    try:
        if account["smtp_security"].upper() == "SSL":
            server = smtplib.SMTP_SSL(account["smtp_host"], int(account["smtp_port"]), timeout=20)
        else:
            server = smtplib.SMTP(account["smtp_host"], int(account["smtp_port"]), timeout=20)
            if account["smtp_security"].upper() == "STARTTLS":
                server.starttls()
        with server:
            server.login(account["sender_email"], password)
        return True, "SMTP login succeeded."
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def test_imap(account: sqlite3.Row) -> tuple[bool, str]:
    password = os.getenv(account["password_env_name"], "")
    if not password:
        return False, f"Missing password environment variable: {account['password_env_name']}"
    try:
        if account["imap_security"].upper() != "SSL":
            return False, "Only IMAP SSL is supported in v1."
        with imaplib.IMAP4_SSL(account["imap_host"], int(account["imap_port"])) as client:
            client.login(account["sender_email"], password)
            client.select(account["inbox_folder_name"])
        return True, "IMAP login succeeded."
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def build_message(sender: str, recipient: str, subject: str, body: str, bcc: str = "") -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    if bcc:
        msg["Bcc"] = bcc
    msg["Subject"] = subject
    msg.set_content(body)
    return msg
