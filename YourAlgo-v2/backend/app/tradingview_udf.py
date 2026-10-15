"""
TradingView UDF (Universal Data Feed) API & Public Stock Market Provider for Indian Equities.
Compatible with TradingView Advanced Charting Library & Public APIs specification.

Endpoints:
1. GET /api/v1/udf/config
2. GET /api/v1/udf/time
3. GET /api/v1/udf/symbols?symbol={symbol}
4. GET /api/v1/udf/search?query={q}&limit={limit}
5. GET /api/v1/udf/history?symbol={symbol}&resolution={res}&from={from}&to={to}
6. GET /api/v1/udf/quotes?symbols={s1,s2,...}
7. Public Market Data Fetcher (Yahoo Finance NSE fallback .NS)
"""

import time
import urllib.request
import urllib.parse
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Query, HTTPException
from .market_data import market_service, get_ist_now

router = APIRouter(prefix="/api/v1/udf", tags=["TradingView UDF"])

# Master dictionary of top Indian NSE Equities & Indices
NSE_SYMBOLS_DB: Dict[str, Dict[str, Any]] = {
    "RELIANCE": {
        "name": "RELIANCE",
        "ticker": "NSE:RELIANCE",
        "description": "Reliance Industries Ltd",
        "exchange": "NSE",
        "type": "stock",
        "currency_code": "INR",
        "session": "0915-1530",
        "timezone": "Asia/Kolkata",
        "minmov": 5,
        "pricescale": 100,
        "base_price": 1285.50
    },
    "TCS": {
        "name": "TCS",
        "ticker": "NSE:TCS",
        "description": "Tata Consultancy Services Ltd",
        "exchange": "NSE",
        "type": "stock",
        "currency_code": "INR",
        "session": "0915-1530",
        "timezone": "Asia/Kolkata",
        "minmov": 5,
        "pricescale": 100,
        "base_price": 3950.00
    },
    "HDFCBANK": {
        "name": "HDFCBANK",
        "ticker": "NSE:HDFCBANK",
        "description": "HDFC Bank Ltd",
        "exchange": "NSE",
        "type": "stock",
        "currency_code": "INR",
        "session": "0915-1530",
        "timezone": "Asia/Kolkata",
        "minmov": 5,
        "pricescale": 100,
        "base_price": 1640.80
    },
    "INFY": {
        "name": "INFY",
        "ticker": "NSE:INFY",
        "description": "Infosys Ltd",
        "exchange": "NSE",
        "type": "stock",
        "currency_code": "INR",
        "session": "0915-1530",
        "timezone": "Asia/Kolkata",
        "minmov": 5,
        "pricescale": 100,
        "base_price": 1820.25
    },
    "ICICIBANK": {
        "name": "ICICIBANK",
        "ticker": "NSE:ICICIBANK",
        "description": "ICICI Bank Ltd",
        "exchange": "NSE",
        "type": "stock",
        "currency_code": "INR",
        "session": "0915-1530",
        "timezone": "Asia/Kolkata",
        "minmov": 5,
        "pricescale": 100,
        "base_price": 1215.10
    },
    "SBIN": {
        "name": "SBIN",
        "ticker": "NSE:SBIN",
        "description": "State Bank of India",
        "exchange": "NSE",
        "type": "stock",
        "currency_code": "INR",
        "session": "0915-1530",
        "timezone": "Asia/Kolkata",
        "minmov": 5,
        "pricescale": 100,
        "base_price": 795.40
    },
    "BHARTIARTL": {
        "name": "BHARTIARTL",
        "ticker": "NSE:BHARTIARTL",
        "description": "Bharti Airtel Ltd",
        "exchange": "NSE",
        "type": "stock",
        "currency_code": "INR",
        "session": "0915-1530",
        "timezone": "Asia/Kolkata",
        "minmov": 5,
        "pricescale": 100,
        "base_price": 1650.00
    },
    "TATAMOTORS": {
        "name": "TATAMOTORS",
        "ticker": "NSE:TATAMOTORS",
        "description": "Tata Motors Ltd",
        "exchange": "NSE",
        "type": "stock",
        "currency_code": "INR",
        "session": "0915-1530",
        "timezone": "Asia/Kolkata",
        "minmov": 5,
        "pricescale": 100,
        "base_price": 940.50
    },
    "NIFTY": {
        "name": "NIFTY",
        "ticker": "NSE:NIFTY",
        "description": "NIFTY 50 Benchmark Index",
        "exchange": "NSE",
        "type": "index",
        "currency_code": "INR",
        "session": "0915-1530",
        "timezone": "Asia/Kolkata",
        "minmov": 5,
        "pricescale": 100,
        "base_price": 24882.49
    },
    "BANKNIFTY": {
        "name": "BANKNIFTY",
        "ticker": "NSE:BANKNIFTY",
        "description": "NIFTY Bank Index",
        "exchange": "NSE",
        "type": "index",
        "currency_code": "INR",
        "session": "0915-1530",
        "timezone": "Asia/Kolkata",
        "minmov": 5,
        "pricescale": 100,
        "base_price": 52125.13
    },
    "SENSEX": {
        "name": "SENSEX",
        "ticker": "BSE:SENSEX",
        "description": "BSE SENSEX 30 Benchmark Index",
        "exchange": "BSE",
        "type": "index",
        "currency_code": "INR",
        "session": "0915-1530",
        "timezone": "Asia/Kolkata",
        "minmov": 5,
        "pricescale": 100,
        "base_price": 72472.33
    },
    "NIFTY50": {
        "name": "NIFTY50",
        "ticker": "NSE:NIFTY",
        "description": "NIFTY 50 Benchmark Index",
        "exchange": "NSE",
        "type": "index",
        "currency_code": "INR",
        "session": "0915-1530",
        "timezone": "Asia/Kolkata",
        "minmov": 5,
        "pricescale": 100,
        "base_price": 22520.45
    }
}

