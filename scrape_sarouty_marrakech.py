#!/usr/bin/env python3
"""
Agency Portal Integrality Scraper (Sarouty / Selektimmo / Barnes Marrakech)
Deep crawl of agency properties in and near Marrakech.

Targets:
- Barnes-Marrakech.com (Luxury Agency Portal: Vente, Location, Saisonnier, Secteurs)
- Sarouty.ma / Property Finder & Selektimmo (Categories, Quartiers, Peripheries)

Constraints:
- curl_cffi with chrome120 & safari17_0 impersonation
- ONE PHOTO MAX PER HOME SCRAPED: main_image (single string URL, no galleries)
- Standardized fields: id, platform, title, url, transaction_type, house_type,
  city='Marrakech', quartier, price_raw, price_mad, surface_m2, bedrooms,
  bathrooms, features, description, main_image, seller_type='Professionnel', scraped_at.
- Output: sarouty_marrakech.json and sarouty_marrakech.csv
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

# French word to number mapping
WORD_TO_NUM = {
    'un': 1, 'une': 1, 'deux': 2, 'trois': 3, 'quatre': 4,
    'cinq': 5, 'six': 6, 'sept': 7, 'huit': 8, 'neuf': 9, 'dix': 10
}

def parse_number_word(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    val = str(val).lower().strip()
    if val in WORD_TO_NUM:
        return WORD_TO_NUM[val]
    nums = re.findall(r'\d+', val)
    return int(nums[0]) if nums else None

def parse_price(price_raw):
    if not price_raw:
        return '', None
    clean = str(price_raw).strip()
    digits = re.sub(r'[^\d]', '', clean)
    if not digits:
        return clean, None
    val = int(digits)
    # Currency conversion: 1 EUR = 10.8 MAD (standard luxury real estate conversion in Morocco)
    if 'EUR' in clean or '€' in clean:
        price_mad = int(val * 10.8)
    else:
        price_mad = val
    return clean, price_mad

def extract_features_from_text(text):
    """Extract standard real estate amenities from French text."""
    if not text:
        return []
    t = text.lower()
    features = []
    amenity_map = [
        ("piscine", "Piscine"),
        ("jardin", "Jardin"),
        ("terrasse", "Terrasse"),
        ("meublé", "Meublé"),
        ("meuble", "Meublé"),
        ("climatisation", "Climatisation"),
        ("climatisé", "Climatisation"),
        ("garage", "Garage"),
        ("parking", "Parking"),
        ("gardien", "Gardien"),
        ("sécurité", "Sécurité"),
        ("ascenseur", "Ascenseur"),
        ("vue atlas", "Vue Atlas"),
        ("vue montagne", "Vue Montagne"),
        ("hammam", "Hammam"),
        ("spa", "Spa"),
        ("jacuzzi", "Jacuzzi"),
        ("cheminée", "Cheminée"),
        ("cuisine équipée", "Cuisine équipée"),
        ("suite parentale", "Suites parentales"),
        ("golf", "Proximité Golf"),
        ("calme", "Calme absolu"),
        ("solarium", "Solarium"),
        ("domotique", "Domotique")
    ]
    for pattern, label in amenity_map:
        if pattern in t and label not in features:
            features.append(label)
    return features


# ==============================================================================
# 1. BARNES MARRAKECH SCRAPER
# ==============================================================================

def scrape_barnes_marrakech(max_workers=8):
    print("=" * 70)
    print("STARTING BARNES MARRAKECH LUXURY AGENCY SCRAPER")
    print("=" * 70)

    session = Session(impersonate="chrome120")
    listings_dict = {}

    search_sections = [
        # (Transaction, Base URL, Max Pages)
        ("Vente", "https://www.barnes-marrakech.com/fr/vente/marrakech.html", 16),
        ("Location", "https://www.barnes-marrakech.com/fr/location/marrakech.html", 5),
        ("Location", "https://www.barnes-marrakech.com/fr/location-saisonniere/marrakech.html", 5),
        ("Vente", "https://www.barnes-marrakech.com/fr/vente/villa-marrakech.html", 15),
        ("Vente", "https://www.barnes-marrakech.com/fr/vente/riad-marrakech.html", 6),
        ("Vente", "https://www.barnes-marrakech.com/fr/vente/appartement-marrakech.html", 6),
        ("Vente", "https://www.barnes-marrakech.com/fr/vente/terrain-marrakech.html", 4),
        ("Vente", "https://www.barnes-marrakech.com/fr/vente/secteur-palmeraie.html", 8),
        ("Vente", "https://www.barnes-marrakech.com/fr/vente/secteur-hivernage.html", 5),
        ("Vente", "https://www.barnes-marrakech.com/fr/vente/secteur-gueliz.html", 5),
        ("Vente", "https://www.barnes-marrakech.com/fr/vente/secteur-golf-amelkis.html", 5),
        ("Vente", "https://www.barnes-marrakech.com/fr/vente/secteur-golf-royal-palm-marrakech.html", 5),
        ("Vente", "https://www.barnes-marrakech.com/fr/vente/secteur-route-d-amizmiz.html", 5),
        ("Vente", "https://www.barnes-marrakech.com/fr/vente/secteur-route-de-l-ourika.html", 5),
        ("Vente", "https://www.barnes-marrakech.com/fr/vente/secteur-route-de-ouarzazate.html", 5),
    ]

    for default_tx, base_url, max_p in search_sections:
        for p in range(1, max_p + 1):
            url = f"{base_url}?page={p}" if p > 1 else base_url
            try:
                resp = None
                for attempt in range(3):
                    try:
                        resp = session.get(url, timeout=25)
                        if resp.status_code == 200:
                            break
                    except Exception:
                        time.sleep(1.5)
                if not resp or resp.status_code != 200:
                    break

                sel = Selector(resp.text)
                cards = sel.css("div.card")
                if not cards:
                    break

                page_new = 0
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

                    # Card fields
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
                    combined_txt = f"{alt_title} {p_text} {href}".lower()
                    house_type = "Villa"
                    if "riad" in combined_txt:
                        house_type = "Riad"
                    elif "appartement" in combined_txt or "duplex" in combined_txt:
                        house_type = "Appartement"
                    elif "terrain" in combined_txt:
                        house_type = "Terrain"
                    elif "immeuble" in combined_txt:
                        house_type = "Immeuble"

                    # Bedrooms & Surface from card
                    bedrooms = None
                    m_bed = re.search(r'(\d+)\s*Chambres?', p_text, re.IGNORECASE)
                    if m_bed:
                        bedrooms = int(m_bed.group(1))

                    surface_m2 = None
                    m_surf = re.search(r'(\d+)\s*m', p_text, re.IGNORECASE)
                    if m_surf:
                        surface_m2 = int(m_surf.group(1))

                    price_str, price_mad = parse_price(price_raw)
                    tx_type = "Location" if ("location" in href.lower() or "location" in base_url.lower()) else default_tx

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
                        "seller_type": "Professionnel",
                        "scraped_at": datetime.now().strftime("%Y-%m-%d")
                    }
                    page_new += 1

                # If no new listings found on page, continue
            except Exception as e:
                print(f"  [!] Error on Barnes {url}: {e}")
                break

    print(f"Discovered {len(listings_dict)} unique listings from Barnes search index.")
    print("Enriching Barnes listings with detail pages...")

    # Detail enricher
    def enrich_barnes(item):
        url = item["url"]
        worker_session = Session(impersonate="chrome120")
        detail_html = None
        for _ in range(3):
            try:
                r = worker_session.get(url, timeout=25)
                if r.status_code == 200:
                    detail_html = r.text
                    break
            except Exception:
                time.sleep(1)

        if not detail_html:
            return item

        sel = Selector(detail_html)

        # Title
        h1 = sel.css("h1::text").get()
        if h1 and h1.strip():
            item["title"] = h1.strip()

        # Price refinement if missing
        if not item["price_raw"] or not item["price_mad"]:
            price_el = sel.css(".product-price::text")
            if price_el:
                p_raw, p_mad = parse_price(price_el.get())
                if p_raw:
                    item["price_raw"] = p_raw
                    item["price_mad"] = p_mad

        # Info block
        info_text = ""
        if sel.css(".div-information"):
            info_text = " ".join(sel.css(".div-information")[0].css("::text").getall())

        m_q = re.search(r'Quartier\s+([^\n\r,]+)', info_text)
        if m_q:
            clean_q = re.sub(r'\s+', ' ', m_q.group(1)).strip()
            if clean_q and "Genre" not in clean_q and "Equipements" not in clean_q:
                item["quartier"] = clean_q

        m_type = re.search(r'Type\s+([A-Za-zÀ-ÿ]+)', info_text)
        if m_type:
            ht = m_type.group(1).capitalize()
            if ht in ["Villa", "Appartement", "Riad", "Terrain", "Duplex", "Immeuble"]:
                item["house_type"] = ht

        if not item["surface_m2"]:
            m_surf = re.search(r'(?:Sur\.\s*habitable|surface)\s*(\d+)\s*m', info_text, re.IGNORECASE)
            if m_surf:
                item["surface_m2"] = int(m_surf.group(1))

        if not item["bedrooms"]:
            m_bed = re.search(r'chambres?\s*(\d+)', info_text, re.IGNORECASE)
            if m_bed:
                item["bedrooms"] = int(m_bed.group(1))

        # Amenities / Features
        features = [x.strip() for x in sel.css(".div-amenities li::text, .div-amenities div.col-12::text").getall() if x.strip() and x.strip() != "Equipements"]
        item["features"] = list(dict.fromkeys(features))

        # Description
        desc_el = sel.css(".div-description, .description")
        if desc_el:
            lines = [t.strip() for t in desc_el[0].css("::text").getall() if t.strip() and "Partager" not in t and "honoraires" not in t]
            item["description"] = " ".join(lines)
        if not item["features"] and item["description"]:
            item["features"] = extract_features_from_text(item["description"])

        # Bathrooms
        desc = item["description"]
        m_b = re.search(r'(\d+|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix)\s*salles?\s*(?:de\s*bains?|d\'eau)', desc, re.IGNORECASE)
        if m_b:
            item["bathrooms"] = parse_number_word(m_b.group(1))
        elif "suite" in desc.lower():
            m_s = re.search(r'(\d+|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix)\s*suites?', desc, re.IGNORECASE)
            if m_s:
                item["bathrooms"] = parse_number_word(m_s.group(1))
        if item["bathrooms"] is None and item["bedrooms"] and item["house_type"] in ["Villa", "Riad"]:
            item["bathrooms"] = item["bedrooms"]

        # High resolution single main image
        img_el = sel.css("img.lazy, .carousel-item img, .detail-image img")
        for im in img_el:
            src = im.attrib.get("data-src") or im.attrib.get("src")
            if src and "produits" in src and "logo" not in src:
                item["main_image"] = src
                break

        return item

    enriched_barnes = []
    items_to_enrich = list(listings_dict.values())
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(enrich_barnes, it): it for it in items_to_enrich}
        done = 0
        for f in as_completed(futures):
            res = f.result()
            enriched_barnes.append(res)
            done += 1
            if done % 50 == 0 or done == len(items_to_enrich):
                print(f"  Enriched Barnes: {done}/{len(items_to_enrich)}")

    print(f"Barnes Marrakech complete: {len(enriched_barnes)} listings enriched.")
    return enriched_barnes


# ==============================================================================
# 2. SAROUTY.MA & SELEKTIMMO SCRAPER
# ==============================================================================

def scrape_sarouty_and_selektimmo(max_workers=8):
    print("\n" + "=" * 70)
    print("STARTING SAROUTY.MA & SELEKTIMMO DEEP CRAWLER")
    print("=" * 70)

    session = Session(impersonate="safari17_0")
    candidate_urls = set()

    # Category endpoints
    categories = [
        "https://www.sarouty.ma/acheter/marrakech/proprietes-a-vendre/",
        "https://www.sarouty.ma/acheter/marrakech/appartements-a-vendre/",
        "https://www.sarouty.ma/acheter/marrakech/villas-a-vendre/",
        "https://www.sarouty.ma/acheter/marrakech/riads-a-vendre/",
        "https://www.sarouty.ma/acheter/marrakech/terrains-a-vendre/",
        "https://www.sarouty.ma/acheter/marrakech/duplex-a-vendre/",
        "https://www.sarouty.ma/commercial-a-vendre/marrakech/",
        "https://www.sarouty.ma/louer/marrakech/proprietes-a-louer/",
        "https://www.sarouty.ma/louer/marrakech/appartements-a-louer/",
        "https://www.sarouty.ma/louer/marrakech/villas-a-louer/",
        "https://www.sarouty.ma/louer/marrakech/riads-a-louer/",
        "https://www.sarouty.ma/louer/marrakech/duplex-a-louer/",
        "https://www.sarouty.ma/commercial-a-louer/marrakech/"
    ]

    # Quartier endpoints
    quartiers = [
        "palmeraie", "gueliz", "hivernage", "ancienne-medina", "medina",
        "agdal", "targa", "chrifia", "route-d-ourika", "amelkis",
        "route-amizmiz", "mhamid", "majorelle", "semlalia", "victor-hugo",
        "daoudiate", "sidi-ghanem", "massira", "tamesloht", "tahanaout",
        "route-de-casablanca", "route-de-fes", "sidi-abdellah-ghiat",
        "bab-atlas", "camp-marseillais", "asni", "marrakech-plaza"
    ]

    quartier_urls = []
    for q in quartiers:
        quartier_urls.append(f"https://www.sarouty.ma/acheter/marrakech/{q}/")
        quartier_urls.append(f"https://www.sarouty.ma/louer/marrakech/{q}/")

    # Selektimmo portal homepage links
    selektimmo_urls = ["https://www.selektimmo.com/"]

    all_crawl_urls = categories + quartier_urls + selektimmo_urls
    print(f"Crawling {len(all_crawl_urls)} discovery entry points across Sarouty & Selektimmo...")

    for url in all_crawl_urls:
        try:
            r = None
            for attempt in range(2):
                try:
                    r = session.get(url, timeout=15)
                    if r.status_code == 200:
                        break
                except Exception:
                    time.sleep(1)
            if not r or r.status_code != 200:
                continue

            sel = Selector(r.text)
            links = sel.css("a::attr(href)").getall()
            for l in links:
                if not l:
                    continue
                # Normalize URL
                if l.startswith("/"):
                    l = "https://www.sarouty.ma" + l
                # Match property detail pages in Marrakech
                if ("/acheter/" in l or "/louer/" in l or "/commercial" in l) and any(c.isdigit() for c in l):
                    if "marrakech" in l.lower() or any(q in l.lower() for q in ["palmeraie", "gueliz", "hivernage", "medina", "ourika", "amizmiz", "chrifia", "targa", "amelkis"]):
                        candidate_urls.add(l.split("?")[0].rstrip("/"))
        except Exception as e:
            pass

    print(f"Discovered {len(candidate_urls)} distinct Sarouty Marrakech listing URLs.")
    print("Enriching Sarouty listings via Schema.org JSON-LD and detail extractors...")

    # Worker for Sarouty detail enrichment
    def enrich_sarouty(url):
        worker_session = Session(impersonate="safari17_0")
        detail_html = None
        for _ in range(3):
            try:
                r = worker_session.get(url, timeout=20)
                if r.status_code == 200:
                    detail_html = r.text
                    break
            except Exception:
                time.sleep(1)

        if not detail_html:
            return None

        sel = Selector(detail_html)

        # 1. Check Schema.org JSON-LD
        ld_data = {}
        for j in sel.css('script[type="application/ld+json"]::text').getall():
            try:
                d = json.loads(j)
                if d.get("@type") == "RealEstateListing":
                    ld_data = d
                    break
            except Exception:
                pass

        # ID from URL
        m_id = re.search(r'(\d+)$', url)
        lid = m_id.group(1) if m_id else str(abs(hash(url)))

        # Transaction type
        tx_type = "Location" if "/louer/" in url.lower() or "louer" in url.lower() else "Vente"

        # Title
        title = ld_data.get("name")
        if title:
            title = re.sub(r'\s*\|\s*Sarouty.*$', '', title).strip()
        if not title:
            h1 = sel.css("h1::text").get()
            title = h1.strip() if h1 else f"{tx_type} Propriété Marrakech"

        # House Type
        url_and_title = f"{url} {title}".lower()
        house_type = "Villa"
        if "riad" in url_and_title:
            house_type = "Riad"
        elif "appartement" in url_and_title:
            house_type = "Appartement"
        elif "duplex" in url_and_title:
            house_type = "Duplex"
        elif "terrain" in url_and_title:
            house_type = "Terrain"
        elif "bureau" in url_and_title or "commercial" in url_and_title or "magasin" in url_and_title:
            house_type = "Commercial"
        elif "immeuble" in url_and_title:
            house_type = "Immeuble"

        # Quartier
        quartier = "Marrakech"
        if ld_data.get("address", {}).get("addressLocality"):
            quartier = ld_data["address"]["addressLocality"].strip()
        else:
            # Extract from URL slug e.g. villa-marrakech-route-d-ourika-903788
            m_slug = re.search(r'-(?:marrakech-)?([a-z\-]+)-\d+$', url.lower())
            if m_slug:
                quartier = m_slug.group(1).replace("-", " ").title()

        # Price
        price_val = ld_data.get("offers", {}).get("price")
        price_curr = ld_data.get("offers", {}).get("priceCurrency") or "MAD"
        price_raw = ""
        price_mad = None
        if price_val:
            try:
                price_mad = int(price_val)
                price_raw = f"{price_mad:,} {price_curr}".replace(",", " ")
            except Exception:
                price_raw, price_mad = parse_price(str(price_val))

        # Surface
        surface_m2 = None
        fs = ld_data.get("floorSize")
        if isinstance(fs, dict):
            surface_m2 = parse_number_word(fs.get("value"))
        elif fs:
            surface_m2 = parse_number_word(fs)

        # Bedrooms & Bathrooms
        bedrooms = parse_number_word(ld_data.get("numberOfBedrooms"))
        bathrooms = parse_number_word(ld_data.get("numberOfBathroomsTotal"))

        # Description
        description = ld_data.get("description") or ""

        # Single main image
        main_img = ld_data.get("image") or ""
        if not main_img:
            # Fallback to page img
            for im in sel.css("img::attr(src), img::attr(data-src)").getall():
                if "property" in im or "upload" in im:
                    main_img = im
                    break

        # Features
        features = extract_features_from_text(description + " " + title)

        return {
            "id": str(lid),
            "platform": "sarouty",
            "title": title,
            "url": url,
            "transaction_type": tx_type,
            "house_type": house_type,
            "city": "Marrakech",
            "quartier": quartier,
            "price_raw": price_raw,
            "price_mad": price_mad,
            "surface_m2": surface_m2,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "features": features,
            "description": description,
            "main_image": main_img,
            "seller_type": "Professionnel",
            "scraped_at": datetime.now().strftime("%Y-%m-%d")
        }

    enriched_sarouty = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(enrich_sarouty, u): u for u in candidate_urls}
        done = 0
        for f in as_completed(futures):
            res = f.result()
            if res and res["id"]:
                enriched_sarouty.append(res)
            done += 1
            if done % 20 == 0 or done == len(candidate_urls):
                print(f"  Enriched Sarouty: {done}/{len(candidate_urls)}")

    print(f"Sarouty complete: {len(enriched_sarouty)} listings enriched.")
    return enriched_sarouty


# ==============================================================================
# 3. COMBINATION, VALIDATION & EXPORT
# ==============================================================================

def save_master_listings(listings, json_path="sarouty_marrakech.json", csv_path="sarouty_marrakech.csv"):
    print("\n" + "=" * 70)
    print(f"SAVING & VALIDATING DATASET ({len(listings)} LISTINGS)")
    print("=" * 70)

    # Deduplicate strictly by ID
    deduped = {}
    for it in listings:
        lid = str(it["id"])
        # Ensure single string image (CRITICAL CONSTRAINT: 1 PHOTO MAX)
        img = it.get("main_image")
        if isinstance(img, list):
            it["main_image"] = img[0] if img else ""
        elif not isinstance(img, str):
            it["main_image"] = str(img) if img else ""

        # Guarantee standard fields
        cleaned_item = {
            "id": str(it.get("id", "")),
            "platform": it.get("platform", "sarouty"),
            "title": str(it.get("title", "")).strip(),
            "url": str(it.get("url", "")).strip(),
            "transaction_type": str(it.get("transaction_type", "Vente")).strip(),
            "house_type": str(it.get("house_type", "Villa")).strip(),
            "city": "Marrakech",
            "quartier": str(it.get("quartier", "Marrakech")).strip(),
            "price_raw": str(it.get("price_raw", "")).strip(),
            "price_mad": it.get("price_mad"),
            "surface_m2": it.get("surface_m2"),
            "bedrooms": it.get("bedrooms"),
            "bathrooms": it.get("bathrooms"),
            "features": it.get("features", []),
            "description": str(it.get("description", "")).strip(),
            "main_image": it.get("main_image", ""),
            "images_count": 1 if it.get("main_image") else 0,
            "seller_type": "Professionnel",
            "scraped_at": it.get("scraped_at", datetime.now().strftime("%Y-%m-%d"))
        }
        deduped[lid] = cleaned_item

    final_list = list(deduped.values())

    # 1. Save JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_list, f, ensure_ascii=False, indent=2)
    json_size = os.path.getsize(json_path)
    print(f"Saved JSON: {json_path} -> {len(final_list)} records, {json_size:,} bytes")

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
        for item in final_list:
            row = dict(item)
            if isinstance(row.get("features"), list):
                row["features"] = "; ".join(row["features"])
            writer.writerow(row)
    csv_size = os.path.getsize(csv_path)
    print(f"Saved CSV:  {csv_path} -> {len(final_list)} records, {csv_size:,} bytes")

    return final_list, json_size, csv_size


def main():
    start_time = time.time()

    # 1. Scrape Barnes Marrakech (Premier luxury agency portal in Marrakech)
    barnes_listings = scrape_barnes_marrakech(max_workers=8)

    # 2. Scrape Sarouty.ma & Selektimmo (Property Finder network)
    sarouty_listings = scrape_sarouty_and_selektimmo(max_workers=8)

    # Combine datasets
    all_listings = barnes_listings + sarouty_listings

    # Save to sarouty_marrakech.json and sarouty_marrakech.csv
    json_path = "sarouty_marrakech.json"
    csv_path = "sarouty_marrakech.csv"
    final_listings, json_size, csv_size = save_master_listings(all_listings, json_path, csv_path)

    # Platform breakdown stats
    platforms = {}
    house_types = {}
    for it in final_listings:
        p = it["platform"]
        platforms[p] = platforms.get(p, 0) + 1
        ht = it["house_type"]
        house_types[ht] = house_types.get(ht, 0) + 1

    duration = time.time() - start_time
    print("\n" + "=" * 70)
    print("INTEGRALITY SCRAPE COMPLETE - FINAL AUDIT REPORT")
    print("=" * 70)
    print(f"Total Unique Listings: {len(final_listings)}")
    print(f"Platform Breakdown:    {platforms}")
    print(f"House Type Breakdown:  {house_types}")
    print(f"JSON File:             {json_path} ({json_size:,} bytes)")
    print(f"CSV File:              {csv_path} ({csv_size:,} bytes)")
    print(f"Execution Duration:    {duration:.2f} seconds")
    print("=" * 70)

if __name__ == "__main__":
    main()
