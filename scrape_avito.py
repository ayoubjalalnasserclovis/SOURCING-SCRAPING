#!/usr/bin/env python3
"""
Production scraper for Avito.ma real estate listings in Marrakech.
Fetches listings using curl_cffi (impersonate='chrome120') and Scrapling Selector.
Extracts rich listing data from __NEXT_DATA__ and CSS selectors, standardizes
fields according to target schema, and saves to JSON and CSV formats.
"""

import sys
import io
import re
import json
import csv
import os
import time
from datetime import datetime
from curl_cffi import requests
from scrapling import Selector

# Ensure UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = "https://www.avito.ma/fr/marrakech/immobilier"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}

KNOWN_QUARTIERS = [
    "Guéliz", "Hivernage", "Palmeraie", "Médina", "Targa", "Agdal",
    "Majorelle", "M'Hamid", "Mhamid", "Daoudiate", "Sidi Youssef Ben Ali",
    "Massira", "Semlalia", "Route de Casablanca", "Route d'Ourika",
    "Route de Fès", "Route d'Amizmiz", "Route de Ouarzazate", "Route de Safi",
    "Route de Tahanaoute", "Chrifia", "Amerchich", "Victor Hugo",
    "Hay Izdihar", "Hay Riad", "Al Fadel", "Bab Doukkala", "Ain Mezouar",
    "Azzouzia", "Mabrouka", "Hay Charaf", "Es Saada", "Hay Andalous",
    "Centre Ville", "Av Mohammed VI", "Sidi Ghanem", "Camp Ghoul"
]

FEATURE_KEYWORDS = [
    ("Ascenseur", r"\bascenseur\b"),
    ("Climatisation", r"\b(?:clim|climatisation|climatisé)\b"),
    ("Piscine", r"\bpiscine\b"),
    ("Jardin", r"\bjardin\b"),
    ("Terrasse", r"\bterrasse\b"),
    ("Balcon", r"\bbalcon\b"),
    ("Parking / Garage", r"\b(?:parking|garage|stationnement|box)\b"),
    ("Meublé", r"\b(?:meublé|meublee|meubl[ée]s?)\b"),
    ("Cuisine équipée", r"\bcuisine\s+(?:équipée|equipee)\b"),
    ("Sécurité / Gardien", r"\b(?:sécurité|securite|gardien|gardiennage|concierge|résidence fermée)\b"),
    ("Vue dégagée / Atlas / Golf", r"\bvue\s+(?:dégagée|degagee|golf|atlas|montagne|panoramique)\b"),
    ("Cheminée", r"\bcheminée|cheminee\b"),
    ("Double vitrage", r"\bdouble vitrage\b"),
]

def classify_house_type(title: str, cat_name: str, desc: str) -> str:
    """Classifies property into standardized house_type with high precision."""
    title_lower = title.lower()
    cat_lower = cat_name.lower()
    
    # 1. First priority: Title (most specific intent)
    if re.search(r"\briad\b", title_lower):
        return "Riad"
    if re.search(r"\bstudio\b", title_lower):
        return "Studio"
    if re.search(r"\bduplex\b", title_lower):
        return "Duplex"
    if re.search(r"\b(?:terrain|terrains|parcelle|lotissement)\b", title_lower):
        return "Terrain"
    if re.search(r"\b(?:bureau|bureaux|plateau)\b", title_lower):
        return "Bureau"
    if re.search(r"\b(?:commerce|commercial|magasin|boutique|local\s+commercial|hangar)\b", title_lower):
        return "Commerce"
    if re.search(r"\b(?:villa|villas)\b", title_lower):
        return "Villa"
    if re.search(r"\b(?:maison|maisons)\b", title_lower):
        return "Maison"
    if re.search(r"\b(?:appartement|appartements|appart)\b", title_lower):
        return "Appartement"

    # 2. Second priority: Category name
    if "riad" in cat_lower:
        return "Riad"
    if "bureau" in cat_lower:
        return "Bureau"
    if "local" in cat_lower or "commerce" in cat_lower:
        return "Commerce"
    if "terrain" in cat_lower or "ferme" in cat_lower:
        return "Terrain"
    if "villa" in cat_lower:
        return "Villa"
    if "maison" in cat_lower:
        return "Maison"
    if "appartement" in cat_lower:
        return "Appartement"
        
    # 3. Third priority: Description with strict word boundaries
    desc_lower = desc.lower()
    if re.search(r"\briad\b", desc_lower):
        return "Riad"
    if re.search(r"\bstudio\b", desc_lower):
        return "Studio"
    if re.search(r"\bduplex\b", desc_lower):
        return "Duplex"
    if re.search(r"\b(?:terrain|terrains)\b", desc_lower):
        return "Terrain"
    if re.search(r"\b(?:villa|villas)\b", desc_lower):
        return "Villa"
    if re.search(r"\b(?:appartement|appartements)\b", desc_lower):
        return "Appartement"
    if re.search(r"\b(?:maison|maisons)\b", desc_lower):
        return "Maison"
    if re.search(r"\b(?:bureau|bureaux)\b", desc_lower):
        return "Bureau"
    if re.search(r"\b(?:commerce|commercial|magasin|boutique)\b", desc_lower):
        return "Commerce"
        
    return "Appartement"