# 1. TradingView UDF /config endpoint
@router.get("/config")
def get_udf_config():
    """
    Returns TradingView UDF capability configurations.
    """
    return {
        "supports_search": True,
        "supports_group_request": False,
        "supports_marks": False,
        "supports_timescale_marks": False,
        "supports_time": True,
        "exchanges": [
            {"value": "NSE", "name": "National Stock Exchange of India", "desc": "NSE Cash & Derivatives"}
        ],
        "symbols_types": [
            {"name": "Stock", "value": "stock"},
            {"name": "Index", "value": "index"}
        ],
        "supported_resolutions": ["1", "5", "15", "30", "60", "D", "W"]
    }

# 2. TradingView UDF /time endpoint
@router.get("/time")
def get_udf_time():
    """
    Returns current server epoch time in seconds.
    """
    return int(time.time())

# 3. TradingView UDF /symbols endpoint
@router.get("/symbols")
def get_udf_symbol(symbol: str = Query(...)):
    """
    Resolves TradingView symbol metadata for Indian market.
    """
    clean_sym = symbol.upper().replace("NSE:", "").replace("BSE:", "").replace(".NS", "")
    info = NSE_SYMBOLS_DB.get(clean_sym)

    if not info:
        # Fallback dynamic resolution
        info = {
            "name": clean_sym,
            "ticker": f"NSE:{clean_sym}",
            "description": f"{clean_sym} (NSE Equity)",
            "exchange": "NSE",
            "type": "stock",
            "currency_code": "INR",
            "session": "0915-1530",
            "timezone": "Asia/Kolkata",
            "minmov": 5,
            "pricescale": 100,
            "base_price": 500.0
        }

    return {
        "name": info["name"],
        "ticker": info["ticker"],
        "description": info["description"],
        "type": info["type"],
        "session": info["session"],
        "exchange": info["exchange"],
        "listed_exchange": info["exchange"],
        "timezone": info["timezone"],
        "minmov": info["minmov"],
        "pricescale": info["pricescale"],
        "minmove2": 0,
        "fractional": False,
        "has_intraday": True,
        "supported_resolutions": ["1", "5", "15", "30", "60", "D", "W"],
        "intraday_multipliers": ["1", "5", "15", "30", "60"],
        "has_no_volume": False,
        "currency_code": info["currency_code"]
    }

# 4. TradingView UDF /search endpoint
@router.get("/search")
def search_udf_symbols(
    query: str = Query(""),
    type: str = Query(""),
    exchange: str = Query(""),
    limit: int = Query(30)
):
    """
    Searches Indian equities matching the query string.
    """
    q = query.upper()
    matches = []
    for sym, data in NSE_SYMBOLS_DB.items():
        if not q or q in sym or q in data["description"].upper():
            matches.append({
                "symbol": sym,
                "full_name": data["ticker"],
                "description": data["description"],
                "exchange": data["exchange"],
                "ticker": data["ticker"],
                "type": data["type"]
            })
            if len(matches) >= limit:
                break
    return matches

