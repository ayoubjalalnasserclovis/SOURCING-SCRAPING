#!/usr/bin/env python3
"""
Production Scraper for Kensington Luxury Properties in Marrakech
(Christie's International Real Estate affiliate)

Extracts all luxury listings in Marrakech:
- Villas, palatial estates, golf residences, luxury riads, apartments, and land.
- Standardized fields:
  id, platform, title, url, transaction_type, house_type, city, quartier,
  price_raw, price_mad, surface_m2, bedrooms, bathrooms, features,
  description, main_image, images_count, seller_type, scraped_at.
- Saves output to kensington_marrakech.json and kensington_marrakech.csv.
"""

import os
import sys
import re
import csv
import json
import time
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests
from scrapling import Selector

# Ensure UTF-8 output on Windows consoles
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_URL = "https://www.kensingtonmorocco.com"
LISTING_BASE = "https://www.kensingtonmorocco.com/proprietes/marrakech/"
MAX_PAGES = 75
WORKERS_LISTING = 10
WORKERS_DETAIL = 12
REQUEST_TIMEOUT = 25

KNOWN_QUARTIERS = [
    'Palmeraie', 'Amelkis', 'Hivernage', 'Guéliz', 'Gueliz', "Route de l'Ourika",
    "Route d'Ourika", 'Route de Fès', 'Route de Casablanca', "Route d'Amizmiz", 'Route Amizmiz',
    'Route du Barrage', 'Route de Tahanaout', 'Al Maaden', 'Medina', 'Médina',
    'Targa', 'Agdal', 'Samanah', 'Royal Palm', 'Chrifia', 'Mhamid', 'Majorelle',
    'Sidi Ghanem', 'Camp de Base', 'Bab Atlas', 'Ain Itti', 'Daoudiate',
    'Sidi Abdallah Ghiat', 'Massira', 'Semlalia', 'Tassoultante', 'Victor Hugo',
    'Golf City', 'Noria', 'Argan Golf'
]

def clean_quartier(q: str) -> str:
    ql = q.lower().strip()
    if ql in ['medina', 'médina']:
        return 'Médina'
    elif ql in ['gueliz', 'guéliz']:
        return 'Guéliz'
    elif 'palmeraie' in ql:
        return 'Palmeraie'
    elif 'amelkis' in ql:
        return 'Amelkis'
    elif 'hivernage' in ql:
        return 'Hivernage'
    elif 'al maaden' in ql:
        return 'Al Maaden'
    elif 'amizmiz' in ql:
        return "Route d'Amizmiz"
    elif 'ourika' in ql:
        return "Route de l'Ourika"
    elif 'tahanaout' in ql:
        return "Route de Tahanaout"
    elif 'fès' in ql or 'fes' in ql:
        return "Route de Fès"
    elif 'casablanca' in ql:
        return "Route de Casablanca"
    elif 'samanah' in ql:
        return 'Samanah'
    elif 'royal palm' in ql:
        return 'Royal Palm'
    elif 'targa' in ql:
        return 'Targa'
    elif 'agdal' in ql:
        return 'Agdal'
    return q.title()

def extract_neighborhood(card_loc: str, title: str, desc: str, url: str) -> str:
    if 'Marrakech -' in card_loc:
        q = card_loc.split('Marrakech -')[-1].strip()
        if q:
            return clean_quartier(q)
    elif 'Marrakech' in card_loc and len(card_loc.replace('Marrakech', '').strip(' -/,')) > 2:
        return clean_quartier(card_loc.replace('Marrakech', '').strip(' -/,'))

    scope = f"{title} {url} {desc}"
    for kq in KNOWN_QUARTIERS:
        if re.search(r'\b' + re.escape(kq) + r'\b', scope, re.IGNORECASE):
            return clean_quartier(kq)
    
    return 'Marrakech'

