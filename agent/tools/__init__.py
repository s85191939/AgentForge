"""LangChain tools that wrap the Ghostfolio API."""

from agent.tools.accounts import get_accounts
from agent.tools.auth import authenticate, health_check
from agent.tools.news import (
    create_news_alert,
    delete_news_alert,
    get_portfolio_news,
    get_symbol_news,
    list_news_alerts,
    update_news_alert,
)
from agent.tools.orders import delete_order, get_orders, import_activities, preview_import
from agent.tools.portfolio import (
    get_portfolio_details,
    get_portfolio_holdings,
    get_portfolio_performance,
)
from agent.tools.symbols import lookup_symbol
from agent.tools.user import get_user_settings

ALL_TOOLS = [
    authenticate,
    health_check,
    get_portfolio_holdings,
    get_portfolio_performance,
    get_portfolio_details,
    get_orders,
    preview_import,
    import_activities,
    delete_order,
    get_accounts,
    lookup_symbol,
    get_user_settings,
    get_portfolio_news,
    get_symbol_news,
    create_news_alert,
    list_news_alerts,
    update_news_alert,
    delete_news_alert,
]

__all__ = ["ALL_TOOLS"]
