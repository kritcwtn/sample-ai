"""Read-only SQL queries for the stock domain.

Hardened for production use:
  - connection timeout (5s) — never block on a dead DB
  - per-query statement timeout (5s)
  - structured logging of every query (sql, params, duration, rowcount, error)
  - safe error handling — never re-raise raw psycopg errors to the LLM
  - hard row cap on every query (defense in depth)
  - fuzzy search uses pg_trgm `%` operator + GIN index for index-friendly lookup

Required indexes (already created via migration):
  CREATE EXTENSION pg_trgm;
  CREATE INDEX idx_products_name_trgm ON products USING gin (name gin_trgm_ops);
  CREATE INDEX idx_products_qty       ON products (qty);
  CREATE INDEX idx_products_sold_desc ON products (sold_count DESC);
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

# Hard cap — even if a tool forgets to specify, we never return more than this.
HARD_ROW_CAP = 1000


# ---- internals ----------------------------------------------------------

def _connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, connect_timeout=CONNECT_TIMEOUT_S)


_SETTING_RE = re.compile(r"^[a-z_][a-z0-9_.]*$")


def _safe_setting(name: str, value: Any) -> str:
    """Render a `SET LOCAL` statement safely. Postgres does not accept
    parameter binding for SET, so we have to inline — validate strictly."""
    if not _SETTING_RE.match(name):
        raise ValueError(f"unsafe setting name: {name!r}")
    if isinstance(value, (int, float)):
        return f"SET LOCAL {name} = {value}"
    s = str(value).replace("'", "''")
    return f"SET LOCAL {name} = '{s}'"


def _query(
    sql: str,
    params: Iterable[Any] = (),
    *,
    settings: dict[str, Any] | None = None,
) -> list[dict]:
    """Run a SELECT and return rows as list[dict].

    On any failure: log, return []. Never raise to the caller — tools should
    handle empty results gracefully and the LLM can apologise to the user.
    """
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


# ---- queries ------------------------------------------------------------

_BASE_COLS = "id, name, qty, sold_count, price, discount_percent, color"


def all_products(limit: int = 100) -> list[dict]:
    limit = clamp_int(limit, 1, 500, default=100)
    return _query(
        f"SELECT {_BASE_COLS} FROM products ORDER BY id LIMIT %s",
        (limit,),
    )


def low_stock(threshold: int = 5, limit: int = 100) -> list[dict]:
    threshold = clamp_int(threshold, 0, 10**6, default=5)
    limit = clamp_int(limit, 1, 500, default=100)
    return _query(
        f"SELECT {_BASE_COLS} FROM products WHERE qty < %s ORDER BY qty ASC LIMIT %s",
        (threshold, limit),
    )


def out_of_stock(limit: int = 100) -> list[dict]:
    limit = clamp_int(limit, 1, 500, default=100)
    return _query(
        f"SELECT {_BASE_COLS} FROM products WHERE qty = 0 ORDER BY id LIMIT %s",
        (limit,),
    )


def best_sellers(limit: int = 5) -> list[dict]:
    limit = clamp_int(limit, 1, 100, default=5)
    return _query(
        f"SELECT {_BASE_COLS} FROM products ORDER BY sold_count DESC LIMIT %s",
        (limit,),
    )


def bottom_sellers(limit: int = 5) -> list[dict]:
    limit = clamp_int(limit, 1, 100, default=5)
    return _query(
        f"SELECT {_BASE_COLS} FROM products ORDER BY sold_count ASC LIMIT %s",
        (limit,),
    )


def find_by_name(
    keyword: str,
    *,
    limit: int = 10,
    fuzzy_threshold: float = 0.25,
) -> list[dict]:
    """Exact ILIKE first; fall back to pg_trgm `%` operator for typos.

    The `%` operator triggers the GIN trigram index — much faster than
    `similarity() > X` which forces a sequential scan.
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return []
    limit = clamp_int(limit, 1, 50, default=10)

    rows = _query(
        f"SELECT {_BASE_COLS} FROM products WHERE name ILIKE %s ORDER BY id LIMIT %s",
        (f"%{keyword}%", limit),
    )
    if rows:
        return rows

    # Fuzzy fallback. set_limit() is per-session; SET LOCAL keeps it inside
    # the implicit transaction created by `with conn`.
    threshold = clamp_float(fuzzy_threshold, 0.05, 1.0, default=0.25)
    return _query(
        f"""
        SELECT {_BASE_COLS}, similarity(name, %s) AS _sim
        FROM products
        WHERE name %% %s
        ORDER BY _sim DESC
        LIMIT %s
        """,
        (keyword, keyword, limit),
        settings={"pg_trgm.similarity_threshold": str(threshold)},
    )


