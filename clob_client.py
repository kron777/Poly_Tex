"""
Polymarket CLOB client wrapper
Handles auth, orders, markets, positions
"""
import time
import requests
from typing import Optional
from logger import get_logger
from config import (CLOB_API, GAMMA_API, POLY_PRIVATE_KEY,
                    POLY_API_KEY, POLY_ADDRESS, POLY_CHAIN_ID)

log = get_logger("clob")

class ClobClient:
    """Thread-safe Polymarket CLOB wrapper"""

    def __init__(self):
        self.base = CLOB_API
        self.gamma = GAMMA_API
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "PolyTex/2.0",
            "Content-Type": "application/json",
        })
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initialize py-clob-client if credentials available"""
        if not POLY_PRIVATE_KEY or not POLY_ADDRESS:
            log.warning("No credentials — read-only mode")
            return
        try:
            from py_clob_client.client import ClobClient as _C
            from py_clob_client.clob_types import ApiCreds
            creds = ApiCreds(
                api_key=POLY_API_KEY,
                api_secret="",
                api_passphrase="",
            )
            self._client = _C(
                host=self.base,
                key=POLY_PRIVATE_KEY,
                chain_id=POLY_CHAIN_ID,
                creds=creds,
            )
            log.info(f"CLOB client ready — {POLY_ADDRESS[:10]}...")
        except Exception as e:
            log.error(f"CLOB init failed: {e}")

    def get_markets(self, limit: int = 100, offset: int = 0) -> list:
        """Fetch active markets from Gamma API"""
        try:
            r = self.session.get(
                f"{self.gamma}/markets",
                params={"limit": limit, "offset": offset,
                        "active": "true", "closed": "false"},
                timeout=10
            )
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else data.get("markets", [])
        except Exception as e:
            log.error(f"get_markets error: {e}")
            return []

    def get_market(self, condition_id: str) -> Optional[dict]:
        """Get single market details"""
        try:
            r = self.session.get(
                f"{self.gamma}/markets/{condition_id}", timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"get_market error: {e}")
            return None

    def get_orderbook(self, token_id: str) -> Optional[dict]:
        """Get live orderbook for a token"""
        try:
            r = self.session.get(
                f"{self.base}/book",
                params={"token_id": token_id},
                timeout=10
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"get_orderbook error: {e}")
            return None

    def get_balance(self) -> float:
        """Get USDC balance"""
        if not self._client:
            return 0.0
        try:
            bal = self._client.get_balance()
            return float(bal or 0)
        except Exception as e:
            log.error(f"get_balance error: {e}")
            return 0.0

    def place_order(self, token_id: str, side: str, size: float,
                    price: float, paper: bool = True) -> Optional[dict]:
        """Place or simulate an order"""
        if paper:
            log.info(f"[PAPER] {side} {size:.2f} @ {price:.4f} token={token_id[:12]}...")
            return {"paper": True, "side": side, "size": size,
                    "price": price, "status": "simulated"}
        if not self._client:
            log.error("No client for live order")
            return None
        try:
            from py_clob_client.clob_types import OrderArgs, OrderType
            args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side,
            )
            resp = self._client.create_and_post_order(args)
            log.info(f"[LIVE] Order placed: {resp}")
            return resp
        except Exception as e:
            log.error(f"place_order error: {e}")
            return None

    def get_positions(self) -> list:
        """Get open positions"""
        if not self._client:
            return []
        try:
            return self._client.get_positions() or []
        except Exception as e:
            log.error(f"get_positions error: {e}")
            return []

    def get_leaderboard(self, limit: int = 50) -> list:
        """Get top traders leaderboard"""
        try:
            r = self.session.get(
                f"{self.gamma}/leaderboard",
                params={"limit": limit, "window": "1w"},
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                return data if isinstance(data, list) else data.get("data", [])
            # Fallback endpoint
            r2 = self.session.get(
                f"https://data-api.polymarket.com/leaderboard",
                params={"limit": limit, "window": "weekly"},
                timeout=10
            )
            if r2.status_code == 200:
                d = r2.json()
                return d if isinstance(d, list) else d.get("data", [])
            return []
        except Exception as e:
            log.error(f"get_leaderboard error: {e}")
            return []

    def get_wallet_trades(self, address: str, limit: int = 100) -> list:
        """Get recent trades for a wallet"""
        try:
            r = self.session.get(
                f"https://data-api.polymarket.com/activity",
                params={"user": address, "limit": limit},
                timeout=10
            )
            if r.status_code == 200:
                d = r.json()
                return d if isinstance(d, list) else d.get("data", [])
            return []
        except Exception as e:
            log.error(f"get_wallet_trades error: {e}")
            return []

# Singleton
_client_instance = None

def get_client() -> ClobClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = ClobClient()
    return _client_instance
