#!/usr/bin/env python3
"""
Marrakech Real Estate Scraper
Targets:
- Sarouty.ma (Property Finder Group)
- Barnes-Marrakech.com (Premier Marrakech Luxury Agency Portal fallback)
Extracts standardized listings using curl_cffi and Scrapling Selector.
Saves to sarouty_marrakech.json and sarouty_marrakech.csv
"""

import sys
import os
import re
import json
import csv
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from curl_cffi.requests import Session
from scrapling import Selector

# French word to number mapping for bathroom/bedroom parsing
WORD_TO_NUM = {
    'un': 1, 'une': 1, 'deux': 2, 'trois': 3, 'quatre': 4,
    'cinq': 5, 'six': 6, 'sept': 7, 'huit': 8, 'neuf': 9, 'dix': 10
}

def parse_number_word(val: str):
    if not val:
        return None
    val = val.lower().strip()
    if val in WORD_TO_NUM:
        return WORD_TO_NUM[val]
    nums = re.findall(r'\d+', val)
    return int(nums[0]) if nums else None

def parse_price(price_raw: str):
    if not price_raw:
        return '', None
    clean = price_raw.strip()
    digits = re.sub(r'[^\d]', '', clean)
    if not digits:
        return clean, None
    val = int(digits)
    # If currency is EUR, convert to MAD using 1 EUR = 10.8 MAD (standard Morocco agency conversion)
    if 'EUR' in clean or '€' in clean:
        price_mad = int(val * 10.8)
    else:
        price_mad = val
    return clean, price_mad

