"""
Trading tools — portfolio, prices, analysis, orders
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class TradingToolsMixin:
    """Mixin providing trading tools — portfolio, prices, analysis, orders tool implementations."""

    # ========== TRADING TOOLS ==========

    async def _trading_portfolio_tool(self, params: Dict) -> str:
        """Get portfolio summary"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled. Set TRADING_ENABLED=true in your environment."
        return await self.trading_skill.get_portfolio(params)

    async def _trading_price_tool(self, params: Dict) -> str:
        """Get current price"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.get_price(params)

    async def _trading_analyze_tool(self, params: Dict) -> str:
        """Analyze market"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.analyze_market(params)

    async def _trading_place_trade_tool(self, params: Dict) -> str:
        """Place a trade"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.place_trade(params)

    async def _trading_cancel_order_tool(self, params: Dict) -> str:
        """Cancel an order"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.cancel_order(params)

    async def _trading_history_tool(self, params: Dict) -> str:
        """Get trade history"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.get_trade_history(params)

    async def _trading_signals_tool(self, params: Dict) -> str:
        """Get current signals"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.get_signals(params)

    async def _trading_start_scan_tool(self, params: Dict) -> str:
        """Start background scanning"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.start_scanning(params)

    async def _trading_stop_scan_tool(self, params: Dict) -> str:
        """Stop background scanning"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.stop_scanning(params)

    async def _trading_risk_status_tool(self, params: Dict) -> str:
        """Get risk status"""
        if not self.trading_skill:
            return "⚠️ Trading is not enabled."
        return await self.trading_skill.get_risk_status(params)

