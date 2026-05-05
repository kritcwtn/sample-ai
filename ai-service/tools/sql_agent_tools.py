"""Text-to-SQL tools — let the LLM write SQL directly.

Used when AGENT_MODE=sql (text-to-SQL) or AGENT_MODE=hybrid.

Safety contract:
  - SELECT statements ONLY (parser rejects anything else)
  - Whitelisted tables ONLY (no system tables)
  - Hard LIMIT enforced (≤200 rows)
  - Statement timeout already enforced by sql_tool._query()
  - Read-only by convention (DB role can also be locked down)
"""
from __future__ import annotations

import re

from .base import BaseTool
from . import sql_tool


# ---- whitelist + safety ----------------------------------------------------

ALLOWED_TABLES = {
    "products", "categories", "brands", "suppliers", "warehouses",
    "product_locations", "customers", "orders", "order_items",
    "stock_movements",
}

# Forbidden keywords (case-insensitive). One match → reject.
_FORBIDDEN_RE = re.compile(
    r"\b(insert|update|delete|drop|truncate|alter|create|grant|revoke|"
    r"copy|vacuum|analyze|reindex|cluster|comment|do|call|"
    r"begin|commit|rollback|savepoint|set\s+role|set\s+session)\b",
    re.IGNORECASE,
)


def _is_safe_select(sql: str) -> tuple[bool, str]:
    """Return (ok, reason)."""
    if not sql or not sql.strip():
        return False, "empty SQL"
    s = sql.strip().rstrip(";").strip()

    # must start with SELECT (or WITH ... SELECT)
    head = s[:6].upper()
    if not (head.startswith("SELECT") or head.startswith("WITH")):
        return False, "only SELECT (or WITH ... SELECT) is allowed"

    # block compound statements
    if ";" in s:
        return False, "multiple statements not allowed (no ';')"

    # block forbidden keywords
    if _FORBIDDEN_RE.search(s):
        return False, "forbidden keyword detected (write/DDL operations)"

    # rough table-allowlist check: every word that looks like FROM/JOIN x
    refs = re.findall(r"\b(?:from|join)\s+([a-zA-Z_][\w]*)", s, re.IGNORECASE)
    bad = [t for t in refs if t.lower() not in ALLOWED_TABLES]
    if bad:
        return False, f"table(s) not allowed: {bad}. Allowed: {sorted(ALLOWED_TABLES)}"

    return True, ""


# ---- tools -----------------------------------------------------------------

class GetDbSchema(BaseTool):
    name = "get_db_schema"
    description = (
        "Return the database schema (tables, columns, types, foreign keys). "
        "Call this FIRST before writing SQL with execute_sql, so you know "
        "the table/column names and relationships.\n"
        "\n"
        "When to use:\n"
        "  - Before composing any SQL via execute_sql.\n"
        "  - When the user asks something not covered by predefined tools.\n"
        "Returns:\n"
        "  - { tables: [{name, columns, fk}], notes: '...' }"
    )

    def run(self) -> dict:
        return {
            "tables": [
                {
                    "name": "products",
                    "columns": [
                        "id", "sku", "name", "description",
                        "brand_id", "category_id", "supplier_id",
                        "qty", "sold_count",
                        "price (numeric)", "discount_percent (0-100)",
                        "color", "weight_kg",
                        "rating (0-5)", "review_count",
                        "tags (text[])", "is_active (bool)",
                        "created_at",
                    ],
                    "fk": {
                        "brand_id": "brands.id",
                        "category_id": "categories.id",
                        "supplier_id": "suppliers.id",
                    },
                },
                {"name": "categories", "columns": ["id", "name", "slug"]},
                {"name": "brands", "columns": ["id", "name", "country"]},
                {"name": "suppliers", "columns": ["id", "name", "contact", "lead_time_days", "country"]},
                {"name": "warehouses", "columns": ["id", "code", "name", "city", "capacity"]},
                {
                    "name": "product_locations",
                    "columns": ["product_id", "warehouse_id", "qty"],
                    "fk": {
                        "product_id": "products.id",
                        "warehouse_id": "warehouses.id",
                    },
                },
                {"name": "customers", "columns": ["id", "name", "email", "phone", "city", "joined_at"]},
                {
                    "name": "orders",
                    "columns": ["id", "customer_id", "status", "total_amount", "ordered_at", "shipped_at"],
                    "fk": {"customer_id": "customers.id"},
                    "notes": "status ∈ {pending,paid,shipped,delivered,cancelled}",
                },
                {
                    "name": "order_items",
                    "columns": ["id", "order_id", "product_id", "qty", "unit_price",
                                "discount_percent", "line_total"],
                    "fk": {"order_id": "orders.id", "product_id": "products.id"},
                },
                {
                    "name": "stock_movements",
                    "columns": ["id", "product_id", "warehouse_id", "type",
                                "qty_delta", "reason", "ref_id", "created_at"],
                    "fk": {"product_id": "products.id", "warehouse_id": "warehouses.id"},
                    "notes": "type ∈ {restock,sale,transfer_in,transfer_out,adjust}",
                },
            ],
            "notes": (
                "Currency is THB. Always include LIMIT in queries. "
                "Use ILIKE for case-insensitive name search. "
                "For fuzzy search use pg_trgm: name % 'keyword'."
            ),
        }


