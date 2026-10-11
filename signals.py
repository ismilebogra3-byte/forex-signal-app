#!/usr/bin/env python3
"""Signal engine: EMA9/21 cross + RSI + MACD filter, ATR based SL/TP.
Run once:  python signals.py
Run loop:  python signals.py --loop
Phone push via ntfy: export NTFY_TOPIC=your-secret-topic
Not financial advice. Test on a demo account first.
"""
import json, os, sys, time
from datetime import datetime, timezone
import requests

UA = {"User-Agent": "Mozilla/5.0"}
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")
INTERVAL = "15m"
STATE_FILE = "state.json"
OUT_FILE = os.path.join("docs", "signals.json")

PAIRS = {
    "EURUSD": ("yahoo", "EURUSD=X"),
    "GBPJPY": ("yahoo", "GBPJPY=X"),
    "USDJPY": ("yahoo", "USDJPY=X"),
    "XAUUSD": ("yahoo", "GC=F"),
    "BTCUSD": ("binance", "BTCUSDT"),
    "BNBUSD": ("binance", "BNBUSDT"),
    "ETHUSD": ("binance", "ETHUSDT"),
}


def fetch_yahoo(sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
    r = requests.get(url, params={"interval": INTERVAL, "range": "5d"},
                     headers=UA, timeout=20).json()
    res = r["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    out = []
    for t, h, l, c in zip(res["timestamp"], q["high"], q["low"], q["close"]):
        if None not in (h, l, c):
            out.append({"t": t, "h": h, "l": l, "c": c})
    return out


def fetch_binance(sym):
    r = requests.get("https://data-api.binance.vision/api/v3/klines",
                     params={"symbol": sym, "interval": INTERVAL, "limit": 200},
                     headers=UA, timeout=20).json()
    return [{"t": k[0] // 1000, "h": float(k[2]), "l": float(k[3]),
             "c": float(k[4])} for k in r]


def ema(vals, n):
    k, out = 2 / (n + 1), [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(closes, n=14):
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    ag, al = gains / n, losses / n
    for i in range(n + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (n - 1) + max(d, 0)) / n
        al = (al * (n - 1) + max(-d, 0)) / n
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def atr(c, n=14):
    trs = []
    for i in range(1, len(c)):
        trs.append(max(c[i]["h"] - c[i]["l"],
                       abs(c[i]["h"] - c[i - 1]["c"]),
                       abs(c[i]["l"] - c[i - 1]["c"])))
    return sum(trs[-n:]) / n


def fmt(p):
    return f"{p:.5f}" if p < 10 else f"{p:.3f}" if p < 1000 else f"{p:.2f}"


def analyze(name, candles):
    candles = candles[:-1]  # drop the still-forming candle
    if len(candles) < 60:
        return None
    closes = [x["c"] for x in candles]
    e9, e21 = ema(closes, 9), ema(closes, 21)
    macd = [a - b for a, b in zip(ema(closes, 12), ema(closes, 26))]
    hist = macd[-1] - ema(macd, 9)[-1]
    r = rsi(closes)
    side = None
    if e9[-2] <= e21[-2] and e9[-1] > e21[-1] and hist > 0 and 45 < r < 70:
        side = "BUY"
    elif e9[-2] >= e21[-2] and e9[-1] < e21[-1] and hist < 0 and 30 < r < 55:
        side = "SELL"
    if not side:
        return None
    entry, a = closes[-1], atr(candles)
    s = 1 if side == "BUY" else -1
    return {
        "pair": name, "side": side, "entry": entry,
        "time": datetime.fromtimestamp(candles[-1]["t"], timezone.utc)
                .strftime("%Y-%m-%d %H:%M UTC"),
        "tp1": entry + s * 1.5 * a, "tp2": entry + s * 3 * a,
        "sl": entry - s * 1.5 * a, "candle": candles[-1]["t"],
    }


def notify(sig):
    msg = (f"{sig['pair']} {sig['side']}\nEntry: {fmt(sig['entry'])}\n"
           f"Time: {sig['time']}\nTP1: {fmt(sig['tp1'])}\n"
           f"TP2: {fmt(sig['tp2'])}\nSL: {fmt(sig['sl'])}")
    print(msg, "\n")
    if NTFY_TOPIC:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode(),
                      headers={"Title": f"{sig['pair']} {sig['side']}",
                               "Priority": "high"}, timeout=15)


def save_signal(sig):
    try:
        data = json.load(open(OUT_FILE))
    except Exception:
        data = []
    row = {k: (fmt(v) if k in ("entry", "tp1", "tp2", "sl") else v)
           for k, v in sig.items() if k != "candle"}
    data.insert(0, row)
    os.makedirs("docs", exist_ok=True)
    json.dump(data[:100], open(OUT_FILE, "w"), indent=1)


def run_once():
    try:
        state = json.load(open(STATE_FILE))
    except Exception:
        state = {}
    for name, (src, sym) in PAIRS.items():
        try:
            candles = fetch_yahoo(sym) if src == "yahoo" else fetch_binance(sym)
            sig = analyze(name, candles)
            if sig and state.get(name) != sig["candle"]:
                notify(sig)
                save_signal(sig)
                state[name] = sig["candle"]
        except Exception as e:
            print(f"[{name}] error: {e}")
    json.dump(state, open(STATE_FILE, "w"))


if __name__ == "__main__":
    run_once()
    while "--loop" in sys.argv:
        time.sleep(900)
        run_once()
