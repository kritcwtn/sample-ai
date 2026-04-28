"""Stock-domain tools.

Each tool ships a structured description so the LLM can pick the right one.
Description format:

    <one-line summary>

    When to use:
      - bullet ...
    When NOT to use:
      - bullet ...
    Arguments:
      - <name>: <explanation> (range/default)
    Examples:
      - User asks "..." → call with {...}
"""
from __future__ import annotations

from typing import Any

from .base import BaseTool, ToolRegistry
from . import sql_tool


# Whitelist of fields that may ever appear in tool output.
_ALLOWED = {"id", "name", "qty", "sold_count", "price", "color"}


def _safe_rows(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        clean = {k: v for k, v in r.items() if k in _ALLOWED}
        # Decimal → float so JSON serialisation works.
        if "price" in clean and clean["price"] is not None:
            clean["price"] = float(clean["price"])
        out.append(clean)
    return out


# -------------------------------------------------------------------------

class ListProducts(BaseTool):
    name = "list_products"
    description = (
        "List every product currently in stock with its remaining quantity and lifetime sold count.\n"
        "\n"
        "When to use:\n"
        "  - User asks for an overview of the catalogue ('สินค้ามีอะไรบ้าง', 'list all products').\n"
        "  - User wants to see everything before deciding what to ask next.\n"
        "When NOT to use:\n"
        "  - User wants only low-stock items → use get_low_stock.\n"
        "  - User wants only top sellers → use get_best_sellers.\n"
        "  - User names a specific product → use search_products_by_name.\n"
        "Arguments:\n"
        "  - limit: max rows to return (1-500, default 100).\n"
        "Examples:\n"
        "  - 'สินค้ามีอะไรบ้าง'         → call with {}\n"
        "  - 'ขอ 10 รายการแรก'         → call with {\"limit\": 10}"
    )
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
        },
    }

    def run(self, limit: int = 100) -> list[dict]:
        return _safe_rows(sql_tool.all_products(limit))


class GetLowStock(BaseTool):
    name = "get_low_stock"
    description = (
        "Get products whose remaining quantity is strictly below a threshold.\n"
        "\n"
        "When to use:\n"
        "  - User asks about items running low, almost out, or needing reorder.\n"
        "  - Keywords: 'ใกล้หมด', 'เหลือน้อย', 'low stock', 'reorder'.\n"
        "When NOT to use:\n"
        "  - User wants items with qty exactly 0 → use get_out_of_stock.\n"
        "  - User wants top/bottom sellers → use get_best_sellers / get_bottom_sellers.\n"
        "Arguments:\n"
        "  - threshold: qty cut-off (1-100, default 5). Returns rows where qty < threshold.\n"
        "  - limit: max rows (1-100, default 50).\n"
        "Examples:\n"
        "  - 'สินค้าตัวไหนใกล้หมด'        → call with {\"threshold\": 5}\n"
        "  - 'ของที่เหลือน้อยกว่า 10 ชิ้น' → call with {\"threshold\": 10}"
    )
    parameters = {
        "type": "object",
        "properties": {
            "threshold": {"type": "integer", "minimum": 1, "maximum": 100, "default": 5},
            "limit":     {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
        },
    }

    def run(self, threshold: int = 5, limit: int = 50) -> list[dict]:
        return _safe_rows(sql_tool.low_stock(threshold, limit))


class GetOutOfStock(BaseTool):
    name = "get_out_of_stock"
    description = (
        "Get products that are completely sold out (qty = 0).\n"
        "\n"
        "When to use:\n"
        "  - User asks 'หมด stock', 'sold out', 'ขายหมดแล้วมีตัวไหน'.\n"
        "When NOT to use:\n"
        "  - For items still in stock but low → use get_low_stock.\n"
        "Arguments:\n"
        "  - limit: max rows (1-100, default 50).\n"
        "Examples:\n"
        "  - 'มีอะไรหมดสต็อกบ้าง' → call with {}"
    )
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
        },
    }

    def run(self, limit: int = 50) -> list[dict]:
        return _safe_rows(sql_tool.out_of_stock(limit))