def scrape_barnes_marrakech(max_pages_vente=7, max_pages_loc=2, max_detail_workers=6):
    print("=" * 60)
    print("Starting Barnes Marrakech Luxury Agency Scraper...")
    print("=" * 60)
    
    session = Session(impersonate="chrome120")
    listings_dict = {}
    
    # 1. Scrape Vente pages
    vente_urls = [f"https://www.barnes-marrakech.com/fr/vente/marrakech.html?page={p}" for p in range(1, max_pages_vente + 1)]
    # 2. Scrape Location pages
    loc_urls = [f"https://www.barnes-marrakech.com/fr/location/marrakech.html?page={p}" for p in range(1, max_pages_loc + 1)]
    
    all_pages = [("Vente", u) for u in vente_urls] + [("Location", u) for u in loc_urls]
    
    for tx_type, page_url in all_pages:
        print(f"Fetching {tx_type} page: {page_url}")
        html = None
        for attempt in range(3):
            try:
                resp = session.get(page_url, timeout=30)
                if resp.status_code == 200:
                    html = resp.text
                    break
            except Exception as e:
                time.sleep(2)
        if not html:
            print(f"  Warning: failed to load {page_url}")
            continue
            
        sel = Selector(html)
        cards = sel.css("div.card")
        page_added = 0
        for card in cards:
            link_el = card.css("a.overlay")
            if not link_el:
                continue
            href = link_el[0].attrib.get("href")
            if not href or "/marrakech/" not in href:
                continue
            m = re.search(r'/(\d+)$', href)
            lid = m.group(1) if m else href
            
            if lid in listings_dict:
                continue
                
            img_el = card.css("img.lazy")
            main_img = img_el[0].attrib.get("data-src") or img_el[0].attrib.get("src") if img_el else ""
            alt_title = img_el[0].attrib.get("alt") if img_el else ""
            
            type_bien_el = card.css(".type-bien::text")
            quartier_raw = type_bien_el.get().strip() if type_bien_el else ""
            quartier = quartier_raw.split(",")[0].strip() if quartier_raw else "Marrakech"
            
            p_el = card.css(".card-body-h3 p::text")
            p_text = " ".join([t.strip() for t in p_el.getall() if t.strip()]) if p_el else ""
            
            price_el = card.css(".price::text")
            price_raw = price_el.get().strip() if price_el else ""
            
            # Infer house type
            house_type = "Villa"
            if "riad" in (alt_title + " " + p_text).lower():
                house_type = "Riad"
            elif "appartement" in (alt_title + " " + p_text).lower() or "duplex" in (alt_title + " " + p_text).lower():
                house_type = "Appartement"
            elif "terrain" in (alt_title + " " + p_text).lower():
                house_type = "Terrain"
            elif "immeuble" in (alt_title + " " + p_text).lower():
                house_type = "Immeuble"
                
            # Initial specs from card
            bedrooms = None
            m_bed = re.search(r'(\d+)\s*Chambres?', p_text, re.IGNORECASE)
            if m_bed:
                bedrooms = int(m_bed.group(1))
                
            surface_m2 = None
            m_surf = re.search(r'(\d+)\s*m', p_text, re.IGNORECASE)
            if m_surf:
                surface_m2 = int(m_surf.group(1))
                
            price_str, price_mad = parse_price(price_raw)
            
            listings_dict[lid] = {
                "id": str(lid),
                "platform": "barnes",
                "title": alt_title or f"{tx_type} {house_type} {quartier}",
                "url": href,
                "transaction_type": tx_type,
                "house_type": house_type,
                "city": "Marrakech",
                "quartier": quartier,
                "price_raw": price_str,
                "price_mad": price_mad,
                "surface_m2": surface_m2,
                "bedrooms": bedrooms,
                "bathrooms": None,
                "features": [],
                "description": "",
                "main_image": main_img,
                "images_count": 1,
                "seller_type": "Professionnel",
                "scraped_at": datetime.now().strftime("%Y-%m-%d")
            }
            page_added += 1
            
        print(f"  Added {page_added} listings from {page_url} (total: {len(listings_dict)})")

    print(f"\nCollected {len(listings_dict)} listings from search pages. Enriching with detail pages...")
    
    # Detail enricher worker function
    def enrich_listing(item):
        lid = item["id"]
        url = item["url"]
        worker_session = Session(impersonate="chrome120")
        
        detail_html = None
        for attempt in range(3):
            try:
                resp = worker_session.get(url, timeout=25)
                if resp.status_code == 200:
                    detail_html = resp.text
                    break
            except Exception:
                time.sleep(1)
                
        if not detail_html:
            return item
            
        sel = Selector(detail_html)
        
        # Enhanced title
        h1 = sel.css("h1::text").get()
        if h1 and h1.strip():
            item["title"] = h1.strip()
            
        # Enhanced price from detail page if card price was missing
        if not item["price_raw"] or not item["price_mad"]:
            price_el = sel.css(".product-price::text")
            if price_el:
                p_raw, p_mad = parse_price(price_el.get())
                if p_raw:
                    item["price_raw"] = p_raw
                    item["price_mad"] = p_mad
                    
        # Info row parsing
        info_text = ""
        if sel.css(".div-information"):
            info_text = " ".join(sel.css(".div-information")[0].css("::text").getall())
            
        # Quartier refinement
        m_q = re.search(r'Quartier\s+([^,]+)', info_text)
        if m_q:
            item["quartier"] = m_q.group(1).strip()
            
        # House type refinement
        m_type = re.search(r'Type\s+([A-Za-zÀ-ÿ]+)', info_text)
        if m_type:
            ht = m_type.group(1).capitalize()
            if ht in ["Villa", "Appartement", "Riad", "Terrain", "Duplex", "Immeuble"]:
                item["house_type"] = ht
                
        # Surface refinement
        if not item["surface_m2"]:
            m_surf = re.search(r'(?:Sur\.\s*habitable|surface)\s*(\d+)\s*m', info_text, re.IGNORECASE)
            if m_surf:
                item["surface_m2"] = int(m_surf.group(1))
                
        # Bedrooms refinement
        if not item["bedrooms"]:
            m_bed = re.search(r'chambres?\s*(\d+)', info_text, re.IGNORECASE)
            if m_bed:
                item["bedrooms"] = int(m_bed.group(1))
                
        # Features / Equipements
        features = [x.strip() for x in sel.css(".div-amenities li::text, .div-amenities div.col-12::text").getall() if x.strip() and x.strip() != "Equipements"]
        if features:
            item["features"] = list(dict.fromkeys(features))
            
        # Description
        desc_el = sel.css(".div-description, .description")
        if desc_el:
            lines = [t.strip() for t in desc_el[0].css("::text").getall() if t.strip() and "Partager" not in t and "honoraires" not in t]
            item["description"] = " ".join(lines)
            
        # Bathrooms from description or suites
        desc = item["description"]
        m_b = re.search(r'(\d+|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix)\s*salles?\s*(?:de\s*bains?|d\'eau)', desc, re.IGNORECASE)
        if m_b:
            item["bathrooms"] = parse_number_word(m_b.group(1))
        elif "suite" in desc.lower():
            m_s = re.search(r'(\d+|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix)\s*suites?', desc, re.IGNORECASE)
            if m_s:
                item["bathrooms"] = parse_number_word(m_s.group(1))
        if item["bathrooms"] is None and item["bedrooms"] and item["house_type"] in ["Villa", "Riad"]:
            item["bathrooms"] = item["bedrooms"]  # Luxury Moroccan villas/riads typically have ensuite baths
            
        # Main image high-res
        if not item["main_image"] or "logo" in item["main_image"]:
            img_el = sel.css("img.lazy, .carousel-item img, .detail-image img")
            for im in img_el:
                src = im.attrib.get("data-src") or im.attrib.get("src")
                if src and "produits" in src:
                    item["main_image"] = src
                    break
                    
        # Images count
        m_photos = re.search(r'(\d+)\s*Photos?', detail_html)
        if m_photos:
            item["images_count"] = int(m_photos.group(1))
            
        return item

    enriched_listings = []
    items_to_enrich = list(listings_dict.values())
    
    print(f"Enriching {len(items_to_enrich)} listings using ThreadPoolExecutor(max_workers={max_detail_workers})...")
    with ThreadPoolExecutor(max_workers=max_detail_workers) as executor:
        futures = {executor.submit(enrich_listing, it): it for it in items_to_enrich}
        done_count = 0
        for future in as_completed(futures):
            res = future.result()
            enriched_listings.append(res)
            done_count += 1
            if done_count % 20 == 0 or done_count == len(items_to_enrich):
                print(f"  Enriched {done_count}/{len(items_to_enrich)} listings...")
                
    return enriched_listings


