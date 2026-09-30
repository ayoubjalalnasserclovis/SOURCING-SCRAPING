"""
Master Concurrent Scraper for Mubawab - Integrality Scraper for Marrakech & Surrounding Zones.
Scrapes the full inventory with House Type & Quartier categorization,
persists to SQLite database with UPSERT, and exports complete datasets.

Constraints:
- 1 PHOTO MAX per home (stored as single URL string 'main_image').
- No large photo arrays stored.
"""

import sys
import io
import os
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


def fetch_single_page(
    page_num: int,
    page_url: str,
    cookies: dict,
    trans_type: str,
    city: str,
    default_quartier: str = "Autre / Centre",
    retries: int = 3
) -> Tuple[int, str, List[Dict[str, Any]], int]:
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
                items = parse_page_listings(
                    r.content,
                    transaction_type=trans_type,
                    city=city,
                    default_quartier=default_quartier
                )
                return page_num, page_url, items, r.status_code
            elif r.status_code == 404:
                return page_num, page_url, [], 404
        except Exception:
            if attempt == retries:
                return page_num, page_url, [], 0
            time.sleep(1.0 * attempt)
            
    return page_num, page_url, [], 0


def scrape_category(
    base_url: str,
    trans_type: str,
    city: str,
    default_quartier: str,
    max_pages: int,
    cookies: dict,
    conn: sqlite3.Connection,
    min_pages: int = 1,
    max_workers: int = 10
) -> int:
    """Scrape all pages of a given category concurrently with intelligent loop detection."""
    print(f"\n" + "=" * 75)
    print(f"[*] Category: [{trans_type}] {base_url}")
    print(f"[*] City/Zone: {city} (Default Quartier: {default_quartier}) | Target Pages: {min_pages}-{max_pages}")
    print("=" * 75)

    # First fetch page 1
    _, _, p1_items, code = fetch_single_page(1, base_url, cookies, trans_type, city, default_quartier)
    if code != 200 or not p1_items:
        print(f"[!] Page 1 check returned HTTP {code} ({len(p1_items)} items). Skipping category.")
        return 0

    save_listings_to_db(conn, p1_items)
    category_seen_ids = set(item["id"] for item in p1_items)
    last_seen_first_id = p1_items[0]["id"] if p1_items else None
    consecutive_same_first_id = 0
    consecutive_empty_or_dupe = 0
    total_new = len(p1_items)
    print(f"[+] Page 1: {len(p1_items)} listings saved. Launching concurrent extraction...")

    if max_pages <= 1:
        return total_new

    # Fetch remaining pages in sequential batches
    batch_size = 12
    all_page_nums = list(range(2, max_pages + 1))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for batch_start_idx in range(0, len(all_page_nums), batch_size):
            batch_pages = all_page_nums[batch_start_idx : batch_start_idx + batch_size]
            futures = {
                executor.submit(
                    fetch_single_page,
                    p,
                    f"{base_url}:p:{p}",
                    cookies,
                    trans_type,
                    city,
                    default_quartier
                ): p
                for p in batch_pages
            }

            # Collect results for this batch
            batch_results = []
            for future in as_completed(futures):
                try:
                    res = future.result()
                    batch_results.append(res)
                except Exception:
                    pass

            # Sort batch results by page number to process in true sequence
            batch_results.sort(key=lambda x: x[0])

            batch_new_items = []
            should_stop = False

            for p_num, url, items, status in batch_results:
                if status == 404 or not items:
                    if p_num >= min_pages:
                        consecutive_empty_or_dupe += 1
                else:
                    first_id = items[0]["id"] if items else None
                    if first_id == last_seen_first_id:
                        consecutive_same_first_id += 1
                    else:
                        consecutive_same_first_id = 0
                        last_seen_first_id = first_id

                    # Check how many items on this page are genuinely new
                    new_on_page = [it for it in items if it["id"] not in category_seen_ids]
                    if not new_on_page:
                        if p_num >= min_pages:
                            consecutive_empty_or_dupe += 1
                    else:
                        consecutive_empty_or_dupe = 0
                        for it in new_on_page:
                            category_seen_ids.add(it["id"])
                    
                    batch_new_items.extend(items)

                # Mubawab loops fallback pages at the end of results (same first ID or consecutive dupes past min_pages)
                if p_num >= min_pages and (consecutive_same_first_id >= 2 or consecutive_empty_or_dupe >= 4):
                    print(f"[*] Confirmed end of listings reached for this category at page {p_num}.")
                    should_stop = True
                    break

            if batch_new_items:
                save_listings_to_db(conn, batch_new_items)
                total_new += len(batch_new_items)
                cur_total = conn.cursor().execute("SELECT COUNT(*) FROM listings").fetchone()[0]
                p_range = f"{batch_pages[0]}-{batch_pages[-1]}"
                print(f"[+] Pages {p_range:>7}: +{len(batch_new_items)} items | Total in DB: {cur_total:,}")

            if should_stop:
                break

            time.sleep(0.2)

    return total_new


