"""Stock-domain tools — schema v2 (catalogue + relations + history)."""
from __future__ import annotations

from typing import Any

from .base import BaseTool, ToolRegistry
from . import sql_tool


_ALLOWED = {
    # core product
    "id", "sku", "name", "qty", "sold_count",
    "price", "discount_percent", "effective_price", "color",
    "weight_kg", "rating", "review_count", "tags", "is_active",
    # joined refs
    "brand", "category", "supplier",
    # extras for specific tools
    "warehouse_code", "warehouse_name", "qty_at_warehouse",
    "city", "lead_time_days", "country",
    # aggregates / time-series
    "metric", "value", "month", "order_count", "revenue", "qty_sold",
    "total_qty", "product_count", "total_sold", "total_spent",
    "days", "capacity",
    # orders / customers
    "customer", "customer_id", "product_id", "warehouse_id",
    "order_id", "status", "ordered_at", "total_amount", "email", "phone",
    "severity",
}


def _safe_rows(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        clean = {k: v for k, v in r.items() if k in _ALLOWED}
        for k in ("price", "discount_percent", "weight_kg", "rating",
                  "total_amount", "revenue", "total_spent", "value"):
            if k in clean and clean[k] is not None:
                try:
                    clean[k] = float(clean[k])
                except (TypeError, ValueError):
                    pass
        # computed effective_price for product rows
        if "price" in clean and "discount_percent" in clean:
            clean["effective_price"] = round(
                clean["price"] * (1 - clean["discount_percent"] / 100), 2
            )
        out.append(clean)
    return out


# =========================================================================
#  PRODUCT BASICS
# =========================================================================

class ListProducts(BaseTool):
    name = "list_products"
    description = (
        "List active products with brand, category, price and key fields.\n"
        "When to use: catalogue overview, 'list all products', 'what do we sell'.\n"
        "When NOT to use: filtered by brand/category/warehouse — use the dedicated tool.\n"
        "Arguments: limit (1-200, default 50)."
    )
    parameters = {
        "type": "object",
        "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50}},
    }
    def run(self, limit: int = 50) -> list[dict]:
        return _safe_rows(sql_tool.all_products(limit))


class GetLowStock(BaseTool):
    name = "get_low_stock"
    description = (
        "Get products whose remaining qty is below a threshold (default < 5).\n"
        "When to use: 'ใกล้หมด', 'low stock', 'reorder list'.\n"
        "Arguments: threshold (1-100), limit."
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
    description = "Get products with qty = 0 (sold out)."
    parameters = {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50}}}
    def run(self, limit: int = 50) -> list[dict]:
        return _safe_rows(sql_tool.out_of_stock(limit))


class GetBestSellers(BaseTool):
    name = "get_best_sellers"
    description = (
        "Top-selling products by lifetime sold_count (highest first).\n"
        "When to use: 'ขายดีที่สุด', 'top seller', 'popular'.\n"
        "When NOT to use: comparing two named products → use search_products_by_name twice.\n"
        "When NOT to use for trending: use get_trending_products for recent N-day window."
    )
    parameters = {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5}}}
    def run(self, limit: int = 5) -> list[dict]:
        return _safe_rows(sql_tool.best_sellers(limit))


class GetBottomSellers(BaseTool):
    name = "get_bottom_sellers"
    description = "Worst-selling products by sold_count (lowest first). Use for 'ขายไม่ดี', 'slow movers'."
    parameters = {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5}}}
    def run(self, limit: int = 5) -> list[dict]:
        return _safe_rows(sql_tool.bottom_sellers(limit))


