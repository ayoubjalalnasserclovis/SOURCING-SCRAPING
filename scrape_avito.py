#!/usr/bin/env python3
"""
Production scraper for Avito.ma Marrakech real estate listings.
Integrality scraper: scrapes all categories and all general real estate listings
in Marrakech using curl_cffi and Scrapling's Selector with high concurrency.
Constraint: Exactly ONE photo max per home scraped (stored in main_image as a string URL).
Saves complete output to avito_marrakech.json and avito_marrakech.csv.
"""

import sys
import io
import re
import json
import csv
import os
import time
import math
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests
from scrapling import Selector

# Ensure UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}

TARGET_CATEGORIES = [
    ("Appartements", "https://www.avito.ma/fr/marrakech/appartements"),
    ("Maisons et Villas", "https://www.avito.ma/fr/marrakech/maisons_et_villas"),
    ("Terrains et Fermes", "https://www.avito.ma/fr/marrakech/terrains_et_fermes"),
    ("Riads", "https://www.avito.ma/fr/marrakech/riads"),
    ("Commerces et Locaux", "https://www.avito.ma/fr/marrakech/commerces_et_locaux_industriels"),
    ("Bureaux et Plateaux", "https://www.avito.ma/fr/marrakech/bureaux_et_plateaux"),
    ("Immobilier Général", "https://www.avito.ma/fr/marrakech/immobilier"),
]

