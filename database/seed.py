"""Deterministic seed script for stock-project schema v2.

Generates ~50k rows of realistic-looking data:
  -    20 categories
  -    30 brands
  -    50 suppliers
  -     8 warehouses
  -   500 products (with all fields)
  - 2,000 product_locations (avg 4 warehouses per product)
  -   500 customers
  - 2,000 orders (last 6 months)
  - 5,000 order_items
  - 8,000 stock_movements

Usage:
    python seed.py

Connection: env DATABASE_URL or defaults to localhost cms_stock.
"""
from __future__ import annotations

import os
import random
from datetime import datetime, timedelta
from decimal import Decimal

import psycopg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgres://postgres:root@localhost:5432/cms_stock",
)
random.seed(42)  # deterministic

# -------------------------------------------------------------------------

CATEGORIES = [
    ("Smartphone", "smartphone"),
    ("Laptop", "laptop"),
    ("Tablet", "tablet"),
    ("Smartwatch", "smartwatch"),
    ("Earbuds", "earbuds"),
    ("Headphone", "headphone"),
    ("Speaker", "speaker"),
    ("Camera", "camera"),
    ("Monitor", "monitor"),
    ("Keyboard", "keyboard"),
    ("Mouse", "mouse"),
    ("Charger", "charger"),
    ("Cable", "cable"),
    ("Storage", "storage"),
    ("Gaming Console", "gaming-console"),
    ("Smart TV", "smart-tv"),
    ("Printer", "printer"),
    ("Router", "router"),
    ("Webcam", "webcam"),
    ("Power Bank", "power-bank"),
]

BRANDS = [
    ("Apple", "USA"), ("Samsung", "South Korea"), ("Sony", "Japan"),
    ("Xiaomi", "China"), ("Huawei", "China"), ("Oppo", "China"),
    ("Vivo", "China"), ("Realme", "China"), ("OnePlus", "China"),
    ("Nothing", "UK"), ("Google", "USA"), ("Microsoft", "USA"),
    ("Asus", "Taiwan"), ("Acer", "Taiwan"), ("Dell", "USA"),
    ("HP", "USA"), ("Lenovo", "China"), ("MSI", "Taiwan"),
    ("Razer", "USA"), ("Logitech", "Switzerland"), ("Bose", "USA"),
    ("JBL", "USA"), ("Sennheiser", "Germany"), ("Anker", "China"),
    ("LG", "South Korea"), ("Nintendo", "Japan"), ("DJI", "China"),
    ("Canon", "Japan"), ("Nikon", "Japan"), ("TP-Link", "China"),
]

SUPPLIERS = [
    "Apple Thailand", "Samsung Thailand", "Sony Asia",
    "Synnex Distribution", "Power Buy", "Banana IT",
    "JIB", "Advice IT", "TG Fone", "Studio7",
    "iStudio Authorized", "Rainbow Tech", "IT Mall",
    "Pantip Plaza", "Jaymart", "TruePalm",
    "DotLife", "MOAH",
    "Lazada Wholesale", "Shopee Distributor",
    "Phaiyon Mart", "Big Camera",
    "Crystal Audio", "Sound Republic", "MAC Lab",
    "Nintendo Asia", "Razer Store", "DJI Authorized",
    "Anker Direct", "Logitech G Store",
    "PC Studio", "Notebook Spec", "GearMan",
    "Ergotrip", "OneSpec", "TechSphere",
    "Quantum Tech", "Octopus Trading", "GadgetHQ",
    "ChargeKing", "CableNetwork", "WattWise",
    "AudioVision", "GamerGear", "Mobile Plus",
    "TabletWorld", "DroneCenter", "PrintHub",
    "RouterPro", "WebcamMart", "HomeTech",
]

WAREHOUSES = [
    ("BKK-SLM", "กรุงเทพ - สีลม", "Bangkok"),
    ("BKK-BNA", "กรุงเทพ - บางนา", "Bangkok"),
    ("BKK-RIN", "กรุงเทพ - รามอินทรา", "Bangkok"),
    ("CNX-MUNG", "เชียงใหม่", "Chiang Mai"),
    ("HKT-001", "ภูเก็ต", "Phuket"),
    ("HDY-001", "หาดใหญ่", "Songkhla"),
    ("KKC-001", "ขอนแก่น", "Khon Kaen"),
    ("KOR-001", "นครราชสีมา", "Nakhon Ratchasima"),
]

