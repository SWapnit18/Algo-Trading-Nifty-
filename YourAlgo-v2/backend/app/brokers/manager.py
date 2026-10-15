from typing import Dict, Any, List, Optional
from .base import BrokerAdapter
from .upstox import UpstoxAdapter
from .paper import PaperAdapter

class BrokerManager:
    """
    Upstox-Dedicated Broker Manager for YourAlgo v2.
    Orchestrates Upstox live execution, paper execution, and position reconciliation.
    """

    @staticmethod
    def get_adapter(
        broker_name: str,
        access_token: Optional[str] = None,
        client_id: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> BrokerAdapter:
        name = (broker_name or "PAPER").upper()
        if name == "UPSTOX":
            return UpstoxAdapter(access_token=access_token, api_key=api_key)
        return PaperAdapter()

    @staticmethod
    async def reconcile(
        user_id: int,
        broker_name: str,
        internal_positions: List[Any],
        adapter: BrokerAdapter
    ) -> Dict[str, Any]:
        """
        Reconciles internal YourAlgo positions with broker-reported positions.
        Returns reconciliation state. If mismatch detected, returns mismatch_detected=True.
        """
        try:
            broker_positions = await adapter.get_positions()
        except Exception as e:
            return {
                "status": "RECONCILIATION_FAILED",
                "mismatch_detected": True,
                "error": f"Failed to fetch positions from {broker_name}: {str(e)}"
            }

        # Build broker quantity map
        broker_qty_map: Dict[str, int] = {}
        for bp in broker_positions:
            sym = bp.get("symbol") or bp.get("tradingsymbol") or bp.get("tradingSymbol") or ""
            qty = int(bp.get("quantity") or bp.get("netQty") or bp.get("net_quantity") or 0)
            if sym and qty != 0:
                broker_qty_map[sym.upper()] = qty

        internal_qty_map: Dict[str, int] = {}
        for ip in internal_positions:
            if ip.status == "OPEN" and ip.quantity > 0:
                internal_qty_map[ip.symbol.upper()] = ip.quantity

        mismatches = []
        all_symbols = set(internal_qty_map.keys()).union(set(broker_qty_map.keys()))

        # For simulated paper adapter or when broker has no live open positions, compare appropriately
        if broker_name.upper() != "PAPER":
            for s in all_symbols:
                iq = internal_qty_map.get(s, 0)
                bq = broker_qty_map.get(s, 0)
                if iq != bq:
                    mismatches.append({
                        "symbol": s,
                        "youralgo_quantity": iq,
                        "broker_quantity": bq,
                        "difference": iq - bq
                    })

        is_mismatch = len(mismatches) > 0
        return {
            "status": "MISMATCH_DETECTED" if is_mismatch else "IN_SYNC",
            "mismatch_detected": is_mismatch,
            "mismatches": mismatches,
            "broker": broker_name,
            "internal_open_count": len(internal_qty_map),
            "broker_open_count": len(broker_qty_map)
        }

broker_manager = BrokerManager()
