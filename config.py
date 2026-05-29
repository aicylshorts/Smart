"""
SMC TRADING SYSTEM - CONFIGURATION
====================================
All settings centralized for easy mobile setup.
"""
import os
from datetime import timedelta

# ============================================================
# API CREDENTIALS (Set via Render Environment Variables)
# ============================================================
OANDA_ACCESS_TOKEN = os.getenv("OANDA_ACCESS_TOKEN", "")
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
OANDA_ENVIRONMENT = os.getenv("OANDA_ENVIRONMENT", "practice")  # 'practice' or 'live'

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ============================================================
# ASSET CONFIGURATION
# ============================================================
# OANDA Instruments (Forex, Indices, Commodities)
OANDA_INSTRUMENTS = [
    # Forex Majors
    "EUR_USD", "GBP_USD", "USD_JPY", "USD_CAD",
    "AUD_USD", "NZD_USD", "USD_CHF", "EUR_GBP",
    "EUR_JPY", "GBP_JPY", "AUD_JPY", "CAD_JPY",
    # Indices
    "NAS100_USD",   # US100 (Nasdaq)
    "US30_USD",     # US30 (Dow Jones)
    "SPX500_USD",   # S&P 500 (bonus)
    "GER30_USD",    # DAX (bonus)
    # Commodities
    "XAU_USD",      # Gold
    "XAG_USD",      # Silver
    "WTI_USD",      # Oil (bonus)
]

# Binance Crypto (USDT pairs tracked, presented as USD)
BINANCE_SYMBOLS = [
    "BTCUSDT",   # Bitcoin
    "ETHUSDT",   # Ethereum
    "SOLUSDT",   # Solana
    "BNBUSDT",   # Binance Coin (bonus)
    "ADAUSDT",   # Cardano (bonus)
    "XRPUSDT",   # Ripple (bonus)
]

# Display names for crypto (user wants USD labels)
CRYPTO_DISPLAY_NAMES = {
    "BTCUSDT": "BTCUSD",
    "ETHUSDT": "ETHUSD",
    "SOLUSDT": "SOLUSD",
    "BNBUSDT": "BNBUSD",
    "ADAUSDT": "ADAUSD",
    "XRPUSDT": "XRPUSD",
}

# ============================================================
# TIMEFRAME CONFIGURATION (Multi-Timeframe Analysis)
# ============================================================
# Higher Timeframe for bias (HTF)
HTF_TIMEFRAME = "H4"      # 4-hour for directional bias
HTF_CANDLE_COUNT = 100    # Candles to fetch for HTF

# Intermediate Timeframe for POI identification
ITF_TIMEFRAME = "H1"      # 1-hour for order blocks / liquidity
ITF_CANDLE_COUNT = 150

# Lower Timeframe for execution (LTF)
LTF_TIMEFRAME = "M15"     # 15-minute for entry confirmation
LTF_CANDLE_COUNT = 200

# Micro Timeframe for precision (MTF)
MTF_TIMEFRAME = "M5"      # 5-minute for fine-tuning
MTF_CANDLE_COUNT = 100

# ============================================================
# SMC PARAMETERS
# ============================================================
# Swing detection lookback
SWING_LOOKBACK = 5          # Bars to confirm swing high/low

# Displacement threshold (body size vs ATR multiplier)
DISPLACEMENT_ATR_MULT = 1.5  # Body must be > 1.5x ATR

# FVG minimum gap size in pips/points (as fraction of price)
FVG_MIN_GAP_PCT = 0.0002    # 0.02% minimum gap

# Order Block parameters
OB_MAX_CANDLES = 3          # Look back max 3 candles for OB
OB_MIN_DISPLACEMENT = 2.0   # Displacement must be 2x ATR

# Liquidity sweep parameters
SWEEP_WICK_RATIO = 0.6      # Wick must be 60% of candle range
SWEEP_BREAK_PCT = 0.00015   # Must break level by 0.015%

# Premium/Discount zone
PREMIUM_DISCOUNT_LEVELS = [0.0, 0.5, 1.0]  # 0=discount, 0.5=equilibrium, 1.0=premium

# Kill Zones (WAT = UTC+1, Forex sessions in WAT)
KILL_ZONES = {
    "london": (9, 12),      # 9:00 - 12:00 WAT (London open)
    "ny_am": (14, 17),      # 14:00 - 17:00 WAT (NY open)
    "ny_pm": (19, 21),      # 19:00 - 21:00 WAT (NY afternoon)
    "asia": (1, 4),         # 1:00 - 4:00 WAT (Asian session)
}

# ============================================================
# SIGNAL PROBABILITY THRESHOLDS
# ============================================================
MIN_PROBABILITY = 70        # Minimum to signal (A grade starts at 70)
A_GRADE_MIN = 70
A_GRADE_MAX = 79
A_PLUS_MIN = 80
A_PLUS_MAX = 100

# ============================================================
# RISK & REWARD PARAMETERS
# ============================================================
DEFAULT_RISK_PERCENT = 1.0  # 1% risk per trade (conservative)
MAX_RISK_PERCENT = 2.0      # Max 2% for A+ setups

# TP levels based on probability (R multiples)
TP_CONFIG = {
    # A grade (70-79): Conservative targets
    "A": {
        "tp1": {"rr": 1.5, "prob": 75, "size": 0.60},  # 60% of position
        "tp2": {"rr": 2.5, "prob": 55, "size": 0.40},  # 40% of position
    },
    # A+ grade (80-100): Aggressive targets
    "A+": {
        "tp1": {"rr": 1.5, "prob": 80, "size": 0.40},
        "tp2": {"rr": 2.5, "prob": 65, "size": 0.30},
        "tp3": {"rr": 4.0, "prob": 45, "size": 0.20},
        "tp4": {"rr": 5.0, "prob": 30, "size": 0.10},
    },
}

# ============================================================
# NEWS FILTER SETTINGS
# ============================================================
NEWS_IMPACT_THRESHOLD = "high"  # Filter high impact news
NEWS_BUFFER_BEFORE = 30         # Minutes before news to block signals
NEWS_BUFFER_AFTER = 30          # Minutes after news to block signals

# High impact events to watch (keywords)
HIGH_IMPACT_EVENTS = [
    "non-farm", "nfp", "cpi", "inflation", "gdp", "interest rate",
    "fomc", "fed", "ecb", "boe", "boj", "rate decision", "unemployment",
    "retail sales", "pmi", "payroll", "jobs", "claim", "speech"
]

# ============================================================
# SIGNAL DEDUPLICATION
# ============================================================
SIGNAL_COOLDOWN_HOURS = 4       # Don't resignal same instrument+direction within 4h

# ============================================================
# TELEGRAM SETTINGS
# ============================================================
TELEGRAM_TIMEOUT = 30
DAILY_SUMMARY_HOUR_WAT = 0      # Midnight WAT (00:00)
DAILY_SUMMARY_MINUTE = 0

# ============================================================
# SYSTEM SETTINGS
# ============================================================
SCAN_INTERVAL_MINUTES = 5       # Scan all instruments every 5 minutes
MAX_CONCURRENT_INSTRUMENTS = 20  # Process in batches if needed
LOG_LEVEL = "INFO"

# Timezone
TIMEZONE_WAT = "Africa/Lagos"   # WAT UTC+1