def total_qty() -> dict:
    rows = _query("SELECT COALESCE(SUM(qty), 0) AS total FROM products")
    return {"metric": "total_qty", "value": int(rows[0]["total"]) if rows else 0}


def total_sold() -> dict:
    rows = _query("SELECT COALESCE(SUM(sold_count), 0) AS total FROM products")
    return {"metric": "total_sold", "value": int(rows[0]["total"]) if rows else 0}


def total_stock_value() -> dict:
    """SUM(qty * effective_price) — inventory value after discounts applied."""
    rows = _query(
        "SELECT COALESCE(SUM(qty * price * (1 - discount_percent/100)), 0)::float AS total "
        "FROM products"
    )
    return {"metric": "total_stock_value", "value": float(rows[0]["total"]) if rows else 0.0}


def discounted_products(min_discount: float = 0.01, limit: int = 50) -> list[dict]:
    """All products currently on promotion (discount_percent > min_discount)."""
    min_discount = clamp_float(min_discount, 0, 100, default=0.01)
    limit = clamp_int(limit, 1, 200, default=50)
    return _query(
        f"""
        SELECT {_BASE_COLS} FROM products
        WHERE discount_percent >= %s
        ORDER BY discount_percent DESC, price ASC
        LIMIT %s
        """,
        (min_discount, limit),
    )


def total_revenue() -> dict:
    """SUM(sold_count * price) — lifetime revenue (assumes price never changed)."""
    rows = _query("SELECT COALESCE(SUM(sold_count * price), 0)::float AS total FROM products")
    return {"metric": "total_revenue", "value": float(rows[0]["total"]) if rows else 0.0}


def by_price_range(min_price: float = 0, max_price: float = 1e12, limit: int = 50) -> list[dict]:
    min_price = clamp_float(min_price, 0, 1e12, default=0)
    max_price = clamp_float(max_price, 0, 1e12, default=1e12)
    limit = clamp_int(limit, 1, 200, default=50)
    return _query(
        f"""
        SELECT {_BASE_COLS} FROM products
        WHERE price BETWEEN %s AND %s
        ORDER BY price ASC
        LIMIT %s
        """,
        (min_price, max_price, limit),
    )


def by_color(color: str, limit: int = 50) -> list[dict]:
    color = (color or "").strip()
    if not color:
        return []
    limit = clamp_int(limit, 1, 200, default=50)
    return _query(
        f"SELECT {_BASE_COLS} FROM products WHERE color ILIKE %s ORDER BY id LIMIT %s",
        (color, limit),
    )


def most_expensive(limit: int = 5) -> list[dict]:
    limit = clamp_int(limit, 1, 50, default=5)
    return _query(
        f"SELECT {_BASE_COLS} FROM products ORDER BY price DESC LIMIT %s",
        (limit,),
    )


def cheapest(limit: int = 5) -> list[dict]:
    limit = clamp_int(limit, 1, 50, default=5)
    return _query(
        f"SELECT {_BASE_COLS} FROM products ORDER BY price ASC LIMIT %s",
        (limit,),
    )
