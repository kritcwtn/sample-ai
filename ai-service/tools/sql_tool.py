"""Read-only SQL queries for the stock domain — schema v2.

Hardened for production use:
  - connection timeout (5s) — never block on a dead DB
  - per-query statement timeout (5s)
  - structured logging of every query
  - safe error handling — never re-raise raw psycopg errors
  - hard row cap on every query
  - fuzzy search uses pg_trgm `%` operator + GIN index

Schema v2 supports JOINs across:
  products ↔ brands / categories / suppliers
  products ↔ product_locations ↔ warehouses
  customers ↔ orders ↔ order_items ↔ products
  stock_movements (audit log, time-series)
"""
from __future__ import annotations

import os
import re
import time
from typing import Any, Iterable

import psycopg

from core.logging_setup import get_logger
from core.validators import clamp_int, clamp_float

log = get_logger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgres://postgres:root@localhost:5432/cms_stock",
)
CONNECT_TIMEOUT_S = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
STATEMENT_TIMEOUT_MS = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "5000"))
HARD_ROW_CAP = 1000

_SETTING_RE = re.compile(r"^[a-z_][a-z0-9_.]*$")


def _safe_setting(name: str, value: Any) -> str:
    if not _SETTING_RE.match(name):
        raise ValueError(f"unsafe setting name: {name!r}")
    if isinstance(value, (int, float)):
        return f"SET LOCAL {name} = {value}"
    s = str(value).replace("'", "''")
    return f"SET LOCAL {name} = '{s}'"


def _connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, connect_timeout=CONNECT_TIMEOUT_S)


def _query(sql: str, params: Iterable[Any] = (), *, settings: dict | None = None) -> list[dict]:
    started = time.monotonic()
    rowcount = 0
    error: str | None = None
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}")
            for k, v in (settings or {}).items():
                cur.execute(_safe_setting(k, v))
            cur.execute(sql, tuple(params))
            cols = [d.name for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            rowcount = len(rows)
            return rows[:HARD_ROW_CAP]
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        return []
    finally:
        log.info(
            "sql.query",
            extra={
                "sql": _shorten(sql),
                "params": list(params),
                "duration_ms": round((time.monotonic() - started) * 1000, 1),
                "rowcount": rowcount,
                "error": error,
            },
        )


def _shorten(s: str, n: int = 200) -> str:
    one_line = " ".join(s.split())
    return one_line if len(one_line) <= n else one_line[:n] + "..."


# ----- column lists ------------------------------------------------------

_PROD_COLS = """
    p.id, p.sku, p.name, p.qty, p.sold_count, p.price, p.discount_percent,
    p.color, p.weight_kg, p.rating, p.review_count, p.tags, p.is_active,
    b.name AS brand, c.name AS category, s.name AS supplier
"""
_PROD_JOINS = """
    FROM products p
    LEFT JOIN brands     b ON b.id = p.brand_id
    LEFT JOIN categories c ON c.id = p.category_id
    LEFT JOIN suppliers  s ON s.id = p.supplier_id
"""


# =====================================================================
#  PRODUCTS — basic
# =====================================================================

def all_products(limit: int = 50) -> list[dict]:
    limit = clamp_int(limit, 1, 200, default=50)
    return _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} WHERE p.is_active ORDER BY p.id LIMIT %s",
        (limit,),
    )


def low_stock(threshold: int = 5, limit: int = 50) -> list[dict]:
    threshold = clamp_int(threshold, 0, 10**6, default=5)
    limit = clamp_int(limit, 1, 200, default=50)
    return _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} "
        f"WHERE p.qty < %s AND p.is_active ORDER BY p.qty ASC LIMIT %s",
        (threshold, limit),
    )


def out_of_stock(limit: int = 50) -> list[dict]:
    limit = clamp_int(limit, 1, 200, default=50)
    return _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} "
        f"WHERE p.qty = 0 AND p.is_active ORDER BY p.id LIMIT %s",
        (limit,),
    )


