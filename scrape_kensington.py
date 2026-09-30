#!/usr/bin/env python3
"""
Production Scraper for Kensington Luxury Properties in Marrakech
(Christie's International Real Estate affiliate)

Extracts the absolute integrality of all luxury properties in and near Marrakech:
- Integrates WP Grid Builder listing archives, XML Sitemaps, and WordPress REST API with ACF.
- Covers Marrakech and surrounding domains: Palmeraie, Amelkis, Al Maaden, Samanah,
  Royal Palm, Route de l'Ourika, Route d'Amizmiz, Route de Fès, Route de Ouarzazate,
  Tameslouhte, Tnine Ourika, etc.
- Standard fields:
  id, platform='kensington', title, url, transaction_type, house_type,
  city='Marrakech', quartier, price_raw, price_mad, surface_m2, bedrooms,
  bathrooms, features, description, main_image (1 photo max), seller_type, scraped_at.
- Strict constraint: ONE PHOTO MAX PER HOME SCRAPED.
- Saves output to kensington_marrakech.json and kensington_marrakech.csv.
"""

import os
import sys
import re
import csv
import json
import html
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
WP_API_BASE = "https://www.kensingtonmorocco.com/wp-json/wp/v2"
MAX_LISTING_PAGES = 75
WORKERS_LISTING = 12
WORKERS_DETAIL = 12
REQUEST_TIMEOUT = 25
EUR_TO_MAD_RATE = 10.8

KNOWN_QUARTIERS = [
    'Palmeraie', 'Amelkis', 'Hivernage', 'Guéliz', 'Gueliz', "Route de l'Ourika",
    "Route d'Ourika", 'Route de Fès', 'Route de Casablanca', "Route d'Amizmiz", 'Route Amizmiz',
    'Route du Barrage', 'Route de Tahanaout', 'Al Maaden', 'Medina', 'Médina',
    'Targa', 'Agdal', 'Samanah', 'Royal Palm', 'Chrifia', 'Mhamid', 'Majorelle',
    'Sidi Ghanem', 'Camp de Base', 'Bab Atlas', 'Ain Itti', 'Daoudiate',
    'Sidi Abdallah Ghiat', 'Massira', 'Semlalia', 'Tassoultante', 'Victor Hugo',
    'Golf City', 'Noria', 'Argan Golf', 'Prestigia', 'Izdihar', 'Ennakhil',
    'Belvédère', 'Ménara', 'Menara', 'Tameslouhte', 'Tnine Ourika', 'Ouarzazate'
]

def clean_quartier(q: str) -> str:
    if not q:
        return 'Marrakech'
    ql = q.lower().strip()
    if ql in ['medina', 'médina']:
        return 'Médina'
    elif ql in ['gueliz', 'guéliz']:
        return 'Guéliz'
    elif 'palmeraie' in ql or 'ennakhil' in ql:
        return 'Palmeraie'
    elif 'amelkis' in ql:
        return 'Amelkis'
    elif 'hivernage' in ql:
        return 'Hivernage'
    elif 'al maaden' in ql or 'maaden' in ql:
        return 'Al Maaden'
    elif 'amizmiz' in ql or 'barrage' in ql:
        return "Route d'Amizmiz"
    elif 'ourika' in ql:
        return "Route de l'Ourika"
    elif 'tahanaout' in ql or 'tarnahout' in ql:
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
    elif 'ouarzazate' in ql:
        return 'Route de Ouarzazate'
    elif 'tameslouht' in ql:
        return "Route d'Amizmiz"
    elif 'noria' in ql:
        return 'Noria Golf'
    elif 'argan' in ql:
        return 'Argan Golf'
    elif 'atlas' in ql:
        return 'Bab Atlas'
    elif 'semlalia' in ql:
        return 'Semlalia'
    elif 'majorelle' in ql:
        return 'Majorelle'
    elif 'chrifia' in ql:
        return 'Chrifia'
    elif 'sidi abdallah' in ql or 'sidi abdellah' in ql:
        return 'Route de Sidi Abdellah Ghyate'
    return q.title()