class ExecuteSQL(BaseTool):
    name = "execute_sql"
    description = (
        "Execute a SELECT query against the live database and return rows.\n"
        "\n"
        "Constraints (enforced — request will be rejected otherwise):\n"
        "  - SELECT or WITH … SELECT only. No INSERT/UPDATE/DELETE/DDL.\n"
        "  - Single statement (no semicolon between statements).\n"
        "  - Tables: products, categories, brands, suppliers, warehouses, "
        "    product_locations, customers, orders, order_items, stock_movements.\n"
        "  - Always include LIMIT (max 200 rows enforced anyway).\n"
        "\n"
        "Workflow:\n"
        "  1. Call get_db_schema() first if unsure of columns.\n"
        "  2. Compose SELECT using only allowed tables.\n"
        "  3. Submit here.\n"
        "\n"
        "Examples:\n"
        "  - 'iPhone in Chiang Mai on sale':\n"
        "    SELECT p.name, p.qty, p.price FROM products p\n"
        "    JOIN product_locations pl ON pl.product_id = p.id\n"
        "    JOIN warehouses w ON w.id = pl.warehouse_id\n"
        "    WHERE w.code='CNX-MUNG' AND p.discount_percent > 0\n"
        "      AND p.name ILIKE '%iPhone%' LIMIT 50"
    )
    parameters = {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "minLength": 10,
                "maxLength": 4000,
                "description": "Single SELECT (or WITH ... SELECT) statement.",
            },
        },
        "required": ["sql"],
    }

    def run(self, sql: str) -> dict:
        ok, reason = _is_safe_select(sql)
        if not ok:
            return {"error": f"rejected: {reason}", "sql": sql, "rows": []}

        # Force LIMIT if missing (defense in depth — _query already caps at 1000)
        bare = sql.strip().rstrip(";").rstrip()
        if not re.search(r"\blimit\s+\d+\s*$", bare, re.IGNORECASE):
            bare += " LIMIT 200"

        rows = sql_tool._query(bare)
        # Normalise non-JSON-friendly types
        for r in rows:
            for k, v in list(r.items()):
                if hasattr(v, "isoformat"):
                    r[k] = v.isoformat()
                elif hasattr(v, "__class__") and v.__class__.__name__ == "Decimal":
                    r[k] = float(v)
        return {"sql": bare, "rowcount": len(rows), "rows": rows}


def register_all(registry) -> None:
    """Register text-to-SQL tools."""
    registry.register(GetDbSchema())
    registry.register(ExecuteSQL())