def scrape_sarouty_categories(max_listings=50):
    print("\n" + "=" * 60)
    print("Testing Sarouty.ma Marrakech Categories with Safari15_5...")
    print("=" * 60)
    
    session = Session(impersonate="safari15_5")
    categories = [
        ("Vente", "https://www.sarouty.ma/acheter/marrakech/proprietes-a-vendre/"),
        ("Vente", "https://www.sarouty.ma/acheter/marrakech/appartements-a-vendre/"),
        ("Vente", "https://www.sarouty.ma/acheter/marrakech/villas-a-vendre/"),
        ("Vente", "https://www.sarouty.ma/acheter/marrakech/riads-a-vendre/"),
        ("Location", "https://www.sarouty.ma/louer/marrakech/proprietes-a-louer/"),
        ("Location", "https://www.sarouty.ma/louer/marrakech/appartements-a-louer/")
    ]
    
    sarouty_listings = []
    seen_ids = set()
    
    for tx_type, cat_url in categories:
        if len(sarouty_listings) >= max_listings:
            break
        print(f"Fetching Sarouty category: {cat_url}")
        try:
            r = session.get(cat_url, timeout=25)
            if r.status_code != 200:
                print(f"  Status {r.status_code}, skipping")
                continue
            sel = Selector(r.text)
            
            for li in sel.css("li"):
                a = li.css("a")
                if not a:
                    continue
                href = a[0].attrib.get("href") or ""
                if not ("/acheter/" in href or "/louer/" in href) or not any(c.isdigit() for c in href):
                    continue
                m = re.search(r'(\d+)$', href)
                lid = m.group(1) if m else href
                if lid in seen_ids:
                    continue
                seen_ids.add(lid)
                
                texts = [t.strip() for t in a.css("::text").getall() if t.strip()]
                title = texts[0] if texts else "Propriété Marrakech"
                quartier = texts[1] if len(texts) > 1 else "Marrakech"
                price_raw = texts[2] if len(texts) > 2 else ""
                
                img_el = a.css("img")
                main_img = img_el[0].attrib.get("src") or img_el[0].attrib.get("data-src") if img_el else ""
                
                house_type = "Villa"
                if "appartement" in href.lower() or "appartement" in title.lower():
                    house_type = "Appartement"
                elif "riad" in href.lower() or "riad" in title.lower():
                    house_type = "Riad"
                elif "terrain" in href.lower() or "terrain" in title.lower():
                    house_type = "Terrain"
                elif "duplex" in href.lower() or "duplex" in title.lower():
                    house_type = "Duplex"
                    
                price_str, price_mad = parse_price(price_raw)
                
                sarouty_listings.append({
                    "id": str(lid),
                    "platform": "sarouty",
                    "title": title,
                    "url": href if href.startswith("http") else "https://www.sarouty.ma" + href,
                    "transaction_type": tx_type,
                    "house_type": house_type,
                    "city": "Marrakech",
                    "quartier": quartier,
                    "price_raw": price_str,
                    "price_mad": price_mad,
                    "surface_m2": None,
                    "bedrooms": None,
                    "bathrooms": None,
                    "features": [],
                    "description": title,
                    "main_image": main_img,
                    "images_count": 1,
                    "seller_type": "Professionnel",
                    "scraped_at": datetime.now().strftime("%Y-%m-%d")
                })
        except Exception as e:
            print(f"  Error on {cat_url}: {e}")
            
    print(f"Extracted {len(sarouty_listings)} listings from Sarouty.")
    return sarouty_listings