def extract_transaction_type(ad_type_obj: dict, cat_name: str, title: str) -> str:
    """Classifies transaction_type as 'Vente' or 'Location'."""
    key = (ad_type_obj.get("key") or "").upper()
    if key == "SELL":
        return "Vente"
    if key in ("LET", "VAC_RENT"):
        return "Location"
    
    label = (ad_type_obj.get("label") or "").lower()
    if "vente" in label or "vendre" in label:
        return "Vente"
    if "louer" in label or "location" in label or "vacance" in label:
        return "Location"
        
    text = f"{cat_name} {title}".lower()
    if any(k in text for k in ["louer", "location", "vacance"]):
        return "Location"
    return "Vente"

def extract_quartier(loc: str, url: str, title: str, desc: str) -> str:
    """Extracts and normalizes neighborhood in Marrakech."""
    loc_part = ""
    if loc:
        if "," in loc:
            loc_part = loc.split(",", 1)[1].strip()
        else:
            loc_part = loc.strip()
            
    if loc_part and loc_part.lower() not in ("marrakech", "autre secteur", "autre"):
        # Normalize spelling if needed
        if loc_part.lower() in ("gueliz", "guéliz"):
            return "Guéliz"
        if loc_part.lower() in ("medina", "médina"):
            return "Médina"
        return loc_part
        
    # Check URL slug: e.g. https://www.avito.ma/fr/agdal/appartements/...
    m = re.search(r"avito\.ma/fr/([^/]+)/", url)
    if m:
        slug = m.group(1).replace("_", " ").title()
        if slug.lower() not in ("marrakech", "immobilier", "unite"):
            if slug.lower() in ("gueliz", "guéliz"): return "Guéliz"
            if slug.lower() in ("medina", "médina"): return "Médina"
            return slug
            
    # Check title / desc against known Marrakech quartiers
    text = f"{title} {desc}".lower()
    for kq in KNOWN_QUARTIERS:
        if kq.lower() in text:
            if kq.lower() in ("gueliz", "guéliz"): return "Guéliz"
            if kq.lower() in ("medina", "médina"): return "Médina"
            if kq.lower() in ("route de fes", "route de fès"): return "Route de Fès"
            return kq
            
    return loc_part if loc_part else "Marrakech"

def extract_features(text: str, params_extra: list = None) -> str:
    """Extracts features list as a comma-separated string."""
    feats = []
    if params_extra:
        for p in params_extra:
            label = p.get("label")
            if label and label not in feats:
                feats.append(label)
                
    text_lower = text.lower()
    for feat_name, pat in FEATURE_KEYWORDS:
        if re.search(pat, text_lower, re.IGNORECASE):
            if feat_name not in feats:
                feats.append(feat_name)
                
    return ", ".join(feats)

