"""
Interactive and CLI tool to filter, query, and export Mubawab listings.
Filters by House Type, Quartier, Transaction Type, Price, and Surface.
"""

import sys
import io
import argparse
import sqlite3
import json
import csv
from typing import List, Dict, Any

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def get_connection(db_path: str = "mubawab_listings.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def print_summary(db_path: str = "mubawab_listings.db"):
    """Print breakdown of listings by House Type and Quartier."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    total = cur.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    print("\n" + "=" * 75)
    print(f" TOTAL SCRAPED LISTINGS IN DATABASE: {total:,}")
    print("=" * 75)

    # Breakdown by House Type
    print("\n[+] BREAKDOWN BY HOUSE TYPE:")
    print(f"{'House Type':<20} | {'Count':<8} | {'% Total':<8} | {'Avg Price (DH)':<18} | {'Avg Surface':<12}")
    print("-" * 75)
    type_stats = cur.execute("""
        SELECT house_type, COUNT(*) as cnt,
               AVG(price_numeric) as avg_price,
               AVG(surface_m2) as avg_surf
        FROM listings
        GROUP BY house_type
        ORDER BY cnt DESC
    """).fetchall()

    for row in type_stats:
        avg_p = f"{int(row['avg_price']):,}" if row['avg_price'] else "N/A"
        avg_s = f"{int(row['avg_surf'])} m²" if row['avg_surf'] else "N/A"
        pct = f"{(row['cnt']/total*100):.1f}%" if total else "0%"
        print(f"{row['house_type']:<20} | {row['cnt']:<8} | {pct:<8} | {avg_p:<18} | {avg_s:<12}")

    # Breakdown by Quartier (Top 15)
    print("\n[+] BREAKDOWN BY TOP QUARTIERS:")
    print(f"{'Quartier / Zone':<26} | {'Count':<8} | {'% Total':<8} | {'Avg Price (DH)':<18}")
    print("-" * 75)
    quartier_stats = cur.execute("""
        SELECT quartier, COUNT(*) as cnt,
               AVG(price_numeric) as avg_price
        FROM listings
        GROUP BY quartier
        ORDER BY cnt DESC
        LIMIT 20
    """).fetchall()

    for row in quartier_stats:
        avg_p = f"{int(row['avg_price']):,}" if row['avg_price'] else "N/A"
        pct = f"{(row['cnt']/total*100):.1f}%" if total else "0%"
        print(f"{row['quartier']:<26} | {row['cnt']:<8} | {pct:<8} | {avg_p:<18}")

    print("=" * 75)
    conn.close()


def query_listings(
    db_path: str = "mubawab_listings.db",
    house_type: str = None,
    quartier: str = None,
    trans_type: str = None,
    min_price: int = None,
    max_price: int = None,
    min_surface: int = None,
    max_surface: int = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Query listings with flexible filters."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    conditions = []
    params = []

    if house_type and house_type.lower() != "all":
        conditions.append("house_type LIKE ?")
        params.append(f"%{house_type}%")

    if quartier and quartier.lower() != "all":
        conditions.append("quartier LIKE ?")
        params.append(f"%{quartier}%")

    if trans_type and trans_type.lower() != "all":
        conditions.append("transaction_type LIKE ?")
        params.append(f"%{trans_type}%")

    if min_price is not None:
        conditions.append("price_numeric >= ?")
        params.append(min_price)

    if max_price is not None:
        conditions.append("price_numeric <= ?")
        params.append(max_price)

    if min_surface is not None:
        conditions.append("surface_m2 >= ?")
        params.append(min_surface)

    if max_surface is not None:
        conditions.append("surface_m2 <= ?")
        params.append(max_surface)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"SELECT * FROM listings {where_clause} ORDER BY price_numeric ASC"
    if limit:
        sql += f" LIMIT {limit}"

    rows = cur.execute(sql, params).fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def export_data(results: List[Dict[str, Any]], export_csv: str = None, export_json: str = None):
    """Export queried results to CSV or JSON."""
    if export_csv:
        if not results:
            print("[!] No records to export to CSV.")
            return
        fieldnames = list(results[0].keys())
        with open(export_csv, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"[✓] Exported {len(results)} records to CSV: {export_csv}")

    if export_json:
        with open(export_json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"[✓] Exported {len(results)} records to JSON: {export_json}")


def main():
    parser = argparse.ArgumentParser(description="Filter and analyze Mubawab listings.")
    parser.add_argument("--summary", action="store_true", help="Display summary statistics by house type and quartier")
    parser.add_argument("--type", type=str, help="Filter by house type (e.g. Appartement, Villa, Riad, Studio, etc.)")
    parser.add_argument("--quartier", type=str, help="Filter by quartier (e.g. Guéliz, Palmeraie, Hivernage, Médina, etc.)")
    parser.add_argument("--trans", type=str, choices=["Vente", "Location", "all"], help="Filter by transaction type")
    parser.add_argument("--min-price", type=int, help="Minimum price in DH")
    parser.add_argument("--max-price", type=int, help="Maximum price in DH")
    parser.add_argument("--min-surface", type=int, help="Minimum surface in m²")
    parser.add_argument("--max-surface", type=int, help="Maximum surface in m²")
    parser.add_argument("--limit", type=int, default=20, help="Max results to display (default 20, 0 for all)")
    parser.add_argument("--export-csv", type=str, help="Path to save filtered results as CSV")
    parser.add_argument("--export-json", type=str, help="Path to save filtered results as JSON")
    parser.add_argument("--db", type=str, default="mubawab_listings.db", help="Path to SQLite database")

    args = parser.parse_args()

    if args.summary or (len(sys.argv) == 1):
        print_summary(args.db)
        if len(sys.argv) == 1:
            print("\nTip: Run with filters, e.g.:")
            print("  python filter_listings.py --type Villa --quartier Palmeraie")
            print("  python filter_listings.py --type Appartement --quartier Guéliz --max-price 1000000 --export-csv gueliz_apparts.csv")
        return

    limit_val = args.limit if args.limit > 0 else None
    results = query_listings(
        db_path=args.db,
        house_type=args.type,
        quartier=args.quartier,
        trans_type=args.trans,
        min_price=args.min_price,
        max_price=args.max_price,
        min_surface=args.min_surface,
        max_surface=args.max_surface,
        limit=limit_val,
    )

    filters_applied = []
    if args.type: filters_applied.append(f"Type='{args.type}'")
    if args.quartier: filters_applied.append(f"Quartier='{args.quartier}'")
    if args.trans: filters_applied.append(f"Trans='{args.trans}'")
    if args.min_price: filters_applied.append(f"Price>={args.min_price:,} DH")
    if args.max_price: filters_applied.append(f"Price<={args.max_price:,} DH")

    print("\n" + "=" * 75)
    print(f" MATCHED LISTINGS: {len(results)} found (Filters: {', '.join(filters_applied) or 'None'})")
    print("=" * 75)

    for i, r in enumerate(results[:25], 1):
        print(f"#{i:<2} [{r['house_type']}] {r['title'][:48]:<48} | {r['price_raw']:<14} | {r['quartier']:<16} | {r['surface_raw']}")
        print(f"     URL: {r['url']}")

    if len(results) > 25:
        print(f"\n... and {len(results) - 25} more listings.")

    if args.export_csv or args.export_json:
        export_data(results, export_csv=args.export_csv, export_json=args.export_json)


if __name__ == "__main__":
    main()
