"""
SMC TRADING SYSTEM - WEB SERVICE MODE
======================================
Runs as a Render Web Service (free tier compatible).
Exposes a health endpoint for uptime pings while SMC scanning runs in background.
"""
import threading
import time
import os
from datetime import datetime, timezone
from flask import Flask, jsonify

app = Flask(__name__)

# Global state
last_scan_time = None
last_scan_signals = 0
total_signals_today = 0
system_status = "INITIALIZING"
scan_thread = None
stop_event = threading.Event()

def scan_loop():
    """Background scanning loop."""
    global last_scan_time, last_scan_signals, total_signals_today, system_status

    # Delay to let Flask fully start
    time.sleep(3)

    try:
        from config import SCAN_INTERVAL_MINUTES
        from signal_engine import engine
        from telegram_bot import telegram

        system_status = "RUNNING"
        telegram.send_system_status("ONLINE", "SMC system running. Scanning every " + str(SCAN_INTERVAL_MINUTES) + " minutes.")

        while not stop_event.is_set():
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
                print("CRITICAL ERROR in scan_loop: " + str(e))
                try:
                    telegram.send_system_status("ERROR", "Scan failed: " + str(e)[:200])
                except:
                    pass
                system_status = "ERROR"

            # Sleep in 1-second increments
            for _ in range(SCAN_INTERVAL_MINUTES * 60):
                if stop_event.is_set():
                    break
                time.sleep(1)

    except Exception as e:
        print("FATAL: Could not start scan loop: " + str(e))
        system_status = "FATAL: " + str(e)

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
            print("OANDA: Credentials configured")

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
        try:
            from signal_engine import engine
            engine.process_all_instruments()
        except Exception as e:
            print("Manual scan error: " + str(e))

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
    app.run(host="0.0.0.0", port=port, threaded=True)
