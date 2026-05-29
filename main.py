"""
SMC TRADING SYSTEM - MAIN ENTRY POINT
======================================
24/7 signal generation via scheduled scanning.
Runs on Render with cron-like scheduling.
"""
import time
import schedule
from datetime import datetime, timezone
import pytz
import sys

from config import SCAN_INTERVAL_MINUTES, TIMEZONE_WAT
from signal_engine import engine
from telegram_bot import telegram

def scan_job():
    """Main scan job - runs every SCAN_INTERVAL_MINUTES."""
    try:
        sep = "=" * 60
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print("\n" + sep)
        print("SMC SCAN STARTED: " + now_str)
        print(sep)

        signals = engine.process_all_instruments()

        engine.send_daily_summary()

        print("\nScan complete. Sleeping " + str(SCAN_INTERVAL_MINUTES) + " minutes...\n")

    except Exception as e:
        print("CRITICAL ERROR in scan_job: " + str(e))
        telegram.send_system_status("ERROR", "Scan failed: " + str(e)[:200])

def startup_check():
    """Verify system is ready on startup."""
    sep = "=" * 60
    print(sep)
    print("SMC TRADING SYSTEM - STARTUP")
    print(sep)

    from config import OANDA_ACCESS_TOKEN, TELEGRAM_BOT_TOKEN

    if not OANDA_ACCESS_TOKEN:
        print("WARNING: OANDA_ACCESS_TOKEN not set!")
    else:
        print("OANDA: Credentials configured")

    if not TELEGRAM_BOT_TOKEN:
        print("WARNING: TELEGRAM_BOT_TOKEN not set!")
    else:
        print("Telegram: Credentials configured")

    telegram.send_system_status("ONLINE", "SMC system initialized and scanning.")

    print("Timezone: WAT (UTC+1)")
    print("Scan interval: " + str(SCAN_INTERVAL_MINUTES) + " minutes")
    print("Minimum probability: A (70%+)")
    print(sep)

def run_scheduler():
    """Run the continuous scheduler."""
    startup_check()

    schedule.every(SCAN_INTERVAL_MINUTES).minutes.do(scan_job)

    scan_job()

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run_scheduler()
