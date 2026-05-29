"""
SMC TRADING SYSTEM - OANDA CLIENT
==================================
Fetches candle data for Forex, Indices, and Commodities.
Uses OANDA v20 REST API (free practice account).
"""
import requests
import pandas as pd
from datetime import datetime, timezone
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
        self.auth_valid = False

        if self.environment == "practice":
            self.base_url = "https://api-fxpractice.oanda.com"
        else:
            self.base_url = "https://api-fxtrade.oanda.com"

        self.headers = {
            "Authorization": "Bearer " + self.access_token,
            "Content-Type": "application/json"
        }

        # Test auth on init
        self._test_auth()

    def _test_auth(self):
        """Test authentication once at startup."""
        if not self.access_token:
            print("OANDA: No access token provided!")
            return

        endpoint = "/v3/accounts/" + self.account_id
        url = self.base_url + endpoint
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                self.auth_valid = True
                print("OANDA: Authentication successful")
            elif response.status_code == 401:
                print("OANDA ERROR 401: Invalid token or account ID. Check your credentials.")
                print("  - Token starts with: " + self.access_token[:10] + "..." if len(self.access_token) > 10 else "  - Token: [empty]")
                print("  - Environment: " + self.environment)
                print("  - Go to https://developer.oanda.com to generate a new token.")
            else:
                print("OANDA Error " + str(response.status_code) + ": " + response.text[:200])
        except Exception as e:
            print("OANDA Auth Test Error: " + str(e))

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        if not self.auth_valid:
            return None

        url = self.base_url + endpoint
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                print("OANDA Error 401: Authentication failed. Token may be expired.")
                return None
            else:
                print("OANDA Error " + str(response.status_code) + ": " + response.text[:200])
                return None
        except Exception as e:
            print("OANDA Request Error: " + str(e))
            return None

    def get_candles(
        self, 
        instrument: str, 
        granularity: str = "H1", 
        count: int = 150,
        price: str = "M"
    ) -> Optional[pd.DataFrame]:
        if not self.auth_valid:
            return None

        endpoint = "/v3/instruments/" + instrument + "/candles"
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
                price_key = price.lower()
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
        if not self.auth_valid:
            return {}

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
        if not self.auth_valid:
            return None

        endpoint = "/v3/accounts/" + self.account_id + "/pricing"
        params = {"instruments": instrument}
        data = self._request(endpoint, params)

        if data and "prices" in data and len(data["prices"]) > 0:
            price = data["prices"][0]
            bid = float(price["bid"])
            ask = float(price["ask"])
            return (bid + ask) / 2
        return None

    def get_instrument_precision(self, instrument: str) -> int:
        if "JPY" in instrument or instrument in ["NAS100_USD", "US30_USD", "SPX500_USD", "GER30_USD"]:
            return 2
        elif instrument in ["XAU_USD"]:
            return 2
        elif instrument in ["XAG_USD", "WTI_USD"]:
            return 3
        else:
            return 5

oanda = OandaClient()