def fetch_listing_page(page_num: int):
    url = f"{LISTING_BASE}?_pagination_properties={page_num}"
    retries = 3
    for attempt in range(retries):
        try:
            resp = requests.get(url, impersonate='chrome120', timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return page_num, []
            
            sel = Selector(resp.content.decode('utf-8', errors='replace'))
            cards = sel.css('.wpgb-card')
            items = []
            for c in cards:
                link = c.css('a::attr(href)').get('')
                if not link or 'marrakech' not in link.lower():
                    continue
                if not link.startswith('http'):
                    link = BASE_URL + link
                
                title = c.css('h2::text').get('').strip()
                price = " ".join([t.strip() for t in c.css('ul.reset li::text').getall() if t.strip()])
                has_euro = bool(c.css('.fa-euro-sign'))
                loc = " ".join([t.strip() for t in c.xpath('.//p[contains(text(), "Marrakech")]//text()').getall() if t.strip()])
                
                img = c.css('img::attr(src)').get('')
                srcset = c.css('img::attr(srcset)').get('')
                if srcset:
                    parts = [p.strip().split(' ') for p in srcset.split(',') if p.strip()]
                    if parts:
                        img = parts[-1][0]
                
                excerpt = " ".join([t.strip() for t in c.xpath('.//div[contains(@style, "color: var(--shade-dark)")]//text()').getall() if t.strip()])
                
                items.append({
                    'url': link,
                    'title': title,
                    'price_raw_card': price,
                    'has_euro': has_euro,
                    'loc_card': loc,
                    'img_card': img,
                    'excerpt': excerpt
                })
            return page_num, items
        except Exception as e:
            if attempt == retries - 1:
                print(f"[!] Error fetching page {page_num}: {e}")
                return page_num, []
            time.sleep(1)

def fetch_and_parse_property(card_data: dict) -> dict:
    url = card_data['url']
    html = ""
    retries = 3
    for attempt in range(retries):
        try:
            resp = requests.get(url, impersonate='chrome120', timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                html = resp.content.decode('utf-8', errors='replace')
                break
        except Exception as e:
            if attempt == retries - 1:
                print(f"[!] Warning: failed to fetch detail for {url}: {e}")
            time.sleep(0.5)

    sel = Selector(html) if html else None

    # 1. ID & Ref
    prop_id = None
    if sel:
        ref_el = sel.css('.property-price-bloc .size-16::text').get()
        if ref_el and 'Ref:' in ref_el:
            prop_id = ref_el.replace('Ref:', '').strip()
    if not prop_id:
        # Fallback to URL slug
        prop_id = url.rstrip('/').split('/')[-1]

    # 2. Platform
    platform = 'kensington'

    # 3. Title
    title = card_data.get('title', '')
    if not title and sel:
        # Extract from title tag
        page_title = sel.css('title::text').get('')
        if '|' in page_title:
            title = page_title.split('|')[0].strip()
        else:
            title = sel.css('h2::text').get('') or sel.css('h1::text').get('')
    if not title:
        title = prop_id.replace('-', ' ').title()

    # 4. URL
    full_url = url

    # 5. Transaction Type: 'Vente' or 'Location'
    card_price_text = card_data.get('price_raw_card', '').strip()
    detail_price_text = ""
    if sel:
        price_bloc = sel.css('.property-price-bloc')
        detail_price_text = " ".join(price_bloc.css('.size-22::text').getall()).strip()

    combined_price_str = f"{detail_price_text} {card_price_text}".lower()
    
    if any(k in url.lower() for k in ['/location', '/locations', '/vacances']) or \
       any(k in combined_price_str for k in ['mois', 'semaine', 'nuit', 'month', 'week', 'night']):
        trans_type = 'Location'
    else:
        trans_type = 'Vente'

    # 6. House Type: 'Villa', 'Riad', 'Appartement', 'Terrain', etc.
    headings = " ".join(sel.css('h1::text').getall()) if sel else ""
    full_text_lower = f"{url} {title} {headings} {card_data.get('excerpt', '')}".lower()
    
    if 'riad' in full_text_lower or 'dar ' in full_text_lower:
        house_type = 'Riad'
    elif any(k in full_text_lower for k in ['appartement', 'apartment', 'penthouse', 'duplex', 'studio']):
        house_type = 'Appartement'
    elif any(k in full_text_lower for k in ['terrain', 'land', 'parcelle', 'lot']):
        house_type = 'Terrain'
    elif any(k in full_text_lower for k in ['palais', 'palace']):
        house_type = 'Palais'
    elif any(k in full_text_lower for k in ['commercial', 'bureau', 'commerce', 'fond de commerce']):
        house_type = 'Commercial'
    elif any(k in full_text_lower for k in ['hotel', 'hôtel', "maison d'hôte", "maison d'hote"]):
        house_type = 'Hôtel'
    elif any(k in full_text_lower for k in ['villa', 'propriété', 'demeure', 'maison', 'residence', 'résidence']):
        house_type = 'Villa'
    else:
        house_type = 'Villa'

    # 7. City
    city = 'Marrakech'

    # 8. Description
    description = ""
    if sel:
        left_col = sel.xpath('//section[2]//div[contains(@class, "grid--2-1")]/div[1]')
        desc_blocks = left_col.css('div.ct-code-block')
        desc_texts = []
        for db in desc_blocks:
            t = " ".join(db.css('::text').getall()).strip()
            if len(t) > 35 and not any(k in t.lower() for k in ['retour']):
                desc_texts.append(t)
        if desc_texts:
            description = max(desc_texts, key=len)
    
    if not description:
        description = card_data.get('excerpt', '')

    # 9. Quartier
    quartier = extract_neighborhood(
        card_loc=card_data.get('loc_card', ''),
        title=title,
        desc=description,
        url=url
    )

    # 10. Price raw & Price MAD
    p_text = detail_price_text or card_price_text
    p_clean = p_text.replace('\xa0', ' ').strip()

    price_raw = None
    price_mad = None
    is_euro = False
    is_mad = False

    if not p_clean or 'psd' in p_clean.lower() or 'demande' in p_clean.lower():
        price_raw = 'Prix sur demande'
        price_mad = None
    else:
        if '€' in p_clean or (sel and bool(sel.css('.property-price-bloc .fa-euro-sign'))) or card_data.get('has_euro'):
            is_euro = True
        elif 'dh' in p_clean.lower() or 'mad' in p_clean.lower():
            is_mad = True

        digits_str = re.sub(r'[^\d]', '', p_clean.split('/')[0])
        if digits_str:
            amt = int(digits_str)
            period = ""
            if '/ mois' in p_clean.lower() or 'mois' in p_clean.lower():
                period = " / Mois"
            elif '/ semaine' in p_clean.lower() or 'semaine' in p_clean.lower():
                period = " / Semaine"
            elif '/ nuit' in p_clean.lower() or 'nuit' in p_clean.lower():
                period = " / Nuit"

            if is_mad:
                price_raw = f"{amt:,} MAD{period}".replace(',', ' ')
                price_mad = amt
            else:
                # Default currency is EUR on Kensington
                price_raw = f"€{amt:,}{period}".replace(',', ' ')
                price_mad = int(round(amt * 10.8))
        else:
            price_raw = p_clean or 'Prix sur demande'
            price_mad = None

    # 11. Surface m2, Bedrooms, Bathrooms
    surface_m2 = None
    bedrooms = None
    bathrooms = None

    if sel:
        # Overview specs in section 2
        spec_p_elements = sel.xpath('//section[2]//div[contains(@class, "grid--3") or contains(@class, "grid")]/p')
        for p in spec_p_elements:
            p_sel = Selector(p.get())
            classes = p_sel.css('i::attr(class)').get() or ''
            text = " ".join(p_sel.css('::text').getall()).strip()
            
            # Bed
            if 'fa-bed' in classes or 'chambre' in text.lower():
                m = re.search(r'(\d+)', text)
                if m:
                    bedrooms = int(m.group(1))
            # Surface habitable
            elif 'fa-house' in classes:
                m = re.search(r'(\d+[\s\d]*)', text.replace('\xa0', ' '))
                if m:
                    surface_m2 = int(re.sub(r'\s+', '', m.group(1)))
            # Surface ruler (plot or habitable fallback)
            elif ('fa-ruler' in classes or 'm²' in text or 'm2' in text) and surface_m2 is None:
                m = re.search(r'(\d+[\s\d]*)', text.replace('\xa0', ' '))
                if m:
                    surface_m2 = int(re.sub(r'\s+', '', m.group(1)))

        # Detailed rooms list
        room_lis = sel.xpath('//section[2]//ul[contains(@class, "grid--2")]/li//text()').getall()
        rooms_text = " | ".join([r.strip() for r in room_lis if r.strip()])
        
        # Check bathrooms
        m_bath = re.search(r'(?:salle[s]?\s*de\s*bains?|sdb|salles?\s*d\'eau)\s*(?:/\s*toilettes)?\s*:\s*(\d+)', rooms_text, re.IGNORECASE)
        if m_bath:
            bathrooms = int(m_bath.group(1))
        
        # Bed fallback from rooms list
        if bedrooms is None:
            m_bed = re.search(r'(?:chambre[s]?|suite[s]?)\s*:\s*(\d+)', rooms_text, re.IGNORECASE)
            if m_bed:
                bedrooms = int(m_bed.group(1))

    # Surface & Bathrooms fallback from description
    if surface_m2 is None and description:
        m_surf = re.search(r'(\d+[\s\d]*)\s*m[²2]', description)
        if m_surf:
            surface_m2 = int(re.sub(r'\s+', '', m_surf.group(1)))

    if bathrooms is None and description:
        m_b = re.search(r'(\d+)\s*(?:salles?\s*de\s*bains?|sdb)', description, re.IGNORECASE)
        if m_b:
            bathrooms = int(m_b.group(1))

    # 12. Features (luxury amenities)
    features = []
    if sel:
        feature_items = sel.xpath('//section[2]//ul[contains(@class, "grid--3")]/li//text()').getall()
        features = [f.strip() for f in feature_items if f.strip()]
        
        # Add luxury rooms if present
        room_lis_text = " ".join(sel.xpath('//section[2]//ul[contains(@class, "grid--2")]/li//text()').getall())
        for luxury_kw in ['Hammam', 'Spa', 'Piscine', 'Jacuzzi', 'Salle de sport', 'Cinéma', 'Tennis', 'Sauna']:
            if luxury_kw.lower() in room_lis_text.lower() and not any(luxury_kw.lower() in f.lower() for f in features):
                features.append(luxury_kw)

    # 13. Images
    clean_imgs = []
    if sel:
        gallery_imgs = sel.css('section:first-of-type img::attr(src)').getall()
        for im in gallery_imgs:
            high_res = re.sub(r'-\d+x\d+(\.\w+)$', r'\1', im)
            if high_res not in clean_imgs:
                clean_imgs.append(high_res)

    images_count = len(clean_imgs)
    main_image = clean_imgs[0] if clean_imgs else card_data.get('img_card')
    if images_count == 0 and main_image:
        images_count = 1

    # 14. Seller Type & Scraped At
    seller_type = 'Professionnel (Kensington Luxury)'
    scraped_at = str(date.today())

    return {
        'id': prop_id,
        'platform': platform,
        'title': title,
        'url': full_url,
        'transaction_type': trans_type,
        'house_type': house_type,
        'city': city,
        'quartier': quartier,
        'price_raw': price_raw,
        'price_mad': price_mad,
        'surface_m2': surface_m2,
        'bedrooms': bedrooms,
        'bathrooms': bathrooms,
        'features': features,
        'description': description,
        'main_image': main_image,
        'images_count': images_count,
        'seller_type': seller_type,
        'scraped_at': scraped_at
    }

def main():
    print("=" * 70)
    print("Starting Kensington Luxury Properties Scraper (Marrakech)")
    print("=" * 70)

    start_time = time.time()

    # Step 1: Collect all listing pages
    print(f"[1/3] Scraping listing pages 1 to {MAX_PAGES}...")
    all_properties = {}

    with ThreadPoolExecutor(max_workers=WORKERS_LISTING) as executor:
        futures = {executor.submit(fetch_listing_page, p): p for p in range(1, MAX_PAGES + 1)}
        for future in as_completed(futures):
            page_num = futures[future]
            try:
                p_num, items = future.result()
                for item in items:
                    if item['url'] not in all_properties:
                        all_properties[item['url']] = item
            except Exception as e:
                print(f"[!] Error processing listing page {page_num}: {e}")

    total_listings = len(all_properties)
    print(f"[OK] Discovered {total_listings} unique luxury listings across Marrakech.")

    # Step 2: Fetch and parse detail pages concurrently
    print(f"[2/3] Fetching and parsing {total_listings} property detail pages...")
    results = []
    completed = 0

    with ThreadPoolExecutor(max_workers=WORKERS_DETAIL) as executor:
        futures = {executor.submit(fetch_and_parse_property, item): item['url'] for item in all_properties.values()}
        for future in as_completed(futures):
            try:
                record = future.result()
                results.append(record)
            except Exception as e:
                print(f"[!] Error processing property: {e}")
            completed += 1
            if completed % 50 == 0 or completed == total_listings:
                print(f"    Progress: {completed}/{total_listings} ({completed/total_listings*100:.1f}%)")

    # Sort results by ID or Title for deterministic output
    results.sort(key=lambda x: (x['transaction_type'], x['house_type'], x['title']))

    # Step 3: Save to JSON and CSV
    print("[3/3] Saving data to kensington_marrakech.json and kensington_marrakech.csv...")
    json_path = os.path.join(os.path.dirname(__file__), 'kensington_marrakech.json')
    csv_path = os.path.join(os.path.dirname(__file__), 'kensington_marrakech.csv')

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # For CSV, serialize features list to comma-separated string
    fieldnames = [
        'id', 'platform', 'title', 'url', 'transaction_type', 'house_type',
        'city', 'quartier', 'price_raw', 'price_mad', 'surface_m2',
        'bedrooms', 'bathrooms', 'features', 'description', 'main_image',
        'images_count', 'seller_type', 'scraped_at'
    ]

    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = dict(r)
            row['features'] = ", ".join(r['features']) if isinstance(r['features'], list) else r['features']
            writer.writerow(row)

    duration = time.time() - start_time
    json_size_mb = os.path.getsize(json_path) / (1024 * 1024)
    csv_size_mb = os.path.getsize(csv_path) / (1024 * 1024)

    print("\n" + "=" * 70)
    print("SCRAPING COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print(f"Total properties scraped: {len(results)}")
    print(f"Total elapsed time:       {duration:.2f} seconds")
    print(f"JSON Output:              {json_path} ({json_size_mb:.2f} MB)")
    print(f"CSV Output:               {csv_path} ({csv_size_mb:.2f} MB)")
    print("=" * 70)

if __name__ == '__main__':
    main()
