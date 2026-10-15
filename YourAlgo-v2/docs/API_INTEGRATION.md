# YourAlgo API Integration Guide

## 1. DhanHQ

Official docs: https://dhanhq.co/docs/v2/

Use:
- Live market feed: WebSocket
- Historical candles: REST
- Orders/trades: REST
- Portfolio: REST

Flow:
Dhan WebSocket -> Market Worker -> Redis -> Indicators -> Strategy -> Risk -> Paper/Live Order.

Important: Dhan's current order docs state that order placement, modification and cancellation require Static IP whitelisting. Verify the current broker requirements before enabling live execution.

## 2. Upstox

Official docs: https://upstox.com/developer/api-documentation/open-api/

Use:
- Market Data Feed V3 WebSocket
- REST order APIs
- Portfolio/order update WebSocket

Instrument keys must be mapped and current API authentication must be implemented on the server.

## 3. Groww

Official docs: https://groww.in/trade-api

Use:
- Live quote/LTP/OHLC
- Current historical candle API
- Orders
- Trades
- Holdings/positions

Groww's current docs say an active Trading API subscription is required. The older historical endpoint is deprecated; implement the current historical candle endpoint.

## 4. NSE

Official historical reports:
https://www.nseindia.com/static/resources/historical-reports-capital-market-daily-monthly-archives

Use exchange data for research/validation where licensing and access terms permit.

## 5. Security

Never put broker access tokens in React. Keep them in backend secrets/secure storage.

Never let the browser bypass the risk engine.

## 6. Development order

1. MySQL + Redis
2. FastAPI
3. Authentication
4. Instrument master
5. Market data
6. Indicators
7. Strategy engine
8. Backtesting
9. ML training
10. Paper trading
11. Broker UAT
12. Controlled live deployment

Live trading is disabled in this starter.
