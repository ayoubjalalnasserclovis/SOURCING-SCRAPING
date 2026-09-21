"""
Mubawab Marrakech Real Estate Scraper using Scrapling and curl_cffi.
Scrapes real estate listings in Marrakech from mubawab.ma and saves to JSON and CSV.
"""

import sys
import io
import time
import json
import csv
import re
from typing import List, Dict, Any, Optional

# Set UTF-8 encoding for console output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from curl_cffi import requests
from scrapling import Selector


def create_session() -> requests.Session:
    """Initialize a browser-like session with curl_cffi impersonating Chrome."""
    session = requests.Session(impersonate="chrome120")
    session.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.mubawab.ma/",
    })
    
    print("[*] Initializing session with mubawab.ma homepage...")
    resp = session.get("https://www.mubawab.ma/", timeout=20)
    if resp.status_code == 200:
        print(f"[+] Homepage accessed successfully. Cookies acquired: {len(session.cookies)}")
    else:
        print(f"[!] Warning: Homepage returned status {resp.status_code}")
    return session


def clean_text(text: Optional[str]) -> str:
    """Normalize whitespace and strip text."""
    if not text:
        return ""
    # Replace non-breaking spaces (\u00a0, \u202f) with regular spaces
    text = re.sub(r"[\s\u00a0\u202f]+", " ", text)
    return text.strip()


def parse_listing(box, base_url: str = "https://www.mubawab.ma") -> Optional[Dict[str, Any]]:
    """Parse a single listing box element using Scrapling Selector."""
    # 1. URL and Title
    link_el = box.xpath(".//a[contains(@href, '/a/') or contains(@href, '/pa/')]")
    if not link_el:
        return None
    
    url = link_el[0].attrib.get("href", "")
    if url.startswith("/"):
        url = base_url + url
    
    title = clean_text(link_el[0].text if link_el[0].text else "")
    if not title:
        # Fallback to title attribute or text in child
        title = clean_text(link_el[0].attrib.get("title", ""))
    
    # Extract listing ID from URL e.g. /fr/pa/8242624/ or /fr/a/8269456/
    id_match = re.search(r"/(?:pa|a)/(\d+)/", url)
    listing_id = id_match.group(1) if id_match else ""

    # 2. Price (MAD / DH)
    # Mubawab uses <bdi> or span with price
    bdi_el = box.xpath(".//bdi")
    if bdi_el and bdi_el[0].text:
        raw_price = clean_text(bdi_el[0].text)
        price_mad = f"{raw_price} DH"
    else:
        # Check for price class or text with DH
        price_tags = box.xpath(".//*[contains(@class, 'price') or contains(@class, 'Price')]//text()").getall()
        price_mad = clean_text(" ".join(price_tags)) if price_tags else ""

    # 3. Description
    desc_el = box.xpath(".//p[contains(@class, 'descLi') or contains(@class, 'listingP')]")
    description = clean_text(desc_el[0].text) if desc_el and desc_el[0].text else ""

    # 4. Specifications (Surface m², Rooms, Bedrooms, Bathrooms)
    spans = box.xpath(".//span//text()").getall()
    surface = ""
    rooms = ""
    bedrooms = ""
    bathrooms = ""
    
    for s in spans:
        s_clean = clean_text(s)
        if re.search(r"\d+\s*m²", s_clean, re.I):
            surface = s_clean
        elif re.search(r"\d+\s*Pièce", s_clean, re.I):
            rooms = s_clean
        elif re.search(r"\d+\s*(?:Ch\b|Chambre)", s_clean, re.I):
            bedrooms = s_clean
        elif re.search(r"\d+\s*Salle", s_clean, re.I):
            bathrooms = s_clean

    # 5. Features / Amenities
    feature_spans = box.xpath(".//span[contains(@class, 'fSize12')]//text()").getall()
    features = [clean_text(f) for f in feature_spans if clean_text(f)]

    # 6. Location / Neighborhood
    # Look for location indications in title, URL slug, or description
    location = "Marrakech"
    # Common Marrakech neighborhoods
    neighborhoods = [
        "Guéliz", "Gueliz", "Hivernage", "Palmeraie", "Médina", "Medina",
        "Majorelle", "Agdal", "Targa", "Mhamid", "M'hamid", "Sidi Youssef Ben Ali",
        "Semlalia", "Samlalia", "Izdihar", "Daoudiate", "Massira", "Victor Hugo",
        "Amelkis", "Route de Casablanca", "Route de l'Ourika", "Route d'Amizmiz",
        "Route de Fès", "Route de Tahanaout", "Chrifia", "Targa", "Camp El Ghoul"
    ]
    found_neighborhood = ""
    combined_text = f"{title} {url} {description}"
    for n in neighborhoods:
        if re.search(r"\b" + re.escape(n) + r"\b", combined_text, re.I):
            found_neighborhood = n
            break
    
    if found_neighborhood:
        location = f"{found_neighborhood}, Marrakech"

    # 7. Images
    images = []
    for img in box.xpath(".//img"):
        src = img.attrib.get("data-lazy") or img.attrib.get("data-url") or img.attrib.get("data-src") or img.attrib.get("src")
        if src and "mubawab-media" in src and src not in images:
            images.append(src)

    return {
        "id": listing_id,
        "title": title,
        "url": url,
        "price": price_mad,
        "location": location,
        "surface": surface,
        "rooms": rooms,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "features": features,
        "description": description,
        "main_image": images[0] if images else "",
        "images_count": len(images),
    }