def best_sellers(limit: int = 5) -> list[dict]:
    limit = clamp_int(limit, 1, 50, default=5)
    return _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} "
        f"WHERE p.is_active ORDER BY p.sold_count DESC LIMIT %s",
        (limit,),
    )


def bottom_sellers(limit: int = 5) -> list[dict]:
    limit = clamp_int(limit, 1, 50, default=5)
    return _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} "
        f"WHERE p.is_active ORDER BY p.sold_count ASC LIMIT %s",
        (limit,),
    )


def find_by_name(keyword: str, *, limit: int = 10, fuzzy_threshold: float = 0.25) -> list[dict]:
    keyword = (keyword or "").strip()
    if not keyword:
        return []
    limit = clamp_int(limit, 1, 50, default=10)

    rows = _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} "
        f"WHERE p.name ILIKE %s ORDER BY p.id LIMIT %s",
        (f"%{keyword}%", limit),
    )
    if rows:
        return rows
    threshold = clamp_float(fuzzy_threshold, 0.05, 1.0, default=0.25)
    return _query(
        f"SELECT {_PROD_COLS}, similarity(p.name, %s) AS _sim {_PROD_JOINS} "
        f"WHERE p.name %% %s ORDER BY _sim DESC LIMIT %s",
        (keyword, keyword, limit),
        settings={"pg_trgm.similarity_threshold": str(threshold)},
    )


def total_qty() -> dict:
    rows = _query("SELECT COALESCE(SUM(qty),0) AS total FROM products WHERE is_active")
    return {"metric": "total_qty", "value": int(rows[0]["total"]) if rows else 0}


def total_sold() -> dict:
    rows = _query("SELECT COALESCE(SUM(sold_count),0) AS total FROM products")
    return {"metric": "total_sold", "value": int(rows[0]["total"]) if rows else 0}


def total_stock_value() -> dict:
    rows = _query(
        "SELECT COALESCE(SUM(qty * price * (1 - discount_percent/100)), 0)::float AS total "
        "FROM products WHERE is_active"
    )
    return {"metric": "total_stock_value", "value": float(rows[0]["total"]) if rows else 0.0}


def discounted_products(min_discount: float = 0.01, limit: int = 50) -> list[dict]:
    min_discount = clamp_float(min_discount, 0, 100, default=0.01)
    limit = clamp_int(limit, 1, 200, default=50)
    return _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} "
        f"WHERE p.discount_percent >= %s AND p.is_active "
        f"ORDER BY p.discount_percent DESC, p.price ASC LIMIT %s",
        (min_discount, limit),
    )


def by_price_range(min_price: float = 0, max_price: float = 1e12, limit: int = 50) -> list[dict]:
    min_price = clamp_float(min_price, 0, 1e12, default=0)
    max_price = clamp_float(max_price, 0, 1e12, default=1e12)
    limit = clamp_int(limit, 1, 200, default=50)
    return _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} "
        f"WHERE p.price BETWEEN %s AND %s AND p.is_active "
        f"ORDER BY p.price ASC LIMIT %s",
        (min_price, max_price, limit),
    )


def by_color(color: str, limit: int = 50) -> list[dict]:
    color = (color or "").strip()
    if not color:
        return []
    limit = clamp_int(limit, 1, 200, default=50)
    return _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} "
        f"WHERE p.color ILIKE %s AND p.is_active ORDER BY p.id LIMIT %s",
        (color, limit),
    )


def most_expensive(limit: int = 5) -> list[dict]:
    limit = clamp_int(limit, 1, 50, default=5)
    return _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} "
        f"WHERE p.is_active ORDER BY p.price DESC LIMIT %s",
        (limit,),
    )


def cheapest(limit: int = 5) -> list[dict]:
    limit = clamp_int(limit, 1, 50, default=5)
    return _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} "
        f"WHERE p.is_active ORDER BY p.price ASC LIMIT %s",
        (limit,),
    )


# =====================================================================
#  BRAND / CATEGORY / SUPPLIER (NEW)
# =====================================================================

