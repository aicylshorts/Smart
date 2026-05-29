"""
SMC TRADING SYSTEM - BINANCE CLIENT
====================================
Fetches candle data for Crypto USD pairs.
Uses Binance public API (no authentication needed for market data).
"""
import requests
import pandas as pd
from datetime import datetime
from typing import Optional, Dict
import time

from config import (
    BINANCE_SYMBOLS, HTF_TIMEFRAME, ITF_TIMEFRAME, 
    LTF_TIMEFRAME, MTF_TIMEFRAME
)

class BinanceClient:
    def __init__(self):
        self.base_url = "https://api.binance.com"
        self.session = requests.Session()

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make public request to Binance API."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Binance Error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"Binance Request Error: {e}")
            return None

    def _convert_timeframe(self, tf: str) -> str:
        """Convert our timeframe format to Binance format."""
        mapping = {
            "M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
            "H1": "1h", "H4": "4h", "D": "1d", "W": "1w"
        }
        return mapping.get(tf, tf)

    def get_candles(
        self, 
        symbol: str, 
        interval: str = "1h", 
        limit: int = 150
    ) -> Optional[pd.DataFrame]:
        """
        Fetch candlestick data from Binance.

        Args:
            symbol: e.g., "BTCUSDT", "ETHUSDT"
            interval: Binance interval (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles (max 1000)

        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        endpoint = "/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": self._convert_timeframe(interval),
            "limit": min(limit, 1000)
        }

        data = self._request(endpoint, params)
        if not data or not isinstance(data, list):
            return None

        records = []
        for k in data:
            records.append({
                "time": pd.to_datetime(k[0], unit="ms"),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5])
            })

        df = pd.DataFrame(records)
        if df.empty:
            return None

        df.set_index("time", inplace=True)
        df.sort_index(inplace=True)

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
            time.sleep(0.2)

        return result

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price."""
        endpoint = "/api/v3/ticker/price"
        params = {"symbol": symbol}
        data = self._request(endpoint, params)

        if data and "price" in data:
            return float(data["price"])
        return None

    def get_instrument_precision(self, symbol: str) -> int:
        """Get decimal precision for symbol."""
        if symbol in ["BTCUSDT", "BTCUSD"]:
            return 2
        elif symbol in ["ETHUSDT", "ETHUSD", "BNBUSDT", "BNBUSD"]:
            return 2
        else:
            return 3

binance = BinanceClient()