def parse_ad_data(ad: dict, scraped_date: str) -> dict:
    """Parses a single Avito ad dictionary into standardized format."""
    # Exclude non-standard ads (e.g. Immoneuf integrations) to ensure 100% genuine Avito listings
    if ad.get("isNc"):
        return None
        
    # IDs
    ad_id = str(ad.get("listId") or ad.get("id") or "")
    if not ad_id:
        return None
        
    title = (ad.get("subject") or "").strip()
    url = ad.get("href") or ""
    if not url.startswith("http"):
        url = f"https://www.avito.ma{url}"
        
    desc = (ad.get("description") or "").strip()
    
    # Category & Ad Type
    cat_info = ad.get("category") or {}
    cat_name = cat_info.get("name") or cat_info.get("formatted") or ""
    ad_type_info = ad.get("adType") or {}
    
    transaction_type = extract_transaction_type(ad_type_info, cat_name, title)
    house_type = classify_house_type(title, cat_name, desc)
    
    # Location
    loc = ad.get("location") or ""
    quartier = extract_quartier(loc, url, title, desc)
    
    # Price
    price_info = ad.get("price") or {}
    price_val = price_info.get("value")
    price_mad = None
    price_raw = None
    if price_val is not None:
        try:
            price_mad = int(float(price_val))
            price_raw = f"{price_mad:,} DH".replace(",", " ")
        except (ValueError, TypeError):
            pass
            
    if price_mad is None:
        # Try extracting from text
        m = re.search(r"(\d[\d\s.,]{2,})\s*(?:dh|dhs|mad)", f"{title} {desc}", re.IGNORECASE)
        if m:
            raw_digits = re.sub(r"[^\d]", "", m.group(1))
            if raw_digits:
                price_mad = int(raw_digits)
                price_raw = f"{price_mad:,} DH".replace(",", " ")

    # Parameters (surface, rooms, bathrooms)
    params_sec = (ad.get("params") or {}).get("secondary") or []
    param_dict = {}
    for p in params_sec:
        param_dict[p.get("key")] = p.get("value")
        
    # Surface
    surface_m2 = None
    if "size" in param_dict and param_dict["size"] is not None:
        try:
            surface_m2 = int(float(str(param_dict["size"]).replace(" ", "")))
        except (ValueError, TypeError):
            pass
    if surface_m2 is None:
        m = re.search(r"(\d+)\s*(?:m²|m2|mètres carrés|metres carres)", f"{title} {desc}", re.IGNORECASE)
        if m:
            surface_m2 = int(m.group(1))
            
    # Bedrooms
    bedrooms = None
    for k in ("rooms", "capacity_rooms"):
        if k in param_dict and param_dict[k] is not None:
            try:
                bedrooms = int(param_dict[k])
                break
            except (ValueError, TypeError):
                pass
    if bedrooms is None:
        m = re.search(r"(\d+)\s*(?:chambres?|chb|pièces?|pieces?)", f"{title} {desc}", re.IGNORECASE)
        if m:
            bedrooms = int(m.group(1))
            
    # Bathrooms
    bathrooms = None
    if "bathrooms" in param_dict and param_dict["bathrooms"] is not None:
        try:
            bathrooms = int(param_dict["bathrooms"])
        except (ValueError, TypeError):
            pass
    if bathrooms is None:
        m = re.search(r"(\d+)\s*(?:salles?\s+de\s+bains?|sdbs?|sdb)", f"{title} {desc}", re.IGNORECASE)
        if m:
            bathrooms = int(m.group(1))

    # Features
    features = extract_features(f"{title} {desc}")
    
    # Images
    main_image = ad.get("defaultImage") or ""
    images_list = ad.get("images") or []
    images_count = len(images_list)
    if images_count == 0 and main_image:
        images_count = 1
        
    # Seller type
    seller_info = ad.get("seller") or {}
    seller_type_raw = (seller_info.get("type") or "").upper()
    if seller_type_raw == "STORE" or ad.get("isShop"):
        seller_type = "Professionnel"
    else:
        seller_type = "Particulier"
        
    return {
        "id": ad_id,
        "platform": "avito",
        "title": title,
        "url": url,
        "transaction_type": transaction_type,
        "house_type": house_type,
        "city": "Marrakech",
        "quartier": quartier,
        "price_raw": price_raw or "",
        "price_mad": price_mad,
        "surface_m2": surface_m2,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "features": features,
        "description": desc,
        "main_image": main_image,
        "images_count": images_count,
        "seller_type": seller_type,
        "scraped_at": scraped_date,
    }

