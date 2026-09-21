"""
Extracts listings from mubawab_listings.db and produces an optimized data.js
for the static frontend, ensuring instant loading locally and on GitHub Pages.
"""

import sqlite3
import json
import os

def build_data():
    conn = sqlite3.connect("mubawab_listings.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute("SELECT * FROM listings ORDER BY price_numeric ASC").fetchall()
    listings = [dict(r) for r in rows]

    total = len(listings)
    print(f"Loaded {total} listings from database.")

    # Calculate summary stats
    house_types = {}
    quartiers = {}
    total_price = 0
    price_count = 0

    for item in listings:
        ht = item.get("house_type") or "Autre"
        q = item.get("quartier") or "Autre / Centre"
        house_types[ht] = house_types.get(ht, 0) + 1
        quartiers[q] = quartiers.get(q, 0) + 1
        
        p = item.get("price_numeric")
        if p and p > 0:
            total_price += p
            price_count += 1

    avg_price = int(total_price / price_count) if price_count else 0

    stats = {
        "total": total,
        "avg_price": avg_price,
        "house_types": dict(sorted(house_types.items(), key=lambda x: x[1], reverse=True)),
        "quartiers": dict(sorted(quartiers.items(), key=lambda x: x[1], reverse=True)),
    }

    # Write data.js with window.MUBAWAB_DATA and window.MUBAWAB_STATS
    js_content = f"""// Auto-generated data file for Mubawab Explorer
window.MUBAWAB_STATS = {json.dumps(stats, ensure_ascii=False, indent=2)};
window.MUBAWAB_DATA = {json.dumps(listings, ensure_ascii=False)};
"""
    with open("data.js", "w", encoding="utf-8") as f:
        f.write(js_content)

    print(f"[+] Created data.js ({os.path.getsize('data.js') / (1024*1024):.2f} MB)")

if __name__ == "__main__":
    build_data()