def scrape_mubawab_marrakech(target_count: int = 100) -> List[Dict[str, Any]]:
    """Scrape at least target_count listings from Mubawab Marrakech."""
    session = create_session()
    
    all_listings: List[Dict[str, Any]] = []
    seen_ids = set()
    page_num = 1
    
    # Categories to scrape if a single category exhausts
    base_urls = [
        "https://www.mubawab.ma/fr/st/marrakech/appartements-a-vendre",
        "https://www.mubawab.ma/fr/st/marrakech/villas-et-maisons-de-luxe-a-vendre",
        "https://www.mubawab.ma/fr/st/marrakech/riads-a-vendre",
        "https://www.mubawab.ma/fr/st/marrakech/maisons-a-vendre",
    ]
    current_cat_idx = 0

    print(f"\n[*] Starting scrape targeting {target_count} results from Mubawab Marrakech...")
    
    while len(all_listings) < target_count and current_cat_idx < len(base_urls):
        base_cat_url = base_urls[current_cat_idx]
        if page_num == 1:
            page_url = base_cat_url
        else:
            page_url = f"{base_cat_url}:p:{page_num}"
        
        print(f"\n[Page {page_num}] Fetching {page_url}...")
        t0 = time.time()
        try:
            resp = session.get(page_url, timeout=20)
            elapsed = time.time() - t0
            
            if resp.status_code != 200:
                print(f"[!] Warning: HTTP {resp.status_code} on {page_url}")
                current_cat_idx += 1
                page_num = 1
                continue
            
            # Parse with Scrapling Selector
            page = Selector(resp.content)
            boxes = page.xpath("//*[contains(@class, 'listingBox')]")
            print(f"[+] Downloaded {len(resp.content)//1024} KB in {elapsed:.2f}s | Found {len(boxes)} listing cards")
            
            if not boxes:
                print("[!] No listings found on this page, moving to next category...")
                current_cat_idx += 1
                page_num = 1
                continue
            
            new_listings_on_page = 0
            for box in boxes:
                item = parse_listing(box)
                if item and item.get("id"):
                    if item["id"] not in seen_ids:
                        seen_ids.add(item["id"])
                        all_listings.append(item)
                        new_listings_on_page += 1
                        
                        if len(all_listings) >= target_count:
                            break
            
            print(f"[+] Added {new_listings_on_page} new listings. Total collected so far: {len(all_listings)}/{target_count}")
            
            page_num += 1
            # Respectful delay between requests
            time.sleep(1.5)
            
        except Exception as e:
            print(f"[!] Error on {page_url}: {e}")
            time.sleep(2)
            page_num += 1

    return all_listings


def save_results(listings: List[Dict[str, Any]], json_path: str = "mubawab_marrakech_100.json", csv_path: str = "mubawab_marrakech_100.csv"):
    """Save listings to JSON and CSV files."""
    # 1. Save JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    print(f"\n[✓] Saved {len(listings)} listings to JSON: {json_path}")
    
    # 2. Save CSV
    fieldnames = [
        "id", "title", "price", "location", "surface", "rooms",
        "bedrooms", "bathrooms", "features", "main_image", "images_count", "url", "description"
    ]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in listings:
            # Flatten features list to comma-separated string for CSV
            row = item.copy()
            row["features"] = ", ".join(item["features"]) if isinstance(item["features"], list) else item["features"]
            writer.writerow(row)
    print(f"[✓] Saved {len(listings)} listings to CSV: {csv_path}")


def print_summary(listings: List[Dict[str, Any]]):
    """Print summary statistics of scraped data."""
    print("\n" + "="*70)
    print(f" SCRAPING SUMMARY - {len(listings)} LISTINGS FROM MUBAWAB MARRAKECH")
    print("="*70)
    for i, item in enumerate(listings[:5], 1):
        print(f"\n#{i}: {item['title']}")
        print(f"    ID:       {item['id']}")
        print(f"    Price:    {item['price']}")
        print(f"    Location: {item['location']}")
        print(f"    Surface:  {item['surface']} | Rooms: {item['rooms']} | Bedrooms: {item['bedrooms']}")
        print(f"    Features: {', '.join(item['features'][:4]) if item['features'] else 'None'}")
        print(f"    URL:      {item['url']}")
    print("\n" + "-"*70)
    print(f"Total Unique Listings Scraped: {len(listings)}")
    print("="*70)


def main():
    target = 100
    listings = scrape_mubawab_marrakech(target_count=target)
    save_results(listings)
    print_summary(listings)


if __name__ == "__main__":
    main()
