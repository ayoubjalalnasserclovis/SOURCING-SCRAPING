"""
Generates compact, high-performance data.js containing ALL 46,954 Marrakech properties.
Uses an array-of-arrays compression format so all 46,954 listings load instantly
in the browser without performance bottlenecks.
"""

import sqlite3
import json
import os

def build_data():
    conn = sqlite3.connect("sourcing_listings.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    total_db_count = cur.execute("SELECT COUNT(*) FROM sourcing_listings").fetchone()[0]
    avg_price_row = cur.execute("SELECT AVG(price_mad) FROM sourcing_listings WHERE price_mad > 0").fetchone()[0]
    avg_price = int(avg_price_row) if avg_price_row else 0

    platforms = ["Avito", "Mubawab", "Kensington Luxury", "Sarouty / Selektimmo", "Bosworth Property"]
    plat_map = {p: i for i, p in enumerate(platforms)}

    trans = ["Vente", "Location"]
    trans_map = {t: i for i, t in enumerate(trans)}

    types = ["Appartement", "Villa", "Terrain", "Riad", "Maison", "Commerce", "Studio", "Bureau", "Duplex", "Autre"]
    type_map = {t: i for i, t in enumerate(types)}

    # Aggregates for KPIs
    plat_counts = {}
    for r in cur.execute("SELECT platform, COUNT(*) as cnt FROM sourcing_listings GROUP BY platform ORDER BY cnt DESC"):
        plat_counts[r["platform"]] = r["cnt"]

    type_counts = {}
    for r in cur.execute("SELECT house_type, COUNT(*) as cnt FROM sourcing_listings GROUP BY house_type ORDER BY cnt DESC"):
        type_counts[r["house_type"] or "Autre"] = r["cnt"]

    quartier_counts = {}
    for r in cur.execute("SELECT quartier, COUNT(*) as cnt FROM sourcing_listings GROUP BY quartier ORDER BY cnt DESC LIMIT 50"):
        quartier_counts[r["quartier"] or "Autre"] = r["cnt"]

    stats = {
        "total": total_db_count,
        "avg_price": avg_price,
        "platforms": plat_counts,
        "house_types": type_counts,
        "quartiers": quartier_counts,
    }

    # Fetch all 46,954 rows
    query = """
        SELECT id, platform, title, url, transaction_type, house_type, quartier, 
               price_raw, price_mad, surface_m2, bedrooms, bathrooms, main_image
        FROM sourcing_listings 
        ORDER BY price_mad ASC
    """
    rows = cur.execute(query).fetchall()

    compact_records = []
    for r in rows:
        p_idx = plat_map.get(r["platform"], 0)
        t_idx = trans_map.get(r["transaction_type"], 0)
        h_idx = type_map.get(r["house_type"], 9)

        compact_records.append([
            r["id"],
            p_idx,
            r["title"] or "",
            r["url"] or "",
            t_idx,
            h_idx,
            r["quartier"] or "",
            r["price_raw"] or "",
            r["price_mad"] or 0,
            r["surface_m2"] or 0,
            r["bedrooms"] or 0,
            r["bathrooms"] or 0,
            r["main_image"] or ""
        ])

    payload = {
        "stats": stats,
        "platforms": platforms,
        "transactions": trans,
        "house_types": types,
        "records": compact_records
    }

    print(f"Packed all {len(compact_records):,} listings into compact structure.")

    js_content = f"""// Auto-generated full dataset for Marrakech Multi-Platform Sourcing Explorer
window.MUBAWAB_STATS = {json.dumps(stats, ensure_ascii=False, indent=2)};
window.MUBAWAB_COMPACT_DATA = {json.dumps(payload, ensure_ascii=False)};
"""
    with open("data.js", "w", encoding="utf-8") as f:
        f.write(js_content)

    size_mb = os.path.getsize("data.js") / (1024 * 1024)
    print(f"[+] Successfully wrote data.js ({size_mb:.2f} MB) containing all {len(compact_records):,} listings!")

if __name__ == "__main__":
    build_data()
