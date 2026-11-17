import json
import logging
import os
import smtplib
import sqlite3
import time
from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from broker import QUEUE, connect, publish


def send(msg):
    due = datetime.fromtimestamp(msg["due"], ZoneInfo("America/Sao_Paulo"))
    mail = EmailMessage()
    mail["From"] = "lembretes@example.test"
    mail["To"] = msg["email"]
    mail["Subject"] = "Lembrete de tarefa pendente no Moodle"
    mail.set_content(f"Olá! A tarefa {msg['task']} está pendente.\n"
                     f"Prazo: {due:%d/%m/%Y às %H:%M} (horário de Brasília).\n"
                     f"Acesse: {msg['url']}\n")
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"]), timeout=8) as smtp:
        smtp.send_message(mail)


def open_db(path):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS envios (id TEXT PRIMARY KEY, enviado INTEGER NOT NULL)")
    return db


def process(db, msg, sender, now):
    if db.execute("SELECT 1 FROM envios WHERE id=?", (msg["id"],)).fetchone():
        return "duplicado"
    if msg["due"] <= now:
        return "vencido"
    sender(msg)
    with db:
        db.execute("INSERT INTO envios VALUES (?, ?)", (msg["id"], now))
    return "enviado"


def handle(db, channel, method, props, body, sender=send):
    attempt = int((props.headers or {}).get("attempt", 1))
    try:
        msg = json.loads(body)
        if not isinstance(msg["due"], int) or not all(
            isinstance(msg[key], str) and msg[key] for key in ("id", "email", "task", "url")
        ):
            raise ValueError("Evento inválido")
    except (ValueError, TypeError, KeyError):
        logging.warning("Evento inválido enviado para fila de falhas")
        publish(channel, QUEUE + ".falhas", body, attempt)
    else:
        try:
            result = process(db, msg, sender, int(time.time()))
        except (OSError, smtplib.SMTPException) as exc:
            logging.warning("Falha SMTP: id=%s tentativa=%s tipo=%s detalhe=%s", msg["id"], attempt, type(exc).__name__, exc)
            queue = QUEUE + (".retry" if attempt < 3 else ".falhas")
            publish(channel, queue, body, attempt + 1 if attempt < 3 else attempt)
        else:
            logging.info("id=%s tentativa=%s resultado=%s", msg["id"], attempt, result)
    channel.basic_ack(method.delivery_tag)


def main():
    logging.basicConfig(level=logging.INFO)
    db = open_db(os.environ["DB_PATH"])
    conn, channel = connect()
    try:
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(QUEUE, lambda ch, method, props, body: handle(db, ch, method, props, body))
        channel.start_consuming()
    finally:
        db.close()
        if conn.is_open:
            conn.close()


if __name__ == "__main__":
    main()
