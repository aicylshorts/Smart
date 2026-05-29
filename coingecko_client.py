"""
SMC TRADING SYSTEM - COINGECKO CLIENT
======================================
Fetches crypto data via CoinGecko API.
- Keyless access (no authentication needed)
- No geo-restrictions (works from any server location)
- 10,000 free calls/month, 100 calls/minute
- OHLCV data available for charting
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

# Timeframe to days mapping for CoinGecko
TIMEFRAME_DAYS = {
    "M5": 1,      # 1 day of minute data
    "M15": 1,
    "M30": 1,
    "H1": 7,      # 7 days of hourly data
    "H4": 30,     # 30 days of 4h data (we'll resample)
    "D": 365,     # 1 year of daily data
}

class CoinGeckoClient:
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.session = requests.Session()
        self.last_request_time = 0
        self.min_interval = 1.2  # Seconds between requests (50 calls/min safe)

    def _rate_limit(self):
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make public request to CoinGecko API."""
        self._rate_limit()
        url = self.base_url + endpoint
        try:
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print("CoinGecko Rate Limit hit. Waiting 60 seconds...")
                time.sleep(60)
                return self._request(endpoint, params)  # Retry once
            else:
                print("CoinGecko Error " + str(response.status_code) + ": " + response.text[:200])
                return None
        except Exception as e:
            print("CoinGecko Request Error: " + str(e))
            return None

    def get_candles(
        self, 
        symbol: str, 
        interval: str = "H1", 
        limit: int = 150
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data from CoinGecko.

        CoinGecko provides market chart data with granularity:
        - 1 day range: minute data (approx 5-min intervals)
        - 1-90 days: hourly data
        - >90 days: daily data

        We fetch the appropriate range and resample to our timeframe.
        """
        coin_id = COIN_IDS.get(symbol)
        if not coin_id:
            print("Unknown CoinGecko mapping for: " + symbol)
            return None

        # Determine days based on timeframe
        days = TIMEFRAME_DAYS.get(interval, 7)

        endpoint = "/coins/" + coin_id + "/market_chart"
        params = {
            "vs_currency": "usd",
            "days": str(days),
            "interval": "daily" if days > 90 else "hourly"
        }

        data = self._request(endpoint, params)
        if not data or "prices" not in data:
            return None

        # CoinGecko returns: [timestamp, price] for prices, market_caps, total_volumes
        prices = data.get("prices", [])
        volumes = data.get("total_volumes", [])

        if not prices or len(prices) < 10:
            return None

        # Build DataFrame from price data
        # Note: CoinGecko doesn't provide OHLC directly, only price points
        # We'll construct candles from price movements
        records = []
        for i in range(len(prices)):
            ts = prices[i][0]  # timestamp in ms
            price = prices[i][1]
            volume = volumes[i][1] if i < len(volumes) else 0

            records.append({
                "time": pd.to_datetime(ts, unit="ms"),
                "price": price,
                "volume": volume
            })

        df = pd.DataFrame(records)
        df.set_index("time", inplace=True)
        df.sort_index(inplace=True)

        # Resample to create OHLCV candles
        # For simplicity, we'll use price sampling to create candles
        if interval in ["M5", "M15", "M30"]:
            # For short timeframes, use the raw data (already ~5min granularity)
            # Create simple candles from consecutive prices
            df["open"] = df["price"].shift(1)
            df["high"] = df["price"].rolling(window=2).max()
            df["low"] = df["price"].rolling(window=2).min()
            df["close"] = df["price"]
            df = df.dropna()
        else:
            # Resample to hourly/daily
            resample_map = {
                "H1": "1H", "H4": "4H", "D": "1D"
            }
            freq = resample_map.get(interval, "1H")

            ohlcv = df.resample(freq).agg({
                "price": ["first", "max", "min", "last"],
                "volume": "sum"
            })
            ohlcv.columns = ["open", "high", "low", "close", "volume"]
            ohlcv = ohlcv.dropna()
            df = ohlcv

        if df.empty or len(df) < 20:
            return None

        # Ensure columns exist
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                df[col] = df["price"] if "price" in df.columns else 0

        # Calculate derived columns
        df["body"] = (df["close"] - df["open"]).abs()
        df["range"] = df["high"] - df["low"]
        df["upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
        df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]
        df["bullish"] = df["close"] > df["open"]
        df["bearish"] = df["close"] < df["open"]

        return df

    def get_all_timeframes(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """Fetch all configured timeframes for a symbol."""
        timeframes = {
            "HTF": (HTF_TIMEFRAME, 100),
            "ITF": (ITF_TIMEFRAME, 150),
            "LTF": (LTF_TIMEFRAME, 200),
            "MTF": (MTF_TIMEFRAME, 100)
        }

        result = {}
        for name, (interval, limit) in timeframes.items():
            df = self.get_candles(symbol, interval, limit)
            if df is not None:
                result[name] = df
            time.sleep(1.5)  # Rate limit respect

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

# Global instance
coingecko = CoinGeckoClient()