def by_brand(brand_name: str, limit: int = 50) -> list[dict]:
    limit = clamp_int(limit, 1, 200, default=50)
    return _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} "
        f"WHERE b.name ILIKE %s AND p.is_active ORDER BY p.sold_count DESC LIMIT %s",
        (brand_name, limit),
    )


def by_category(category_name: str, limit: int = 50) -> list[dict]:
    limit = clamp_int(limit, 1, 200, default=50)
    return _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} "
        f"WHERE c.name ILIKE %s AND p.is_active ORDER BY p.sold_count DESC LIMIT %s",
        (category_name, limit),
    )


def list_brands() -> list[dict]:
    return _query(
        """
        SELECT b.id, b.name, b.country,
               COUNT(p.id) AS product_count,
               COALESCE(SUM(p.sold_count),0)::int AS total_sold
        FROM brands b LEFT JOIN products p ON p.brand_id = b.id AND p.is_active
        GROUP BY b.id ORDER BY total_sold DESC
        """
    )


def list_categories() -> list[dict]:
    return _query(
        """
        SELECT c.id, c.name,
               COUNT(p.id) AS product_count,
               COALESCE(SUM(p.qty),0)::int AS total_qty
        FROM categories c LEFT JOIN products p ON p.category_id = c.id AND p.is_active
        GROUP BY c.id ORDER BY product_count DESC
        """
    )


def by_supplier(supplier_name: str, limit: int = 50) -> list[dict]:
    limit = clamp_int(limit, 1, 200, default=50)
    return _query(
        f"SELECT {_PROD_COLS}, s.lead_time_days {_PROD_JOINS} "
        f"WHERE s.name ILIKE %s AND p.is_active ORDER BY p.id LIMIT %s",
        (supplier_name, limit),
    )


# =====================================================================
#  WAREHOUSES (NEW)
# =====================================================================

def list_warehouses() -> list[dict]:
    return _query(
        """
        SELECT w.id, w.code, w.name, w.city, w.capacity,
               COALESCE(SUM(pl.qty),0)::int AS total_qty,
               COUNT(DISTINCT pl.product_id) AS product_count
        FROM warehouses w LEFT JOIN product_locations pl ON pl.warehouse_id = w.id
        GROUP BY w.id ORDER BY total_qty DESC
        """
    )


def stock_at_warehouse(warehouse_code: str, limit: int = 50) -> list[dict]:
    limit = clamp_int(limit, 1, 200, default=50)
    return _query(
        f"""
        SELECT {_PROD_COLS}, w.code AS warehouse_code, w.name AS warehouse_name, pl.qty AS qty_at_warehouse
        {_PROD_JOINS}
        JOIN product_locations pl ON pl.product_id = p.id
        JOIN warehouses w ON w.id = pl.warehouse_id
        WHERE w.code = %s AND pl.qty > 0
        ORDER BY pl.qty DESC LIMIT %s
        """,
        (warehouse_code, limit),
    )


def warehouses_holding(product_keyword: str) -> list[dict]:
    """Show which warehouses currently hold stock of a given product (keyword match)."""
    kw = (product_keyword or "").strip()
    if not kw:
        return []
    return _query(
        """
        SELECT p.id AS product_id, p.name, w.code, w.name AS warehouse_name, w.city, pl.qty
        FROM products p
        JOIN product_locations pl ON pl.product_id = p.id
        JOIN warehouses w ON w.id = pl.warehouse_id
        WHERE p.name ILIKE %s AND pl.qty > 0
        ORDER BY pl.qty DESC LIMIT 50
        """,
        (f"%{kw}%",),
    )


# =====================================================================
#  CUSTOMERS / ORDERS (NEW)
# =====================================================================

