# YourAlgo v2 Architecture

React -> FastAPI REST/WebSocket -> services -> MySQL/Redis

Market:
Broker WebSocket -> Market Worker -> Redis -> Indicator Engine -> Strategy Engine

Research:
Historical Data -> Data Cleaning -> Features -> Labels -> Train -> Walk Forward -> OOS

Execution:
Signal -> Risk Engine -> Idempotency -> Order Engine -> Broker Adapter -> Broker -> Reconciliation -> MySQL

Safety:
Stale data, daily loss cap, max positions, max trades/day, kill switch and duplicate-order protection are server-side concerns.
