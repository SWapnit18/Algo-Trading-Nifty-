from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any

class BrokerAdapter(ABC):
    name: str = "BASE"

    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Verify broker API credentials and establish session."""
        ...

    @abstractmethod
    async def get_profile(self) -> Dict[str, Any]:
        """Fetch trader profile and account identifier."""
        ...

    @abstractmethod
    async def get_balance(self) -> Dict[str, Any]:
        """Fetch available funds and margin summary."""
        ...

    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Fetch active open and closed positions directly from broker."""
        ...

    @abstractmethod
    async def get_orders(self) -> List[Dict[str, Any]]:
        """Fetch order book from broker."""
        ...

    @abstractmethod
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
        """Place an order through the broker API."""
        ...

    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Modify an existing open order."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an open order."""
        ...

    @abstractmethod
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Query current execution state of an order."""
        ...

    @abstractmethod
    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch real-time tick/quote data."""
        ...

    @abstractmethod
    async def subscribe_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """Subscribe to WebSocket/live feed for symbols."""
        ...

    @abstractmethod
    async def close_position(self, symbol: str, quantity: Optional[int] = None) -> Dict[str, Any]:
        """Close/square-off an open position at market price."""
        ...