class SearchProductsByName(BaseTool):
    name = "search_products_by_name"
    description = (
        "Search products by name keyword. Tries exact substring (ILIKE) first; "
        "falls back to fuzzy similarity for typos like 'ihpone' → 'iPhone'.\n"
        "When to use: user mentions a specific product/SKU; comparing named products (call once per product).\n"
        "Arguments: keyword (required), limit (1-20)."
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
    description = "Total remaining qty across all active products."
    def run(self) -> dict:
        return sql_tool.total_qty()


class GetTotalSold(BaseTool):
    name = "get_total_sold"
    description = "Total lifetime units sold across all products."
    def run(self) -> dict:
        return sql_tool.total_sold()


class GetTotalStockValue(BaseTool):
    name = "get_total_stock_value"
    description = (
        "Monetary value of remaining stock: SUM(qty × price × (1 - discount/100)) in THB.\n"
        "When to use: 'มูลค่าสต็อก', 'inventory value'."
    )
    def run(self) -> dict:
        return sql_tool.total_stock_value()


class GetMostExpensive(BaseTool):
    name = "get_most_expensive"
    description = "Top-N products by listed price (highest first)."
    parameters = {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5}}}
    def run(self, limit: int = 5) -> list[dict]:
        return _safe_rows(sql_tool.most_expensive(limit))


class GetCheapest(BaseTool):
    name = "get_cheapest"
    description = "Top-N products by listed price (lowest first)."
    parameters = {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5}}}
    def run(self, limit: int = 5) -> list[dict]:
        return _safe_rows(sql_tool.cheapest(limit))


class GetByPriceRange(BaseTool):
    name = "get_products_by_price_range"
    description = (
        "Filter products by price range (min/max in THB).\n"
        "When to use: 'ราคาไม่เกิน X', 'budget under Y', 'between A and B'."
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


class GetByColor(BaseTool):
    name = "get_products_by_color"
    description = "Filter products by color. Use for 'สีดำ', 'silver products'."
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


class GetDiscountedProducts(BaseTool):
    name = "get_discounted_products"
    description = (
        "Products currently on promotion (discount_percent > min). Sorted by discount desc.\n"
        "When to use: 'ลดราคา', 'sale', 'promotion'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "min_discount": {"type": "number", "minimum": 0, "maximum": 100, "default": 0.01},
            "limit":        {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
        },
    }
    def run(self, min_discount: float = 0.01, limit: int = 50) -> list[dict]:
        return _safe_rows(sql_tool.discounted_products(min_discount, limit))


# =========================================================================
#  BRAND / CATEGORY / SUPPLIER
# =========================================================================

class GetByBrand(BaseTool):
    name = "get_products_by_brand"
    description = (
        "Find products from a specific brand (Apple, Samsung, Sony, etc.). "
        "Sorted by lifetime sold_count.\n"
        "When to use: 'สินค้า Apple', 'Samsung products', 'Brand X catalogue'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "brand": {"type": "string", "minLength": 1, "maxLength": 50},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
        },
        "required": ["brand"],
    }
    def run(self, brand: str, limit: int = 50) -> list[dict]:
        return _safe_rows(sql_tool.by_brand(brand, limit))


class GetByCategory(BaseTool):
    name = "get_products_by_category"
    description = (
        "Find products by category name (Smartphone, Laptop, Earbuds, ...). "
        "Sorted by sold_count.\n"
        "When to use: 'หมวด Phone', 'Laptops', 'Smartwatch list'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "minLength": 1, "maxLength": 50},
            "limit":    {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
        },
        "required": ["category"],
    }
    def run(self, category: str, limit: int = 50) -> list[dict]:
        return _safe_rows(sql_tool.by_category(category, limit))


class ListBrands(BaseTool):
    name = "list_brands"
    description = (
        "List every brand with product count and total sold. Sorted by total_sold desc.\n"
        "When to use: 'แบรนด์ไหนขายดีสุด', 'how many brands', 'brand ranking'."
    )
    def run(self) -> list[dict]:
        return _safe_rows(sql_tool.list_brands())


class ListCategories(BaseTool):
    name = "list_categories"
    description = (
        "List every category with product count and total qty.\n"
        "When to use: 'มีหมวดหมู่อะไรบ้าง', 'category breakdown'."
    )
    def run(self) -> list[dict]:
        return _safe_rows(sql_tool.list_categories())


