"""
SMC TRADING SYSTEM - DATABASE
==============================
SQLite for signal tracking, deduplication, and daily summaries.
"""
import sqlite3
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "smc_signals.db")

class SignalDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Signals table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instrument TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    probability INTEGER NOT NULL,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profits TEXT,
                    setup_type TEXT,
                    timeframe TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    notified INTEGER DEFAULT 0,
                    expired INTEGER DEFAULT 0,
                    hit_tp INTEGER DEFAULT 0,
                    hit_sl INTEGER DEFAULT 0,
                    notes TEXT
                )
            """)

            # Deduplication tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signal_locks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instrument TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    locked_until DATETIME NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Daily summary tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    summary_date DATE NOT NULL UNIQUE,
                    total_signals INTEGER DEFAULT 0,
                    a_signals INTEGER DEFAULT 0,
                    a_plus_signals INTEGER DEFAULT 0,
                    buy_signals INTEGER DEFAULT 0,
                    sell_signals INTEGER DEFAULT 0,
                    instruments TEXT,
                    sent INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # News events cache
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_time DATETIME NOT NULL,
                    currency TEXT NOT NULL,
                    impact TEXT NOT NULL,
                    title TEXT NOT NULL,
                    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    def is_signal_locked(self, instrument: str, direction: str, cooldown_hours: int = 4) -> bool:
        """Check if instrument+direction is in cooldown."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cutoff = datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
            cursor.execute("""
                SELECT 1 FROM signal_locks 
                WHERE instrument = ? AND direction = ? AND locked_until > ?
                LIMIT 1
            """, (instrument, direction, cutoff))
            return cursor.fetchone() is not None

    def lock_signal(self, instrument: str, direction: str, cooldown_hours: int = 4):
        """Lock instrument+direction for cooldown period."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            locked_until = datetime.now(timezone.utc) + timedelta(hours=cooldown_hours)
            cursor.execute("""
                INSERT INTO signal_locks (instrument, direction, locked_until)
                VALUES (?, ?, ?)
            """, (instrument, direction, locked_until))
            conn.commit()

    def save_signal(self, signal: Dict[str, Any]) -> int:
        """Save a signal and return its ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO signals 
                (instrument, direction, grade, probability, entry_price, stop_loss, 
                 take_profits, setup_type, timeframe, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal["instrument"],
                signal["direction"],
                signal["grade"],
                signal["probability"],
                signal.get("entry_price"),
                signal.get("stop_loss"),
                json.dumps(signal.get("take_profits", [])),
                signal.get("setup_type"),
                signal.get("timeframe"),
                signal.get("notes", "")
            ))
            conn.commit()
            return cursor.lastrowid

    def get_today_signals(self) -> List[Dict[str, Any]]:
        """Get all signals from today."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT * FROM signals 
                WHERE date(timestamp) = ?
                ORDER BY timestamp DESC
            """, (today,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_signals_for_summary(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Get aggregated signal data for daily summary."""
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) FROM signals WHERE date(timestamp) = ?
            """, (date_str,))
            total = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM signals WHERE date(timestamp) = ? AND grade = 'A'
            """, (date_str,))
            a_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM signals WHERE date(timestamp) = ? AND grade = 'A+'
            """, (date_str,))
            a_plus_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM signals WHERE date(timestamp) = ? AND direction = 'BUY'
            """, (date_str,))
            buy_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM signals WHERE date(timestamp) = ? AND direction = 'SELL'
            """, (date_str,))
            sell_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT DISTINCT instrument FROM signals WHERE date(timestamp) = ?
            """, (date_str,))
            instruments = [row[0] for row in cursor.fetchall()]

            return {
                "date": date_str,
                "total": total,
                "a_count": a_count,
                "a_plus_count": a_plus_count,
                "buy_count": buy_count,
                "sell_count": sell_count,
                "instruments": instruments
            }

    def save_daily_summary(self, summary: Dict[str, Any]) -> bool:
        """Save daily summary. Returns True if new, False if already exists."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO daily_summaries 
                    (summary_date, total_signals, a_signals, a_plus_signals, 
                     buy_signals, sell_signals, instruments)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    summary["date"],
                    summary["total"],
                    summary["a_count"],
                    summary["a_plus_count"],
                    summary["buy_count"],
                    summary["sell_count"],
                    json.dumps(summary["instruments"])
                ))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def mark_summary_sent(self, date_str: str):
        """Mark daily summary as sent."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE daily_summaries SET sent = 1 WHERE summary_date = ?
            """, (date_str,))
            conn.commit()

    def get_unsent_summaries(self) -> List[str]:
        """Get dates of unsent summaries."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT summary_date FROM daily_summaries 
                WHERE sent = 0 AND summary_date < date('now')
            """)
            return [row[0] for row in cursor.fetchall()]

    def save_news_events(self, events: List[Dict[str, Any]]):
        """Cache news events."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for event in events:
                cursor.execute("""
                    INSERT INTO news_events (event_time, currency, impact, title)
                    VALUES (?, ?, ?, ?)
                """, (
                    event["time"],
                    event["currency"],
                    event["impact"],
                    event["title"]
                ))
            conn.commit()

    def get_active_news_block(self, currencies: List[str], buffer_before: int = 30, buffer_after: int = 30) -> Optional[Dict[str, Any]]:
        """Check if any high-impact news is within buffer window."""
        now = datetime.now(timezone.utc)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            placeholders = ",".join(["?"] * len(currencies))
            cursor.execute(f"""
                SELECT * FROM news_events 
                WHERE currency IN ({placeholders}) 
                AND datetime(event_time) BETWEEN ? AND ?
                AND impact = 'high'
                ORDER BY event_time ASC
                LIMIT 1
            """, (*currencies, now - timedelta(minutes=buffer_before), now + timedelta(minutes=buffer_after)))

            row = cursor.fetchone()
            return dict(row) if row else None

    def cleanup_old_data(self, days: int = 7):
        """Clean old signal locks and news."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            cursor.execute("DELETE FROM signal_locks WHERE locked_until < ?", (cutoff,))
            cursor.execute("DELETE FROM news_events WHERE fetched_at < ?", (cutoff,))
            conn.commit()

# Global instance
db = SignalDatabase()
