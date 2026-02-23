"""LangChain tools that wrap the Ghostfolio API."""

from agent.tools.portfolio import (
    get_portfolio_details,
    get_portfolio_holdings,
    get_portfolio_performance,
)
from agent.tools.orders import get_orders, import_activities
from agent.tools.accounts import get_accounts
from agent.tools.symbols import lookup_symbol
from agent.tools.auth import authenticate, health_check
from agent.tools.user import get_user_settings

ALL_TOOLS = [
    authenticate,
    health_check,
    get_portfolio_holdings,
    get_portfolio_performance,
    get_portfolio_details,
    get_orders,
    import_activities,
    get_accounts,
    lookup_symbol,
    get_user_settings,
]

__all__ = ["ALL_TOOLS"]