# Map category → likely brands (more realistic distribution)
CATEGORY_BRANDS: dict[str, list[str]] = {
    "Smartphone": ["Apple", "Samsung", "Xiaomi", "Huawei", "Oppo", "Vivo", "Realme", "OnePlus", "Nothing", "Google"],
    "Laptop":     ["Apple", "Asus", "Acer", "Dell", "HP", "Lenovo", "MSI", "Razer", "Microsoft"],
    "Tablet":     ["Apple", "Samsung", "Microsoft", "Lenovo", "Xiaomi", "Huawei"],
    "Smartwatch": ["Apple", "Samsung", "Xiaomi", "Huawei"],
    "Earbuds":    ["Apple", "Samsung", "Sony", "Bose", "JBL", "Sennheiser", "Anker", "Nothing"],
    "Headphone":  ["Sony", "Bose", "Sennheiser", "JBL", "Apple", "Razer", "Logitech"],
    "Speaker":    ["Bose", "JBL", "Sony", "Anker", "LG"],
    "Camera":     ["Sony", "Canon", "Nikon", "DJI"],
    "Monitor":    ["Samsung", "LG", "Asus", "Dell", "MSI", "Acer"],
    "Keyboard":   ["Logitech", "Razer", "Apple", "MSI", "Asus"],
    "Mouse":      ["Logitech", "Razer", "Apple", "Microsoft"],
    "Charger":    ["Anker", "Apple", "Samsung", "Xiaomi"],
    "Cable":      ["Anker", "Apple", "Samsung"],
    "Storage":    ["Samsung", "Sony", "Anker"],
    "Gaming Console": ["Nintendo", "Sony", "Microsoft"],
    "Smart TV":   ["Samsung", "LG", "Sony", "Xiaomi"],
    "Printer":    ["HP", "Canon"],
    "Router":     ["TP-Link", "Asus"],
    "Webcam":     ["Logitech", "Razer"],
    "Power Bank": ["Anker", "Xiaomi", "Samsung"],
}

# Common product name patterns per category
NAME_TEMPLATES: dict[str, list[str]] = {
    "Smartphone":   ["{brand} Phone {n} Pro", "{brand} {n} Ultra", "{brand} Note {n}", "{brand} Galaxy S{n}"],
    "Laptop":       ["{brand} Book Pro {n}\"", "{brand} Air M{n}", "{brand} ZenBook {n}", "{brand} ThinkPad X{n}"],
    "Tablet":       ["{brand} Pad {n}", "{brand} Tab S{n}", "{brand} MatePad {n}"],
    "Smartwatch":   ["{brand} Watch Series {n}", "{brand} Watch Ultra {n}", "{brand} Buds Watch {n}"],
    "Earbuds":      ["{brand} Buds Pro {n}", "{brand} Free Buds {n}", "{brand} AirPods {n}"],
    "Headphone":    ["{brand} WH-{n}XM", "{brand} QuietComfort {n}", "{brand} Studio {n}"],
    "Speaker":      ["{brand} Sound {n}", "{brand} Flip {n}", "{brand} Charge {n}"],
    "Camera":       ["{brand} Alpha A{n}", "{brand} EOS R{n}", "{brand} Z{n}"],
    "Monitor":      ["{brand} Monitor {n}\"", "{brand} OLED {n}\"", "{brand} ROG {n}\""],
    "Keyboard":     ["{brand} MX Keys {n}", "{brand} Magic Keyboard {n}", "{brand} BlackWidow V{n}"],
    "Mouse":        ["{brand} MX Master {n}", "{brand} Magic Mouse {n}", "{brand} DeathAdder V{n}"],
    "Charger":      ["{brand} {n}W USB-C Charger", "{brand} GaN {n}W"],
    "Cable":        ["{brand} USB-C Cable {n}m", "{brand} Lightning {n}m"],
    "Storage":      ["{brand} SSD {n}TB", "{brand} MicroSD {n}GB"],
    "Gaming Console": ["{brand} Switch OLED v{n}", "{brand} PS{n}", "{brand} Xbox Series {n}"],
    "Smart TV":     ["{brand} OLED {n}\"", "{brand} QLED {n}\""],
    "Printer":      ["{brand} LaserJet {n}", "{brand} PIXMA {n}"],
    "Router":       ["{brand} AX{n}", "{brand} Mesh WiFi {n}"],
    "Webcam":       ["{brand} StreamCam {n}", "{brand} C{n}HD"],
    "Power Bank":   ["{brand} PowerCore {n}mAh", "{brand} Mi PowerBank {n}"],
}

