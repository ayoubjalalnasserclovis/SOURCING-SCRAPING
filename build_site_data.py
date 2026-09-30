"""
Generates data.js from sourcing_listings.db for the unified multi-platform web explorer.
Optimized for ultra-fast browser loading across all 46,954 properties.
"""

import sqlite3
import json
import os

def build_data():
    conn = sqlite3.connect("sourcing_listings.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Select all essential display fields for 46,954 properties
    query = """
        SELECT 
            id, platform, title, url, transaction_type, house_type, 
            quartier, price_raw, price_mad, surface_m2, bedrooms, 
            bathrooms, main_image, substr(description, 1, 120) as description
        FROM sourcing_listings 
        ORDER BY price_mad ASC
    """
    rows = cur.execute(query).fetchall()
    listings = [dict(r) for r in rows]

    total = len(listings)
    print(f"Loaded {total} unified listings from sourcing_listings.db.")

    platforms = {}
    house_types = {}
    quartiers = {}
    total_price = 0
    price_count = 0

    for item in listings:
        plat = item.get("platform") or "Autre"
        ht = item.get("house_type") or "Autre"
        q = item.get("quartier") or "Autre / Centre"
        
        platforms[plat] = platforms.get(plat, 0) + 1
        house_types[ht] = house_types.get(ht, 0) + 1
        quartiers[q] = quartiers.get(q, 0) + 1
        
        p = item.get("price_mad")
        if p and p > 0:
            total_price += p
            price_count += 1

    avg_price = int(total_price / price_count) if price_count else 0

    stats = {
        "total": total,
        "avg_price": avg_price,
        "platforms": dict(sorted(platforms.items(), key=lambda x: x[1], reverse=True)),
        "house_types": dict(sorted(house_types.items(), key=lambda x: x[1], reverse=True)),
        "quartiers": dict(sorted(quartiers.items(), key=lambda x: x[1], reverse=True)),
    }

    js_content = f"""// Auto-generated data file for Marrakech Multi-Platform Sourcing Explorer
window.MUBAWAB_STATS = {json.dumps(stats, ensure_ascii=False, indent=2)};
window.MUBAWAB_DATA = {json.dumps(listings, ensure_ascii=False)};
"""
    with open("data.js", "w", encoding="utf-8") as f:
        f.write(js_content)

    print(f"[+] Created unified data.js ({os.path.getsize('data.js') / (1024*1024):.2f} MB)")

if __name__ == "__main__":
    build_data()
