"""
Master Concurrent Scraper for Mubawab.
Scrapes all available listings with House Type & Quartier categorization,
persists to SQLite database with UPSERT, and exports filtered datasets.
"""

import sys
import io
import time
import json
import csv
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from curl_cffi import requests
from mubawab_core import init_db, save_listings_to_db, parse_page_listings


def get_base_session() -> Tuple[requests.Session, dict]:
    """Get initialized session and cookies from Mubawab homepage."""
    session = requests.Session(impersonate="chrome120")
    session.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.mubawab.ma/",
    })
    print("[*] Contacting Mubawab homepage for security tokens & cookies...")
    r = session.get("https://www.mubawab.ma/", timeout=20)
    if r.status_code != 200:
        print(f"[!] Warning: Homepage returned HTTP {r.status_code}")
    cookies = dict(session.cookies)
    print(f"[+] Session established. Got {len(cookies)} cookies.")
    return session, cookies


def fetch_single_page(page_url: str, cookies: dict, trans_type: str, city: str, retries: int = 3) -> Tuple[str, List[Dict[str, Any]], int]:
    """Fetch and parse a single listing page with retry mechanism."""
    s = requests.Session(impersonate="chrome120")
    s.cookies.update(cookies)
    s.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.mubawab.ma/",
    })
    
    for attempt in range(1, retries + 1):
        try:
            r = s.get(page_url, timeout=25)
            if r.status_code == 200:
                items = parse_page_listings(r.content, transaction_type=trans_type, city=city)
                return page_url, items, r.status_code
            elif r.status_code == 404:
                return page_url, [], 404
        except Exception as e:
            if attempt == retries:
                return page_url, [], 0
            time.sleep(1.0 * attempt)
            
    return page_url, [], 0


def scrape_category(
    base_url: str,
    trans_type: str,
    city: str,
    cookies: dict,
    conn: sqlite3.Connection,
    max_pages: int = 100,
    max_workers: int = 6
) -> int:
    """Scrape all pages of a given category concurrently and save to DB in batches."""
    print(f"\n" + "=" * 70)
    print(f"[*] Starting scrape for [{city} - {trans_type}]: {base_url}")
    print(f"[*] Target pages: {max_pages} | Concurrency: {max_workers} threads")
    print("=" * 70)

    # First fetch page 1 to check total listings and ensure category exists
    _, p1_items, code = fetch_single_page(base_url, cookies, trans_type, city)
    if code != 200 or not p1_items:
        print(f"[!] Category check failed (HTTP {code}). Skipping.")
        return 0

    save_listings_to_db(conn, p1_items)
    total_scraped = len(p1_items)
    print(f"[+] Page 1: {len(p1_items)} listings saved. Starting concurrent batch...")

    # Build URLs for remaining pages
    page_urls = [f"{base_url}:p:{p}" for p in range(2, max_pages + 1)]
    consecutive_empty = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit batches of pages
        batch_size = 20
        for i in range(0, len(page_urls), batch_size):
            batch = page_urls[i : i + batch_size]
            futures = {
                executor.submit(fetch_single_page, url, cookies, trans_type, city): url
                for url in batch
            }
            batch_items = []
            for future in as_completed(futures):
                url = futures[future]
                try:
                    _, items, status = future.result()
                    if items:
                        batch_items.extend(items)
                        consecutive_empty = 0
                    else:
                        consecutive_empty += 1
                except Exception as e:
                    pass

            if batch_items:
                save_listings_to_db(conn, batch_items)
                total_scraped += len(batch_items)
                cur_count = conn.cursor().execute("SELECT COUNT(*) FROM listings").fetchone()[0]
                batch_range = f"{i+2}-{min(i+1+batch_size, max_pages)}"
                print(f"[+] Pages {batch_range:>7}: +{len(batch_items)} items | Total in DB: {cur_count:,}")

            if consecutive_empty >= 10:
                print(f"[*] Reached end of listings for this category.")
                break

            time.sleep(0.5)

    return total_scraped


def export_all(db_path: str = "mubawab_listings.db"):
    """Export complete dataset and filtered slices to CSV and JSON."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    total = cur.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    print(f"\n[*] Exporting {total:,} total listings...")

    # 1. Full JSON
    all_rows = [dict(r) for r in cur.execute("SELECT * FROM listings ORDER BY price_numeric ASC").fetchall()]
    with open("mubawab_complete_listings.json", "w", encoding="utf-8") as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=2)
    print(f"[✓] Exported: mubawab_complete_listings.json ({len(all_rows):,} records)")

    # 2. Full CSV
    fieldnames = list(all_rows[0].keys()) if all_rows else []
    with open("mubawab_complete_listings.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"[✓] Exported: mubawab_complete_listings.csv ({len(all_rows):,} records)")

    # 3. Filtered slices by House Type
    house_types = ["Appartement", "Villa", "Riad", "Studio", "Duplex", "Maison", "Terrain"]
    for ht in house_types:
        rows = [dict(r) for r in cur.execute("SELECT * FROM listings WHERE house_type = ? ORDER BY price_numeric ASC", (ht,)).fetchall()]
        if rows:
            filename = f"listings_{ht.lower()}s.csv"
            with open(filename, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"  -> Exported slice: {filename} ({len(rows):,} records)")

    # 4. Filtered slices by Quartier
    quartiers = ["Guéliz", "Palmeraie", "Hivernage", "Majorelle", "Médina", "Targa", "M'hamid", "Agdal"]
    for q in quartiers:
        rows = [dict(r) for r in cur.execute("SELECT * FROM listings WHERE quartier = ? ORDER BY price_numeric ASC", (q,)).fetchall()]
        if rows:
            clean_q = re.sub(r"[^a-zA-Z0-9]", "", q).lower()
            filename = f"listings_quartier_{clean_q}.csv"
            with open(filename, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"  -> Exported slice: {filename} ({len(rows):,} records)")

    conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Complete Mubawab Scraper")
    parser.add_argument("--max-pages", type=int, default=60, help="Maximum pages per category to scrape (default 60)")
    parser.add_argument("--workers", type=int, default=6, help="Concurrent worker threads (default 6)")
    args = parser.parse_args()

    t_start = time.time()
    conn = init_db("mubawab_listings.db")
    _, cookies = get_base_session()

    # Categories to scrape completely
    categories = [
        ("https://www.mubawab.ma/fr/ct/marrakech/immobilier-a-vendre", "Vente", "Marrakech"),
        ("https://www.mubawab.ma/fr/ct/marrakech/immobilier-a-louer", "Location", "Marrakech"),
    ]

    for base_url, trans_type, city in categories:
        scrape_category(
            base_url=base_url,
            trans_type=trans_type,
            city=city,
            cookies=cookies,
            conn=conn,
            max_pages=args.max_pages,
            max_workers=args.workers
        )

    # Export datasets
    export_all("mubawab_listings.db")

    # Print summary
    from filter_listings import print_summary
    print_summary("mubawab_listings.db")

    print(f"\n[✓] All jobs completed in {time.time() - t_start:.1f}s.")


if __name__ == "__main__":
    main()