class GetBestSellers(BaseTool):
    name = "get_best_sellers"
    description = (
        "Get the top-selling products ordered by lifetime sold_count (highest first).\n"
        "\n"
        "When to use:\n"
        "  - User asks for popular/best/top items: 'ขายดี', 'best seller', 'top 5'.\n"
        "When NOT to use:\n"
        "  - User compares specific named products → use search_products_by_name twice.\n"
        "  - User wants worst sellers → use get_bottom_sellers.\n"
        "Arguments:\n"
        "  - limit: how many top rows (1-50, default 5).\n"
        "Examples:\n"
        "  - 'สินค้าขายดีที่สุด'        → call with {\"limit\": 1}\n"
        "  - 'top 10 ขายดี'            → call with {\"limit\": 10}"
    )
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5},
        },
    }

    def run(self, limit: int = 5) -> list[dict]:
        return _safe_rows(sql_tool.best_sellers(limit))


class GetBottomSellers(BaseTool):
    name = "get_bottom_sellers"
    description = (
        "Get the slowest-selling products ordered by sold_count (lowest first).\n"
        "\n"
        "When to use:\n"
        "  - 'ขายไม่ดี', 'ขายน้อยที่สุด', 'slow movers', 'least popular'.\n"
        "When NOT to use:\n"
        "  - For top sellers → use get_best_sellers.\n"
        "Arguments:\n"
        "  - limit: how many bottom rows (1-50, default 5).\n"
        "Examples:\n"
        "  - 'สินค้าขายได้น้อยที่สุด' → call with {\"limit\": 1}"
    )
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5},
        },
    }

    def run(self, limit: int = 5) -> list[dict]:
        return _safe_rows(sql_tool.bottom_sellers(limit))


class SearchProductsByName(BaseTool):
    name = "search_products_by_name"
    description = (
        "Search for products by a name keyword. Tries an exact substring match (case-insensitive) "
        "first; if nothing matches, falls back to fuzzy similarity (handles typos like "
        "'ihpone' → 'iPhone').\n"
        "\n"
        "When to use:\n"
        "  - User mentions a specific product name (or brand fragment).\n"
        "  - User compares two named products → call this tool ONCE PER PRODUCT, not get_best_sellers.\n"
        "  - User asks if a product exists ('มี iPhone ไหม', 'AirPods มีของไหม').\n"
        "When NOT to use:\n"
        "  - General overview without a name → use list_products.\n"
        "Arguments:\n"
        "  - keyword: required, 1-100 characters. Brand or product fragment.\n"
        "  - limit: max rows (1-20, default 10).\n"
        "Examples:\n"
        "  - 'มี iPhone 15 ไหม'  → {\"keyword\": \"iPhone 15\"}\n"
        "  - 'iPad เหลือเท่าไร'   → {\"keyword\": \"iPad\"}\n"
        "  - 'ihpone กับ MacBook' → call twice: {\"keyword\": \"ihpone\"} then {\"keyword\": \"MacBook\"}"
    )
    parameters = {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "minLength": 1, "maxLength": 100},
            "limit":   {"type": "integer", "minimum": 1, "maximum": 20, "default": 10},
        },
        "required": ["keyword"],
    }

    def run(self, keyword: str, limit: int = 10) -> list[dict]:
        return _safe_rows(sql_tool.find_by_name(keyword, limit=limit))


class GetTotalStock(BaseTool):
    name = "get_total_stock"
    description = (
        "Get the sum of remaining quantity across all products.\n"
        "\n"
        "When to use:\n"
        "  - 'รวมสต็อกมีเท่าไร', 'total stock', 'ของในคลังรวมกี่ชิ้น'.\n"
        "When NOT to use:\n"
        "  - For per-product breakdown → use list_products.\n"
        "  - For lifetime sales total → use get_total_sold.\n"
        "Examples:\n"
        "  - 'ในคลังมีของรวมเท่าไร' → {}"
    )

    def run(self) -> dict:
        return sql_tool.total_qty()


