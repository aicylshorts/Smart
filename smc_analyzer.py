"""
SMC TRADING SYSTEM - CORE ANALYZER
====================================
Implements Smart Money Concepts:
- Market Structure (BOS, CHoCH, Swing Points)
- Liquidity Sweeps (Equal Highs/Lows, Inducement)
- Order Blocks (OB) & Breaker Blocks (BB)
- Fair Value Gaps (FVG)
- Displacement Detection
- Premium/Discount Zones
- Probability Scoring (A: 70-79, A+: 80-100)
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from config import (
    SWING_LOOKBACK, DISPLACEMENT_ATR_MULT, FVG_MIN_GAP_PCT,
    OB_MAX_CANDLES, OB_MIN_DISPLACEMENT, SWEEP_WICK_RATIO,
    SWEEP_BREAK_PCT, A_GRADE_MIN, A_PLUS_MIN, KILL_ZONES,
    TP_CONFIG
)

class Direction(Enum):
    BULLISH = "BUY"
    BEARISH = "SELL"
    NEUTRAL = "NEUTRAL"

class StructureType(Enum):
    BOS = "Break of Structure"
    CHOCH = "Change of Character"
    NONE = "None"

@dataclass
class SwingPoint:
    index: int
    price: float
    time: pd.Timestamp
    type: str

@dataclass
class OrderBlock:
    index: int
    time: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    type: str
    strength: float
    is_breaker: bool = False
    mitigated: bool = False

@dataclass
class FairValueGap:
    index: int
    time: pd.Timestamp
    top: float
    bottom: float
    type: str
    size: float
    filled: bool = False

@dataclass
class LiquiditySweep:
    index: int
    time: pd.Timestamp
    level: float
    type: str
    direction: str
    strength: float

@dataclass
class Setup:
    instrument: str
    direction: Direction
    grade: str
    probability: int
    entry_price: float
    stop_loss: float
    take_profits: List[Dict[str, Any]]
    setup_type: str
    timeframe: str
    notes: str
    confluence_score: int

class SMCAnalyzer:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._prepare_data()

    def _prepare_data(self):
        df = self.df
        df["tr1"] = df["high"] - df["low"]
        df["tr2"] = (df["high"] - df["close"].shift(1)).abs()
        df["tr3"] = (df["low"] - df["close"].shift(1)).abs()
        df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
        df["atr"] = df["tr"].rolling(window=14).mean()
        df["body_pct"] = df["body"] / df["range"]
        df["upper_wick_pct"] = df["upper_wick"] / df["range"]
        df["lower_wick_pct"] = df["lower_wick"] / df["range"]
        df["is_displacement"] = df["body"] > (df["atr"] * DISPLACEMENT_ATR_MULT)
        df["direction"] = np.where(df["close"] > df["open"], "bullish", 
                          np.where(df["close"] < df["open"], "bearish", "doji"))

    def find_swing_points(self) -> Tuple[List[SwingPoint], List[SwingPoint]]:
        df = self.df
        swing_highs = []
        swing_lows = []
        lookback = SWING_LOOKBACK

        for i in range(lookback, len(df) - lookback):
            window_high = df["high"].iloc[i - lookback:i + lookback + 1]
            window_low = df["low"].iloc[i - lookback:i + lookback + 1]

            if df["high"].iloc[i] == window_high.max():
                left_highs = df["high"].iloc[i - lookback:i]
                right_highs = df["high"].iloc[i + 1:i + lookback + 1]
                if len(left_highs) > 0 and len(right_highs) > 0:
                    if df["high"].iloc[i] > left_highs.max() and df["high"].iloc[i] >= right_highs.max():
                        swing_highs.append(SwingPoint(
                            index=i,
                            price=df["high"].iloc[i],
                            time=df.index[i],
                            type="high"
                        ))

            if df["low"].iloc[i] == window_low.min():
                left_lows = df["low"].iloc[i - lookback:i]
                right_lows = df["low"].iloc[i + 1:i + lookback + 1]
                if len(left_lows) > 0 and len(right_lows) > 0:
                    if df["low"].iloc[i] < left_lows.min() and df["low"].iloc[i] <= right_lows.min():
                        swing_lows.append(SwingPoint(
                            index=i,
                            price=df["low"].iloc[i],
                            time=df.index[i],
                            type="low"
                        ))

        return swing_highs, swing_lows

    def analyze_structure(self, swing_highs: List[SwingPoint], swing_lows: List[SwingPoint]) -> Dict[str, Any]:
        if not swing_highs or not swing_lows:
            return {"trend": Direction.NEUTRAL, "last_bos": None, "last_choch": None}

        all_swings = sorted(swing_highs + swing_lows, key=lambda x: x.index)
        trend = Direction.NEUTRAL
        last_bos = None
        last_choch = None

        recent = all_swings[-6:] if len(all_swings) >= 6 else all_swings

        if len(recent) >= 4:
            highs = [s for s in recent if s.type == "high"]
            lows = [s for s in recent if s.type == "low"]

            if len(highs) >= 2 and len(lows) >= 2:
                if highs[-1].price > highs[-2].price and lows[-1].price > lows[-2].price:
                    trend = Direction.BULLISH
                    last_bos = {"type": "bullish_bos", "index": highs[-1].index, "price": highs[-1].price}
                elif highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price:
                    trend = Direction.BEARISH
                    last_bos = {"type": "bearish_bos", "index": lows[-1].index, "price": lows[-1].price}

                if trend == Direction.BULLISH:
                    if len(lows) >= 3 and lows[-1].price < lows[-2].price:
                        last_choch = {"type": "bearish_choch", "index": lows[-1].index, "price": lows[-1].price}
                elif trend == Direction.BEARISH:
                    if len(highs) >= 3 and highs[-1].price > highs[-2].price:
                        last_choch = {"type": "bullish_choch", "index": highs[-1].index, "price": highs[-1].price}

        return {
            "trend": trend,
            "last_bos": last_bos,
            "last_choch": last_choch,
            "swing_highs": swing_highs,
            "swing_lows": swing_lows
        }

    def detect_liquidity_sweeps(self, structure: Dict[str, Any]) -> List[LiquiditySweep]:
        df = self.df
        swing_highs = structure.get("swing_highs", [])
        swing_lows = structure.get("swing_lows", [])
        sweeps = []

        if len(swing_highs) >= 2:
            for i in range(len(swing_highs) - 1):
                for j in range(i + 1, len(swing_highs)):
                    high1 = swing_highs[i]
                    high2 = swing_highs[j]
                    tolerance = high1.price * 0.0002

                    if abs(high1.price - high2.price) <= tolerance:
                        if high2.index < len(df) - 1:
                            post_high = df.iloc[high2.index + 1:min(high2.index + 5, len(df))]
                            for idx in range(len(post_high)):
                                candle = post_high.iloc[idx]
                                actual_idx = high2.index + 1 + idx

                                if candle["high"] > high2.price * (1 + SWEEP_BREAK_PCT):
                                    if candle["close"] < high2.price:
                                        if actual_idx + 1 < len(df):
                                            next_candle = df.iloc[actual_idx + 1]
                                            if next_candle["is_displacement"] and next_candle["direction"] == "bearish":
                                                sweeps.append(LiquiditySweep(
                                                    index=actual_idx,
                                                    time=df.index[actual_idx],
                                                    level=high2.price,
                                                    type="buy_side",
                                                    direction="bearish",
                                                    strength=candle["upper_wick_pct"]
                                                ))

        if len(swing_lows) >= 2:
            for i in range(len(swing_lows) - 1):
                for j in range(i + 1, len(swing_lows)):
                    low1 = swing_lows[i]
                    low2 = swing_lows[j]
                    tolerance = low1.price * 0.0002

                    if abs(low1.price - low2.price) <= tolerance:
                        if low2.index < len(df) - 1:
                            post_low = df.iloc[low2.index + 1:min(low2.index + 5, len(df))]
                            for idx in range(len(post_low)):
                                candle = post_low.iloc[idx]
                                actual_idx = low2.index + 1 + idx

                                if candle["low"] < low2.price * (1 - SWEEP_BREAK_PCT):
                                    if candle["close"] > low2.price:
                                        if actual_idx + 1 < len(df):
                                            next_candle = df.iloc[actual_idx + 1]
                                            if next_candle["is_displacement"] and next_candle["direction"] == "bullish":
                                                sweeps.append(LiquiditySweep(
                                                    index=actual_idx,
                                                    time=df.index[actual_idx],
                                                    level=low2.price,
                                                    type="sell_side",
                                                    direction="bullish",
                                                    strength=candle["lower_wick_pct"]
                                                ))

        return sweeps

    def find_order_blocks(self, structure: Dict[str, Any]) -> List[OrderBlock]:
        df = self.df
        obs = []

        for i in range(OB_MAX_CANDLES, len(df) - 1):
            if df["is_displacement"].iloc[i]:
                displacement_dir = df["direction"].iloc[i]

                for j in range(1, OB_MAX_CANDLES + 1):
                    if i - j < 0:
                        break

                    prev_candle = df.iloc[i - j]

                    if displacement_dir == "bullish" and prev_candle["direction"] == "bearish":
                        all_opposing = True
                        for k in range(1, j):
                            if df["direction"].iloc[i - k] == "bullish":
                                all_opposing = False
                                break

                        if all_opposing:
                            strength = df["body"].iloc[i] / df["atr"].iloc[i]
                            if strength >= OB_MIN_DISPLACEMENT:
                                obs.append(OrderBlock(
                                    index=i - j,
                                    time=df.index[i - j],
                                    open=prev_candle["open"],
                                    high=prev_candle["high"],
                                    low=prev_candle["low"],
                                    close=prev_candle["close"],
                                    type="bullish",
                                    strength=strength
                                ))
                            break

                    elif displacement_dir == "bearish" and prev_candle["direction"] == "bullish":
                        all_opposing = True
                        for k in range(1, j):
                            if df["direction"].iloc[i - k] == "bearish":
                                all_opposing = False
                                break

                        if all_opposing:
                            strength = df["body"].iloc[i] / df["atr"].iloc[i]
                            if strength >= OB_MIN_DISPLACEMENT:
                                obs.append(OrderBlock(
                                    index=i - j,
                                    time=df.index[i - j],
                                    open=prev_candle["open"],
                                    high=prev_candle["high"],
                                    low=prev_candle["low"],
                                    close=prev_candle["close"],
                                    type="bearish",
                                    strength=strength
                                ))
                            break

        return obs

    def find_breaker_blocks(self, obs: List[OrderBlock], structure: Dict[str, Any]) -> List[OrderBlock]:
        df = self.df
        breakers = []

        for ob in obs:
            if ob.index + 1 >= len(df):
                continue

            post_ob = df.iloc[ob.index + 1:]

            if ob.type == "bullish":
                broken = post_ob[post_ob["close"] < ob.low]
                if not broken.empty:
                    broken_idx = broken.index[0]
                    broken_pos = df.index.get_loc(broken_idx)

                    if broken_pos + 1 < len(df):
                        next_candle = df.iloc[broken_pos + 1]
                        if next_candle["is_displacement"] and next_candle["direction"] == "bearish":
                            breaker = OrderBlock(
                                index=ob.index,
                                time=ob.time,
                                open=ob.open,
                                high=ob.high,
                                low=ob.low,
                                close=ob.close,
                                type="bearish",
                                strength=ob.strength,
                                is_breaker=True
                            )
                            breakers.append(breaker)

            elif ob.type == "bearish":
                broken = post_ob[post_ob["close"] > ob.high]
                if not broken.empty:
                    broken_idx = broken.index[0]
                    broken_pos = df.index.get_loc(broken_idx)

                    if broken_pos + 1 < len(df):
                        next_candle = df.iloc[broken_pos + 1]
                        if next_candle["is_displacement"] and next_candle["direction"] == "bullish":
                            breaker = OrderBlock(
                                index=ob.index,
                                time=ob.time,
                                open=ob.open,
                                high=ob.high,
                                low=ob.low,
                                close=ob.close,
                                type="bullish",
                                strength=ob.strength,
                                is_breaker=True
                            )
                            breakers.append(breaker)

        return breakers

    def find_fvg(self) -> List[FairValueGap]:
        df = self.df
        fvgs = []

        for i in range(1, len(df) - 1):
            prev_candle = df.iloc[i - 1]
            mid_candle = df.iloc[i]
            next_candle = df.iloc[i + 1]

            if mid_candle["body"] == 0:
                continue

            if mid_candle["direction"] == "bullish":
                gap_bottom = prev_candle["high"]
                gap_top = next_candle["low"]

                if gap_top > gap_bottom:
                    gap_size = gap_top - gap_bottom
                    min_gap = mid_candle["close"] * FVG_MIN_GAP_PCT

                    if gap_size >= min_gap and mid_candle["is_displacement"]:
                        fvgs.append(FairValueGap(
                            index=i,
                            time=df.index[i],
                            top=gap_top,
                            bottom=gap_bottom,
                            type="bullish",
                            size=gap_size
                        ))

            elif mid_candle["direction"] == "bearish":
                gap_top = prev_candle["low"]
                gap_bottom = next_candle["high"]

                if gap_top > gap_bottom:
                    gap_size = gap_top - gap_bottom
                    min_gap = mid_candle["close"] * FVG_MIN_GAP_PCT

                    if gap_size >= min_gap and mid_candle["is_displacement"]:
                        fvgs.append(FairValueGap(
                            index=i,
                            time=df.index[i],
                            top=gap_top,
                            bottom=gap_bottom,
                            type="bearish",
                            size=gap_size
                        ))

        return fvgs

    def calculate_premium_discount(self, lookback: int = 50) -> float:
        df = self.df
        if len(df) < lookback:
            lookback = len(df)

        recent = df.iloc[-lookback:]
        range_high = recent["high"].max()
        range_low = recent["low"].min()

        if range_high == range_low:
            return 0.5

        current = df["close"].iloc[-1]
        position = (current - range_low) / (range_high - range_low)
        return position

    def score_setup(
        self,
        direction: Direction,
        structure: Dict[str, Any],
        sweeps: List[LiquiditySweep],
        obs: List[OrderBlock],
        fvgs: List[FairValueGap],
        breakers: List[OrderBlock],
        timeframe_name: str
    ) -> Tuple[int, str, Dict[str, Any]]:
        score = 0
        details = {
            "htf_alignment": False,
            "sweep_quality": 0,
            "fvg_confluence": False,
            "ob_quality": 0,
            "ltf_confirmation": False,
            "premium_discount": 0.5,
            "in_killzone": False,
            "breaker_confluence": False,
        }

        current_idx = len(self.df) - 1
        current_price = self.df["close"].iloc[-1]

        trend = structure.get("trend", Direction.NEUTRAL)
        if trend != Direction.NEUTRAL:
            if (direction == Direction.BULLISH and trend == Direction.BULLISH) or \
               (direction == Direction.BEARISH and trend == Direction.BEARISH):
                score += 20
                details["htf_alignment"] = True
            elif (direction == Direction.BULLISH and trend == Direction.BEARISH) or \
                 (direction == Direction.BEARISH and trend == Direction.BULLISH):
                score -= 10

        recent_sweeps = [s for s in sweeps if s.index >= current_idx - 10]
        if recent_sweeps:
            for sweep in recent_sweeps:
                if (direction == Direction.BULLISH and sweep.direction == "bullish") or \
                   (direction == Direction.BEARISH and sweep.direction == "bearish"):
                    sweep_score = min(15, int(sweep.strength * 20))
                    score += sweep_score
                    details["sweep_quality"] = sweep.strength
                    break

        recent_fvgs = [f for f in fvgs if f.index >= current_idx - 15]
        for fvg in recent_fvgs:
            if (direction == Direction.BULLISH and fvg.type == "bullish") or \
               (direction == Direction.BEARISH and fvg.type == "bearish"):
                if direction == Direction.BULLISH:
                    if current_price <= fvg.top * 1.001 and current_price >= fvg.bottom * 0.999:
                        score += 15
                        details["fvg_confluence"] = True
                        break
                else:
                    if current_price >= fvg.bottom * 0.999 and current_price <= fvg.top * 1.001:
                        score += 15
                        details["fvg_confluence"] = True
                        break

        recent_obs = [ob for ob in obs if ob.index >= current_idx - 20]
        for ob in recent_obs:
            if (direction == Direction.BULLISH and ob.type == "bullish") or \
               (direction == Direction.BEARISH and ob.type == "bearish"):
                if direction == Direction.BULLISH:
                    if current_price <= ob.high and current_price >= ob.low:
                        ob_score = min(15, int(ob.strength * 5))
                        score += ob_score
                        details["ob_quality"] = ob.strength
                        break
                else:
                    if current_price >= ob.low and current_price <= ob.high:
                        ob_score = min(15, int(ob.strength * 5))
                        score += ob_score
                        details["ob_quality"] = ob.strength
                        break

        recent_breakers = [b for b in breakers if b.index >= current_idx - 20]
        for breaker in recent_breakers:
            if (direction == Direction.BULLISH and breaker.type == "bullish") or \
               (direction == Direction.BEARISH and breaker.type == "bearish"):
                if direction == Direction.BULLISH:
                    if current_price <= breaker.high and current_price >= breaker.low:
                        score += 10
                        details["breaker_confluence"] = True
                        break
                else:
                    if current_price >= breaker.low and current_price <= breaker.high:
                        score += 10
                        details["breaker_confluence"] = True
                        break

        pd_ratio = self.calculate_premium_discount()
        details["premium_discount"] = pd_ratio

        if direction == Direction.BULLISH:
            if pd_ratio < 0.4:
                score += 10
            elif pd_ratio < 0.5:
                score += 5
            elif pd_ratio > 0.7:
                score -= 5
        elif direction == Direction.BEARISH:
            if pd_ratio > 0.6:
                score += 10
            elif pd_ratio > 0.5:
                score += 5
            elif pd_ratio < 0.3:
                score -= 5

        from datetime import datetime
        import pytz

        wat = pytz.timezone("Africa/Lagos")
        now_wat = datetime.now(wat)
        hour = now_wat.hour

        for zone_name, (start, end) in KILL_ZONES.items():
            if start <= hour <= end:
                score += 10
                details["in_killzone"] = True
                details["killzone"] = zone_name
                break

        last_choch = structure.get("last_choch")
        last_bos = structure.get("last_bos")

        if last_choch:
            choch_age = current_idx - last_choch["index"]
            if choch_age <= 5:
                if (direction == Direction.BULLISH and last_choch["type"] == "bullish_choch") or \
                   (direction == Direction.BEARISH and last_choch["type"] == "bearish_choch"):
                    score += 15
                    details["ltf_confirmation"] = True

        if not details["ltf_confirmation"] and last_bos:
            bos_age = current_idx - last_bos["index"]
            if bos_age <= 5:
                if (direction == Direction.BULLISH and last_bos["type"] == "bullish_bos") or \
                   (direction == Direction.BEARISH and last_bos["type"] == "bearish_bos"):
                    score += 10
                    details["ltf_confirmation"] = True

        score = max(0, min(100, score))

        if score >= A_PLUS_MIN:
            grade = "A+"
        elif score >= A_GRADE_MIN:
            grade = "A"
        else:
            grade = "B"

        return score, grade, details

    def generate_setup(self, instrument: str, timeframe_name: str) -> Optional[Setup]:
        swing_highs, swing_lows = self.find_swing_points()
        structure = self.analyze_structure(swing_highs, swing_lows)
        sweeps = self.detect_liquidity_sweeps(structure)
        obs = self.find_order_blocks(structure)
        breakers = self.find_breaker_blocks(obs, structure)
        fvgs = self.find_fvg()

        direction = Direction.NEUTRAL

        recent_sweeps = [s for s in sweeps if s.index >= len(self.df) - 10]
        recent_fvgs = [f for f in fvgs if f.index >= len(self.df) - 15]
        recent_obs = [ob for ob in obs if ob.index >= len(self.df) - 20]

        bullish_score = 0
        bearish_score = 0

        for sweep in recent_sweeps:
            if sweep.direction == "bullish":
                bullish_score += 2
            else:
                bearish_score += 2

        for fvg in recent_fvgs:
            if fvg.type == "bullish":
                bullish_score += 1
            else:
                bearish_score += 1

        for ob in recent_obs:
            if ob.type == "bullish":
                bullish_score += 1
            else:
                bearish_score += 1

        if bullish_score > bearish_score + 1:
            direction = Direction.BULLISH
        elif bearish_score > bullish_score + 1:
            direction = Direction.BEARISH

        if direction != Direction.NEUTRAL:
            prob, grade, details = self.score_setup(
                direction, structure, sweeps, obs, fvgs, breakers, timeframe_name
            )

            if prob >= A_GRADE_MIN:
                current_price = self.df["close"].iloc[-1]
                atr = self.df["atr"].iloc[-1]

                if direction == Direction.BULLISH:
                    entry_candidates = [current_price]
                    for ob in recent_obs:
                        if ob.type == "bullish":
                            entry_candidates.append(ob.low)
                    for fvg in recent_fvgs:
                        if fvg.type == "bullish":
                            entry_candidates.append(fvg.bottom)

                    entry = min(entry_candidates) if entry_candidates else current_price
                    sl = entry - (atr * 1.5)

                    recent_lows = [s.price for s in swing_lows if s.index >= len(self.df) - 20]
                    if recent_lows:
                        structure_sl = min(recent_lows) - (atr * 0.5)
                        sl = min(sl, structure_sl)

                else:
                    entry_candidates = [current_price]
                    for ob in recent_obs:
                        if ob.type == "bearish":
                            entry_candidates.append(ob.high)
                    for fvg in recent_fvgs:
                        if fvg.type == "bearish":
                            entry_candidates.append(fvg.top)

                    entry = max(entry_candidates) if entry_candidates else current_price
                    sl = entry + (atr * 1.5)

                    recent_highs = [s.price for s in swing_highs if s.index >= len(self.df) - 20]
                    if recent_highs:
                        structure_sl = max(recent_highs) + (atr * 0.5)
                        sl = max(sl, structure_sl)

                risk = abs(entry - sl)
                if risk == 0:
                    risk = atr

                tps = []
                tp_config = TP_CONFIG.get(grade, TP_CONFIG["A"])

                for tp_name, tp_data in tp_config.items():
                    rr = tp_data["rr"]
                    tp_prob = tp_data["prob"]
                    size = tp_data["size"]

                    if direction == Direction.BULLISH:
                        tp_price = entry + (risk * rr)
                    else:
                        tp_price = entry - (risk * rr)

                    tps.append({
                        "level": round(tp_price, 5),
                        "rr": rr,
                        "probability": tp_prob,
                        "size_pct": size,
                        "label": tp_name.upper()
                    })

                notes_parts = []
                if details["htf_alignment"]:
                    notes_parts.append("HTF aligned")
                if details["sweep_quality"] > 0:
                    notes_parts.append("Sweep: " + str(round(details["sweep_quality"], 2)))
                if details["fvg_confluence"]:
                    notes_parts.append("FVG confluence")
                if details["ob_quality"] > 0:
                    notes_parts.append("OB strength: " + str(round(details["ob_quality"], 1)))
                if details["breaker_confluence"]:
                    notes_parts.append("Breaker block")
                if details["in_killzone"]:
                    notes_parts.append("Killzone: " + details.get("killzone", ""))

                notes = " | ".join(notes_parts) if notes_parts else "Standard setup"

                return Setup(
                    instrument=instrument,
                    direction=direction,
                    grade=grade,
                    probability=prob,
                    entry_price=round(entry, 5),
                    stop_loss=round(sl, 5),
                    take_profits=tps,
                    setup_type="SMC_" + timeframe_name,
                    timeframe=timeframe_name,
                    notes=notes,
                    confluence_score=sum([
                        details["htf_alignment"],
                        details["fvg_confluence"],
                        details["breaker_confluence"],
                        details["ltf_confirmation"]
                    ])
                )

        return None
