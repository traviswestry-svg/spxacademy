import math
import os
import random
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
MASSIVE_BASE = os.getenv("MASSIVE_BASE", "https://api.massive.com")
DEFAULT_SYMBOL = os.getenv("TRAINER_SYMBOL", "SPX")
PROXY_TICKER = os.getenv("TRAINER_PROXY_TICKER", "SPY")

LESSONS = [
    {
        "title": "A+ 0DTE Entry Checklist",
        "body": "Trade with trend, near value, after a confirmation candle. Avoid chasing wide candles far from EMA8/VWAP. Your job is not to predict every move; it is to wait for the cleanest 15-minute opportunity.",
        "checks": ["VWAP side agrees with your trade", "EMA8 is on the correct side of EMA21", "Entry candle closes in your direction", "Risk is defined before entry", "Exit plan is under 15 minutes"],
    },
    {
        "title": "Candle Reading for SPX Speed",
        "body": "On SPX 0DTE, a candle is not just green or red. Read body size, wick rejection, location versus VWAP, and whether the candle appears after extension or pullback.",
        "checks": ["Big body after extension can be a chase trap", "Long lower wick near VWAP can show dip absorption", "Long upper wick near resistance can show supply", "Doji after a run means decision pressure, not confidence"],
    },
    {
        "title": "Exit Discipline",
        "body": "The simulator rewards trade management: protect capital, take high-quality movement, and avoid turning a quick 0DTE scalp into a hope trade.",
        "checks": ["Take partial/exit when momentum slows", "Do not let a green trade reverse to red", "Exit if thesis candle fails", "Respect the 15-minute training window"],
    },
]

SCENARIOS = {
    "trend_up": {"label": "Trend Up Pullback", "trend": 1.0, "chop": 0.8, "trap": 0.5, "description": "Bull trend with pullbacks to VWAP/EMA. Teaches patience and pullback entries."},
    "trend_down": {"label": "Trend Down Rejection", "trend": -1.0, "chop": 0.8, "trap": 0.5, "description": "Bear trend with failed bounces. Teaches short entries after rejection."},
    "chop": {"label": "Chop / No-Trade Day", "trend": 0.0, "chop": 2.1, "trap": 1.4, "description": "Fast rotations and fake breaks. Teaches when not to trade."},
    "reversal": {"label": "Morning Reversal", "trend": 0.7, "chop": 1.25, "trap": 1.1, "description": "Initial move reverses. Teaches not marrying bias."},
    "news": {"label": "News Spike Hard Mode", "trend": 0.25, "chop": 2.6, "trap": 2.2, "description": "Violent candles and slippage-like movement. Teaches caution around speed."},
}


def ema(values, period):
    if not values:
        return []
    k = 2 / (period + 1)
    out = [values[0]]
    for value in values[1:]:
        out.append(value * k + out[-1] * (1 - k))
    return out


def atr(bars, period=14):
    if not bars:
        return []
    trs = []
    for i, bar in enumerate(bars):
        prev_close = bars[i - 1]["close"] if i else bar["close"]
        tr = max(bar["high"] - bar["low"], abs(bar["high"] - prev_close), abs(bar["low"] - prev_close))
        trs.append(tr)
    out = []
    running = trs[0]
    for i, tr in enumerate(trs):
        if i < period:
            running = sum(trs[: i + 1]) / (i + 1)
        else:
            running = ((running * (period - 1)) + tr) / period
        out.append(running)
    return out