class GetBySupplier(BaseTool):
    name = "get_products_by_supplier"
    description = (
        "Products from a specific supplier (importer/distributor). "
        "Includes lead_time_days for reorder planning.\n"
        "When to use: 'supplier เจ้าไหนส่งอะไร', 'lead time'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "supplier": {"type": "string", "minLength": 1, "maxLength": 80},
            "limit":    {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
        },
        "required": ["supplier"],
    }
    def run(self, supplier: str, limit: int = 50) -> list[dict]:
        return _safe_rows(sql_tool.by_supplier(supplier, limit))


# =========================================================================
#  WAREHOUSES
# =========================================================================

class ListWarehouses(BaseTool):
    name = "list_warehouses"
    description = (
        "List all warehouses with code, city, total_qty, capacity.\n"
        "When to use: 'มีสาขา/โกดังที่ไหนบ้าง', 'warehouse capacity'."
    )
    def run(self) -> list[dict]:
        return _safe_rows(sql_tool.list_warehouses())


class StockAtWarehouse(BaseTool):
    name = "get_stock_at_warehouse"
    description = (
        "Top products with stock at a specific warehouse (by code: BKK-SLM, BKK-BNA, "
        "BKK-RIN, CNX-MUNG, HKT-001, HDY-001, KKC-001, KOR-001).\n"
        "When to use: 'สาขาบางนามีอะไรเหลือบ้าง', 'inventory at warehouse X'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "warehouse_code": {"type": "string", "minLength": 3, "maxLength": 20},
            "limit":          {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
        },
        "required": ["warehouse_code"],
    }
    def run(self, warehouse_code: str, limit: int = 50) -> list[dict]:
        return _safe_rows(sql_tool.stock_at_warehouse(warehouse_code.upper(), limit))


class WarehousesHolding(BaseTool):
    name = "get_warehouses_holding_product"
    description = (
        "Show which warehouses currently hold stock of a given product (by name keyword), "
        "with qty per warehouse.\n"
        "When to use: 'iPhone อยู่สาขาไหนบ้าง', 'where is product X stocked'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "product_keyword": {"type": "string", "minLength": 1, "maxLength": 80},
        },
        "required": ["product_keyword"],
    }
    def run(self, product_keyword: str) -> list[dict]:
        return _safe_rows(sql_tool.warehouses_holding(product_keyword))


# =========================================================================
#  CUSTOMERS / ORDERS
# =========================================================================

class FindCustomer(BaseTool):
    name = "find_customer"
    description = (
        "Search customers by name keyword. Returns customer info + order_count + total_spent.\n"
        "When to use: user names a customer; 'ลูกค้าชื่อ ...'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": 50},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
        },
        "required": ["name"],
    }
    def run(self, name: str, limit: int = 10) -> list[dict]:
        return _safe_rows(sql_tool.find_customer(name, limit))


class TopCustomers(BaseTool):
    name = "get_top_customers"
    description = (
        "Top customers by total amount spent within recent N days (default 180). "
        "Sorted by total_spent desc.\n"
        "When to use: 'ลูกค้ารายใหญ่', 'VIP customers', 'top spenders'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            "days":  {"type": "integer", "minimum": 1, "maximum": 730, "default": 180},
        },
    }
    def run(self, limit: int = 10, days: int = 180) -> list[dict]:
        return _safe_rows(sql_tool.top_customers(limit, days))


class RecentOrders(BaseTool):
    name = "get_recent_orders"
    description = "Recent orders within last N days. Sorted by ordered_at desc."
    parameters = {
        "type": "object",
        "properties": {
            "days":  {"type": "integer", "minimum": 1, "maximum": 365, "default": 7},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
        },
    }
    def run(self, days: int = 7, limit: int = 20) -> list[dict]:
        return _safe_rows(sql_tool.recent_orders(days, limit))


class CustomerOrders(BaseTool):
    name = "get_customer_orders"
    description = (
        "Get orders for a specific customer (by name keyword).\n"
        "When to use: 'ลูกค้า X ซื้ออะไรบ้าง', 'order history of ...'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "customer_name": {"type": "string", "minLength": 1, "maxLength": 50},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
        },
        "required": ["customer_name"],
    }
    def run(self, customer_name: str, limit: int = 20) -> list[dict]:
        return _safe_rows(sql_tool.customer_orders(customer_name, limit))