def scrape_avito_marrakech(target_count: int = 250, max_pages: int = 10):
    """Scrapes Avito.ma Marrakech real estate listings until target_count reached."""
    all_listings = []
    seen_ids = set()
    scraped_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"Starting Avito Marrakech scraper at {datetime.now().isoformat()}...")
    print(f"Target listings count: {target_count} (max pages: {max_pages})")
    
    page = 1
    while page <= max_pages and len(all_listings) < target_count:
        url = f"{BASE_URL}?o={page}" if page > 1 else BASE_URL
        print(f"\n[Page {page}] Fetching {url}...")
        
        try:
            resp = requests.get(url, impersonate="chrome120", headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"[Page {page}] Failed with HTTP status {resp.status_code}")
                page += 1
                time.sleep(1)
                continue
                
            sel = Selector(resp.text)
            next_data_elem = sel.css("script#__NEXT_DATA__::text").get()
            
            if not next_data_elem:
                print(f"[Page {page}] No __NEXT_DATA__ element found.")
                page += 1
                continue
                
            data = json.loads(next_data_elem)
            comp_props = data.get("props", {}).get("pageProps", {}).get("componentProps", {})
            ads_data = comp_props.get("ads", {})
            ad_list = ads_data.get("ads", [])
            
            print(f"[Page {page}] Received {len(ad_list)} raw ads in payload.")
            
            page_extracted = 0
            for raw_ad in ad_list:
                parsed = parse_ad_data(raw_ad, scraped_date)
                if not parsed:
                    continue
                if parsed["id"] in seen_ids:
                    continue
                    
                seen_ids.add(parsed["id"])
                all_listings.append(parsed)
                page_extracted += 1
                
                if len(all_listings) >= target_count:
                    break
                    
            print(f"[Page {page}] Extracted {page_extracted} new unique listings. Total so far: {len(all_listings)}")
            
        except Exception as e:
            print(f"[Page {page}] Error during scraping: {e}")
            
        page += 1
        time.sleep(1.2)  # Polite crawl delay
        
    print(f"\nScraping complete! Total unique listings captured: {len(all_listings)}")
    return all_listings

def save_outputs(listings: list, json_path: str, csv_path: str):
    """Saves listings to JSON and CSV formats."""
    # 1. JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    print(f"Saved JSON to: {json_path}")
    
    # 2. CSV
    fieldnames = [
        "id", "platform", "title", "url", "transaction_type", "house_type",
        "city", "quartier", "price_raw", "price_mad", "surface_m2",
        "bedrooms", "bathrooms", "features", "description",
        "main_image", "images_count", "seller_type", "scraped_at"
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for item in listings:
            writer.writerow(item)
    print(f"Saved CSV to: {csv_path}")

def verify_outputs(json_path: str, csv_path: str):
    """Verifies file existence, sizes, and record count."""
    print("\n--- Output Verification ---")
    for path, name in [(json_path, "JSON"), (csv_path, "CSV")]:
        if not os.path.exists(path):
            print(f"ERROR: {name} file does not exist at {path}!")
            return False
        size_bytes = os.path.getsize(path)
        print(f"{name} file: {path}")
        print(f"  Size: {size_bytes / 1024:.2f} KB ({size_bytes} bytes)")
        
    with open(json_path, "r", encoding="utf-8") as f:
        json_records = json.load(f)
    print(f"JSON Record count: {len(json_records)}")
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        csv_records = list(reader)
    print(f"CSV Record count: {len(csv_records)}")
    
    if len(json_records) == len(csv_records) and len(json_records) >= 150:
        print(f"SUCCESS: Both files match with {len(json_records)} verified records (>= 150 target).")
        return True
    else:
        print(f"WARNING: Record counts or target criteria mismatch.")
        return False

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_output = os.path.join(current_dir, "avito_marrakech.json")
    csv_output = os.path.join(current_dir, "avito_marrakech.csv")
    
    # Target 250 listings (well within the 150-300 requirement)
    listings = scrape_avito_marrakech(target_count=250, max_pages=10)
    save_outputs(listings, json_output, csv_output)
    verify_outputs(json_output, csv_output)
