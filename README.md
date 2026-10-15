# 🚀 YourAlgo v2 — Indian Equity Algorithmic Trading & Quantitative AI Platform

[![NSE Market Timing](https://img.shields.io/badge/Exchange-NSE%20India%20(IST)-0284c7.svg)](https://www.nseindia.com)
[![SEBI Compliance](https://img.shields.io/badge/Risk%20Engine-SEBI%20Compliant-10b981.svg)](#-mathematical-risk-engine--position-sizing)
[![Broker Support](https://img.shields.io/badge/Broker-Upstox%20API%20v2%20%7C%20Paper-f59e0b.svg)](#-upstox-v2--paper-broker-adapters)
[![Validation Suite](https://img.shields.io/badge/Live%20Tests-33%2F33%20Passed-22c55e.svg)](#-live-market-validation-suite)
[![Tech Stack](https://img.shields.io/badge/Stack-FastAPI%20%2B%20React%20%2B%20TypeScript%20%2B%20Vite-8b5cf6.svg)](#%EF%B8%8F-technology-stack)
[![Database](https://img.shields.io/badge/Warehouse-MySQL%208.0%20%2B%20Redis-06b6d4.svg)](#-nse-data-warehouse--mysql-pipeline)

> **YourAlgo v2** is an institutional-grade, sub-second algorithmic trading, quantitative analytics, and AI screening platform engineered specifically for the **National Stock Exchange of India (NSE)**. It delivers real-time order execution via Upstox API v2, high-fidelity paper trading with accurate Indian tick sizes (₹0.05), AI-driven stock scoring (InvestIQ & Kronos), an official TradingView UDF chart studio, and a SEBI-aligned risk management engine.

---

## 📑 Table of Contents
- [✨ Key Platform Capabilities](#-key-platform-capabilities)
- [🏗️ System Architecture](#%EF%B8%8F-system-architecture)
- [⚙️ Technology Stack](#%EF%B8%8F-technology-stack)
- [📈 Core Quantitative Algorithms](#-core-quantitative-algorithms)
- [🛡️ Mathematical Risk Engine & Position Sizing](#%EF%B8%8F-mathematical-risk-engine--position-sizing)
- [🤖 InvestIQ AI Engine (3,100+ Equities)](#-investiq-ai-engine-3100-equities)
- [⏳ Kronos AI Foundation Model](#-kronos-ai-foundation-model)
- [📊 TradingView Real-Time Chart Studio](#-tradingview-real-time-chart-studio)
- [🗄️ NSE Data Warehouse & MySQL Pipeline](#%EF%B8%8F-nse-data-warehouse--mysql-pipeline)
- [🧪 Live Market Validation Suite](#-live-market-validation-suite)
- [🚀 Quickstart & Setup Guide](#-quickstart--setup-guide)
- [📁 Repository Structure](#-repository-structure)
- [⚖️ Risk Disclaimer](#%EF%B8%8F-risk-disclaimer)

---

## ✨ Key Platform Capabilities

1. **Authoritative Indian Market Timings & Sessions**:
   - Accurately tracks Indian Standard Time (IST, UTC+5:30), Pre-Market Call Auction (09:00 – 09:15), Regular Trading (09:15 – 15:30), and Post-Market Closing Session.
2. **Strict Indian Rupee (₹) & Tick Size Engine**:
   - Strictly enforces NSE's official **₹0.05 tick size**, lot size rules, and INR currency formatting across all live quotes, order limits, and position tracking.
3. **Upstox API v2 & Paper Trading Adapter**:
   - Zero-risk paper simulation with realistic slippage, simulated fills, and live Upstox OAuth 2.0 Web SSO authentication.
4. **Autonomous Execution Engine**:
   - Multi-strategy execution loops evaluating **EMA + VWAP + RSI**, **15-Minute Opening Range Breakout (ORB)**, and **VWAP Pullback**.
5. **AI Research & Quantitative Alpha**:
   - Built-in **InvestIQ** multi-factor scoring (Market + Financial + FinBERT Sentiment) and **Kronos** deep time-series transformer forecasts.
6. **TradingView Chart Studio**:
   - Full candlestick charting with official UDF datafeed protocol (`/api/v1/udf`), custom indicators, and one-click order placement directly from chart levels.

---

## 🏗️ System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           REACT + VITE FRONTEND (PORT 5173 / 8000)          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Dashboard &  │  │ TradingView  │  │ InvestIQ AI  │  │ Kronos AI       │  │
│  │ Live Ticker  │  │ Chart Studio │  │ Screening    │  │ Foundation View │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────────┬────────┘  │
└─────────┼─────────────────┼─────────────────┼───────────────────┼───────────┘
          │                 │ REST / WebSockets                   │
┌─────────▼─────────────────▼─────────────────▼───────────────────▼───────────┐
│                           FASTAPI ASYNC BACKEND (PORT 8000)                 │
│  ┌───────────────────┐  ┌─────────────────────┐  ┌───────────────────────┐  │
│  │ Automation Engine │  │ Market Data Service │  │ SEBI Risk Engine      │  │
│  │ (Quant Strats)    │  │ (NSE Quotes / UDF)  │  │ (Max Loss / Kill Sw.) │  │
│  └─────────┬─────────┘  └──────────┬──────────┘  └───────────┬───────────┘  │
│            │                       │                         │              │
│  ┌─────────▼─────────┐  ┌──────────▼──────────┐  ┌───────────▼───────────┐  │
│  │ Upstox Adapter v2 │  │ Paper Broker Engine │  │ SQLite / MySQL Storage│  │
│  └───────────────────┘  └─────────────────────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Technology Stack

| Layer | Technology | Production Role |
|---|---|---|
| **Frontend UI** | React 19 + TypeScript + Vite | High-speed, responsive trading terminal with glassmorphic dark design |
| **Charting** | TradingView Lightweight Charts | Canvas-rendered candlesticks, multi-timeframe overlays, technical indicators |
| **Backend API** | FastAPI + Uvicorn (Python 3.10+) | High-concurrency async REST endpoints, WebSocket streaming, Pydantic validation |
| **Broker Integration** | Upstox API v2 & Paper Engine | Automated order routing, position tracking, OAuth 2.0 Web SSO |
| **Database** | MySQL 8.0+ / SQLite + SQLAlchemy | Relational storage for users, orders, executions, and 100k+ NSE historical records |
| **Cache & Real-Time** | Redis 7.0+ (Optional) | Distributed tick caching, atomic locks, rate-limiting |
| **Machine Learning** | PyTorch / scikit-learn / FinBERT | Deep time-series transformer forecasts and sentiment classification |

---

## 📈 Core Quantitative Algorithms

Primary execution runs on mathematically deterministic, backtested strategies:

### 1. EMA + VWAP + RSI Trend Following Strategy
A **Long Entry** order is triggered *only* when all conditions align simultaneously:
- **EMA Trend:** `EMA(20) > EMA(50)`
- **Value Anchor:** `Close Price > VWAP`
- **Momentum:** `RSI(14) > 50.0`
- **Volume Confirmation:** `Volume > 20-bar Average Volume`
- **Position Guard:** No existing open position in the instrument
- **Account Guard:** Cumulative loss < Daily Max Loss Limit
- **Risk Gate:** Approved by server-side `validate_trade()`

**Exit Triggers:**
- **Target Hit:** `Entry + (Stop Distance × 3)` (1:3 Risk/Reward)
- **Stop Loss Hit:** ATR-based volatility stop reached
- **Trend Invalidation:** `EMA(20) < EMA(50)` or `Close < VWAP`
- **EOD Cutoff:** `15:15 IST` intraday auto-square off
- **Emergency:** Global Kill Switch trigger

### 2. 15-Minute Opening Range Breakout (ORB)
- Captures high-momentum institutional moves after the opening session.
- Establishes the 09:15 – 09:30 IST high/low boundaries.
- Triggers breakout entry with buffer above range high with Stop Loss placed at VWAP or range midpoint.

### 3. VWAP Pullback Strategy
- Identifies strong intraday trends that temporarily retrace to institutional average pricing.
- Enters on bullish candlestick confirmation touching the VWAP support band.

---

## 🛡️ Mathematical Risk Engine & Position Sizing

The client UI **never** decides trade quantities. The server-side Risk Engine dynamically calculates the exact number of shares using fixed account equity risk and Average True Range (ATR):

### Formula:
```text
Risk Amount (₹)        = Account Equity × Risk Percentage (1%)
Stop Loss Distance (₹) = 1.5 × ATR(14)
Calculated Quantity    = floor( Risk Amount ÷ Stop Loss Distance )
Target Price (₹)       = Entry Price + ( 3.0 × Stop Loss Distance )  [1:3 Risk/Reward]
```

### Numerical Example:
| Parameter | Value | Description |
|---|---|---|
| **Account Equity** | ₹1,00,000 | Available liquid trading capital |
| **Risk per Trade** | 1.0% (₹1,000) | Maximum loss permitted if Stop Loss is hit |
| **LTP / Entry Price** | ₹1,000.00 | Current market price at signal generation |
| **ATR(14) Volatility**| ₹12.00 | Average True Range over past 14 candles |
| **Stop Distance** | ₹18.00 | Volatility-adapted buffer: `1.5 × ₹12.00` |
| **Stop Loss Price** | ₹982.00 | `₹1,000.00 - ₹18.00` |
| **Target Price (1:3)**| ₹1,054.00 | `₹1,000.00 + (3 × ₹18.00)` (₹54 profit/share) |
| **Calculated Order Qty**| **55 shares** | `floor( ₹1,000 ÷ ₹18.00 ) = 55 shares` (Max Risk = ₹990) |

---

## 🤖 InvestIQ AI Engine (3,100+ Equities)

InvestIQ continuously scans and ranks all **3,100+ NSE-listed companies** across Large, Mid, Small-cap, and SME segments using a blended 3-tier quantitative model:

$$\text{Growth Score} = 0.95 \times (0.70 \times \text{Market Trend} + 0.30 \times \text{Financial Health}) + 0.05 \times \text{FinBERT Sentiment} - \text{Penalties}$$

- **Market Trend:** Outperformance vs NIFTY Smallcap 250, proximity to 52-week highs, 50/200 EMA orientation, downside deviation.
- **Financial Health:** Quarterly revenue & net profit growth, debt-to-equity ratio, ROCE/ROE metrics, operating cash flow.
- **FinBERT Sentiment:** NLP sentiment analysis of official NSE company filings and announcements (Positive / Neutral / Negative).
- **Classification:** 🟢 Strong (75+), 🔵 Positive (60–75), ⚪ Neutral (40–60), 🔴 Weak (<40).

---

## ⏳ Kronos AI Foundation Model

- Deep time-series transformer model tailored for Indian equity price prediction.
- Generates predictive trajectories, confidence intervals (80% / 95%), support/resistance levels, and multi-horizon target probabilities.
- Visualizes forecasting momentum indicators directly on the charting interface.

---

## 📊 TradingView Real-Time Chart Studio

- Official **TradingView UDF API** endpoints (`/api/v1/udf/config`, `/symbols`, `/history`, `/time`).
- Sub-minute, intraday (1m, 5m, 15m), and daily historical candlesticks.
- Technical overlays: **VWAP**, **SuperTrend**, **RSI (14)**, **Bollinger Bands**, and **Volume Profile**.
- One-click order execution trigger directly from chart levels.

---

## 🗄️ NSE Data Warehouse & MySQL Pipeline

Includes complete DDL and batch ETL scripts to load official NSE datasets into MySQL 8.0+:

- **`schema_nse_data.sql`**: Complete relational schema creating normalized tables:
  - `nse_equities` (~2,603 listed stocks)
  - `nse_etfs` (~352 exchange traded funds)
  - `nse_sme_equities` (~579 SME stocks)
  - `nse_corporate_actions` (Upcoming dividends, splits, bonuses)
  - `nse_credit_ratings` (CRISIL, ICRA, CARE rating actions)
  - `nse_debt_securities` (~3,000 corporate bonds & debentures)
  - `nse_name_changes` & `nse_symbol_changes` (Historical ticker mappings)
- **`ingest_nse_to_mysql.py`**: Automated Python ETL pipeline with batching, type sanitation, and progress reporting.
- See [`MYSQL_NSE_INGESTION_GUIDE.md`](file:///c:/Users/patel/Desktop/Algo%20Trading/MYSQL_NSE_INGESTION_GUIDE.md) for full ingestion instructions.

---

## 🧪 Live Market Validation Suite

The platform includes an automated 33-step Indian market verification suite ([`backend/run_indian_market_live_test.py`](file:///c:/Users/patel/Desktop/Algo%20Trading/YourAlgo-v2/backend/run_indian_market_live_test.py)):

```text
================================================================================
   INDIAN REAL MARKET LIVE VALIDATION SUMMARY: 33/33 PASSED
================================================================================
 [PASS] IST Timezone Accuracy (UTC+5:30)
 [PASS] NSE Trading Session Detection (Pre-Market, Regular, Post-Market)
 [PASS] NSE Tick Size Compliance (Mod ₹0.05 validation on live quotes)
 [PASS] SEBI Risk Engine Sizing & Circuit Breakers
 [PASS] Quant Strategies (EMA/VWAP, 15m ORB, VWAP Pullback)
 [PASS] Upstox Broker OAuth Dialog Generation & Lifecycle
 [PASS] FastAPI Endpoints (/market/status, /instruments, /quotes, /investiq)
🎉 ALL CHECKS PASSED: YourAlgo v2 conforms 100% to Indian Real Market rules!
```

---

## 🚀 Quickstart & Setup Guide

### Prerequisites
- **Python 3.10+** (with virtual environment support)
- **Node.js 18+** & npm
- (Optional) **MySQL 8.0+** & Redis for full database persistence

---

### Method 1: One-Click Windows Launcher (Recommended)
Double-click:
```bat
start_youralgo.bat
```
This automatically verifies environment settings, ensures frontend build assets are ready, starts Uvicorn on `http://127.0.0.1:8000`, and opens your default browser.

---

### Method 2: Development Mode (Hot-Reload)

#### 1. Configure Environment:
```bash
cd "YourAlgo-v2"
cp .env.example .env
```
*(Populate your Upstox API credentials if live broker connection is desired. By default, Paper Trading is active with zero risk).*

#### 2. Start Backend:
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### 3. Start Frontend:
```bash
cd ../frontend
npm install
npm run dev
```

- **Frontend Terminal**: `http://localhost:5173`
- **Backend API Docs**: `http://localhost:8000/docs`
- **TradingView UDF Feed**: `http://localhost:8000/api/v1/udf`

---

## 📁 Repository Structure

```text
Algo-Trading-/
├── start_youralgo.bat                # Root one-click Windows launcher
├── schema_nse_data.sql              # MySQL DDL for NSE Data Warehouse
├── ingest_nse_to_mysql.py           # Python ETL pipeline for NSE historical data
├── MYSQL_NSE_INGESTION_GUIDE.md     # Step-by-step MySQL migration guide
├── YourAlgo_v2_Architecture.html    # Interactive visual architecture diagram
└── YourAlgo-v2/                     # Core Platform Application
    ├── run.py                       # Unified platform launcher
    ├── backend/                     # FastAPI Backend Application
    │   ├── app/
    │   │   ├── main.py              # App entrypoint & WebSocket handlers
    │   │   ├── market_data.py       # NSE live quote feeder & tick manager
    │   │   ├── risk.py              # SEBI risk engine & capital sizing
    │   │   ├── automation_engine.py # Autonomous strategy execution loops
    │   │   ├── strategies.py        # Quant models (ORB, EMA/VWAP, Pullback)
    │   │   ├── investiq_service.py  # AI 3,100+ stock scoring service
    │   │   ├── kronos_engine.py     # Time-series transformer AI forecasts
    │   │   ├── tradingview_udf.py   # TradingView UDF protocol endpoints
    │   │   └── brokers/             # Upstox v2 & Paper Trading adapters
    │   └── run_indian_market_live_test.py # 33-step verification suite
    └── frontend/                    # Modern React 19 + TypeScript + Vite UI
        ├── src/
        │   ├── main.tsx             # Primary workspace UI & routing
        │   ├── InvestIQView.tsx     # InvestIQ AI ranking & sector analysis
        │   ├── KronosView.tsx       # Kronos AI prediction studio
        │   ├── TradingViewView.tsx  # Interactive candlestick chart studio
        │   └── index.css            # Dark/glassmorphic design system
        └── package.json
```

---

## ⚖️ Risk Disclaimer

*YourAlgo v2, InvestIQ, and Kronos are quantitative research, simulation, and execution tools. They do not constitute financial advice. Algorithmic trading in equities and derivatives involves substantial risk of capital loss. Always validate strategies extensively in paper mode before allocating real capital.*