# =========================================================================
#  TIME-SERIES / TREND
# =========================================================================

class RevenuePeriod(BaseTool):
    name = "get_revenue_period"
    description = (
        "Total revenue (sum of order totals) within recent N days (excludes cancelled).\n"
        "When to use: 'รายได้เดือนนี้', 'revenue last 30 days', 'รายได้ 7 วัน'."
    )
    parameters = {
        "type": "object",
        "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 3650, "default": 30}},
    }
    def run(self, days: int = 30) -> dict:
        return sql_tool.revenue_period(days)


class SalesByMonth(BaseTool):
    name = "get_sales_by_month"
    description = (
        "Monthly breakdown of orders + revenue for last N months. Useful for trends.\n"
        "When to use: 'ขายเดือนไหนดีสุด', 'monthly trend', 'compare months'."
    )
    parameters = {
        "type": "object",
        "properties": {"months": {"type": "integer", "minimum": 1, "maximum": 24, "default": 6}},
    }
    def run(self, months: int = 6) -> list[dict]:
        return _safe_rows(sql_tool.sales_by_month(months))


class TrendingProducts(BaseTool):
    name = "get_trending_products"
    description = (
        "Top products by units sold within recent N days (joined via order_items). "
        "Reflects RECENT performance, unlike get_best_sellers which uses lifetime.\n"
        "When to use: 'ขายดีตอนนี้', 'trending', 'this month best sellers'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "days": {"type": "integer", "minimum": 1, "maximum": 365, "default": 30},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
        },
    }
    def run(self, days: int = 30, limit: int = 10) -> list[dict]:
        return _safe_rows(sql_tool.trending_products(days, limit))


# =========================================================================
#  QUALITY / RATING
# =========================================================================

class TopRated(BaseTool):
    name = "get_top_rated"
    description = (
        "Top-rated products (highest rating, with min_reviews threshold to avoid noise).\n"
        "When to use: 'รีวิวดีที่สุด', 'best rated', 'top quality'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "limit":       {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            "min_reviews": {"type": "integer", "minimum": 0, "maximum": 1000, "default": 20},
        },
    }
    def run(self, limit: int = 10, min_reviews: int = 20) -> list[dict]:
        return _safe_rows(sql_tool.top_rated(limit, min_reviews))


class LowestRated(BaseTool):
    name = "get_lowest_rated"
    description = "Worst-rated products (with min_reviews to filter junk data)."
    parameters = {
        "type": "object",
        "properties": {
            "limit":       {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            "min_reviews": {"type": "integer", "minimum": 0, "maximum": 1000, "default": 10},
        },
    }
    def run(self, limit: int = 10, min_reviews: int = 10) -> list[dict]:
        return _safe_rows(sql_tool.lowest_rated(limit, min_reviews))


class MostReviewed(BaseTool):
    name = "get_most_reviewed"
    description = "Products with the most reviews (popularity by review count)."
    parameters = {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10}}}
    def run(self, limit: int = 10) -> list[dict]:
        return _safe_rows(sql_tool.most_reviewed(limit))


# =========================================================================
#  COMPOSABLE
# =========================================================================

