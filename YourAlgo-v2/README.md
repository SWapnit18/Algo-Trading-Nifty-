# YourAlgo v2

Dynamic Indian-equity algo trading platform starter.

## Stack
- Frontend: React + Vite + TypeScript
- Backend: FastAPI + SQLAlchemy
- Database: MySQL
- Cache/queues: Redis
- Real-time: WebSockets
- Broker adapters: Dhan, Upstox, Groww
- ML: Python/scikit-learn-ready structure

## Important
Live execution is intentionally disabled by default. Broker credentials are never stored in the frontend.
Use PAPER mode while developing and validating the strategy.

## Run
1. Copy `.env.example` to `.env`.
2. Start MySQL + Redis:
   `docker compose -f infra/docker-compose.yml up -d`
3. Backend:
   `cd backend`
   `python -m venv .venv`
   Windows: `.venv\Scripts\activate`
   `pip install -r requirements.txt`
   `uvicorn app.main:app --reload --port 8000`
4. Frontend:
   `cd frontend`
   `npm install`
   `npm run dev`

Frontend: http://localhost:5173
Backend: http://localhost:8000
Docs: http://localhost:8000/docs

## API integration plan
Dhan:
- REST for orders/account operations
- WebSocket for live market data
- Historical candles for research/backtesting
- Live order APIs require the broker's current authentication/static-IP requirements.

Upstox:
- REST APIs for trading
- Market Data Feed V3 WebSocket
- Portfolio/order update WebSocket

Groww:
- REST APIs for live data, historical candles, orders and portfolio
- Current Groww docs require an active Trading API subscription.
- Use the current historical candle endpoint; the older historical endpoint is deprecated.

See `docs/API_INTEGRATION.md`.