class GetTotalSold(BaseTool):
    name = "get_total_sold"
    description = (
        "Get the lifetime total of units sold across all products.\n"
        "\n"
        "When to use:\n"
        "  - 'ขายไปแล้วทั้งหมดกี่ชิ้น', 'total sold', 'lifetime sales'.\n"
        "When NOT to use:\n"
        "  - For best/worst sellers → use get_best_sellers / get_bottom_sellers.\n"
        "Examples:\n"
        "  - 'รวมขายไปทั้งหมดเท่าไร' → {}"
    )

    def run(self) -> dict:
        return sql_tool.total_sold()


# -------------------------------------------------------------------------
# Composable tool — combines two underlying queries into one logical alert.

class GetCriticalAlerts(BaseTool):
    name = "get_critical_alerts"
    description = (
        "Get a critical-stock report combining out-of-stock items and items below a "
        "low-stock threshold, in one call.\n"
        "\n"
        "When to use:\n"
        "  - Daily overview, dashboard, 'อะไรน่ากังวลตอนนี้', 'inventory health'.\n"
        "When NOT to use:\n"
        "  - User wants only out-of-stock or only low-stock — use the dedicated tool.\n"
        "Arguments:\n"
        "  - threshold: low-stock cutoff (1-50, default 5).\n"
        "Returns:\n"
        "  - items: list of {id, name, qty, sold_count, severity}. severity is "
        "    'out_of_stock' for qty=0 and 'low' for qty<threshold.\n"
        "Examples:\n"
        "  - 'รายงานสินค้าต้องดูแล' → {}"
    )
    parameters = {
        "type": "object",
        "properties": {
            "threshold": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5},
        },
    }

    def run(self, threshold: int = 5) -> list[dict]:
        out = _safe_rows(sql_tool.out_of_stock(50))
        low = _safe_rows(sql_tool.low_stock(threshold, 50))

        seen_ids: set[int] = set()
        result: list[dict] = []
        for r in out:
            seen_ids.add(r["id"])
            result.append({**r, "severity": "out_of_stock"})
        for r in low:
            if r["id"] in seen_ids:
                continue
            result.append({**r, "severity": "low"})
        return result


# -------------------------------------------------------------------------

class GetByColor(BaseTool):
    name = "get_products_by_color"
    description = (
        "Get products filtered by color (case-insensitive).\n"
        "\n"
        "When to use:\n"
        "  - User asks 'มีสีดำไหม', 'สินค้าสี Silver', 'show me black products'.\n"
        "When NOT to use:\n"
        "  - User asks for a specific product by name → use search_products_by_name.\n"
        "Arguments:\n"
        "  - color: required. Examples: 'Black', 'Silver', 'Midnight'.\n"
        "  - limit: max rows (1-200, default 50).\n"
        "Examples:\n"
        "  - 'สินค้าสี Silver มีอะไร' → {\"color\": \"Silver\"}"
    )
    parameters = {
        "type": "object",
        "properties": {
            "color": {"type": "string", "minLength": 1, "maxLength": 50},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
        },
        "required": ["color"],
    }

    def run(self, color: str, limit: int = 50) -> list[dict]:
        return _safe_rows(sql_tool.by_color(color, limit))