class SearchProducts(BaseTool):
    name = "search_products"
    description = (
        "Unified product search that combines MULTIPLE filters in ONE call: "
        "brand, category, warehouse, color, on_sale, price range, min_rating. "
        "Use this for COMPOUND questions that mix 2+ filters.\n"
        "\n"
        "When to use:\n"
        "  - User combines filters: 'Smartwatch ที่สาขาเชียงใหม่ ที่ลดราคา', "
        "    'Apple ราคาไม่เกิน 30000', 'สีดำของ Samsung'.\n"
        "  - User asks 'ที่[brand]และ[category]และ[wh]'.\n"
        "When NOT to use:\n"
        "  - Single filter only — use the dedicated tool (get_products_by_brand, etc.).\n"
        "  - Searching by name keyword → use search_products_by_name.\n"
        "Arguments:\n"
        "  - brand:          brand name (e.g. 'Apple')\n"
        "  - category:       category name (e.g. 'Smartwatch')\n"
        "  - warehouse_code: warehouse code (e.g. 'CNX-MUNG' for Chiang Mai). "
        "Codes: BKK-SLM, BKK-BNA, BKK-RIN, CNX-MUNG, HKT-001, HDY-001, KKC-001, KOR-001.\n"
        "  - color:          color name (e.g. 'Black')\n"
        "  - on_sale:        true to keep only discounted items\n"
        "  - min_price/max_price: price bounds in THB\n"
        "  - min_rating:     0-5\n"
        "  - sort:           id | price_asc | price_desc | sold | rating | discount\n"
        "  - limit:          1-200 (default 50)\n"
        "Examples:\n"
        "  - 'Smartwatch ที่เชียงใหม่ ลดราคา' → "
        "{\"category\": \"Smartwatch\", \"warehouse_code\": \"CNX-MUNG\", \"on_sale\": true}\n"
        "  - 'Apple Smartphone ลด' → "
        "{\"brand\": \"Apple\", \"category\": \"Smartphone\", \"on_sale\": true}\n"
        "  - 'สีดำ ราคา 5k-20k' → "
        "{\"color\": \"Black\", \"min_price\": 5000, \"max_price\": 20000}"
    )
    parameters = {
        "type": "object",
        "properties": {
            "brand":          {"type": "string", "maxLength": 50},
            "category":       {"type": "string", "maxLength": 50},
            "warehouse_code": {"type": "string", "maxLength": 20},
            "color":          {"type": "string", "maxLength": 30},
            "on_sale":        {"type": "boolean", "default": False},
            "min_price":      {"type": "number", "minimum": 0},
            "max_price":      {"type": "number", "minimum": 0},
            "min_rating":     {"type": "number", "minimum": 0, "maximum": 5},
            "sort":           {"type": "string", "maxLength": 20},
            "limit":          {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
        },
    }

    def run(self, **kwargs) -> list[dict]:
        return _safe_rows(sql_tool.search_products(**kwargs))


class GetCriticalAlerts(BaseTool):
    name = "get_critical_alerts"
    description = (
        "Combined alert: out-of-stock + low-stock items, in one call. Each row has 'severity'.\n"
        "When to use: 'รายงานสินค้าต้องดูแล', 'inventory alert dashboard'."
    )
    parameters = {
        "type": "object",
        "properties": {"threshold": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5}},
    }
    def run(self, threshold: int = 5) -> list[dict]:
        out = _safe_rows(sql_tool.out_of_stock(50))
        low = _safe_rows(sql_tool.low_stock(threshold, 50))
        seen: set = set()
        result: list[dict] = []
        for r in out:
            seen.add(r["id"])
            result.append({**r, "severity": "out_of_stock"})
        for r in low:
            if r["id"] in seen:
                continue
            result.append({**r, "severity": "low"})
        return result


# =========================================================================
#  REGISTRATION
# =========================================================================

_ALL_TOOLS: tuple[type[BaseTool], ...] = (
    # core product
    ListProducts,
    GetLowStock,
    GetOutOfStock,
    GetBestSellers,
    GetBottomSellers,
    SearchProductsByName,
    GetTotalStock,
    GetTotalSold,
    GetTotalStockValue,
    GetMostExpensive,
    GetCheapest,
    GetByPriceRange,
    GetByColor,
    GetDiscountedProducts,
    # brand / category / supplier
    GetByBrand,
    GetByCategory,
    ListBrands,
    ListCategories,
    GetBySupplier,
    # warehouses
    ListWarehouses,
    StockAtWarehouse,
    WarehousesHolding,
    # customers / orders
    FindCustomer,
    TopCustomers,
    RecentOrders,
    CustomerOrders,
    # time-series
    RevenuePeriod,
    SalesByMonth,
    TrendingProducts,
    # quality
    TopRated,
    LowestRated,
    MostReviewed,
    # composable / unified
    SearchProducts,
    GetCriticalAlerts,
)


def register_all(registry: ToolRegistry) -> None:
    for cls in _ALL_TOOLS:
        registry.register(cls())
