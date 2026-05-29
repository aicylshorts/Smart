"""
SMC TRADING SYSTEM - TELEGRAM BOT
==================================
Sends concise trading signals and daily summaries.
No emojis to avoid encoding issues.
"""
import requests
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import pytz

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TIMEOUT, TIMEZONE_WAT

class TelegramBot:
    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.base_url = "https://api.telegram.org/bot" + self.token

    def _send_message(self, text: str) -> bool:
        if not self.token or not self.chat_id:
            print("Telegram credentials not configured")
            return False

        url = self.base_url + "/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        try:
            response = requests.post(url, json=payload, timeout=TELEGRAM_TIMEOUT)
            if response.status_code == 200:
                return True
            else:
                print("Telegram Error: " + str(response.status_code) + " - " + response.text)
                return False
        except Exception as e:
            print("Telegram Send Error: " + str(e))
            return False

    def send_signal(self, setup: Dict[str, Any]) -> bool:
        direction = setup["direction"]
        grade = setup["grade"]
        prob = setup["probability"]
        instrument = setup["instrument"]
        entry = setup["entry_price"]
        sl = setup["stop_loss"]
        tps = setup["take_profits"]
        notes = setup.get("notes", "")

        wat = pytz.timezone(TIMEZONE_WAT)
        now_wat = datetime.now(wat)
        time_str = now_wat.strftime("%H:%M WAT")

        lines = [
            "<b>SMC SIGNAL - " + grade + "</b>",
            "",
            "Instrument: " + instrument,
            "Direction: " + direction,
            "Probability: " + str(prob) + "%",
            "Time: " + time_str,
            "",
            "Entry: " + str(entry),
            "SL: " + str(sl),
            "",
        ]

        for tp in tps:
            label = tp["label"]
            price = tp["level"]
            rr = tp["rr"]
            prob_tp = tp["probability"]
            size = int(tp["size_pct"] * 100)
            lines.append(label + ": " + str(price) + " (RR:" + str(rr) + ", Prob:" + str(prob_tp) + "%, Size:" + str(size) + "%)")

        if notes:
            lines.append("")
            lines.append("Notes: " + notes)

        lines.append("")
        lines.append("Risk max 1-2%. Manage your trade.")

        message = "\n".join(lines)
        return self._send_message(message)

    def send_daily_summary(self, summary: Dict[str, Any]) -> bool:
        date_str = summary["date"]
        total = summary["total"]
        a_count = summary["a_count"]
        a_plus_count = summary["a_plus_count"]
        buy_count = summary["buy_count"]
        sell_count = summary["sell_count"]
        instruments = summary["instruments"]

        lines = [
            "<b>DAILY SMC SUMMARY</b>",
            "Date: " + date_str,
            "",
            "Total Signals: " + str(total),
            "A Grade: " + str(a_count),
            "A+ Grade: " + str(a_plus_count),
            "Buy Signals: " + str(buy_count),
            "Sell Signals: " + str(sell_count),
            "",
        ]

        if instruments:
            lines.append("Instruments: " + ", ".join(instruments))
        else:
            lines.append("No signals generated today.")

        lines.append("")
        lines.append("Markets closed or low probability conditions.")
        lines.append("Ready for tomorrow.")

        message = "\n".join(lines)
        return self._send_message(message)

    def send_system_status(self, status: str, details: str = "") -> bool:
        message = "<b>SMC SYSTEM</b>\n\nStatus: " + status
        if details:
            message += "\n" + details
        return self._send_message(message)

telegram = TelegramBot()
