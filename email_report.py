#!/usr/bin/env python3.13
"""Send a daily portfolio report email using the saved history."""

from __future__ import annotations

import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pandas as pd

# Update these values before running.
SENDER_EMAIL = "you@example.com"
RECEIVER_EMAIL = "you@example.com"
EMAIL_PASSWORD = "your-app-password"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

HISTORY_PATH = Path("history.csv")


def load_history() -> pd.DataFrame:
    if not HISTORY_PATH.exists():
        raise FileNotFoundError(
            f"{HISTORY_PATH} is missing. Run main.py to generate portfolio history."
        )
    df = pd.read_csv(HISTORY_PATH)
    if df.empty:
        raise ValueError("history.csv has no data to report.")
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values("date", inplace=True)
    return df


def format_report(df: pd.DataFrame) -> str:
    """Build the email body with latest totals and recent history."""
    today = date.today().isoformat()
    if (df["date"] == pd.to_datetime(today)).any():
        latest = df[df["date"] == pd.to_datetime(today)].iloc[-1]
    else:
        latest = df.iloc[-1]

    recent = df.tail(5).copy()
    recent["date"] = recent["date"].dt.strftime("%Y-%m-%d")
    recent["total_usd"] = recent["total_usd"].map(lambda v: f"{v:,.2f}")
    recent["total_twd"] = recent["total_twd"].map(lambda v: f"{v:,.2f}")
    recent["daily_return_pct"] = recent["daily_return_pct"].map(lambda v: f"{v:.2f}%")

    lines = [
        f"Portfolio Summary for {latest['date'].strftime('%Y-%m-%d')}",
        "",
        f"Total USD: ${latest['total_usd']:,.2f}",
        f"Total TWD: NT${latest['total_twd']:,.2f}",
        f"Daily Return: {latest['daily_return_pct']:.2f}%",
        "",
        "Recent History (last 5 records):",
    ]

    lines.append(recent.to_string(index=False))
    return "\n".join(lines)


def send_email(body: str) -> None:
    """Send the email via SMTP with TLS."""
    message = MIMEMultipart()
    message["From"] = SENDER_EMAIL
    message["To"] = RECEIVER_EMAIL
    message["Subject"] = "Daily Portfolio Report"
    message.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, EMAIL_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())


def main() -> None:
    df = load_history()
    body = format_report(df)
    send_email(body)
    print("Daily report sent successfully.")


if __name__ == "__main__":
    main()
