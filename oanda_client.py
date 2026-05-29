"""
SMC TRADING SYSTEM - OANDA CLIENT
==================================
Fetches candle data for Forex, Indices, and Commodities.
Uses OANDA v20 REST API (free practice account).
"""
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import time

from config import (
    OANDA_ACCESS_TOKEN, OANDA_ACCOUNT_ID, OANDA_ENVIRONMENT,
    HTF_TIMEFRAME, ITF_TIMEFRAME, LTF_TIMEFRAME, MTF_TIMEFRAME
)

class OandaClient:
    def __init__(self):
        self.access_token = OANDA_ACCESS_TOKEN
        self.account_id = OANDA_ACCOUNT_ID
        self.environment = OANDA_ENVIRONMENT

        if self.environment == "practice":
            self.base_url = "https://api-fxpractice.oanda.com"
        else:
            self.base_url = "https://api-fxtrade.oanda.com"

        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated request to OANDA API."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"OANDA Error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"OANDA Request Error: {e}")
            return None

    def get_candles(
        self, 
        instrument: str, 
        granularity: str = "H1", 
        count: int = 150,
        price: str = "M"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch candlestick data.

        Args:
            instrument: e.g., "EUR_USD", "XAU_USD", "NAS100_USD"
            granularity: OANDA timeframe (S5, M1, M5, M15, M30, H1, H4, D)
            count: Number of candles
            price: "B"=bid, "A"=ask, "M"=mid

        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        endpoint = f"/v3/instruments/{instrument}/candles"
        params = {
            "granularity": granularity,
            "count": count,
            "price": price,
            "dailyAlignment": 17,
            "alignmentTimezone": "America/New_York"
        }

        data = self._request(endpoint, params)
        if not data or "candles" not in data:
            return None

        candles = data["candles"]
        if not candles:
            return None

        records = []
        for candle in candles:
            if candle.get("complete", False):
                price_key = f"{price.lower()}"
                records.append({
                    "time": pd.to_datetime(candle["time"]),
                    "open": float(candle[price_key]["o"]),
                    "high": float(candle[price_key]["h"]),
                    "low": float(candle[price_key]["l"]),
                    "close": float(candle[price_key]["c"]),
                    "volume": int(candle["volume"])
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

    def get_all_timeframes(self, instrument: str) -> Dict[str, pd.DataFrame]:
        """Fetch all configured timeframes for an instrument."""
        timeframes = {
            "HTF": (HTF_TIMEFRAME, 100),
            "ITF": (ITF_TIMEFRAME, 150),
            "LTF": (LTF_TIMEFRAME, 200),
            "MTF": (MTF_TIMEFRAME, 100)
        }

        result = {}
        for name, (granularity, count) in timeframes.items():
            df = self.get_candles(instrument, granularity, count)
            if df is not None:
                result[name] = df
            time.sleep(0.2)

        return result

    def get_current_price(self, instrument: str) -> Optional[float]:
        """Get current mid price."""
        endpoint = f"/v3/accounts/{self.account_id}/pricing"
        params = {"instruments": instrument}
        data = self._request(endpoint, params)

        if data and "prices" in data and len(data["prices"]) > 0:
            price = data["prices"][0]
            bid = float(price["bid"])
            ask = float(price["ask"])
            return (bid + ask) / 2
        return None

    def get_instrument_precision(self, instrument: str) -> int:
        """Get decimal precision for instrument."""
        if "JPY" in instrument or instrument in ["NAS100_USD", "US30_USD", "SPX500_USD", "GER30_USD"]:
            return 2
        elif instrument in ["XAU_USD"]:
            return 2
        elif instrument in ["XAG_USD", "WTI_USD"]:
            return 3
        else:
            return 5

oanda = OandaClient()
