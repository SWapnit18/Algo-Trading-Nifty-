import uuid
from typing import Optional, Dict, List, Any
from .base import BrokerAdapter

class PaperAdapter(BrokerAdapter):
    name = "PAPER"

    def __init__(self, initial_balance: float = 50000.0):
        self.balance = initial_balance
        self._positions: Dict[str, Dict[str, Any]] = {}
        self._orders: List[Dict[str, Any]] = []

    async def authenticate(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "SUCCESS", "authenticated": True, "broker": "PAPER"}

    async def get_profile(self) -> Dict[str, Any]:
        return {
            "status": "SUCCESS",
            "client_id": "PAPER_SIMULATOR",
            "name": "Simulated Paper Account",
            "broker": "PAPER"
        }

    async def get_balance(self) -> Dict[str, Any]:
        return {"available_cash": self.balance, "collateral": 0.0, "currency": "INR"}

    async def get_positions(self) -> List[Dict[str, Any]]:
        return list(self._positions.values())

    async def get_orders(self) -> List[Dict[str, Any]]:
        return self._orders

    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        target: Optional[float] = None,
        client_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        order_ref = client_order_id or f"paper_{uuid.uuid4().hex[:10]}"
        fill_price = price or 1000.0
        order_record = {
            "order_id": order_ref,
            "client_order_id": order_ref,
            "symbol": symbol.upper(),
            "side": side.upper(),
            "quantity": quantity,
            "price": fill_price,
            "status": "FILLED",
            "broker": "PAPER"
        }
        self._orders.append(order_record)

        if side.upper() == "BUY":
            cost = fill_price * quantity
            self.balance = max(0.0, self.balance - cost)
            self._positions[symbol.upper()] = {
                "symbol": symbol.upper(),
                "quantity": quantity,
                "avg_price": fill_price,
                "current_price": fill_price,
                "stop_loss": stop_loss,
                "target": target
            }
        elif side.upper() == "SELL":
            if symbol.upper() in self._positions:
                pos = self._positions[symbol.upper()]
                self.balance += fill_price * quantity
                del self._positions[symbol.upper()]

        return {
            "status": "FILLED",
            "broker_order_id": order_ref,
            "client_order_id": order_ref,
            "execution_price": fill_price,
            "broker": "PAPER",
            "symbol": symbol.upper(),
            "side": side.upper(),
            "quantity": quantity
        }

    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None
    ) -> Dict[str, Any]:
        return {"status": "MODIFIED", "order_id": order_id, "broker": "PAPER"}

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        return {"status": "CANCELLED", "order_id": order_id, "broker": "PAPER"}

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        return {"order_id": order_id, "status": "FILLED", "broker": "PAPER"}

    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        return {"symbol": symbol, "status": "PAPER_SIMULATION"}

    async def subscribe_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        return {"status": "SUBSCRIBED", "broker": "PAPER", "symbols": symbols}

    async def close_position(self, symbol: str, quantity: Optional[int] = None) -> Dict[str, Any]:
        return await self.place_order(symbol=symbol, side="SELL", quantity=quantity or 1, order_type="MARKET")
