# 🚀 YourAlgo v2 — Indian Equity Algorithmic Trading Platform

For the full architectural specification, quantitative formulas, risk engine details, and complete setup guide, refer to the primary root documentation:
👉 **[Root README.md](../README.md)**

---

## ⚡ Quickstart

### 1. Launch Platform (One-Click)
Double-click:
```bat
start_youralgo.bat
```
Or execute:
```bash
python run.py
```

### 2. Full Development Mode (Hot-Reload)
```bash
python run.py --dev
```
- **Backend API**: `http://127.0.0.1:8000` (FastAPI Swagger: `/docs`)
- **Frontend UI**: `http://127.0.0.1:5173` (Vite HMR)
- **TradingView UDF Feed**: `http://127.0.0.1:8000/api/v1/udf`

---

## 🧪 Run Indian Real Market Validation Suite
```bash
cd backend
python run_indian_market_live_test.py
```
*(Validates 33/33 tests covering IST session timings, NSE tick sizes, SEBI risk checks, Upstox adapters, and quant strategy signals).*