COLORS = ["Black", "White", "Silver", "Space Gray", "Midnight", "Starlight",
          "Blue", "Pink", "Red", "Green", "Gold", "Graphite", "Natural Titanium",
          "Purple", "Yellow"]

PRICE_RANGES: dict[str, tuple[int, int]] = {
    "Smartphone":     (6_000, 60_000),
    "Laptop":         (15_000, 80_000),
    "Tablet":         (8_000, 45_000),
    "Smartwatch":     (4_000, 25_000),
    "Earbuds":        (1_500, 12_000),
    "Headphone":      (3_000, 25_000),
    "Speaker":        (1_500, 18_000),
    "Camera":         (15_000, 120_000),
    "Monitor":        (5_000, 50_000),
    "Keyboard":       (1_500, 9_000),
    "Mouse":          (700, 6_000),
    "Charger":        (300, 2_500),
    "Cable":          (200, 1_500),
    "Storage":        (500, 8_000),
    "Gaming Console": (8_000, 22_000),
    "Smart TV":       (12_000, 90_000),
    "Printer":        (3_000, 18_000),
    "Router":         (1_000, 9_000),
    "Webcam":         (1_500, 7_000),
    "Power Bank":     (500, 3_500),
}

WEIGHT_RANGES: dict[str, tuple[float, float]] = {
    "Smartphone": (0.15, 0.25), "Laptop": (1.0, 3.0), "Tablet": (0.4, 0.8),
    "Smartwatch": (0.03, 0.08), "Earbuds": (0.04, 0.08), "Headphone": (0.2, 0.4),
    "Speaker": (0.5, 4.0), "Camera": (0.5, 1.5), "Monitor": (3.0, 12.0),
    "Keyboard": (0.4, 1.5), "Mouse": (0.07, 0.2), "Charger": (0.1, 0.4),
    "Cable": (0.05, 0.2), "Storage": (0.02, 0.15), "Gaming Console": (1.0, 4.0),
    "Smart TV": (10.0, 40.0), "Printer": (3.0, 10.0), "Router": (0.4, 1.5),
    "Webcam": (0.1, 0.3), "Power Bank": (0.2, 0.6),
}

THAI_FIRST = ["สมชาย","สมหญิง","นภา","ภูมิ","ปาริชาติ","ธนวัฒน์","สุภาพร","วสันต์",
              "อรอุมา","ธีรพงษ์","ณัฐพล","พิมพ์ใจ","วิชัย","อนุชา","กฤติยา","พงศกร",
              "ชนิดา","ภานุพงศ์","สมศักดิ์","วรรณวิภา","ธนกร","กิตติชัย","ปวีณา","อนันต์"]
THAI_LAST  = ["ใจดี","ทองดี","สุขใจ","พิมพ์ทอง","กล้าหาญ","แสนสุข","งามสง่า","พงษ์ภัทร",
              "ภัทรกุล","ศรีสุข","วิเศษ","ภูริภัทร","อาชาไนย","ตันติ","วิจิตร","พิทักษ์",
              "ลาภเจริญ","สุขสวัสดิ์","วงษ์วิวัฒน์","ธนเดช"]
THAI_CITIES = ["กรุงเทพ","นนทบุรี","เชียงใหม่","ภูเก็ต","ขอนแก่น","นครราชสีมา","อุดรธานี","พิษณุโลก","ชลบุรี","สงขลา"]

TAGS_POOL = ["flagship","budget","gaming","wireless","portable","5g","oled",
             "noise-cancel","water-resistant","fast-charge","compact","premium",
             "entry-level","creator","professional","2024","2025"]


# -------------------------------------------------------------------------

def random_phone() -> str:
    return f"08{random.randint(0, 9)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}"


def random_email(name: str, idx: int) -> str:
    base = "".join(c for c in name if c.isascii() and c.isalpha()).lower() or f"user{idx}"
    return f"{base}{idx}@example.com"