def export_all(db_path: str = "mubawab_listings.db"):
    """Export complete dataset and filtered slices to CSV and JSON."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    total = cur.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    print(f"\n" + "=" * 75)
    print(f"[*] EXPORTING COMPLETE DATASET ({total:,} UNIQUE LISTINGS)...")
    print("=" * 75)

    all_rows = [dict(r) for r in cur.execute("SELECT * FROM listings ORDER BY price_numeric ASC").fetchall()]

    # Verify single photo constraint strictly:
    for row in all_rows:
        img = row.get("main_image")
        if isinstance(img, list):
            row["main_image"] = img[0] if img else ""
        elif not isinstance(img, str):
            row["main_image"] = str(img or "")

    # 1. Full JSON
    json_path = "mubawab_complete_listings.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=2)
    json_size_mb = os.path.getsize(json_path) / (1024 * 1024)
    print(f"[✓] Exported: {json_path} ({len(all_rows):,} records, {json_size_mb:.2f} MB)")

    # 2. Full CSV
    csv_path = "mubawab_complete_listings.csv"
    fieldnames = list(all_rows[0].keys()) if all_rows else []
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    csv_size_mb = os.path.getsize(csv_path) / (1024 * 1024)
    print(f"[✓] Exported: {csv_path} ({len(all_rows):,} records, {csv_size_mb:.2f} MB)")

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
            print(f"  -> Slice: {filename} ({len(rows):,} records)")

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
            print(f"  -> Slice: {filename} ({len(rows):,} records)")

    conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Complete Mubawab Integrality Scraper")
    parser.add_argument("--workers", type=int, default=10, help="Concurrent worker threads (default 10)")
    args = parser.parse_args()

    t_start = time.time()
    conn = init_db("mubawab_listings.db")
    _, cookies = get_base_session()

    # Complete target inventory covering Marrakech and all surrounding zones
    categories = [
        # 1. Main Marrakech Sales (~8,100 listings, ~262 pages)
        ("https://www.mubawab.ma/fr/ct/marrakech/immobilier-a-vendre", "Vente", "Marrakech", "Autre / Centre", 260, 265),
        # 2. Main Marrakech Rentals (~3,460 listings, ~109 pages)
        ("https://www.mubawab.ma/fr/ct/marrakech/immobilier-a-louer", "Location", "Marrakech", "Autre / Centre", 108, 115),
        # 3. Marrakech Vacation Rentals (~190 listings, ~7 pages)
        ("https://www.mubawab.ma/fr/st/marrakech/appartements-vacational", "Location Vacances", "Marrakech", "Autre / Centre", 6, 10),
        # 4. Surrounding Zones & Communes
        ("https://www.mubawab.ma/fr/ct/ourika/immobilier-a-vendre", "Vente", "Marrakech", "Route de l'Ourika", 4, 6),
        ("https://www.mubawab.ma/fr/ct/ourika/immobilier-a-louer", "Location", "Marrakech", "Route de l'Ourika", 1, 3),
        ("https://www.mubawab.ma/fr/ct/harbil/immobilier-a-vendre", "Vente", "Marrakech", "Tamansourt", 1, 3),
        ("https://www.mubawab.ma/fr/ct/harbil/immobilier-a-louer", "Location", "Marrakech", "Tamansourt", 1, 2),
        ("https://www.mubawab.ma/fr/ct/tassoultante/immobilier-a-vendre", "Vente", "Marrakech", "Tassoultante", 3, 5),
        ("https://www.mubawab.ma/fr/ct/tassoultante/immobilier-a-louer", "Location", "Marrakech", "Tassoultante", 1, 2),
        ("https://www.mubawab.ma/fr/ct/tameslohte/immobilier-a-vendre", "Vente", "Marrakech", "Tameslohte", 2, 4),
        ("https://www.mubawab.ma/fr/ct/tameslohte/immobilier-a-louer", "Location", "Marrakech", "Tameslohte", 1, 2),
        ("https://www.mubawab.ma/fr/ct/ait-ourir/immobilier-a-vendre", "Vente", "Marrakech", "Aït Ourir", 2, 4),
        ("https://www.mubawab.ma/fr/ct/ait-ourir/immobilier-a-louer", "Location", "Marrakech", "Aït Ourir", 1, 2),
        ("https://www.mubawab.ma/fr/ct/amizmiz/immobilier-a-vendre", "Vente", "Marrakech", "Route d'Amizmiz", 2, 4),
        ("https://www.mubawab.ma/fr/ct/amizmiz/immobilier-a-louer", "Location", "Marrakech", "Route d'Amizmiz", 1, 2),
        ("https://www.mubawab.ma/fr/ct/agafay/immobilier-a-vendre", "Vente", "Marrakech", "Agafay", 1, 2),
        ("https://www.mubawab.ma/fr/ct/agafay/immobilier-a-louer", "Location", "Marrakech", "Agafay", 1, 2),
    ]

    for base_url, trans_type, city, default_q, min_p, max_p in categories:
        scrape_category(
            base_url=base_url,
            trans_type=trans_type,
            city=city,
            default_quartier=default_q,
            min_pages=min_p,
            max_pages=max_p,
            cookies=cookies,
            conn=conn,
            max_workers=args.workers
        )

    # Export all datasets
    export_all("mubawab_listings.db")

    # Print summary
    try:
        from filter_listings import print_summary
        print_summary("mubawab_listings.db")
    except Exception as e:
        print(f"Summary print: {e}")

    # Also sync unified sourcing database and data.js
    try:
        from unify_sourcing import ingest_mubawab, export_unified, DB_PATH
        s_conn = sqlite3.connect(DB_PATH)
        ingest_mubawab(s_conn)
        export_unified(s_conn)
        s_conn.close()
        
        from build_site_data import build_data
        build_data()
    except Exception as e:
        print(f"Site data sync note: {e}")

    print(f"\n[✓] ALL JOBS COMPLETED in {time.time() - t_start:.1f}s.")


if __name__ == "__main__":
    main()
