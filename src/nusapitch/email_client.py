from __future__ import annotations

import imaplib
import os
import smtplib
import sqlite3
import time
from email.message import EmailMessage
from email.utils import formatdate, getaddresses, make_msgid

from .imports import normalize_domain


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
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=normalize_domain(sender) or None)
    msg.set_content(body)
    return msg


def send_smtp(account: sqlite3.Row, message: EmailMessage) -> tuple[str, str]:
    password = os.getenv(account["password_env_name"], "")
    if not password:
        raise ValueError(f"Missing password environment variable: {account['password_env_name']}")

    recipients = [
        email
        for _, email in getaddresses(
            message.get_all("to", []) + message.get_all("cc", []) + message.get_all("bcc", [])
        )
        if email
    ]
    if not recipients:
        raise ValueError("No email recipients found")

    if account["smtp_security"].upper() == "SSL":
        server = smtplib.SMTP_SSL(account["smtp_host"], int(account["smtp_port"]), timeout=30)
    else:
        server = smtplib.SMTP(account["smtp_host"], int(account["smtp_port"]), timeout=30)
        if account["smtp_security"].upper() == "STARTTLS":
            server.starttls()

    with server:
        server.login(account["sender_email"], password)
        refused = server.send_message(message, from_addr=account["sender_email"], to_addrs=recipients)

    message_id = str(message["Message-ID"])
    if refused:
        return message_id, f"Partial SMTP refusal: {refused}"
    return message_id, "SMTP send accepted"


def save_to_sent(account: sqlite3.Row, message: EmailMessage) -> str:
    password = os.getenv(account["password_env_name"], "")
    if not password:
        raise ValueError(f"Missing password environment variable: {account['password_env_name']}")
    if account["imap_security"].upper() != "SSL":
        raise ValueError("Only IMAP SSL is supported in v1.")

    with imaplib.IMAP4_SSL(account["imap_host"], int(account["imap_port"])) as client:
        client.login(account["sender_email"], password)
        status, _ = client.append(
            account["sent_folder_name"],
            None,
            imaplib.Time2Internaldate(time.time()),
            message.as_bytes(),
        )
    if status != "OK":
        raise ValueError(f"IMAP append returned {status}")
    return "Saved to IMAP Sent"