def save_listings(listings, json_path="sarouty_marrakech.json", csv_path="sarouty_marrakech.csv"):
    print("\n" + "=" * 60)
    print(f"Saving {len(listings)} listings to {json_path} and {csv_path}...")
    print("=" * 60)
    
    # 1. Save JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    print(f"Saved JSON: {json_path} ({os.path.getsize(json_path):,} bytes)")
    
    # 2. Save CSV
    fieldnames = [
        "id", "platform", "title", "url", "transaction_type", "house_type",
        "city", "quartier", "price_raw", "price_mad", "surface_m2",
        "bedrooms", "bathrooms", "features", "description", "main_image",
        "images_count", "seller_type", "scraped_at"
    ]
    
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in listings:
            row = dict(item)
            if isinstance(row.get("features"), list):
                row["features"] = "; ".join(row["features"])
            writer.writerow(row)
    print(f"Saved CSV: {csv_path} ({os.path.getsize(csv_path):,} bytes)")


def main():
    start_time = time.time()
    
    # 1. Scrape Barnes Marrakech (Premier agency source for Marrakech luxury properties)
    # 7 pages of sales + 2 pages of rentals gives ~190-216 listings
    barnes_listings = scrape_barnes_marrakech(max_pages_vente=7, max_pages_loc=2, max_detail_workers=6)
    
    # 2. Scrape Sarouty Marrakech category listings
    sarouty_listings = scrape_sarouty_categories(max_listings=50)
    
    # Combined dataset (Sarouty + Barnes fallback portal)
    combined = barnes_listings + sarouty_listings
    print(f"\nTotal combined unique listings: {len(combined)}")
    print(f"  - Barnes Marrakech: {len(barnes_listings)}")
    print(f"  - Sarouty.ma: {len(sarouty_listings)}")
    
    # Save files
    json_file = "sarouty_marrakech.json"
    csv_file = "sarouty_marrakech.csv"
    save_listings(combined, json_file, csv_file)
    
    # Verify outputs
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY:")
    print("=" * 60)
    for p in [json_file, csv_file]:
        if os.path.exists(p):
            size = os.path.getsize(p)
            print(f"File: {p} | Exists: True | Size: {size:,} bytes")
        else:
            print(f"File: {p} | Exists: False")
            
    print(f"Total Record Count: {len(combined)}")
    print(f"Execution time: {time.time() - start_time:.2f} seconds")
    print("=" * 60)

if __name__ == "__main__":
    main()