def classify_candle(bar, prev=None):
    rng = max(bar["high"] - bar["low"], 0.01)
    body = abs(bar["close"] - bar["open"])
    upper = bar["high"] - max(bar["open"], bar["close"])
    lower = min(bar["open"], bar["close"]) - bar["low"]
    direction = "bullish" if bar["close"] > bar["open"] else "bearish" if bar["close"] < bar["open"] else "doji"
    shape = "normal candle"
    lesson = "Normal candle. Judge it by location: VWAP, EMA8/EMA21, prior high/low, and whether it follows extension or pullback."
    if body / rng < 0.18:
        shape = "doji / indecision"
        lesson = "Doji/indecision: neither side controlled the close. On SPX 0DTE, this usually says wait unless the next candle confirms direction."
    elif lower / rng > 0.42 and direction == "bullish":
        shape = "bullish rejection"
        lesson = "Bullish rejection: sellers pushed down, buyers reclaimed. Stronger when it happens at VWAP, EMA21, or prior support."
    elif upper / rng > 0.42 and direction == "bearish":
        shape = "bearish rejection"
        lesson = "Bearish rejection: buyers pushed up, sellers rejected. Stronger when it happens below VWAP or at prior resistance."
    elif body / rng > 0.64:
        shape = "wide momentum candle"
        lesson = "Wide momentum candle: confirms force, but entering late after it can be a chase. Prefer pullback or continuation confirmation."
    if prev:
        if bar["close"] > prev["high"] and direction == "bullish":
            shape = "bullish outside / breakout candle"
            lesson = "Bullish outside/breakout candle: strong, but avoid buying the top if it is far from EMA8/VWAP."
        if bar["close"] < prev["low"] and direction == "bearish":
            shape = "bearish outside / breakdown candle"
            lesson = "Bearish outside/breakdown candle: strong, but avoid shorting the low if it is extended from value."
    return {
        "direction": direction,
        "shape": shape,
        "lesson": lesson,
        "bodyPct": round(100 * body / rng),
        "upperWickPct": round(100 * upper / rng),
        "lowerWickPct": round(100 * lower / rng),
    }


def add_indicators(bars):
    closes = [b["close"] for b in bars]
    e8 = ema(closes, 8)
    e21 = ema(closes, 21)
    e50 = ema(closes, 50)
    a14 = atr(bars, 14)
    cpv = 0.0
    cv = 0.0
    for i, bar in enumerate(bars):
        tp = (bar["high"] + bar["low"] + bar["close"]) / 3
        volume = max(float(bar.get("volume", 1)), 1.0)
        cpv += tp * volume
        cv += volume
        bar["ema8"] = round(e8[i], 2)
        bar["ema21"] = round(e21[i], 2)
        bar["ema50"] = round(e50[i], 2)
        bar["vwap"] = round(cpv / cv, 2)
        bar["atr"] = round(a14[i], 2)
        bar["candle"] = classify_candle(bar, bars[i - 1] if i else None)
    return bars


def fetch_market_bars():
    if not POLYGON_API_KEY:
        return None
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=18)
    end = today + timedelta(days=1)
    url = f"{MASSIVE_BASE}/v2/aggs/ticker/{PROXY_TICKER}/range/1/minute/{start}/{end}?adjusted=true&sort=asc&limit=50000&apiKey={POLYGON_API_KEY}"
    try:
        resp = requests.get(url, timeout=20)
        data = resp.json()
        if resp.status_code != 200 or not data.get("results"):
            return None
        raw = data["results"][-390:]
        scale = 10.0 if DEFAULT_SYMBOL.upper() == "SPX" else 1.0
        bars = []
        for r in raw:
            ts = datetime.fromtimestamp(r["t"] / 1000, tz=timezone.utc).astimezone().isoformat()
            bars.append({"time": ts, "open": round(r["o"] * scale, 2), "high": round(r["h"] * scale, 2), "low": round(r["l"] * scale, 2), "close": round(r["c"] * scale, 2), "volume": int(r.get("v", 1))})
        return bars
    except Exception:
        return None


def synthetic_session(scenario="news", seed=None):
    cfg = SCENARIOS.get(scenario, SCENARIOS["news"])
    rng = random.Random(seed or f"{datetime.utcnow().strftime('%Y%m%d%H%M')}-{scenario}")
    bars = []
    base = 6100 + rng.uniform(-85, 85)
    price = base
    start = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
    trend_strength = cfg["trend"] * rng.uniform(0.09, 0.28)
    reverse_at = rng.choice([55, 80, 118]) if scenario == "reversal" else None
    for i in range(210):
        if reverse_at and i == reverse_at:
            trend_strength *= -1.85
        burst = 1.0
        if 18 < i < 45 or 78 < i < 110 or 142 < i < 172:
            burst = rng.uniform(1.3, 2.8) * cfg["trap"]
        mean_revert = -0.024 * (price - base) * (1.4 if scenario == "chop" else 0.7)
        chop_wave = math.sin(i / rng.uniform(3.3, 6.2)) * rng.uniform(0.5, 2.2) * cfg["chop"]
        shock = rng.gauss(0, 1.25 * burst * max(cfg["chop"], 0.7))
        drift = trend_strength + mean_revert + chop_wave + shock
        if scenario in ("trend_up", "trend_down"):
            drift += trend_strength * i / 55
        if scenario == "news" and i in (38, 96, 151):
            drift += rng.choice([-1, 1]) * rng.uniform(7, 16)
        o = price
        c = price + drift
        wick = abs(rng.gauss(2.4, 1.1)) * max(burst, 1)
        h = max(o, c) + wick * rng.uniform(0.35, 1.35)
        l = min(o, c) - wick * rng.uniform(0.35, 1.35)
        volume = int(rng.uniform(85000, 390000) * max(burst, 1))
        bars.append({"time": (start + timedelta(minutes=i)).isoformat(), "open": round(o, 2), "high": round(h, 2), "low": round(l, 2), "close": round(c, 2), "volume": volume})
        price = c
    return bars


