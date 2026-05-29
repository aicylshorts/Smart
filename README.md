# SMC TRADING SYSTEM

## Overview
24/7 Smart Money Concepts trading signal generator running on Render free tier.
- Scans Forex, Indices, Commodities via OANDA
- Scans Crypto via Binance
- Sends signals to Telegram
- Filters high-impact news
- Daily summaries at midnight WAT

## How It Works (Render Free Tier)
This runs as a **Web Service** with a lightweight Flask server that:
1. Exposes `/` (health check) and `/ping` endpoints
2. Runs SMC scanning in a **background thread** every 5 minutes
3. Can be kept alive with free uptime monitoring services

## Assets Monitored
### OANDA (Forex + Indices + Commodities)
EUR/USD, GBP/USD, USD/JPY, USD/CAD, AUD/USD, NZD/USD, USD/CHF,
EUR/GBP, EUR/JPY, GBP/JPY, AUD/JPY, CAD/JPY,
US100 (NAS100), US30 (Dow), SPX500, GER30,
XAU/USD (Gold), XAG/USD (Silver), WTI/USD (Oil)

### Binance (Crypto - displayed as USD pairs)
BTC/USD, ETH/USD, SOL/USD, BNB/USD, ADA/USD, XRP/USD

## SMC Concepts Implemented
- Market Structure (BOS, CHoCH)
- Liquidity Sweeps (Equal Highs/Lows)
- Order Blocks (OB)
- Breaker Blocks (BB)
- Fair Value Gaps (FVG)
- Premium/Discount Zones
- Kill Zone Timing (London/NY sessions in WAT)

## Signal Grading
- **A Grade**: 70-79% probability
- **A+ Grade**: 80-100% probability
- Minimum threshold: A (70%)

## Dynamic Take Profits
Based on probability, not fixed:
- A: TP1 at 1.5R (60% position), TP2 at 2.5R (40%)
- A+: TP1 at 1.5R (40%), TP2 at 2.5R (30%), TP3 at 4R (20%), TP4 at 5R (10%)

## Setup Instructions

### 1. Get API Keys
- **OANDA**: Create free practice account at https://developer.oanda.com/
- **Telegram**: Message @BotFather to create bot, get token
- **Telegram Chat ID**: Message @userinfobot or start bot and check updates

### 2. Deploy to Render
1. Create GitHub repo, push these files
2. Go to https://render.com
3. Create **New Web Service** (NOT Background Worker)
4. Connect your GitHub repo
5. Add environment variables in Render dashboard:
   - `OANDA_ACCESS_TOKEN`
   - `OANDA_ACCOUNT_ID`
   - `OANDA_ENVIRONMENT` = `practice` (or `live` when ready)
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
6. Deploy

### 3. Keep It Alive (Important for Free Tier)
Render free web services sleep after 15 minutes of inactivity.
**Use a free uptime monitor to ping your service every 10 minutes:**

**Option A: UptimeRobot (Recommended)**
- Go to https://uptimerobot.com
- Create free account
- Add monitor: HTTP(s)
- URL: `https://YOUR-SERVICE-NAME.onrender.com/ping`
- Interval: Every 5 minutes
- This keeps your service awake 24/7

**Option B: Cron-Job.org**
- Go to https://cron-job.org
- Create free account
- Add cron job hitting `https://YOUR-SERVICE-NAME.onrender.com/ping`
- Set to every 10 minutes

### 4. Local Testing (optional)
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python app.py
```
Then visit http://localhost:10000/ for health status.

## Files (All Flattened)
- `app.py` - Entry point (Flask web server + background scanner)
- `config.py` - All settings
- `database.py` - SQLite tracking
- `oanda_client.py` - Forex/Indices data
- `binance_client.py` - Crypto data
- `smc_analyzer.py` - Core SMC logic
- `news_filter.py` - News blocking
- `telegram_bot.py` - Notifications
- `signal_engine.py` - Orchestration
- `requirements.txt` - Dependencies
- `render.yaml` - Render config
- `Procfile` - Process config
- `.env.example` - Env template

## Endpoints
| Endpoint | Purpose |
|----------|---------|
| `/` | Health check + system status (JSON) |
| `/ping` | Simple "pong" for uptime monitors |
| `/scan` | Trigger manual scan |

## Timezone
All signals in **WAT (UTC+1)** - West Africa Time.

## News Filter
Blocks signals 30min before/after high-impact news:
NFP, CPI, FOMC, Rate Decisions, GDP, etc.

## Deduplication
Same instrument+direction locked for 4 hours after signal.

## Database
SQLite auto-creates `smc_signals.db` for tracking.