def extract_neighborhood(card_loc: str, title: str, desc: str, url: str) -> str:
    if card_loc:
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

def normalize_house_type(prop_type: str, subtype: str, title: str, desc: str, url: str) -> str:
    combined = f"{prop_type} {subtype} {title} {desc} {url}".lower()
    if 'riad' in combined or 'dar ' in combined:
        return 'Riad'
    elif any(k in combined for k in ['palais', 'palace', 'hôtel particulier', 'hotel particulier', 'mansion']):
        return 'Palais'
    elif any(k in combined for k in ['appartement', 'apartment', 'penthouse', 'duplex', 'triplex', 'studio', 'flat']):
        return 'Appartement'
    elif any(k in combined for k in ['terrain', 'land', 'parcelle', 'lot', 'plot']):
        return 'Terrain'
    elif any(k in combined for k in ['commercial', 'bureau', 'office', 'commerce', 'fond de commerce', 'local', 'business', 'premises', 'immeuble']):
        return 'Commercial'
    elif any(k in combined for k in ['hotel', 'hôtel', "maison d'hôte", "maison d'hote", "bed and breakfast"]):
        return 'Hôtel'
    elif any(k in combined for k in ['villa', 'propriété', 'demeure', 'ferme', 'farm', 'maison', 'house', 'townhouse']):
        return 'Villa'
    return 'Villa'

def fetch_listing_page(page_num: int):
    """Fetch one WP Grid Builder pagination page from the website."""
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
                if not link:
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
                    'url': link.rstrip('/'),
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
                return page_num, []
            time.sleep(1)

