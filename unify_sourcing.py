"""
Master Aggregator & Normalizer for Marrakech Real Estate Sourcing.
Combines all 5 platforms into a unified schema, saves to SQLite database,
and generates master CSV/JSON exports with platform breakdown statistics.
"""

import sys
import io
import json
import csv
import re
import os
import sqlite3
from typing import List, Dict, Any, Optional

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DB_PATH = "sourcing_listings.db"

def init_sourcing_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Initialize master SQLite database for all sourcing platforms."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sourcing_listings (
            id TEXT PRIMARY KEY,
            platform TEXT,
            title TEXT,
            url TEXT,
            transaction_type TEXT,
            house_type TEXT,
            city TEXT,
            quartier TEXT,
            price_raw TEXT,
            price_mad INTEGER,
            surface_m2 INTEGER,
            bedrooms TEXT,
            bathrooms TEXT,
            features TEXT,
            description TEXT,
            main_image TEXT,
            images_count INTEGER,
            seller_type TEXT,
            scraped_at TEXT
        )
    """)
    # Indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_src_platform ON sourcing_listings(platform)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_src_house_type ON sourcing_listings(house_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_src_quartier ON sourcing_listings(quartier)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_src_price ON sourcing_listings(price_mad)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_src_trans ON sourcing_listings(transaction_type)")
    conn.commit()
    return conn

def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = re.sub(r"[\s\u00a0\u202f]+", " ", str(text))
    return text.strip()

def normalize_quartier(q: Optional[str]) -> str:
    if not q:
        return "Autre / Centre"
    q_clean = clean_text(q)
    ql = q_clean.lower()
    if any(k in ql for k in ["gueliz", "guéliz"]): return "Guéliz"
    if any(k in ql for k in ["medina", "médina", "kasbah", "mouassine", "mellah", "riad laarous"]): return "Médina"
    if any(k in ql for k in ["palmeraie", "annakhil"]): return "Palmeraie"
    if "hivernage" in ql: return "Hivernage"
    if "majorelle" in ql: return "Majorelle"
    if any(k in ql for k in ["targa"]): return "Targa"
    if any(k in ql for k in ["mhamid", "m'hamid"]): return "M'hamid"
    if any(k in ql for k in ["agdal"]): return "Agdal"
    if any(k in ql for k in ["semlalia", "samlalia"]): return "Semlalia"
    if "amelkis" in ql: return "Amelkis"
    if "prestigia" in ql: return "Prestigia"
    if "izdihar" in ql: return "Izdihar"
    if "ourika" in ql: return "Route de l'Ourika"
    if "casablanca" in ql: return "Route de Casablanca"
    if "tahanaout" in ql: return "Route de Tahanaout"
    if "fès" in ql or "fes" in ql: return "Route de Fès"
    if "chrifia" in ql: return "Chrifia"
    return q_clean

def normalize_house_type(t: Optional[str], title: str = "", desc: str = "") -> str:
    text = f"{t or ''} {title} {desc}".lower()
    if re.search(r'\b(riad|riads)\b', text): return 'Riad'
    if re.search(r'\b(villa|villas|palais|domaine)\b', text): return 'Villa'
    if re.search(r'\b(duplex)\b', text): return 'Duplex'
    if re.search(r'\b(studio|studios)\b', text): return 'Studio'
    if re.search(r'\b(penthouse|penthouses)\b', text): return 'Penthouse'
    if re.search(r'\b(appartement|appartements|appart)\b', text): return 'Appartement'
    if re.search(r'\b(terrain|terrains|lot)\b', text): return 'Terrain'
    if re.search(r'\b(maison|maisons|douiria)\b', text): return 'Maison'
    if re.search(r'\b(commerce|magasin|local commercial)\b', text): return 'Commerce'
    if re.search(r'\b(bureau|bureaux)\b', text): return 'Bureau'
    return 'Autre'

def ingest_mubawab(conn: sqlite3.Connection):
    """Ingest existing Mubawab listings from mubawab_listings.db."""
    src_db = "mubawab_listings.db"
    if not os.path.exists(src_db):
        return 0
    s_conn = sqlite3.connect(src_db)
    s_conn.row_factory = sqlite3.Row
    rows = s_conn.cursor().execute("SELECT * FROM listings").fetchall()
    
    items = []
    for r in rows:
        item = {
            "id": f"mubawab_{r['id']}",
            "platform": "Mubawab",
            "title": r['title'],
            "url": r['url'],
            "transaction_type": r['transaction_type'] or "Vente",
            "house_type": normalize_house_type(r['house_type'], r['title']),
            "city": "Marrakech",
            "quartier": normalize_quartier(r['quartier']),
            "price_raw": r['price_raw'],
            "price_mad": r['price_numeric'],
            "surface_m2": r['surface_m2'],
            "bedrooms": r['bedrooms'],
            "bathrooms": r['bathrooms'],
            "features": r['features'],
            "description": r['description'],
            "main_image": r['main_image'],
            "images_count": r['images_count'],
            "seller_type": "Professionnel / Agence",
            "scraped_at": r['scraped_date'] or "2026-09-21"
        }
        items.append(item)
    s_conn.close()
    
    insert_items(conn, items)
    return len(items)

def ingest_json_file(conn: sqlite3.Connection, filepath: str, platform_name: str, default_seller: str = "Professionnel") -> int:
    """Ingest JSON file produced by platform scrapers."""
    if not os.path.exists(filepath):
        return 0
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[!] Error reading {filepath}: {e}")
        return 0

    items = []
    for r in data:
        orig_id = str(r.get("id") or hash(r.get("url") or ""))
        item = {
            "id": f"{platform_name.lower()}_{orig_id}",
            "platform": platform_name,
            "title": clean_text(r.get("title")),
            "url": r.get("url", ""),
            "transaction_type": r.get("transaction_type") or "Vente",
            "house_type": normalize_house_type(r.get("house_type"), r.get("title", ""), r.get("description", "")),
            "city": "Marrakech",
            "quartier": normalize_quartier(r.get("quartier")),
            "price_raw": clean_text(r.get("price_raw") or str(r.get("price") or "")),
            "price_mad": r.get("price_mad") or r.get("price_numeric"),
            "surface_m2": r.get("surface_m2"),
            "bedrooms": clean_text(r.get("bedrooms")),
            "bathrooms": clean_text(r.get("bathrooms")),
            "features": clean_text(r.get("features") if isinstance(r.get("features"), str) else ", ".join(r.get("features") or [])),
            "description": clean_text(r.get("description")),
            "main_image": r.get("main_image", ""),
            "images_count": r.get("images_count") or 0,
            "seller_type": r.get("seller_type") or default_seller,
            "scraped_at": r.get("scraped_at") or "2026-09-30"
        }
        items.append(item)

    insert_items(conn, items)
    return len(items)

def insert_items(conn: sqlite3.Connection, items: List[Dict[str, Any]]):
    """Batch insert into SQLite."""
    cur = conn.cursor()
    cur.executemany("""
        INSERT OR REPLACE INTO sourcing_listings (
            id, platform, title, url, transaction_type, house_type, city, quartier,
            price_raw, price_mad, surface_m2, bedrooms, bathrooms, features,
            description, main_image, images_count, seller_type, scraped_at
        ) VALUES (
            :id, :platform, :title, :url, :transaction_type, :house_type, :city, :quartier,
            :price_raw, :price_mad, :surface_m2, :bedrooms, :bathrooms, :features,
            :description, :main_image, :images_count, :seller_type, :scraped_at
        )
    """, items)
    conn.commit()

def export_unified(conn: sqlite3.Connection):
    """Export master datasets in JSON and CSV."""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = [dict(r) for r in cur.execute("SELECT * FROM sourcing_listings ORDER BY platform, price_mad ASC").fetchall()]
    total = len(rows)
    print(f"\n[+] Total Unified Records across all platforms: {total:,}")

    # Master JSON
    with open("sourcing_all_listings.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)
    print(f"[✓] Exported: sourcing_all_listings.json ({len(rows):,} records)")

    # Master CSV
    if rows:
        fieldnames = list(rows[0].keys())
        with open("sourcing_all_listings.csv", "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[✓] Exported: sourcing_all_listings.csv ({len(rows):,} records)")

    # Print summary breakdown by platform
    print("\n" + "=" * 70)
    print(f"{'Platform':<22} | {'Listings':<10} | {'Avg Price (DH)':<18} | {'Top House Type'}")
    print("-" * 70)
    p_stats = cur.execute("""
        SELECT platform, COUNT(*) as cnt, AVG(price_mad) as avg_p
        FROM sourcing_listings
        GROUP BY platform
        ORDER BY cnt DESC
    """).fetchall()
    for p in p_stats:
        avg_str = f"{int(p['avg_p']):,} DH" if p['avg_p'] else "N/A"
        print(f"{p['platform']:<22} | {p['cnt']:<10} | {avg_str:<18}")
    print("=" * 70)

def main():
    conn = init_sourcing_db()
    
    # Ingest Mubawab
    m_count = ingest_mubawab(conn)
    print(f"[+] Ingested from Mubawab: {m_count:,} records")

    # Ingest Avito
    a_count = ingest_json_file(conn, "avito_marrakech.json", "Avito", default_seller="Particulier / Pro")
    print(f"[+] Ingested from Avito: {a_count:,} records")

    # Ingest Kensington
    k_count = ingest_json_file(conn, "kensington_marrakech.json", "Kensington Luxury", default_seller="Professionnel (Kensington)")
    print(f"[+] Ingested from Kensington: {k_count:,} records")

    # Ingest Bosworth
    b_count = ingest_json_file(conn, "bosworth_marrakech.json", "Bosworth Property", default_seller="Professionnel (Bosworth)")
    print(f"[+] Ingested from Bosworth Property: {b_count:,} records")

    # Ingest Sarouty / Selektimmo
    s_count = ingest_json_file(conn, "sarouty_marrakech.json", "Sarouty / Selektimmo", default_seller="Professionnel")
    print(f"[+] Ingested from Sarouty / Agency: {s_count:,} records")

    export_unified(conn)
    conn.close()

if __name__ == "__main__":
    main()
