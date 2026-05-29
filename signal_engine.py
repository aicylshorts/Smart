"""
SMC TRADING SYSTEM - SIGNAL ENGINE
===================================
Orchestrates data fetching, SMC analysis, and signal generation.
"""
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import traceback

from config import (
    OANDA_INSTRUMENTS, BINANCE_SYMBOLS, CRYPTO_DISPLAY_NAMES,
    MIN_PROBABILITY, SIGNAL_COOLDOWN_HOURS, SCAN_INTERVAL_MINUTES
)
from database import db
from oanda_client import oanda
from binance_client import binance
from smc_analyzer import SMCAnalyzer, Setup
from news_filter import news_filter
from telegram_bot import telegram

class SignalEngine:
    def __init__(self):
        self.oanda = oanda
        self.binance = binance
        self.processed_count = 0
        self.error_count = 0

    def analyze_oanda_instrument(self, instrument: str) -> Optional[Setup]:
        try:
            data = self.oanda.get_all_timeframes(instrument)

            if not data or "LTF" not in data:
                return None

            ltf_df = data["LTF"]
            htf_df = data.get("HTF")

            if ltf_df is None or len(ltf_df) < 50:
                return None

            analyzer = SMCAnalyzer(ltf_df)
            setup = analyzer.generate_setup(instrument, "LTF")

            if setup and htf_df is not None and len(htf_df) > 30:
                htf_analyzer = SMCAnalyzer(htf_df)
                htf_swing_highs, htf_swing_lows = htf_analyzer.find_swing_points()
                htf_structure = htf_analyzer.analyze_structure(htf_swing_highs, htf_swing_lows)
                htf_trend = htf_structure.get("trend")

                if htf_trend and htf_trend.value != setup.direction.value and htf_trend.value != "NEUTRAL":
                    setup.probability = max(MIN_PROBABILITY, setup.probability - 15)
                    if setup.probability < MIN_PROBABILITY:
                        return None
                    setup.notes += " | Counter HTF trend"

            return setup

        except Exception as e:
            print("Error analyzing " + instrument + ": " + str(e))
            self.error_count += 1
            return None

    def analyze_binance_symbol(self, symbol: str) -> Optional[Setup]:
        try:
            data = self.binance.get_all_timeframes(symbol)

            if not data or "LTF" not in data:
                return None

            ltf_df = data["LTF"]
            if ltf_df is None or len(ltf_df) < 50:
                return None

            display_name = CRYPTO_DISPLAY_NAMES.get(symbol, symbol)

            analyzer = SMCAnalyzer(ltf_df)
            setup = analyzer.generate_setup(display_name, "LTF")

            return setup

        except Exception as e:
            print("Error analyzing " + symbol + ": " + str(e))
            self.error_count += 1
            return None

    def process_all_instruments(self) -> List[Dict[str, Any]]:
        signals = []

        print("[" + datetime.utcnow().strftime("%H:%M:%S") + "] Starting scan...")

        for instrument in OANDA_INSTRUMENTS:
            if news_filter.is_news_blocked(instrument):
                next_news = news_filter.get_next_news(instrument)
                print("  " + instrument + ": BLOCKED (News: " + str(next_news) + ")")
                continue

            setup = self.analyze_oanda_instrument(instrument)
            if setup and setup.probability >= MIN_PROBABILITY:
                direction_str = setup.direction.value
                if not db.is_signal_locked(instrument, direction_str, SIGNAL_COOLDOWN_HOURS):
                    signal_dict = {
                        "instrument": setup.instrument,
                        "direction": direction_str,
                        "grade": setup.grade,
                        "probability": setup.probability,
                        "entry_price": setup.entry_price,
                        "stop_loss": setup.stop_loss,
                        "take_profits": setup.take_profits,
                        "setup_type": setup.setup_type,
                        "timeframe": setup.timeframe,
                        "notes": setup.notes,
                    }

                    db.save_signal(signal_dict)
                    db.lock_signal(instrument, direction_str, SIGNAL_COOLDOWN_HOURS)
                    telegram.send_signal(signal_dict)
                    signals.append(signal_dict)
                    print("  " + instrument + ": " + setup.grade + " " + direction_str + " (" + str(setup.probability) + "%)")
                else:
                    print("  " + instrument + ": " + setup.grade + " " + direction_str + " (COOLDOWN)")
            else:
                print("  " + instrument + ": No setup")

        for symbol in BINANCE_SYMBOLS:
            display_name = CRYPTO_DISPLAY_NAMES.get(symbol, symbol)

            setup = self.analyze_binance_symbol(symbol)
            if setup and setup.probability >= MIN_PROBABILITY:
                direction_str = setup.direction.value
                if not db.is_signal_locked(display_name, direction_str, SIGNAL_COOLDOWN_HOURS):
                    signal_dict = {
                        "instrument": setup.instrument,
                        "direction": direction_str,
                        "grade": setup.grade,
                        "probability": setup.probability,
                        "entry_price": setup.entry_price,
                        "stop_loss": setup.stop_loss,
                        "take_profits": setup.take_profits,
                        "setup_type": setup.setup_type,
                        "timeframe": setup.timeframe,
                        "notes": setup.notes,
                    }

                    db.save_signal(signal_dict)
                    db.lock_signal(display_name, direction_str, SIGNAL_COOLDOWN_HOURS)
                    telegram.send_signal(signal_dict)
                    signals.append(signal_dict)
                    print("  " + display_name + ": " + setup.grade + " " + direction_str + " (" + str(setup.probability) + "%)")
                else:
                    print("  " + display_name + ": " + setup.grade + " " + direction_str + " (COOLDOWN)")
            else:
                print("  " + display_name + ": No setup")

        self.processed_count += 1
        print("[" + datetime.utcnow().strftime("%H:%M:%S") + "] Scan complete. " + str(len(signals)) + " signals.")

        db.cleanup_old_data()

        return signals

    def send_daily_summary(self) -> bool:
        from datetime import datetime
        import pytz

        wat = pytz.timezone("Africa/Lagos")
        now_wat = datetime.now(wat)

        if now_wat.hour != 0 or now_wat.minute > 5:
            return False

        yesterday = (now_wat - timedelta(days=1)).strftime("%Y-%m-%d")
        summary = db.get_signals_for_summary(yesterday)

        if not db.save_daily_summary(summary):
            return False

        telegram.send_daily_summary(summary)
        db.mark_summary_sent(yesterday)
        return True

engine = SignalEngine()