KNOWN_QUARTIERS = [
    "Guéliz", "Hivernage", "Palmeraie", "Médina", "Targa", "Agdal",
    "Majorelle", "M'Hamid", "Mhamid", "Daoudiate", "Sidi Youssef Ben Ali",
    "Massira", "Semlalia", "Route de Casablanca", "Route d'Ourika",
    "Route de Fès", "Route d'Amizmiz", "Route de Ouarzazate", "Route de Safi",
    "Route de Tahanaoute", "Chrifia", "Amerchich", "Victor Hugo",
    "Hay Izdihar", "Hay Riad", "Al Fadel", "Bab Doukkala", "Ain Mezouar",
    "Azzouzia", "Mabrouka", "Hay Charaf", "Es Saada", "Hay Andalous",
    "Centre Ville", "Av Mohammed VI", "Sidi Ghanem", "Camp Ghoul",
    "Prestigia", "Amelkis", "Al Maaden", "Sidi Abbad", "Kasbah",
    "Mellah", "Bab Atlas", "Samanah", "Golf City"
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
    """Classifies property into standardized house_type."""
    title_lower = title.lower()
    cat_lower = cat_name.lower()
    
    # 1. First priority: Title (most specific)
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
    if re.search(r"\b(?:maison|maisons|douiria)\b", title_lower):
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
        
    # 3. Third priority: Description
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

def extract_transaction_type(ad_type_obj: dict, cat_info: dict, title: str) -> str:
    """Classifies transaction_type as 'Vente' or 'Location'."""
    key = (ad_type_obj.get("key") or "").upper()
    if key == "SELL":
        return "Vente"
    if key in ("LET", "VAC_RENT", "CO_RENT"):
        return "Location"
    
    parent_id = str((cat_info.get("parent") or {}).get("id") or "")
    cat_id = str(cat_info.get("id") or "")
    if parent_id == "1200" or cat_id == "1200":
        return "Vente"
    if parent_id in ("1300", "1500", "1400") or cat_id in ("1300", "1500", "1400"):
        return "Location"

    label = (ad_type_obj.get("label") or "").lower()
    if "vente" in label or "vendre" in label:
        return "Vente"
    if "louer" in label or "location" in label or "vacance" in label or "colocation" in label:
        return "Location"
        
    cat_name = cat_info.get("name") or cat_info.get("formatted") or ""
    text = f"{cat_name} {title}".lower()
    if any(k in text for k in ["louer", "location", "vacance", "colocation", "nuitée"]):
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
        if loc_part.lower() in ("gueliz", "guéliz"): return "Guéliz"
        if loc_part.lower() in ("medina", "médina"): return "Médina"
        return loc_part
        
    m = re.search(r"avito\.ma/fr/([^/]+)/", url)
    if m:
        slug = m.group(1).replace("_", " ").title()
        if slug.lower() not in ("marrakech", "immobilier", "unite"):
            if slug.lower() in ("gueliz", "guéliz"): return "Guéliz"
            if slug.lower() in ("medina", "médina"): return "Médina"
            return slug
            
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
    """
    Parses an Avito ad dictionary into standardized schema.
    CRITICAL CONSTRAINT: Exactly ONE photo max stored in main_image as a single string URL.
    """
    if ad.get("isNc"):
        return None
        
    ad_id = str(ad.get("listId") or ad.get("id") or "")
    if not ad_id:
        return None
        
    title = (ad.get("subject") or "").strip()
    url = ad.get("href") or ""
    if not url.startswith("http"):
        url = f"https://www.avito.ma{url}"
        
    desc = (ad.get("description") or "").strip()
    
    cat_info = ad.get("category") or {}
    cat_name = cat_info.get("name") or cat_info.get("formatted") or ""
    ad_type_info = ad.get("adType") or {}
    
    transaction_type = extract_transaction_type(ad_type_info, cat_info, title)
    house_type = classify_house_type(title, cat_name, desc)
    
    loc = ad.get("location") or ""
    quartier = extract_quartier(loc, url, title, desc)
    
    price_info = ad.get("price") or {}
    price_val = price_info.get("value")
    price_mad = None
    price_raw = ""
    if price_val is not None:
        try:
            price_mad = int(float(price_val))
            price_raw = f"{price_mad:,} DH".replace(",", " ")
        except (ValueError, TypeError):
            pass
            
    if price_mad is None:
        m = re.search(r"(\d[\d\s.,]{2,})\s*(?:dh|dhs|mad)", f"{title} {desc}", re.IGNORECASE)
        if m:
            raw_digits = re.sub(r"[^\d]", "", m.group(1))
            if raw_digits:
                try:
                    price_mad = int(raw_digits)
                    price_raw = f"{price_mad:,} DH".replace(",", " ")
                except ValueError:
                    pass

    params_sec = (ad.get("params") or {}).get("secondary") or []
    param_dict = {}
    for p in params_sec:
        param_dict[p.get("key")] = p.get("value")
        
    surface_m2 = None
    if "size" in param_dict and param_dict["size"] is not None:
        try:
            surface_m2 = int(float(str(param_dict["size"]).replace(" ", "")))
        except (ValueError, TypeError):
            pass
    if surface_m2 is None:
        m = re.search(r"(\d+)\s*(?:m²|m2|mètres carrés|metres carres)", f"{title} {desc}", re.IGNORECASE)
        if m:
            try:
                surface_m2 = int(m.group(1))
            except ValueError:
                pass
            
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
            try:
                bedrooms = int(m.group(1))
            except ValueError:
                pass
            
    bathrooms = None
    if "bathrooms" in param_dict and param_dict["bathrooms"] is not None:
        try:
            bathrooms = int(param_dict["bathrooms"])
        except (ValueError, TypeError):
            pass
    if bathrooms is None:
        m = re.search(r"(\d+)\s*(?:salles?\s+de\s+bains?|sdbs?|sdb)", f"{title} {desc}", re.IGNORECASE)
        if m:
            try:
                bathrooms = int(m.group(1))
            except ValueError:
                pass

    features = extract_features(f"{title} {desc}")
    
    # ONE PHOTO MAX CONSTRAINT:
    # Strictly store main_image as a single string URL
    main_image = ad.get("defaultImage") or ""
    images_list = ad.get("images") or []
    images_count = len(images_list)
    
    # If defaultImage is missing or a generic placeholder, use first real image if present
    if (not main_image or "ad_pl_cat_" in main_image) and images_list:
        main_image = images_list[0]
        
    if not isinstance(main_image, str):
        main_image = str(main_image) if main_image else ""
    if images_count == 0 and main_image:
        images_count = 1
        
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
        "price_raw": price_raw,
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

# Thread-local storage for HTTP/2 persistent sessions
_thread_local = threading.local()

def get_session():
    if not hasattr(_thread_local, "session"):
        _thread_local.session = requests.Session(impersonate="chrome120")
    return _thread_local.session

def fetch_page_ads(url: str, page: int, retries: int = 3):
    """Fetches a single page and returns the parsed raw ads list."""
    page_url = f"{url}?o={page}" if page > 1 else url
    
    for attempt in range(retries):
        s = get_session()
        try:
            resp = s.get(page_url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                raw = None
                try:
                    sel = Selector(resp.text)
                    raw = sel.css("script#__NEXT_DATA__::text").get()
                except Exception:
                    pass
                if not raw:
                    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', resp.text, re.DOTALL)
                    if m:
                        raw = m.group(1)
                        
                if raw:
                    data = json.loads(raw)
                    comp = data.get("props", {}).get("pageProps", {}).get("componentProps", {})
                    ads_data = comp.get("ads", {})
                    ad_list = ads_data.get("ads", [])
                    return page, ad_list
            elif resp.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            elif resp.status_code == 404:
                return page, []
        except Exception:
            # Recreate session on network error
            try:
                _thread_local.session = requests.Session(impersonate="chrome120")
            except Exception:
                pass
            time.sleep(0.5 * (attempt + 1))
            
    return page, []

def save_outputs(listings: list, json_path: str, csv_path: str):
    """Atomically saves listings to JSON and CSV formats."""
    # Write JSON
    tmp_json = f"{json_path}.tmp"
    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    if os.path.exists(json_path):
        try: os.remove(json_path)
        except OSError: pass
    os.replace(tmp_json, json_path)
    
    # Write CSV
    tmp_csv = f"{csv_path}.tmp"
    fieldnames = [
        "id", "platform", "title", "url", "transaction_type", "house_type",
        "city", "quartier", "price_raw", "price_mad", "surface_m2",
        "bedrooms", "bathrooms", "features", "description",
        "main_image", "images_count", "seller_type", "scraped_at"
    ]
    with open(tmp_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for item in listings:
            writer.writerow(item)
    if os.path.exists(csv_path):
        try: os.remove(csv_path)
        except OSError: pass
    os.replace(tmp_csv, csv_path)

def scrape_full_avito_marrakech(max_workers: int = 12):
    """
    Main integrality scraper for Avito Marrakech.
    Systematically processes all categories and general listings.
    """
    start_time = time.time()
    scraped_date = datetime.now().strftime("%Y-%m-%d")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, "avito_marrakech.json")
    csv_path = os.path.join(current_dir, "avito_marrakech.csv")
    
    print(f"=== Starting Avito.ma Marrakech Integrality Scraper ===")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Concurrency: {max_workers} worker threads")
    
    all_listings = []
    seen_ids = set()
    lock = threading.Lock()
    
    # If existing data file exists, load IDs to avoid duplicate work if restarting
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
                for item in existing:
                    if item.get("id"):
                        seen_ids.add(str(item["id"]))
                        all_listings.append(item)
            print(f"Loaded {len(all_listings)} existing listings into memory.")
        except Exception as e:
            print(f"Could not load existing file: {e}")
            all_listings = []
            seen_ids = set()

    # Iterate through categories
    for cat_name, cat_url in TARGET_CATEGORIES:
        print(f"\n>>> Checking Category: {cat_name} ({cat_url})")
        # Step 1: Probe page 1 to get total listing count
        s = requests.Session(impersonate="chrome120")
        try:
            resp = s.get(cat_url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"Failed to access {cat_url}, status: {resp.status_code}")
                continue
            sel = Selector(resp.text)
            raw = sel.css("script#__NEXT_DATA__::text").get()
            if not raw:
                print(f"No __NEXT_DATA__ found for {cat_url}")
                continue
            data = json.loads(raw)
            comp = data.get("props", {}).get("pageProps", {}).get("componentProps", {})
            total_ads = comp.get("ads", {}).get("totalListingAds") or comp.get("facetedSearchResponse", {}).get("count", {}).get("total")
            if not total_ads:
                total_ads = 0
            total_ads = int(total_ads)
            total_pages = math.ceil(total_ads / 35) if total_ads > 0 else 1
            print(f"[{cat_name}] Total ads indexed: {total_ads} across ~{total_pages} pages.")
        except Exception as e:
            print(f"Error checking category {cat_name}: {e}")
            continue

        if total_pages == 0:
            continue

        # Step 2: Fetch all pages concurrently with ThreadPoolExecutor
        print(f"[{cat_name}] Scraping pages 1 to {total_pages} with {max_workers} threads...")
        pages = list(range(1, total_pages + 1))
        
        cat_extracted = 0
        pages_processed = 0
        consecutive_empty = 0

        # Process in batches of 100 pages for memory efficiency and checkpointing
        batch_size = 100
        for i in range(0, len(pages), batch_size):
            batch = pages[i:i + batch_size]
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(fetch_page_ads, cat_url, p): p for p in batch}
                for fut in as_completed(futures):
                    p = futures[fut]
                    try:
                        _, raw_ads = fut.result()
                    except Exception as e:
                        raw_ads = []
                    
                    pages_processed += 1
                    if not raw_ads:
                        consecutive_empty += 1
                        if consecutive_empty > 15:
                            # 15 consecutive empty pages indicates end of listings
                            pass
                        continue
                    else:
                        consecutive_empty = 0

                    with lock:
                        for ad in raw_ads:
                            parsed = parse_ad_data(ad, scraped_date)
                            if parsed and parsed["id"] not in seen_ids:
                                seen_ids.add(parsed["id"])
                                all_listings.append(parsed)
                                cat_extracted += 1

            print(f"  [{cat_name}] Progress: {pages_processed}/{total_pages} pages done | Category new: +{cat_extracted} | Grand total: {len(all_listings)}")
            
            # Periodic checkpoint save
            with lock:
                save_outputs(all_listings, json_path, csv_path)

        print(f"[{cat_name}] Completed! Extracted {cat_extracted} unique listings from this category.")

    # Final save and verification
    print("\n=== Finalizing Output Files ===")
    save_outputs(all_listings, json_path, csv_path)
    
    elapsed = time.time() - start_time
    json_size = os.path.getsize(json_path)
    csv_size = os.path.getsize(csv_path)
    
    print(f"\n=======================================================")
    print(f"SCRAPING RUN COMPLETE in {elapsed / 60:.2f} minutes ({elapsed:.1f}s)")
    print(f"Total Unique Listings Scraped: {len(all_listings):,}")
    print(f"JSON File: {json_path}")
    print(f"  Size: {json_size / (1024 * 1024):.2f} MB ({json_size:,} bytes)")
    print(f"CSV File:  {csv_path}")
    print(f"  Size: {csv_size / (1024 * 1024):.2f} MB ({csv_size:,} bytes)")
    print(f"=======================================================")
    
    return len(all_listings), json_size, csv_size

if __name__ == "__main__":
    scrape_full_avito_marrakech(max_workers=12)
