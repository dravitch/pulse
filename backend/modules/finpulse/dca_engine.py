"""
DCAEngine — Level 1 DCA backtest.

Uses historical OHLCV data from CCXT (Binance) to simulate monthly buys.
Computes: total invested, final value, ROI %, units accumulated, Sharpe ratio.
"""

import logging
import math
from datetime import datetime, timezone

from .exchanges import fetch_ohlcv

logger = logging.getLogger(__name__)


class DCAEngine:
    async def backtest_level1(
        self,
        asset: str,
        monthly_amount: float,
        periods: int = 60,
    ) -> dict:
        """
        Simulate DCA: buy `monthly_amount` USD of `asset` every month
        for `periods` months using real historical prices from Binance.

        Returns:
            total_invested, final_value, roi (%), units_accumulated,
            sharpe_ratio, volatility, transactions (list)
        """
        # Fetch enough daily candles: periods months × 31 days + buffer
        limit = min(periods * 31 + 60, 1000)
        candles = await fetch_ohlcv(asset, timeframe="1d", limit=limit)

        if len(candles) < 2:
            return {"error": f"Not enough historical data for {asset}"}

        # Convert to monthly series: first candle of each month
        monthly: list[dict] = []
        seen_months: set[str] = set()
        for candle in candles:
            ts_ms, _open, _high, _low, close, _vol = candle
            dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            month_key = dt.strftime("%Y-%m")
            if month_key not in seen_months:
                seen_months.add(month_key)
                monthly.append({"date": dt, "price": float(close)})

        # Trim to requested number of periods
        monthly = monthly[-periods:] if len(monthly) >= periods else monthly

        if not monthly:
            return {"error": "No monthly data available"}

        # ── Simulate DCA ──────────────────────────────────────────────────
        total_units = 0.0
        total_invested = 0.0
        transactions = []
        portfolio_values: list[float] = []

        for month in monthly:
            price = month["price"]
            units_bought = monthly_amount / price
            total_units += units_bought
            total_invested += monthly_amount
            portfolio_value = total_units * price
            portfolio_values.append(portfolio_value)

            transactions.append({
                "date": month["date"].strftime("%Y-%m-%d"),
                "price": round(price, 2),
                "units_bought": round(units_bought, 8),
                "cumulative_units": round(total_units, 8),
                "portfolio_value": round(portfolio_value, 2),
            })

        final_price = monthly[-1]["price"]
        final_value = total_units * final_price
        roi = ((final_value - total_invested) / total_invested) * 100 if total_invested else 0

        # ── Risk metrics ─────────────────────────────────────────────────
        monthly_returns: list[float] = []
        for i in range(1, len(portfolio_values)):
            prev = portfolio_values[i - 1]
            if prev > 0:
                monthly_returns.append((portfolio_values[i] - prev) / prev)

        if monthly_returns:
            avg_return = sum(monthly_returns) / len(monthly_returns)
            variance = sum((r - avg_return) ** 2 for r in monthly_returns) / len(monthly_returns)
            volatility = math.sqrt(variance) * math.sqrt(12) * 100  # annualised %
            risk_free = 0.04 / 12  # 4% annual risk-free rate, monthly
            sharpe = (
                (avg_return - risk_free) / math.sqrt(variance) * math.sqrt(12)
                if variance > 0
                else 0.0
            )
        else:
            volatility = 0.0
            sharpe = 0.0

        return {
            "asset": asset,
            "monthly_amount": monthly_amount,
            "periods": len(monthly),
            "total_invested": round(total_invested, 2),
            "final_value": round(final_value, 2),
            "roi": round(roi, 2),
            "units_accumulated": round(total_units, 8),
            "avg_buy_price": round(total_invested / total_units, 2) if total_units else 0,
            "current_price": round(final_price, 2),
            "volatility_annual_pct": round(volatility, 2),
            "sharpe_ratio": round(sharpe, 3),
            "transactions": transactions,
        }