class GetByPriceRange(BaseTool):
    name = "get_products_by_price_range"
    description = (
        "Get products whose price falls within a range (inclusive). Useful for "
        "budget filters and 'ของไม่เกิน X บาท' style questions.\n"
        "\n"
        "When to use:\n"
        "  - 'สินค้าราคาไม่เกิน 10000', 'ระหว่าง 5000-20000', 'budget under 1000'.\n"
        "When NOT to use:\n"
        "  - Top/bottom by price → use get_most_expensive / get_cheapest.\n"
        "Arguments:\n"
        "  - min_price: lower bound in THB (default 0).\n"
        "  - max_price: upper bound in THB (default unlimited).\n"
        "  - limit: max rows (1-200, default 50).\n"
        "Examples:\n"
        "  - 'ราคาไม่เกิน 10000'  → {\"max_price\": 10000}\n"
        "  - 'ระหว่าง 5k-20k'      → {\"min_price\": 5000, \"max_price\": 20000}"
    )
    parameters = {
        "type": "object",
        "properties": {
            "min_price": {"type": "number", "minimum": 0, "default": 0},
            "max_price": {"type": "number", "minimum": 0, "default": 1e12},
            "limit":     {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
        },
    }

    def run(self, min_price: float = 0, max_price: float = 1e12, limit: int = 50) -> list[dict]:
        return _safe_rows(sql_tool.by_price_range(min_price, max_price, limit))


class GetMostExpensive(BaseTool):
    name = "get_most_expensive"
    description = (
        "Get the most expensive products (highest price first).\n"
        "\n"
        "When to use:\n"
        "  - 'สินค้าราคาแพงสุด', 'top expensive', 'premium products'.\n"
        "Arguments:\n"
        "  - limit: how many top items (1-50, default 5).\n"
        "Examples:\n"
        "  - 'สินค้าแพงสุด'      → {\"limit\": 1}\n"
        "  - 'top 5 ราคาสูง'    → {\"limit\": 5}"
    )
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5},
        },
    }

    def run(self, limit: int = 5) -> list[dict]:
        return _safe_rows(sql_tool.most_expensive(limit))


class GetCheapest(BaseTool):
    name = "get_cheapest"
    description = (
        "Get the cheapest products (lowest price first).\n"
        "\n"
        "When to use:\n"
        "  - 'สินค้าถูกที่สุด', 'cheapest item', 'budget pick'.\n"
        "Arguments:\n"
        "  - limit: how many bottom items (1-50, default 5).\n"
        "Examples:\n"
        "  - 'ของถูกสุด'           → {\"limit\": 1}\n"
        "  - 'top 3 ราคาต่ำ'      → {\"limit\": 3}"
    )
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5},
        },
    }

    def run(self, limit: int = 5) -> list[dict]:
        return _safe_rows(sql_tool.cheapest(limit))


class GetTotalStockValue(BaseTool):
    name = "get_total_stock_value"
    description = (
        "Get the total monetary value of remaining stock (SUM(qty × price)) in THB.\n"
        "\n"
        "When to use:\n"
        "  - 'มูลค่าสต็อกทั้งหมด', 'inventory value', 'ของในคลังเป็นเงินเท่าไร'.\n"
        "When NOT to use:\n"
        "  - Lifetime sales revenue → use get_total_revenue.\n"
        "  - Just qty count → use get_total_stock.\n"
        "Examples:\n"
        "  - 'มูลค่าสต็อกในคลังตอนนี้' → {}"
    )

    def run(self) -> dict:
        return sql_tool.total_stock_value()


class GetTotalRevenue(BaseTool):
    name = "get_total_revenue"
    description = (
        "Get lifetime revenue: SUM(sold_count × price). Assumes price has not changed "
        "historically — this is a snapshot estimate.\n"
        "\n"
        "When to use:\n"
        "  - 'รายได้รวมทั้งหมดเท่าไร', 'lifetime revenue', 'sales total in baht'.\n"
        "When NOT to use:\n"
        "  - Just unit count → use get_total_sold.\n"
        "Examples:\n"
        "  - 'รายได้สะสมทั้งหมด' → {}"
    )

    def run(self) -> dict:
        return sql_tool.total_revenue()


_ALL_TOOLS: tuple[type[BaseTool], ...] = (
    ListProducts,
    GetLowStock,
    GetOutOfStock,
    GetBestSellers,
    GetBottomSellers,
    SearchProductsByName,
    GetTotalStock,
    GetTotalSold,
    GetTotalStockValue,
    GetTotalRevenue,
    GetByColor,
    GetByPriceRange,
    GetMostExpensive,
    GetCheapest,
    GetCriticalAlerts,
)


def register_all(registry: ToolRegistry) -> None:
    """Register every stock tool. Other projects can mirror this entry-point."""
    for cls in _ALL_TOOLS:
        registry.register(cls())