def fetch_wp_api_page(post_type: str, page_num: int):
    """Fetch one page of 100 items from WP REST API."""
    url = f"{WP_API_BASE}/{post_type}?per_page=100&page={page_num}"
    retries = 3
    for attempt in range(retries):
        try:
            resp = requests.get(url, impersonate='chrome120', timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return post_type, page_num, data
            return post_type, page_num, []
        except Exception:
            if attempt == retries - 1:
                return post_type, page_num, []
            time.sleep(1)

def is_marrakech_or_surrounding(item: dict) -> bool:
    """Filter to ensure the property belongs to Marrakech or surrounding domains."""
    link = item.get('link', '').lower()
    if link.rstrip('/') == 'https://www.kensingtonmorocco.com/vente':
        return False
    
    # 1. Direct path check
    if '/marrakech/' in link:
        return True
    if any(k in link for k in ['/tameslouhte/', '/tnine-ourika/', '/ouarzazate/']):
        return True

    acf = item.get('acf') or {}
    addr = str((acf.get('google_map') or {}).get('address', ''))
    city = str(acf.get('city', ''))
    
    # 2. ACF address/city check
    if any(m in addr.lower() or m in city.lower() for m in ['marrakech', 'ourika', 'tameslouht', 'ouarzazate']):
        return True

    # 3. Known domain check in description or title
    title = str(item.get('title', {}).get('rendered', '')).lower()
    desc = str(acf.get('description_fr', '') or acf.get('description_eng', '')).lower()
    for kq in KNOWN_QUARTIERS:
        if re.search(r'\b' + re.escape(kq.lower()) + r'\b', f"{title} {desc}"):
            return True

    return False

def parse_property_from_api(item: dict, post_type: str, card_map: dict) -> dict:
    """Parse property item from WP REST API + ACF, augmented with card data."""
    acf = item.get('acf') or {}
    link = item.get('link', '').rstrip('/')
    
    # 1. ID & Ref
    ref = acf.get('reference')
    if not ref or not str(ref).strip():
        ref = link.rstrip('/').split('/')[-1]
    
    # 2. Platform
    platform = 'kensington'

    # 3. Title
    raw_title = item.get('title', {}).get('rendered', '') or acf.get('titlefr', '')
    title = html.unescape(raw_title).strip()
    if not title:
        title = ref.replace('-', ' ').title()

    # 4. URL
    full_url = link + '/'

    # 5. Transaction Type
    if post_type in ['rental_properties', 'holiday_rental'] or \
       any(k in link for k in ['/locations/', '/vacances/', '/rent/']):
        trans_type = 'Location'
    else:
        trans_type = 'Vente'

    # 6. Description
    desc_fr = acf.get('description_fr', '')
    desc_eng = acf.get('description_eng', '')
    description = desc_fr.strip() if desc_fr and len(desc_fr.strip()) > 30 else (desc_eng.strip() if desc_eng else '')
    
    card_info = card_map.get(link, {})
    if not description:
        description = card_info.get('excerpt', '')

    # 7. House Type
    pinfo = acf.get('property_info_fr') or acf.get('property_info') or {}
    subtype = str(pinfo.get('subtype', ''))
    prop_type = str(acf.get('property_type', ''))
    house_type = normalize_house_type(prop_type, subtype, title, description, link)

    # 8. City
    city = 'Marrakech'

    # 9. Quartier
    card_loc = card_info.get('loc_card', '')
    quartier = extract_neighborhood(card_loc, title, description, link)

    # 10. Price Raw & Price MAD
    is_poa = str(acf.get('poa', '')).lower() in ['true', '1', 'yes']
    price_val = acf.get('price')
    cur = str(acf.get('currency', 'EUR')).strip()
    period = acf.get('price_period_fr') or acf.get('price_period') or ''
    
    price_raw = None
    price_mad = None

    if is_poa or not price_val or str(price_val).strip() in ['0', '']:
        price_raw = 'Prix sur demande'
        price_mad = None
    else:
        try:
            amt = int(float(str(price_val).replace(' ', '').replace(',', '')))
            period_str = ""
            if period:
                period_str = f" / {period.title()}"
            elif trans_type == 'Location':
                if 'week' in period.lower() or 'semaine' in period.lower() or post_type == 'holiday_rental':
                    period_str = " / Semaine"
                else:
                    period_str = " / Mois"

            if cur.upper() in ['MAD', 'DH', 'DHS']:
                price_raw = f"{amt:,} MAD{period_str}".replace(',', ' ')
                price_mad = amt
            else:
                price_raw = f"€{amt:,}{period_str}".replace(',', ' ')
                price_mad = int(round(amt * EUR_TO_MAD_RATE))
        except Exception:
            price_raw = str(price_val)
            price_mad = None

    # Fallback to card price if API price was empty
    if not price_raw and card_info.get('price_raw_card'):
        price_raw = card_info.get('price_raw_card')

    # 11. Surface m2
    psize = pinfo.get('property_size') or {}
    surface_m2 = None
    try:
        internal_sz = psize.get('internal_size')
        if internal_sz and int(float(str(internal_sz).replace(' ', ''))) > 0:
            surface_m2 = int(float(str(internal_sz).replace(' ', '')))
        else:
            plot_sz = psize.get('plot_size')
            if plot_sz and int(float(str(plot_sz).replace(' ', ''))) > 0:
                surface_m2 = int(float(str(plot_sz).replace(' ', '')))
    except Exception:
        pass

    if surface_m2 is None and description:
        m_surf = re.search(r'(\d+[\s\d]*)\s*m[²2]', description)
        if m_surf:
            surface_m2 = int(re.sub(r'\s+', '', m_surf.group(1)))

    # 12. Bedrooms & Bathrooms
    bedrooms = None
    try:
        beds_total = acf.get('bedrooms_total')
        if beds_total is not None and str(beds_total).isdigit() and int(beds_total) > 0:
            bedrooms = int(beds_total)
    except Exception:
        pass

    bathrooms = None
    areas = acf.get('areas_fr') or acf.get('areas') or []
    if isinstance(areas, list):
        for a in areas:
            t = (a.get('type') or '').lower()
            if any(k in t for k in ['bain', 'bath', 'douche', 'shower']):
                num = a.get('number')
                if num and str(num).isdigit():
                    bathrooms = (bathrooms or 0) + int(num)

    # Fallback from description
    if bedrooms is None and description:
        m_bed = re.search(r'(\d+)\s*(?:chambre[s]?|suite[s]?)', description, re.IGNORECASE)
        if m_bed:
            bedrooms = int(m_bed.group(1))

    if bathrooms is None and description:
        m_bath = re.search(r'(\d+)\s*(?:salles?\s*de\s*bains?|sdb|salles?\s*d\'eau)', description, re.IGNORECASE)
        if m_bath:
            bathrooms = int(m_bath.group(1))

    # 13. Features
    feats = []
    prop_feats = acf.get('property_features_fr') or acf.get('property_features') or []
    if isinstance(prop_feats, list):
        for f in prop_feats:
            fname = f.get('feature')
            if fname and fname.strip() and fname.strip() not in feats:
                feats.append(fname.strip())

    # Add luxury amenities from areas_fr
    if isinstance(areas, list):
        for a in areas:
            t = (a.get('type') or '').strip()
            for kw in ['Hammam', 'Spa', 'Piscine', 'Jacuzzi', 'Salle de sport', 'Cinéma', 'Tennis', 'Sauna']:
                if kw.lower() in t.lower() and not any(kw.lower() in x.lower() for x in feats):
                    feats.append(kw)

    # 14. Main Image (STRICT CONSTRAINT: ONE PHOTO MAX PER HOME)
    # Store ONLY a single string URL. Never an array.
    main_image = ""
    img_data = acf.get('image_data')
    if isinstance(img_data, list) and img_data:
        first_img = img_data[0].get('image_url_apimo') or img_data[0].get('image_url')
        if first_img:
            main_image = str(first_img).strip()

    if not main_image and card_info.get('img_card'):
        main_image = str(card_info.get('img_card')).strip()

    # 15. Seller Type & Scraped At
    seller_type = 'Professionnel (Kensington Luxury)'
    scraped_at = str(date.today())

    return {
        'id': str(ref),
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
        'features': feats,
        'description': description,
        'main_image': main_image,
        'seller_type': seller_type,
        'scraped_at': scraped_at
    }

def main():
    print("=" * 70)
    print("KENSINGTON LUXURY PROPERTIES - INTEGRAL MARRAKECH SCRAPER")
    print("=" * 70)
    start_time = time.time()

    # Step 1: Collect listing cards across all 75 pagination pages
    print(f"[1/4] Scraping WP Grid Builder listing pages (1 to {MAX_LISTING_PAGES})...")
    card_map = {}
    with ThreadPoolExecutor(max_workers=WORKERS_LISTING) as executor:
        futures = {executor.submit(fetch_listing_page, p): p for p in range(1, MAX_LISTING_PAGES + 1)}
        for future in as_completed(futures):
            p_num, items = future.result()
            for it in items:
                if it['url'] not in card_map:
                    card_map[it['url']] = it

    print(f"[✓] Discovered {len(card_map)} property cards from listing grid pages.")

    # Step 2: Fetch all properties via WP REST API
    print("[2/4] Querying WordPress REST API across all property post types...")
    api_items = []
    
    # Endpoints to query: (post_type, max_pages)
    post_types = [
        ('property_sales', 10),      # ~778 sales
        ('rental_properties', 4),    # ~170 long-term rentals
        ('holiday_rental', 4)        # ~184 holiday rentals
    ]

    with ThreadPoolExecutor(max_workers=WORKERS_DETAIL) as executor:
        futures = []
        for pt, max_p in post_types:
            for p in range(1, max_p + 1):
                futures.append(executor.submit(fetch_wp_api_page, pt, p))

        for future in as_completed(futures):
            pt, p_num, items = future.result()
            for it in items:
                api_items.append((pt, it))

    print(f"[✓] Retrieved {len(api_items)} total properties from WordPress REST API.")

    # Step 3: Filter and parse Marrakech & surrounding domains
    print("[3/4] Filtering and normalizing Marrakech luxury properties...")
    records = []
    seen_urls = set()

    for pt, it in api_items:
        link = it.get('link', '').rstrip('/')
        if not link or link in seen_urls:
            continue

        if is_marrakech_or_surrounding(it):
            seen_urls.add(link)
            rec = parse_property_from_api(it, pt, card_map)
            records.append(rec)

    # Check if any URL from card_map was not covered by API
    for url, c_info in card_map.items():
        if url not in seen_urls:
            # Fallback parse from card data
            seen_urls.add(url)
            ref = url.rstrip('/').split('/')[-1]
            rec = {
                'id': ref,
                'platform': 'kensington',
                'title': c_info.get('title') or ref.replace('-', ' ').title(),
                'url': url + '/',
                'transaction_type': 'Location' if any(k in url for k in ['/locations/', '/vacances/']) else 'Vente',
                'house_type': normalize_house_type('', '', c_info.get('title', ''), c_info.get('excerpt', ''), url),
                'city': 'Marrakech',
                'quartier': extract_neighborhood(c_info.get('loc_card', ''), c_info.get('title', ''), c_info.get('excerpt', ''), url),
                'price_raw': c_info.get('price_raw_card') or 'Prix sur demande',
                'price_mad': None,
                'surface_m2': None,
                'bedrooms': None,
                'bathrooms': None,
                'features': [],
                'description': c_info.get('excerpt', ''),
                'main_image': c_info.get('img_card', ''),
                'seller_type': 'Professionnel (Kensington Luxury)',
                'scraped_at': str(date.today())
            }
            records.append(rec)

    # Sort deterministically
    records.sort(key=lambda x: (x['transaction_type'], x['house_type'], x['title']))

    # Step 4: Save output to JSON and CSV
    print(f"[4/4] Saving {len(records)} records to kensington_marrakech.json and kensington_marrakech.csv...")
    json_path = os.path.join(os.path.dirname(__file__), 'kensington_marrakech.json')
    csv_path = os.path.join(os.path.dirname(__file__), 'kensington_marrakech.csv')

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    fieldnames = [
        'id', 'platform', 'title', 'url', 'transaction_type', 'house_type',
        'city', 'quartier', 'price_raw', 'price_mad', 'surface_m2',
        'bedrooms', 'bathrooms', 'features', 'description', 'main_image',
        'seller_type', 'scraped_at'
    ]

    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            row = dict(r)
            row['features'] = ", ".join(r['features']) if isinstance(r['features'], list) else str(r['features'])
            writer.writerow(row)

    duration = time.time() - start_time
    json_size_bytes = os.path.getsize(json_path)
    csv_size_bytes = os.path.getsize(csv_path)
    json_size_mb = json_size_bytes / (1024 * 1024)
    csv_size_mb = csv_size_bytes / (1024 * 1024)

    # Verification statistics
    with_img = sum(1 for r in records if r['main_image'])
    with_price = sum(1 for r in records if r['price_mad'] is not None)
    with_surf = sum(1 for r in records if r['surface_m2'] is not None)
    with_beds = sum(1 for r in records if r['bedrooms'] is not None)
    with_baths = sum(1 for r in records if r['bathrooms'] is not None)

    print("\n" + "=" * 70)
    print("KENSINGTON LUXURY SCRAPING COMPLETED")
    print("=" * 70)
    print(f"Total luxury properties scraped: {len(records)}")
    print(f"Total execution time:            {duration:.2f} seconds")
    print(f"JSON Output:                     {json_path}")
    print(f"  - Size:                        {json_size_mb:.2f} MB ({json_size_bytes:,} bytes)")
    print(f"CSV Output:                      {csv_path}")
    print(f"  - Size:                        {csv_size_mb:.2f} MB ({csv_size_bytes:,} bytes)")
    print("-" * 70)
    print("DATA QUALITY METRICS:")
    print(f"  - Properties with main_image (1 max): {with_img}/{len(records)} ({with_img/len(records)*100:.1f}%)")
    print(f"  - Properties with numeric price MAD:  {with_price}/{len(records)} ({with_price/len(records)*100:.1f}%)")
    print(f"  - Properties with surface m2:         {with_surf}/{len(records)} ({with_surf/len(records)*100:.1f}%)")
    print(f"  - Properties with bedrooms:           {with_beds}/{len(records)} ({with_beds/len(records)*100:.1f}%)")
    print(f"  - Properties with bathrooms:          {with_baths}/{len(records)} ({with_baths/len(records)*100:.1f}%)")
    print("=" * 70)

if __name__ == '__main__':
    main()
