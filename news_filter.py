"""
SMC TRADING SYSTEM - NEWS FILTER
=================================
Fetches and filters high-impact economic news.
Uses lightweight scraping + caching to avoid API limits.
"""
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
import re

from config import HIGH_IMPACT_EVENTS, NEWS_BUFFER_BEFORE, NEWS_BUFFER_AFTER
from database import db

class NewsFilter:
    def __init__(self):
        self.last_fetch = None
        self.cached_events = []

    def fetch_investing_calendar(self) -> List[Dict[str, Any]]:
        """Fetch today's economic events from Investing.com."""
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            url = "https://sslecal2.investing.com?columns=exc_currency,exc_importance,exc_actual,exc_forecast,exc_previous&importance=3&calType=week&timeZone=8&countries=25,4,17,39,72,26,10,14,48,32,56,33,6,27,37,11,36,12,5,62,41,35,71,43,38,44,45,46,60,47,55,54,59,57,64,58,61,53,42,63,40,1,18,2,30,7,19,22,28,29,17,24,10,14,48&category=_employment,_economicActivity,_inflation,_credit,_centralBanks,_confidenceIndex,_balance,_Bonds&dateFrom=" + today + "&dateTo=" + today

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json"
            }

            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                events = []
                for item in data.get("data", []):
                    event = {
                        "time": pd.to_datetime(item.get("date")),
                        "currency": item.get("country", ""),
                        "impact": "high" if item.get("importance") == 3 else "medium",
                        "title": item.get("title", ""),
                        "actual": item.get("actual", ""),
                        "forecast": item.get("forecast", "")
                    }
                    events.append(event)
                return events
        except Exception as e:
            print("Investing.com fetch failed: " + str(e))

        return []

    def fetch_forexfactory(self) -> List[Dict[str, Any]]:
        try:
            url = "https://www.forexfactory.com/calendar"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=15)
            return []
        except Exception as e:
            print("ForexFactory fetch failed: " + str(e))
            return []

    def get_today_events(self) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)

        if self.last_fetch and (now - self.last_fetch) < timedelta(hours=2):
            return self.cached_events

        events = self.fetch_investing_calendar()
        if not events:
            events = self.fetch_forexfactory()

        high_impact = [e for e in events if e["impact"] == "high"]

        self.cached_events = high_impact
        self.last_fetch = now

        if high_impact:
            db.save_news_events(high_impact)

        return high_impact

    def is_news_blocked(self, instrument: str) -> bool:
        events = self.get_today_events()
        if not events:
            return False

        currency_map = {
            "EUR_USD": ["EUR", "USD"], "GBP_USD": ["GBP", "USD"],
            "USD_JPY": ["USD", "JPY"], "USD_CAD": ["USD", "CAD"],
            "AUD_USD": ["AUD", "USD"], "NZD_USD": ["NZD", "USD"],
            "USD_CHF": ["USD", "CHF"], "EUR_GBP": ["EUR", "GBP"],
            "EUR_JPY": ["EUR", "JPY"], "GBP_JPY": ["GBP", "JPY"],
            "AUD_JPY": ["AUD", "JPY"], "CAD_JPY": ["CAD", "JPY"],
            "NAS100_USD": ["USD"], "US30_USD": ["USD"],
            "SPX500_USD": ["USD"], "GER30_USD": ["EUR"],
            "XAU_USD": ["USD"], "XAG_USD": ["USD"],
            "WTI_USD": ["USD"],
        }

        if "USDT" in instrument or ("USD" in instrument and "_" not in instrument):
            return False

        currencies = currency_map.get(instrument, [])
        if not currencies:
            return False

        block = db.get_active_news_block(currencies, NEWS_BUFFER_BEFORE, NEWS_BUFFER_AFTER)
        return block is not None

    def get_next_news(self, instrument: str) -> Optional[str]:
        events = self.get_today_events()
        if not events:
            return None

        currency_map = {
            "EUR_USD": ["EUR", "USD"], "GBP_USD": ["GBP", "USD"],
            "USD_JPY": ["USD", "JPY"], "USD_CAD": ["USD", "CAD"],
            "AUD_USD": ["AUD", "USD"], "NZD_USD": ["NZD", "USD"],
            "USD_CHF": ["USD", "CHF"], "EUR_GBP": ["EUR", "GBP"],
            "EUR_JPY": ["EUR", "JPY"], "GBP_JPY": ["GBP", "JPY"],
            "AUD_JPY": ["AUD", "JPY"], "CAD_JPY": ["CAD", "JPY"],
            "NAS100_USD": ["USD"], "US30_USD": ["USD"],
            "SPX500_USD": ["USD"], "GER30_USD": ["EUR"],
            "XAU_USD": ["USD"], "XAG_USD": ["USD"],
            "WTI_USD": ["USD"],
        }

        currencies = currency_map.get(instrument, [])
        if not currencies:
            return None

        now = datetime.now(timezone.utc)
        future_events = [
            e for e in events 
            if e["currency"] in currencies and e["time"] > now
        ]

        if future_events:
            next_event = min(future_events, key=lambda x: x["time"])
            time_until = next_event["time"] - now
            hours = int(time_until.total_seconds() / 3600)
            mins = int((time_until.total_seconds() % 3600) / 60)
            return next_event["title"] + " in " + str(hours) + "h" + str(mins) + "m"

        return None

news_filter = NewsFilter()