def find_customer(name_keyword: str, limit: int = 10) -> list[dict]:
    kw = (name_keyword or "").strip()
    if not kw:
        return []
    limit = clamp_int(limit, 1, 50, default=10)
    return _query(
        """
        SELECT id, name, email, phone, city,
               (SELECT COUNT(*) FROM orders WHERE customer_id = c.id) AS order_count,
               (SELECT COALESCE(SUM(total_amount),0)::float FROM orders WHERE customer_id = c.id
                AND status <> 'cancelled') AS total_spent
        FROM customers c WHERE name ILIKE %s ORDER BY id LIMIT %s
        """,
        (f"%{kw}%", limit),
    )


def top_customers(limit: int = 10, days: int = 180) -> list[dict]:
    limit = clamp_int(limit, 1, 50, default=10)
    days = clamp_int(days, 1, 3650, default=180)
    return _query(
        """
        SELECT c.id, c.name, c.city,
               COUNT(o.id) AS order_count,
               COALESCE(SUM(o.total_amount),0)::float AS total_spent
        FROM customers c
        JOIN orders o ON o.customer_id = c.id
        WHERE o.status <> 'cancelled'
          AND o.ordered_at >= NOW() - (%s || ' days')::interval
        GROUP BY c.id ORDER BY total_spent DESC LIMIT %s
        """,
        (days, limit),
    )


def recent_orders(days: int = 7, limit: int = 20) -> list[dict]:
    days = clamp_int(days, 1, 365, default=7)
    limit = clamp_int(limit, 1, 100, default=20)
    return _query(
        """
        SELECT o.id, o.status, o.total_amount::float AS total_amount,
               o.ordered_at, c.name AS customer
        FROM orders o JOIN customers c ON c.id = o.customer_id
        WHERE o.ordered_at >= NOW() - (%s || ' days')::interval
        ORDER BY o.ordered_at DESC LIMIT %s
        """,
        (days, limit),
    )


def customer_orders(customer_name: str, limit: int = 20) -> list[dict]:
    kw = (customer_name or "").strip()
    if not kw:
        return []
    limit = clamp_int(limit, 1, 100, default=20)
    return _query(
        """
        SELECT o.id, o.status, o.total_amount::float AS total_amount, o.ordered_at,
               c.name AS customer
        FROM orders o JOIN customers c ON c.id = o.customer_id
        WHERE c.name ILIKE %s ORDER BY o.ordered_at DESC LIMIT %s
        """,
        (f"%{kw}%", limit),
    )


# =====================================================================
#  TIME-SERIES / TREND (NEW)
# =====================================================================

def revenue_period(days: int = 30) -> dict:
    days = clamp_int(days, 1, 3650, default=30)
    rows = _query(
        """
        SELECT COALESCE(SUM(total_amount),0)::float AS total,
               COUNT(*) AS order_count
        FROM orders
        WHERE ordered_at >= NOW() - (%s || ' days')::interval
          AND status <> 'cancelled'
        """,
        (days,),
    )
    if not rows:
        return {"metric": "revenue_period", "days": days, "value": 0.0, "order_count": 0}
    r = rows[0]
    return {
        "metric": "revenue_period",
        "days": days,
        "value": float(r["total"]),
        "order_count": int(r["order_count"]),
    }


def sales_by_month(months: int = 6) -> list[dict]:
    months = clamp_int(months, 1, 24, default=6)
    return _query(
        """
        SELECT to_char(date_trunc('month', ordered_at), 'YYYY-MM') AS month,
               COUNT(*) AS order_count,
               COALESCE(SUM(total_amount),0)::float AS revenue
        FROM orders
        WHERE ordered_at >= NOW() - (%s || ' months')::interval
          AND status <> 'cancelled'
        GROUP BY 1 ORDER BY 1 DESC
        """,
        (months,),
    )