def session_context(bars, scenario="news", source="synthetic"):
    first = bars[0]["open"]
    last = bars[-1]["close"]
    hi = max(b["high"] for b in bars)
    lo = min(b["low"] for b in bars)
    cfg = SCENARIOS.get(scenario, SCENARIOS["news"])
    return {
        "symbol": DEFAULT_SYMBOL,
        "instrument": "SPX 0DTE Academy Dashboard v1.0",
        "warning": "Training only. This dashboard does not place trades and is not financial advice.",
        "rangePoints": round(hi - lo, 2),
        "netMovePoints": round(last - first, 2),
        "difficulty": cfg["description"],
        "scenario": scenario,
        "scenarioLabel": cfg["label"],
        "source": source,
    }


def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


def setup_quality_at(bars, i, direction):
    b = bars[i]
    sign = 1 if direction == "long" else -1
    trend_good = (b["ema8"] > b["ema21"] and b["close"] > b["vwap"]) if sign == 1 else (b["ema8"] < b["ema21"] and b["close"] < b["vwap"])
    near_value = min(abs(b["close"] - b["vwap"]), abs(b["close"] - b["ema8"]), abs(b["close"] - b["ema21"])) <= max(b.get("atr", 1) * 0.65, 1)
    candle = b.get("candle", {})
    confirm = (sign == 1 and candle.get("direction") == "bullish" and candle.get("lowerWickPct", 0) >= 15) or (sign == -1 and candle.get("direction") == "bearish" and candle.get("upperWickPct", 0) >= 15)
    chase = abs(b["close"] - b["ema8"]) / max(b.get("atr", 1), 0.01)
    score = (30 if trend_good else 8) + (25 if near_value else 8) + (25 if confirm else 7) + (20 if chase <= 0.95 else 6)
    return {"score": round(clamp(score)), "trendGood": trend_good, "nearValue": near_value, "confirmation": confirm, "chaseMultiple": round(chase, 2)}