# 5. TradingView UDF /history endpoint
@router.get("/history")
async def get_udf_history(
    symbol: str = Query(...),
    resolution: str = Query("15"),
    from_time: Optional[int] = Query(None, alias="from"),
    to_time: Optional[int] = Query(None, alias="to"),
    countback: Optional[int] = Query(80)
):
    """
    Returns K-line bar history in standard TradingView UDF format:
    { s: 'ok', t: [...], o: [...], h: [...], l: [...], c: [...], v: [...] }
    """
    clean_sym = symbol.upper().replace("NSE:", "").replace("BSE:", "").replace(".NS", "")
    
    # Map resolution string
    tf = "15m"
    if resolution in ["1", "5"]:
        tf = "5m"
    elif resolution in ["15", "30"]:
        tf = "15m"
    elif resolution in ["60", "120"]:
        tf = "1h"
    elif resolution in ["D", "1D", "W"]:
        tf = "1D"

    limit_bars = min(max(countback or 60, 20), 200)

    try:
        candles = await market_service.get_historical_data(clean_sym, timeframe=tf, limit=limit_bars)
        if not candles:
            return {"s": "no_data"}

        t_list, o_list, h_list, l_list, c_list, v_list = [], [], [], [], [], []
        for c in candles:
            # Parse timestamp to unix seconds
            try:
                dt = datetime.strptime(c.timestamp, "%Y-%m-%d %H:%M:%S")
                epoch_sec = int(dt.replace(tzinfo=timezone.utc).timestamp())
            except Exception:
                epoch_sec = int(time.time())

            t_list.append(epoch_sec)
            o_list.append(c.open)
            h_list.append(c.high)
            l_list.append(c.low)
            c_list.append(c.close)
            v_list.append(c.volume)

        return {
            "s": "ok",
            "t": t_list,
            "o": o_list,
            "h": h_list,
            "l": l_list,
            "c": c_list,
            "v": v_list
        }
    except Exception as e:
        return {"s": "error", "errmsg": str(e)}

# 6. TradingView UDF /quotes endpoint
@router.get("/quotes")
async def get_udf_quotes(symbols: str = Query(...)):
    """
    Batch quotes for TradingView watchlist and order panel.
    """
    sym_list = [s.strip().upper().replace("NSE:", "").replace("BSE:", "").replace(".NS", "") for s in symbols.split(",")]
    result_data = []

    for sym in sym_list:
        q = await market_service.get_quote(sym)
        if q:
            result_data.append({
                "s": "ok",
                "n": f"NSE:{sym}",
                "v": {
                    "ch": q.change,
                    "chp": q.change_pct,
                    "short_name": sym,
                    "exchange": "NSE",
                    "description": NSE_SYMBOLS_DB.get(sym, {}).get("description", f"{sym} Equity"),
                    "lp": q.ltp,
                    "open_price": q.open,
                    "high_price": q.high,
                    "low_price": q.low,
                    "prev_close_price": q.close,
                    "volume": q.volume
                }
            })

    return {"s": "ok", "d": result_data}

# ----------------- PUBLIC APIS FALLBACK (Yahoo Finance NSE) -----------------
@router.get("/public/quote/{symbol}")
def get_public_yahoo_quote(symbol: str):
    """
    Fetches actual live real-time price from free public Yahoo Finance NSE endpoint (.NS).
    Zero authentication / API key required.
    """
    clean_sym = symbol.upper().replace("NSE:", "").replace("BSE:", "").replace(".NS", "").replace(".BO", "")
    target_ticker = f"{clean_sym}.NS"
    exchange = "NSE"

    if clean_sym in ["NIFTY", "NIFTY50", "NIFTY_50", "NIFTYFIFTY"]:
        target_ticker = "^NSEI"
        clean_sym = "NIFTY"
        exchange = "NSE"
    elif clean_sym in ["SENSEX", "BSESENSEX", "BSE_SENSEX"]:
        target_ticker = "^BSESN"
        clean_sym = "SENSEX"
        exchange = "BSE"
    elif clean_sym == "BANKNIFTY":
        target_ticker = "^NSEBANK"
        clean_sym = "BANKNIFTY"
        exchange = "NSE"

    encoded_ticker = urllib.parse.quote(target_ticker)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_ticker}?interval=15m&range=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            res = data.get("chart", {}).get("result", [])[0]
            meta = res.get("meta", {})
            ltp = meta.get("regularMarketPrice", 0.0)
            prev = meta.get("chartPreviousClose", ltp)
            change = round(ltp - prev, 2)
            change_pct = round((change / prev) * 100, 2) if prev > 0 else 0.0

            return {
                "source": "Public APIs (Yahoo Finance India)",
                "symbol": clean_sym,
                "ticker": target_ticker,
                "exchange": exchange,
                "currency": meta.get("currency", "INR"),
                "ltp": ltp,
                "previous_close": prev,
                "change": change,
                "change_pct": change_pct,
                "day_high": meta.get("regularMarketDayHigh", ltp),
                "day_low": meta.get("regularMarketDayLow", ltp),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Public API fetch failed: {str(e)}")
