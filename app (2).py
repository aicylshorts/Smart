"""
SMC TRADING SYSTEM - WEB SERVICE MODE
======================================
Runs as a Render Web Service (free tier compatible).
Exposes a health endpoint for uptime pings while SMC scanning runs in background.
"""
import threading
import time
import os
import sys
from datetime import datetime, timezone
from flask import Flask, jsonify

# Import everything at module level so errors are visible immediately
print("Importing modules...")
try:
    from config import SCAN_INTERVAL_MINUTES, TIMEZONE_WAT
    from signal_engine import engine
    from telegram_bot import telegram
    print("All imports successful")
except Exception as e:
    print("FATAL IMPORT ERROR: " + str(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

app = Flask(__name__)

# Global state
last_scan_time = None
last_scan_signals = 0
total_signals_today = 0
system_status = "INITIALIZING"
scan_thread = None
stop_event = threading.Event()

def run_scan():
    """Execute one scan cycle."""
    global last_scan_time, last_scan_signals, total_signals_today, system_status

    try:
        print("\n" + "=" * 60)
        print("SMC SCAN STARTED: " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
        print("=" * 60)

        signals = engine.process_all_instruments()

        last_scan_time = datetime.now(timezone.utc).isoformat()
        last_scan_signals = len(signals)
        total_signals_today += len(signals)

        engine.send_daily_summary()

        print("\nScan complete. Sleeping " + str(SCAN_INTERVAL_MINUTES) + " minutes...\n")

    except Exception as e:
        print("CRITICAL ERROR in scan: " + str(e))
        import traceback
        traceback.print_exc()
        try:
            telegram.send_system_status("ERROR", "Scan failed: " + str(e)[:200])
        except:
            pass
        system_status = "ERROR"

def scan_loop():
    """Background scanning loop."""
    global system_status

    # Delay to let Flask fully start
    print("Scanner thread started. Waiting 10 seconds before first scan...")
    time.sleep(10)

    system_status = "RUNNING"

    try:
        telegram.send_system_status("ONLINE", "SMC system running. Scanning every " + str(SCAN_INTERVAL_MINUTES) + " minutes.")
    except Exception as e:
        print("Telegram startup message failed: " + str(e))

    # Run first scan immediately
    run_scan()

    while not stop_event.is_set():
        # Sleep in 1-second increments so we can respond to stop_event quickly
        sleep_seconds = SCAN_INTERVAL_MINUTES * 60
        print("Scanner sleeping for " + str(sleep_seconds) + " seconds...")

        for _ in range(sleep_seconds):
            if stop_event.is_set():
                break
            time.sleep(1)

        if not stop_event.is_set():
            run_scan()

def startup_check():
    """Verify system is ready."""
    print("=" * 60)
    print("SMC TRADING SYSTEM - STARTUP")
    print("=" * 60)

    try:
        from config import OANDA_ACCESS_TOKEN, TELEGRAM_BOT_TOKEN, SCAN_INTERVAL_MINUTES

        if not OANDA_ACCESS_TOKEN:
            print("WARNING: OANDA_ACCESS_TOKEN not set!")
        else:
            print("OANDA: Credentials configured (token starts with " + OANDA_ACCESS_TOKEN[:8] + "...)")

        if not TELEGRAM_BOT_TOKEN:
            print("WARNING: TELEGRAM_BOT_TOKEN not set!")
        else:
            print("Telegram: Credentials configured")

        print("Scan interval: " + str(SCAN_INTERVAL_MINUTES) + " minutes")
        print("Minimum probability: A (70%+)")
        print("Mode: Web Service (Render free tier)")

    except Exception as e:
        print("WARNING: Could not load config: " + str(e))

    print("=" * 60)

@app.route("/")
def health():
    """Health check endpoint - keeps Render free tier alive."""
    return jsonify({
        "status": system_status,
        "last_scan": last_scan_time,
        "last_scan_signals": last_scan_signals,
        "total_signals_today": total_signals_today,
        "service": "SMC Trading System",
        "version": "1.0"
    })

@app.route("/ping")
def ping():
    """Simple ping for uptime monitors."""
    return "pong", 200

@app.route("/scan")
def manual_scan():
    """Trigger a manual scan."""
    def do_scan():
        run_scan()

    threading.Thread(target=do_scan, daemon=True).start()
    return jsonify({"message": "Scan triggered"}), 200

if __name__ == "__main__":
    startup_check()

    # Start background scanner thread
    scan_thread = threading.Thread(target=scan_loop, daemon=True)
    scan_thread.start()

    # Start Flask server (Render provides PORT env var)
    port = int(os.environ.get("PORT", 10000))
    print("Starting Flask on port " + str(port))

    # Use threaded=True to handle concurrent requests
    app.run(host="0.0.0.0", port=port, threaded=True)
