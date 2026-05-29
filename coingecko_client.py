"""
SMC TRADING SYSTEM - COINGECKO CLIENT
======================================
Fetches crypto OHLCV data via CoinGecko API.
Uses /coins/{id}/ohlc endpoint for proper candlestick data.
- Keyless access (no authentication needed)
- No geo-restrictions
- 10,000 free calls/month, ~30 calls/minute safe rate
"""
import requests
import pandas as pd
from datetime import datetime, timezone
from typing import Optional, Dict, List
import time

from config import (
    CRYPTO_DISPLAY_NAMES, HTF_TIMEFRAME, ITF_TIMEFRAME, 
    LTF_TIMEFRAME, MTF_TIMEFRAME
)

# CoinGecko coin IDs mapping
COIN_IDS = {
    "BTCUSDT": "bitcoin",
    "ETHUSDT": "ethereum",
    "SOLUSDT": "solana",
    "BNBUSDT": "binancecoin",
    "ADAUSDT": "cardano",
    "XRPUSDT": "ripple",
}

# Timeframe to CoinGecko days parameter
# CoinGecko OHLC endpoint uses 'days' parameter: 1, 7, 14, 30, 90, 180, 365
TIMEFRAME_DAYS = {
    "M5": 1,      # 1 day (gives ~5min granularity)
    "M15": 1,     # 1 day
    "M30": 1,     # 1 day
    "H1": 7,      # 7 days (hourly data)
    "H4": 30,     # 30 days (hourly, we resample)
    "D": 365,     # 365 days (daily data)
}

class CoinGeckoClient:
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.session = requests.Session()
        self.last_request_time = 0
        self.min_interval = 2.0  # Seconds between requests (30 calls/min safe)
        self.api_working = True

    def _rate_limit(self):
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make public request to CoinGecko API."""
        if not self.api_working:
            return None

        self._rate_limit()
        url = self.base_url + endpoint
        try:
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print("CoinGecko Rate Limit hit. Waiting 60 seconds...")
                time.sleep(60)
                return self._request(endpoint, params)
            else:
                print("CoinGecko Error " + str(response.status_code) + ": " + response.text[:200])
                if response.status_code == 403:
                    self.api_working = False
                return None
        except Exception as e:
            print("CoinGecko Request Error: " + str(e))
            return None

    def get_ohlc(
        self, 
        symbol: str, 
        days: int = 7
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLC data from CoinGecko /coins/{id}/ohlc endpoint.

        Returns: [timestamp, open, high, low, close] for each candle.

        CoinGecko OHLC granularity:
        - 1 day: ~5 minute intervals
        - 7-30 days: ~1 hour intervals  
        - >30 days: ~4 hour intervals
        """
        coin_id = COIN_IDS.get(symbol)
        if not coin_id:
            print("Unknown CoinGecko mapping for: " + symbol)
            return None

        endpoint = "/coins/" + coin_id + "/ohlc"
        params = {
            "vs_currency": "usd",
            "days": str(days),
        }

        data = self._request(endpoint, params)
        if not data or not isinstance(data, list):
            print("CoinGecko OHLC: No data returned for " + symbol)
            return None

        if len(data) < 10:
            print("CoinGecko OHLC: Insufficient data for " + symbol + " (" + str(len(data)) + " candles)")
            return None

        # Parse OHLC data: [timestamp, open, high, low, close]
        records = []
        for candle in data:
            if len(candle) >= 5:
                records.append({
                    "time": pd.to_datetime(candle[0], unit="ms"),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                })

        df = pd.DataFrame(records)
        if df.empty or len(df) < 10:
            return None

        df.set_index("time", inplace=True)
        df.sort_index(inplace=True)

        # Add volume placeholder (OHLC endpoint doesn't provide volume)
        df["volume"] = 0.0

        # Calculate derived columns for SMC analysis
        df["body"] = (df["close"] - df["open"]).abs()
        df["range"] = df["high"] - df["low"]
        df["upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
        df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]
        df["bullish"] = df["close"] > df["open"]
        df["bearish"] = df["close"] < df["open"]

        print("CoinGecko OHLC: Fetched " + str(len(df)) + " candles for " + symbol + " (" + str(days) + " days)")
        return df

    def get_all_timeframes(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """Fetch all configured timeframes for a symbol."""
        timeframes = {
            "HTF": (HTF_TIMEFRAME, 30),    # 30 days for H4
            "ITF": (ITF_TIMEFRAME, 7),     # 7 days for H1
            "LTF": (LTF_TIMEFRAME, 1),     # 1 day for M15
            "MTF": (MTF_TIMEFRAME, 1),     # 1 day for M5
        }

        result = {}
        for name, (tf_name, days) in timeframes.items():
            df = self.get_ohlc(symbol, days)
            if df is not None:
                result[name] = df
            time.sleep(2.0)  # Rate limit respect

        return result

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price."""
        coin_id = COIN_IDS.get(symbol)
        if not coin_id:
            return None

        endpoint = "/simple/price"
        params = {
            "ids": coin_id,
            "vs_currencies": "usd"
        }
        data = self._request(endpoint, params)

        if data and coin_id in data:
            return float(data[coin_id]["usd"])
        return None

    def get_instrument_precision(self, symbol: str) -> int:
        """Get decimal precision for symbol."""
        if symbol in ["BTCUSDT", "BTCUSD"]:
            return 2
        elif symbol in ["ETHUSDT", "ETHUSD", "BNBUSDT", "BNBUSD"]:
            return 2
        else:
            return 3

coingecko = CoinGeckoClient()
