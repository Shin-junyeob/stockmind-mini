"""
notify.py - 오늘 예측 결과를 Gmail로 전송

실행: PYTHONPATH=src python src/notify.py
환경변수: GMAIL_USER, GMAIL_APP_PASSWORD, NOTIFY_EMAIL
"""

import logging
import os
import smtplib
import sys
from datetime import date
from email.message import EmailMessage

from dotenv import load_dotenv
load_dotenv()

from db.writer import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

GMAIL_USER        = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL      = os.getenv("NOTIFY_EMAIL", GMAIL_USER)


def fetch_today_predictions() -> list[dict]:
    """오늘 prediction_logs에서 예측 결과 조회."""
    today = date.today().isoformat()
    sql = f"""
        SELECT ticker, prediction_date, direction, up_probability,
               proba_a, proba_b, proba_c, threshold_used
        FROM prediction_logs
        WHERE prediction_date = '{today}'
        ORDER BY ticker
    """
    with engine.connect() as conn:
        from sqlalchemy import text
        rows = conn.execute(text(sql)).fetchall()
    return [dict(row._mapping) for row in rows]


def build_email_body(predictions: list[dict]) -> str:
    today = date.today().isoformat()
    lines = [f"📈 Stockmind Mini 예측 결과 — {today}\n"]

    for p in predictions:
        arrow    = "▲ UP  " if p["direction"] == "up" else "▼ DOWN"
        prob_pct = round(p["up_probability"] * 100, 1)
        lines.append(
            f"{p['ticker']:<14} {arrow}  "
            f"up_prob={prob_pct}%  threshold={p['threshold_used']}"
        )
        lines.append(
            f"{'':14}   A={round(p['proba_a']*100,1)}%  "
            f"B={round(p['proba_b']*100,1)}%  "
            f"C={round(p['proba_c']*100,1)}%"
        )
        lines.append("")

    lines.append("* 본 메일은 자동 발송됩니다. 투자 판단의 책임은 본인에게 있습니다.")
    return "\n".join(lines)


def send_email(subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = NOTIFY_EMAIL
    msg.set_content(body)

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)

    logger.info(f"이메일 전송 완료 → {NOTIFY_EMAIL}")


def run_notify() -> None:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        logger.warning("GMAIL_USER 또는 GMAIL_APP_PASSWORD 미설정 — 스킵")
        return

    predictions = fetch_today_predictions()
    if not predictions:
        logger.warning("오늘 예측 결과 없음 — 스킵")
        return

    today   = date.today().isoformat()
    subject = f"[Stockmind] {today} 예측 결과"
    body    = build_email_body(predictions)

    send_email(subject, body)


if __name__ == "__main__":
    run_notify()