def main() -> None:
    print(f"Connecting: {DATABASE_URL}")
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        # ---- categories ----
        print("Seeding categories...")
        for name, slug in CATEGORIES:
            cur.execute("INSERT INTO categories (name, slug) VALUES (%s, %s)", (name, slug))
        cur.execute("SELECT id, name FROM categories")
        categories = {n: i for i, n in cur.fetchall()}

        # ---- brands ----
        print("Seeding brands...")
        for name, country in BRANDS:
            cur.execute("INSERT INTO brands (name, country) VALUES (%s, %s)", (name, country))
        cur.execute("SELECT id, name FROM brands")
        brands = {n: i for i, n in cur.fetchall()}

        # ---- suppliers ----
        print("Seeding suppliers...")
        for s in SUPPLIERS[:50]:
            cur.execute(
                "INSERT INTO suppliers (name, contact, lead_time_days, country) "
                "VALUES (%s, %s, %s, %s)",
                (s, f"contact@{s.lower().replace(' ', '')}.co.th",
                 random.choice([3, 5, 7, 10, 14, 21, 30]), "Thailand"),
            )
        cur.execute("SELECT id FROM suppliers")
        supplier_ids = [r[0] for r in cur.fetchall()]

        # ---- warehouses ----
        print("Seeding warehouses...")
        for code, name, city in WAREHOUSES:
            cur.execute(
                "INSERT INTO warehouses (code, name, city, capacity) "
                "VALUES (%s, %s, %s, %s)",
                (code, name, city, random.randint(5_000, 30_000)),
            )
        cur.execute("SELECT id FROM warehouses")
        warehouse_ids = [r[0] for r in cur.fetchall()]

        # ---- products ----
        print("Seeding 500 products...")
        product_ids: list[tuple[int, int, float]] = []  # (id, qty_total, price)
        sku_seen: set[str] = set()
        for i in range(500):
            cat_name, _ = random.choice(CATEGORIES)
            brand_name = random.choice(CATEGORY_BRANDS.get(cat_name, [b for b, _ in BRANDS]))
            template = random.choice(NAME_TEMPLATES.get(cat_name, ["{brand} Item {n}"]))
            n_part = random.choice([
                str(random.randint(1, 30)),
                f"{random.choice(['Pro','Ultra','Plus','Max','Lite'])}",
                f"{random.randint(2020, 2025)}",
            ])
            name = template.format(brand=brand_name, n=n_part)

            # SKU unique
            sku_base = f"{brand_name[:3].upper()}-{cat_name[:3].upper()}-{i:04d}"
            sku = sku_base
            while sku in sku_seen:
                sku = f"{sku_base}-{random.randint(10, 99)}"
            sku_seen.add(sku)

            lo, hi = PRICE_RANGES[cat_name]
            price = round(random.uniform(lo, hi), -1)  # round to 10
            wlo, whi = WEIGHT_RANGES[cat_name]
            weight = round(random.uniform(wlo, whi), 3)

            discount = random.choices(
                [0, 5, 10, 15, 20, 25, 30],
                weights=[60, 10, 10, 8, 6, 4, 2],
            )[0]
            rating = round(random.gauss(4.2, 0.4), 1)
            rating = min(5.0, max(2.5, rating))
            review_count = max(0, int(random.gauss(80, 60)))
            color = random.choice(COLORS)
            tags = random.sample(TAGS_POOL, k=random.randint(1, 4))
            qty_total = random.choices([0, 5, 25, 60, 150], weights=[8, 22, 35, 25, 10])[0]
            sold = max(0, int(random.gauss(50, 70)))
            desc = (
                f"{name} - premium {cat_name.lower()} from {brand_name}. "
                f"Comes in {color}. Tags: {', '.join(tags)}."
            )

            cur.execute(
                """
                INSERT INTO products
                  (sku, name, description, brand_id, category_id, supplier_id,
                   qty, sold_count, price, discount_percent, color, weight_kg,
                   rating, review_count, tags, is_active, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                        NOW() - (random()*INTERVAL '180 days'))
                RETURNING id
                """,
                (sku, name, desc, brands[brand_name], categories[cat_name],
                 random.choice(supplier_ids),
                 qty_total, sold, price, discount, color, weight,
                 rating, review_count, tags, random.random() > 0.05),
            )
            pid = cur.fetchone()[0]
            product_ids.append((pid, qty_total, float(price)))

        # ---- product_locations ----
        print("Seeding product_locations...")
        for pid, qty_total, _ in product_ids:
            if qty_total == 0:
                # zero-stock: still create rows with 0
                for wid in random.sample(warehouse_ids, k=random.randint(1, 3)):
                    cur.execute(
                        "INSERT INTO product_locations (product_id, warehouse_id, qty) "
                        "VALUES (%s, %s, 0)",
                        (pid, wid),
                    )
                continue
            # Distribute qty_total across N warehouses
            n_wh = random.randint(2, 5)
            chosen = random.sample(warehouse_ids, k=min(n_wh, len(warehouse_ids)))
            cuts = sorted(random.sample(range(1, qty_total), k=len(chosen) - 1)) if qty_total > len(chosen) else None
            if cuts is None:
                # too small to split; first warehouse gets it all
                cur.execute(
                    "INSERT INTO product_locations (product_id, warehouse_id, qty) "
                    "VALUES (%s, %s, %s)",
                    (pid, chosen[0], qty_total),
                )
                for wid in chosen[1:]:
                    cur.execute(
                        "INSERT INTO product_locations (product_id, warehouse_id, qty) "
                        "VALUES (%s, %s, 0)",
                        (pid, wid),
                    )
                continue
            parts = [cuts[0]] + [cuts[i] - cuts[i - 1] for i in range(1, len(cuts))] + [qty_total - cuts[-1]]
            for wid, q in zip(chosen, parts):
                cur.execute(
                    "INSERT INTO product_locations (product_id, warehouse_id, qty) "
                    "VALUES (%s, %s, %s)",
                    (pid, wid, q),
                )

        # ---- customers ----
        print("Seeding 500 customers...")
        customer_ids: list[int] = []
        for i in range(500):
            full_name = f"{random.choice(THAI_FIRST)} {random.choice(THAI_LAST)}"
            cur.execute(
                "INSERT INTO customers (name, email, phone, city, joined_at) "
                "VALUES (%s, %s, %s, %s, NOW() - (random()*INTERVAL '730 days')) RETURNING id",
                (full_name, random_email(full_name, i), random_phone(), random.choice(THAI_CITIES)),
            )
            customer_ids.append(cur.fetchone()[0])

        # ---- orders + order_items ----
        print("Seeding 2000 orders + ~5000 items...")
        for _ in range(2_000):
            cust = random.choice(customer_ids)
            ordered_at = datetime.now() - timedelta(
                days=random.randint(0, 180),
                hours=random.randint(0, 23),
            )
            status = random.choices(
                ["pending", "paid", "shipped", "delivered", "cancelled"],
                weights=[5, 15, 15, 60, 5],
            )[0]
            shipped_at = None
            if status in {"shipped", "delivered"}:
                shipped_at = ordered_at + timedelta(days=random.randint(1, 5))

            n_items = random.choices([1, 2, 3, 4, 5], weights=[55, 25, 12, 6, 2])[0]
            chosen = random.sample(product_ids, k=n_items)
            items: list[tuple[int, int, float, float, float]] = []
            total = 0.0
            for pid, _, price in chosen:
                q = random.choices([1, 2, 3], weights=[80, 15, 5])[0]
                disc = random.choices([0, 5, 10, 15], weights=[70, 15, 10, 5])[0]
                line = round(price * q * (1 - disc / 100), 2)
                items.append((pid, q, price, disc, line))
                total += line

            cur.execute(
                "INSERT INTO orders (customer_id, status, total_amount, ordered_at, shipped_at) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (cust, status, round(total, 2), ordered_at, shipped_at),
            )
            order_id = cur.fetchone()[0]
            for pid, q, p, d, lt in items:
                cur.execute(
                    "INSERT INTO order_items (order_id, product_id, qty, unit_price, "
                    "discount_percent, line_total) VALUES (%s, %s, %s, %s, %s, %s)",
                    (order_id, pid, q, p, d, lt),
                )

        # ---- stock_movements ----
        print("Seeding ~8000 stock_movements...")
        types_w = [("restock", 0.30), ("sale", 0.50),
                   ("transfer_in", 0.07), ("transfer_out", 0.07), ("adjust", 0.06)]
        types, weights = zip(*types_w)
        for _ in range(8_000):
            pid, _, _ = random.choice(product_ids)
            wid = random.choice(warehouse_ids)
            t = random.choices(types, weights=weights)[0]
            if t in {"restock", "transfer_in"}:
                delta = random.randint(5, 50)
            elif t in {"sale", "transfer_out"}:
                delta = -random.randint(1, 5)
            else:
                delta = random.randint(-5, 5)
            cur.execute(
                "INSERT INTO stock_movements (product_id, warehouse_id, type, qty_delta, "
                "reason, created_at) VALUES (%s, %s, %s, %s, %s, NOW() - (random()*INTERVAL '180 days'))",
                (pid, wid, t, delta, f"{t} #{random.randint(1000, 9999)}"),
            )

        conn.commit()

    print("\nDone!")
    print("Run psql to verify:")
    print("  SELECT COUNT(*) FROM products;       -- 500")
    print("  SELECT COUNT(*) FROM orders;         -- 2000")
    print("  SELECT COUNT(*) FROM stock_movements;-- 8000")


if __name__ == "__main__":
    main()