def score_trade(payload):
    bars = payload.get("bars", [])
    entry_i = int(payload.get("entryIndex", -1))
    exit_i = int(payload.get("exitIndex", -1))
    direction = payload.get("direction", "long")
    if not bars or entry_i < 2 or exit_i <= entry_i or exit_i >= len(bars):
        return {"score": 0, "grade": "Invalid", "summary": "Trade could not be scored. Entry and exit must both exist after replay starts.", "details": []}
    entry = bars[entry_i]
    exitb = bars[exit_i]
    sign = 1 if direction == "long" else -1
    entry_price = float(payload.get("entryPrice", entry["close"]))
    exit_price = float(payload.get("exitPrice", exitb["close"]))
    pnl_points = round((exit_price - entry_price) * sign, 2)
    window = exit_i - entry_i
    trade_bars = bars[entry_i: exit_i + 1]
    mfe = max((b["high"] - entry_price) if sign == 1 else (entry_price - b["low"]) for b in trade_bars)
    mae = min((b["low"] - entry_price) if sign == 1 else (entry_price - b["high"]) for b in trade_bars)
    capture = 0 if mfe <= 0 else clamp((pnl_points / mfe) * 100)
    quality = setup_quality_at(bars, entry_i, direction)
    entry_score = round(quality["score"] * 0.60)
    exit_score = 0
    exit_score += 12 if window <= 15 else 0
    exit_score += 15 if capture >= 70 else 10 if capture >= 45 else 5 if pnl_points > 0 else 1
    exit_score += 8 if pnl_points > 0 else 3 if abs(mae) <= max(entry.get("atr", 1), 1) else 1
    exit_score += 5 if abs(mae) <= max(entry.get("atr", 1) * 1.25, 2) else 1
    total = round(clamp(entry_score + exit_score))
    grade = "A+" if total >= 95 else "A" if total >= 90 else "B" if total >= 80 else "C" if total >= 70 else "D" if total >= 60 else "Needs Work"
    mistakes = []
    if not quality["trendGood"]: mistakes.append("fought VWAP/EMA trend")
    if not quality["nearValue"]: mistakes.append("entered away from value")
    if not quality["confirmation"]: mistakes.append("weak candle confirmation")
    if quality["chaseMultiple"] > 0.95: mistakes.append("chased extension")
    if window > 15: mistakes.append("held beyond 15-minute drill")
    details = [
        f"P/L: {pnl_points:+.2f} points over {window} minute(s). MFE: {mfe:.2f}; MAE: {mae:.2f}; capture: {capture:.0f}%.",
        "Entry aligned with VWAP/EMA trend." if quality["trendGood"] else "Entry fought the short-term VWAP/EMA trend. Wait for alignment unless intentionally practicing countertrend scalps.",
        "Entry was near value." if quality["nearValue"] else "Entry was extended from VWAP/EMA value. SPX 0DTE punishes late entries because contracts move too fast.",
        "Candle confirmation supported the entry." if quality["confirmation"] else "Candle confirmation was not clean. Look for rejection wick plus close in your direction.",
        "Exit stayed inside the 15-minute rule." if window <= 15 else "Exit violated the 15-minute training rule.",
    ]
    summary = "Clean academy rep. Keep repeating this pattern." if total >= 85 else "Good learning rep. Main issue: " + (", ".join(mistakes) if mistakes else "exit management.")
    return {"score": total, "grade": grade, "summary": summary, "pnlPoints": pnl_points, "mfe": round(mfe, 2), "mae": round(mae, 2), "capturePct": round(capture), "entryScore": entry_score, "exitScore": exit_score, "mistakes": mistakes, "details": details}


@app.route("/")
def root():
    return jsonify({"app": "SPX 0DTE Academy Dashboard v1.0 API", "status": "ok", "training_only": True})


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/api/trainer/lessons")
def lessons():
    return jsonify({"lessons": LESSONS, "scenarios": SCENARIOS})


@app.route("/api/trainer/session")
def trainer_session():
    scenario = request.args.get("scenario", "news")
    live = request.args.get("live", "false").lower() == "true"
    source = "synthetic_hard_mode"
    bars = fetch_market_bars() if live else None
    if bars:
        source = f"{PROXY_TICKER}_proxy_scaled"
    else:
        bars = synthetic_session(scenario=scenario)
    bars = add_indicators(bars)
    return jsonify({"bars": bars, "context": session_context(bars, scenario=scenario, source=source), "source": source})


@app.route("/api/trainer/score", methods=["POST"])
def trainer_score():
    return jsonify(score_trade(request.get_json(force=True)))


@app.route("/api/trainer/coach", methods=["POST"])
def trainer_coach():
    payload = request.get_json(force=True)
    bars = payload.get("bars", [])
    index = int(payload.get("index", 0))
    if not bars or index < 0 or index >= len(bars):
        return jsonify({"lesson": "No candle selected."})
    b = bars[index]
    bias = "bullish" if b["ema8"] > b["ema21"] and b["close"] > b["vwap"] else "bearish" if b["ema8"] < b["ema21"] and b["close"] < b["vwap"] else "mixed/choppy"
    q_long = setup_quality_at(bars, index, "long")
    q_short = setup_quality_at(bars, index, "short")
    best = "WAIT"
    if q_long["score"] >= 78 and q_long["score"] >= q_short["score"] + 8:
        best = "LONG practice candidate"
    elif q_short["score"] >= 78 and q_short["score"] >= q_long["score"] + 8:
        best = "SHORT practice candidate"
    lesson = f"Candle: {b['candle']['shape']} ({b['candle']['direction']}). Bias is {bias}. Coach call: {best}. Long quality {q_long['score']}/100; short quality {q_short['score']}/100. {b['candle']['lesson']}"
    return jsonify({"lesson": lesson, "bias": bias, "longQuality": q_long, "shortQuality": q_short, "bestAction": best})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