def trending_products(days: int = 30, limit: int = 10) -> list[dict]:
    """Top products by units sold in the recent window (joined via order_items)."""
    days = clamp_int(days, 1, 365, default=30)
    limit = clamp_int(limit, 1, 50, default=10)
    return _query(
        """
        SELECT p.id, p.sku, p.name, b.name AS brand, c.name AS category,
               SUM(oi.qty)::int AS qty_sold,
               COALESCE(SUM(oi.line_total),0)::float AS revenue
        FROM order_items oi
        JOIN products   p ON p.id = oi.product_id
        JOIN orders     o ON o.id = oi.order_id
        LEFT JOIN brands     b ON b.id = p.brand_id
        LEFT JOIN categories c ON c.id = p.category_id
        WHERE o.ordered_at >= NOW() - (%s || ' days')::interval
          AND o.status <> 'cancelled'
        GROUP BY p.id, b.name, c.name
        ORDER BY qty_sold DESC LIMIT %s
        """,
        (days, limit),
    )


# =====================================================================
#  QUALITY / RATING (NEW)
# =====================================================================

def top_rated(limit: int = 10, min_reviews: int = 20) -> list[dict]:
    limit = clamp_int(limit, 1, 50, default=10)
    min_reviews = clamp_int(min_reviews, 0, 1000, default=20)
    return _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} "
        f"WHERE p.is_active AND p.review_count >= %s "
        f"ORDER BY p.rating DESC, p.review_count DESC LIMIT %s",
        (min_reviews, limit),
    )


def lowest_rated(limit: int = 10, min_reviews: int = 10) -> list[dict]:
    limit = clamp_int(limit, 1, 50, default=10)
    min_reviews = clamp_int(min_reviews, 0, 1000, default=10)
    return _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} "
        f"WHERE p.is_active AND p.review_count >= %s "
        f"ORDER BY p.rating ASC LIMIT %s",
        (min_reviews, limit),
    )


def search_products(
    *,
    brand: str | None = None,
    category: str | None = None,
    warehouse_code: str | None = None,
    color: str | None = None,
    on_sale: bool = False,
    min_price: float | None = None,
    max_price: float | None = None,
    min_rating: float | None = None,
    limit: int = 50,
    sort: str = "id",
) -> list[dict]:
    """One unified filter tool — combines any of the supported filters
    into a single query. Used when the user asks compound questions like
    'Smartwatch ที่สาขาเชียงใหม่ ที่ลดราคา'."""
    limit = clamp_int(limit, 1, 200, default=50)
    where = ["p.is_active"]
    params: list[Any] = []

    if brand:
        where.append("b.name ILIKE %s"); params.append(brand)
    if category:
        where.append("c.name ILIKE %s"); params.append(category)
    if color:
        where.append("p.color ILIKE %s"); params.append(color)
    if on_sale:
        where.append("p.discount_percent > 0")
    if min_price is not None:
        where.append("p.price >= %s"); params.append(clamp_float(min_price, 0, 1e12, default=0))
    if max_price is not None:
        where.append("p.price <= %s"); params.append(clamp_float(max_price, 0, 1e12, default=1e12))
    if min_rating is not None:
        where.append("p.rating >= %s"); params.append(clamp_float(min_rating, 0, 5, default=0))

    join_wh = ""
    if warehouse_code:
        join_wh = (
            " JOIN product_locations pl ON pl.product_id = p.id "
            " JOIN warehouses w ON w.id = pl.warehouse_id AND w.code ILIKE %s "
        )
        params.append(warehouse_code)
        where.append("pl.qty > 0")

    sort_col = {
        "price_asc":  "p.price ASC",
        "price_desc": "p.price DESC",
        "sold":       "p.sold_count DESC",
        "rating":     "p.rating DESC",
        "discount":   "p.discount_percent DESC",
    }.get(sort, "p.id")

    sql = (
        f"SELECT DISTINCT {_PROD_COLS} {_PROD_JOINS} {join_wh} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY {sort_col} LIMIT %s"
    )
    params.append(limit)
    return _query(sql, tuple(params))


def most_reviewed(limit: int = 10) -> list[dict]:
    limit = clamp_int(limit, 1, 50, default=10)
    return _query(
        f"SELECT {_PROD_COLS} {_PROD_JOINS} "
        f"WHERE p.is_active ORDER BY p.review_count DESC LIMIT %s",
        (limit,),
    )
