#!/usr/bin/env python3
"""
Production Scraper for Bosworth Property Marrakech
Specialist in authentic Medina riads, guest houses, and historic palaces.

Platform: https://bosworthpropertymarrakech.com/
Framework: curl_cffi (impersonate='chrome120') + Scrapling Selector
Outputs: bosworth_marrakech.json, bosworth_marrakech.csv
"""

import os
import sys
import re
import csv
import json
import time
import random
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from curl_cffi import requests
from scrapling import Selector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('bosworth_scraper')

BASE_URL = "https://bosworthpropertymarrakech.com"
TODAY_STR = datetime.now().strftime('%Y-%m-%d')
EXCHANGE_RATES = {
    'EUR': 10.8,
    'GBP': 13.0,
    'USD': 10.0,
    'MAD': 1.0
}

def get_session():
    return requests.Session(impersonate='chrome120')

def fetch_property_urls():
    """Fetch all property URLs from sitemaps and archive pagination."""
    s = get_session()
    urls = set()
    
    # 1. XML Sitemaps from sitemap_index.xml
    sitemap_targets = ['property-sitemap1.xml', 'property-sitemap2.xml', 'properties-sitemap1.xml']
    try:
        idx_resp = s.get(f"{BASE_URL}/sitemap_index.xml", timeout=20)
        if idx_resp.status_code == 200:
            root = ET.fromstring(idx_resp.content)
            for elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                loc = elem.text.strip()
                if 'property' in loc:
                    sm_name = loc.split('/')[-1]
                    if sm_name not in sitemap_targets:
                        sitemap_targets.append(sm_name)
    except Exception as e:
        logger.warning(f"Error fetching sitemap_index: {e}")

    archive_urls_to_crawl = [
        f"{BASE_URL}/properties/",
        f"{BASE_URL}/properties/for_sale/",
        f"{BASE_URL}/property-type/riad-for-sale-marrakech/",
        f"{BASE_URL}/property-type/guesthouse-for-sale-marrakech/",
        f"{BASE_URL}/property-type/commercial-property-for-sale-marrakech/",
        f"{BASE_URL}/property-type/luxury-property-for-sale-marrakech/",
    ]

    for sitemap_name in sitemap_targets:
        sm_url = sitemap_name if sitemap_name.startswith('http') else f"{BASE_URL}/{sitemap_name}"
        try:
            logger.info(f"Fetching sitemap: {sm_url}")
            resp = s.get(sm_url, timeout=20)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                    u = elem.text.strip()
                    if '/property/' in u and u.strip('/') != f"{BASE_URL}/property":
                        urls.add(u)
                    elif '/properties/' in u and u not in archive_urls_to_crawl:
                        archive_urls_to_crawl.append(u)
            else:
                logger.warning(f"Sitemap {sm_url} returned status {resp.status_code}")
        except Exception as e:
            logger.error(f"Error fetching sitemap {sm_url}: {e}")

    logger.info(f"Collected {len(urls)} property URLs from sitemaps.")

    # 2. Archive pagination check
    for base_archive in archive_urls_to_crawl:
        for page_num in range(1, 30):
            sep = '&' if '?' in base_archive else '?'
            page_url = f"{base_archive.rstrip('/')}/{sep}page_num={page_num}" if page_num > 1 else base_archive
            try:
                resp = s.get(page_url, timeout=20)
                if resp.status_code != 200:
                    break
                sel = Selector(resp.text)
                links = [a.attrib['href'] for a in sel.css('a') if '/property/' in a.attrib.get('href', '')]
                valid_links = [l for l in links if l.strip('/') != f"{BASE_URL}/property"]
                if not valid_links:
                    break
                new_on_page = 0
                for l in valid_links:
                    if not l.startswith('http'):
                        l = f"{BASE_URL}{l}"
                    if l not in urls:
                        urls.add(l)
                        new_on_page += 1
                if new_on_page == 0 and page_num > 1:
                    break
            except Exception as e:
                logger.warning(f"Error on archive page {page_url}: {e}")
                break

    logger.info(f"Total unique property URLs gathered: {len(urls)}")
    return sorted(list(urls))

def parse_price(price_raw):
    """Parse raw price string and convert to MAD integer."""
    if not price_raw:
        return None, None
    raw = price_raw.strip()
    if any(term in raw.upper() for term in ['POA', 'PRICE ON APPLICATION', 'UPON REQUEST', 'CONTACT']):
        return raw, None
    
    # Currency identification
    curr = 'EUR'
    if '£' in raw or 'GBP' in raw.upper():
        curr = 'GBP'
    elif 'MAD' in raw.upper() or 'DHS' in raw.upper() or 'DIRHAM' in raw.upper():
        curr = 'MAD'
    elif '$' in raw or 'USD' in raw.upper():
        curr = 'USD'
    elif '€' in raw or 'EUR' in raw.upper():
        curr = 'EUR'
        
    clean_num = re.sub(r'[^\d\.,\']', '', raw)
    if not clean_num:
        return raw, None
        
    num_str = clean_num.replace("'", "").replace(" ", "")
    num_str = re.sub(r'[\.,](\d{3})', r'\1', num_str)
    num_str = num_str.replace('.', '').replace(',', '')
    
    try:
        val = int(num_str)
        # Handle dummy placeholder prices (e.g. €1)
        if val <= 10:
            return raw, None
            
        multiplier = EXCHANGE_RATES.get(curr, 10.8)
        price_mad = int(round(val * multiplier))
        return raw, price_mad
    except ValueError:
        return raw, None

def detect_house_type(title, desc="", url=""):
    """Classify property into standard types based on authoritative title and keywords."""
    t = title.lower()
    u = url.lower()
    d = desc.lower()

    if any(k in t or k in u for k in ['hotel', 'guesthouse', 'guest house', "maison d'hote", "maison d’hôte", 'boutique hotel']):
        return "Maison d'Hôtes"
    if any(k in t or k in u for k in ['palace', 'palais']):
        return "Palais"
    if any(k in t or k in u for k in ['douiria', 'douirya']):
        return "Douiria"
    if 'commercial' in t or 'shop' in t or 'commercial' in u:
        return "Commerce"
    if 'riad' in t or 'riad' in u:
        return "Riad"
    if any(k in t or k in u for k in ['apartment', 'appartement', 'flat', 'penthouse']):
        return "Appartement"
    if 'villa' in t or 'villa' in u:
        return "Villa"
    if any(k in t or k in u for k in ['land', 'terrain', 'hectare', 'plot']):
        return "Terrain"
    if any(k in t or k in u for k in ['farm', 'ferme']):
        return "Ferme"
    if any(k in t or k in u for k in ['house', 'maison']):
        return "Maison"

    if any(k in d for k in ['hotel', 'guesthouse', 'guest house']):
        return "Maison d'Hôtes"
    if 'riad' in d:
        return "Riad"
    if 'villa' in d:
        return "Villa"
    if 'apartment' in d or 'appartement' in d:
        return "Appartement"

    return "Riad"

def detect_quartier(loc_raw, title, desc="", url=""):
    """Identify Medina quarter or zone in Marrakech."""
    combined = f"{loc_raw} {title} {desc} {url}".lower()
    
    quarters = [
        ('Mouassine', ['mouassine']),
        ('Kasbah', ['kasbah']),
        ('Riad Laarous', ['riad laarous', 'riad larousse', 'laarous', 'larousse']),
        ('Sidi Mimoun', ['sidi mimoun']),
        ('Bab Doukkala', ['bab doukkala', 'bab doukalla']),
        ('Bab Taghzout', ['bab taghzout', 'taghzout']),
        ('Bab Aylan', ['bab aylan', 'bab aylen']),
        ('Kennaria', ['kennaria', 'kenaria']),
        ('Ben Youssef', ['ben youssef', 'bin youssef']),
        ('Berimma', ['berimma', 'berima', 'barrima']),
        ('Mellah', ['mellah', 'hay essalam']),
        ('Dar El Bacha', ['dar el bacha', 'dar el basha', 'dar elbacha']),
        ('Ksour', ['ksour', 'el ksour']),
        ('Arset El Maach', ['arset el maach', 'arset el maâch']),
        ('Arset El Hiri', ['arset el hiri']),
        ('Arset El Bardii', ['arset el bardii', 'arset el bardi']),
        ('Dabachi', ['dabachi', 'derb dabachi', 'derb debachi']),
        ('Kaat Benahid', ['kaat benahid', 'kaat ben ahid']),
        ('Sidi Benslimane', ['sidi benslimane', 'benslimane']),
        ('Sidi Ayoub', ['sidi ayoub']),
        ('Zaouia Abbassia', ['zaouia', 'zaouia abbassia', 'zawiya']),
        ('Hart Soura', ['hart soura', 'hart sourah']),
        ('Derb Chtouka', ['chtouka', 'derb chtouka']),
        ('Derb Jdid', ['derb jdid']),
        ('Place des Ferblantiers', ['ferblantiers', 'place des ferblantiers']),
        ('Rahba Kedima', ['rahba kedima', 'rahba lakdima', 'place des epices']),
        ('Bahia', ['bahia']),
        ('Assouel', ['assouel']),
        ('Gueliz', ['gueliz', 'guéliz']),
        ('Hivernage', ['hivernage']),
        ('Palmeraie', ['palmeraie']),
        ('Route de Fes', ['route de fes', 'fes road']),
        ('Route de l\'Ourika', ['route de l\'ourika', 'ourika road', 'ourika']),
        ('Route d\'Amizmiz', ['route d\'amizmiz', 'amizmiz road', 'amizmiz']),
        ('Agdal', ['agdal']),
        ('Targa', ['targa']),
        ('Royal Golf', ['royal golf']),
        ('Amelkis', ['amelkis']),
        ('Essaouira', ['essaouira']),
    ]
    
    loc_lower = loc_raw.lower() if loc_raw else ''
    for q_name, aliases in quarters:
        if any(alias in loc_lower for alias in aliases):
            return q_name
            
    tu_lower = f"{title} {url}".lower()
    for q_name, aliases in quarters:
        if any(alias in tu_lower for alias in aliases):
            return q_name
            
    for q_name, aliases in quarters:
        if any(alias in combined for alias in aliases):
            return q_name
            
    if 'medina' in combined or 'médina' in combined:
        return 'Médina'
        
    return 'Marrakech'

def extract_features(sel, title, desc):
    """Extract amenities and key features from listing elements and text."""
    features = set()
    
    for item in sel.css('.property-features .feature-item'):
        txt = item.get_all_text(strip=True) if hasattr(item, 'get_all_text') else (item.text or '').strip()
        if not txt:
            continue
        lines = [l.strip() for l in txt.split('\n') if l.strip()]
        if len(lines) == 2:
            k, v = lines[0].rstrip(':'), lines[1]
            if k.lower() not in ['city', 'internal area', 'total area', 'plot area', 'bedrooms', 'bathrooms']:
                features.add(f"{k}: {v}")
        elif len(lines) == 1:
            k = lines[0].rstrip(':')
            if k.lower() not in ['city', 'details', 'main features']:
                features.add(k)
                
    full_text = f"{title} {desc}".lower()
    
    if any(k in full_text for k in ['patio', 'courtyard', 'cour intérieure', 'cour interieure']):
        features.add('Patio')
    if any(k in full_text for k in ['swimming pool', 'piscine']):
        features.add('Piscine')
    if any(k in full_text for k in ['bassin', 'plunge pool', 'whirlpool']):
        features.add('Bassin')
    if any(k in full_text for k in ['terrace', 'roof terrace', 'terrasse', 'panoramic terrace', 'rooftop']):
        features.add('Terrasse panoramique')
    if any(k in full_text for k in ['freehold', 'titled', 'titre foncier', 'titré', 'titre']):
        features.add('Titre Foncier')
    if any(k in full_text for k in ['hammam', 'steam room', 'bain de vapeur']):
        features.add('Hammam')
    if any(k in full_text for k in ['air condition', 'air-condition', 'air conditioning', 'climatisation', 'a/c']):
        features.add('Climatisation')
    if any(k in full_text for k in ['fireplace', 'cheminée', 'cheminee']):
        features.add('Cheminée')
    if any(k in full_text for k in ['solarium']):
        features.add('Solarium')
    if any(k in full_text for k in ['atlas view', 'atlas views', 'vue atlas', 'view of the atlas', 'vue sur l\'atlas']):
        features.add('Vue Atlas')
    if any(k in full_text for k in ['parking', 'car access', 'accessible en voiture', 'accès voiture', 'acces voiture']):
        features.add('Accès voiture / Parking')
    if any(k in full_text for k in ['fitted kitchen', 'equipped kitchen', 'cuisine équipée', 'modern kitchen']):
        features.add('Cuisine équipée')
    if any(k in full_text for k in ['jacuzzi', 'hot tub']):
        features.add('Jacuzzi')

    return sorted(list(features))

def parse_property_page(html, url):
    """Parse a single property page into a standardized record."""
    sel = Selector(html)
    
    # 1. ID
    m_id = re.search(r'/(\d+)/?$', url)
    if m_id:
        prop_id = m_id.group(1)
    else:
        slug = url.strip('/').split('/')[-1]
        prop_id = slug
        
    # 2. Title
    title_el = sel.css('.et_pb_text_0_tb_body')
    if title_el:
        title = title_el[0].get_all_text(strip=True)
    else:
        t_el = sel.css('title')
        title = t_el[0].text.strip() if t_el and t_el[0].text else ''
    title = re.sub(r'\s*-\s*Bosworth Property.*$', '', title, flags=re.IGNORECASE).strip()
    
    # 3. Location / Quartier
    loc_el = sel.css('.et_pb_text_1_tb_body')
    loc_raw = loc_el[0].get_all_text(strip=True) if loc_el else ''
    
    # 4. Price
    price_el = sel.css('.et_pb_text_2_tb_body')
    price_raw = price_el[0].get_all_text(strip=True) if price_el else ''
    price_raw, price_mad = parse_price(price_raw)
    
    # 5. Bedrooms, Bathrooms, Surface
    # Strictly scoped to .features-icons and .property-features
    bedrooms = None
    bathrooms = None
    surface_m2 = None
    
    for item in sel.css('.features-icons .feature-item'):
        img = item.css('img')
        val = item.css('.feature-value')
        if img and val:
            alt = (img[0].attrib.get('alt', '') or '').lower()
            src = (img[0].attrib.get('src', '') or '').lower()
            val_txt = val[0].get_all_text(strip=True) if hasattr(val[0], 'get_all_text') else (val[0].text or '').strip()
            
            if 'bedroom' in alt or 'bedroom' in src:
                try:
                    bedrooms = int(re.sub(r'[^\d]', '', val_txt))
                except ValueError:
                    pass
            elif 'bathroom' in alt or 'bathroom' in src:
                try:
                    bathrooms = int(re.sub(r'[^\d]', '', val_txt))
                except ValueError:
                    pass
            elif 'area' in alt or 'area' in src or 'm2' in val_txt.lower() or 'm²' in val_txt:
                s_clean = re.sub(r'[^\d\.,]', '', val_txt).replace(',', '')
                try:
                    surface_m2 = float(s_clean)
                except ValueError:
                    pass

    # Fallback to .property-features if not found in .features-icons
    for f in sel.css('.property-features .feature-item'):
        ftxt = f.get_all_text(strip=True) if hasattr(f, 'get_all_text') else (f.text or '').strip()
        lines = [l.strip() for l in ftxt.split('\n') if l.strip()]
        if len(lines) == 2:
            k, v = lines[0].lower(), lines[1]
            if 'bedroom' in k and bedrooms is None:
                m = re.search(r'\d+', v)
                if m: bedrooms = int(m.group(0))
            elif 'bathroom' in k and bathrooms is None:
                m = re.search(r'\d+', v)
                if m: bathrooms = int(m.group(0))
            elif ('area' in k or 'plot' in k or 'internal' in k) and surface_m2 is None:
                s_clean = re.sub(r'[^\d\.,]', '', v).replace(',', '')
                try: surface_m2 = float(s_clean)
                except ValueError: pass

    # 6. Description
    desc_parts = []
    for el in sel.css('.et_pb_text_5_tb_body, .et_pb_text_6_tb_body'):
        txt = el.get_all_text(strip=True) if hasattr(el, 'get_all_text') else (el.text or '').strip()
        if txt and txt not in desc_parts:
            desc_parts.append(txt)
            
    description = "\n\n".join(desc_parts).strip()
    
    if surface_m2 is None:
        m_surf = re.search(r'(\d+(?:[\.,]\d+)?)\s*m[2²]', description, re.IGNORECASE)
        if m_surf:
            try:
                surface_m2 = float(m_surf.group(1).replace(',', ''))
            except ValueError:
                pass

    # 7. House type
    house_type = detect_house_type(title, description, url)
    
    # 8. City and Quartier
    quartier = detect_quartier(loc_raw, title, description, url)
    city = 'Marrakech'
    
    # 9. Features
    features = extract_features(sel, title, description)
    
    # 10. Images: main gallery slider
    images = []
    for el in sel.css('.slider-img'):
        du = el.attrib.get('data-url') or el.attrib.get('data-src') or el.attrib.get('src')
        if du and du.startswith('http') and du not in images:
            images.append(du)
            
    if not images:
        for img in sel.css('img'):
            src = img.attrib.get('src') or img.attrib.get('data-src') or ''
            if src.startswith('http') and ('qobrix' in src or 'uploads' in src) and not any(ic in src for ic in ['logo', 'icon', 'canvas']):
                if src not in images:
                    images.append(src)
                    
    main_image = images[0] if images else None
    images_count = len(images)
    
    # 11. Transaction type
    transaction_type = 'Location' if '/for_rent/' in url.lower() or '/rent/' in url.lower() else 'Vente'

    record = {
        'id': prop_id,
        'platform': 'bosworth',
        'title': title,
        'url': url,
        'transaction_type': transaction_type,
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
        'seller_type': 'Professionnel (Bosworth Property)',
        'scraped_at': TODAY_STR
    }
    
    return record

def scrape_worker(url, session):
    """Worker to fetch and parse a single listing URL with backoff and jitter."""
    retries = 5
    base_sleep = 1.0
    
    for attempt in range(retries):
        try:
            time.sleep(random.uniform(0.3, 0.6))
            resp = session.get(url, timeout=25)
            
            if resp.status_code == 200:
                record = parse_property_page(resp.text, url)
                return record
            elif resp.status_code == 429:
                wait_sec = (attempt + 1) * 3 + random.uniform(1.0, 3.0)
                logger.warning(f"Rate limited (429) on {url.split('/')[-2]}, sleeping {wait_sec:.1f}s...")
                time.sleep(wait_sec)
            elif resp.status_code == 404:
                logger.warning(f"404 Not Found: {url}")
                return None
            else:
                logger.warning(f"Attempt {attempt+1}: Status {resp.status_code} for {url}")
                time.sleep(base_sleep * (attempt + 1))
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} exception on {url}: {e}")
            time.sleep(base_sleep * (attempt + 1))
            
    logger.error(f"Failed to fetch {url} after {retries} attempts.")
    return None

def main():
    start_time = time.time()
    logger.info("=== STARTING BOSWORTH PROPERTY MARRAKECH PRODUCTION SCRAPER ===")
    
    # 1. Discover all property URLs
    urls = fetch_property_urls()
    total_urls = len(urls)
    logger.info(f"Target count: {total_urls} properties to scrape.")

    # 2. Scrape with polite concurrency (max 3 workers)
    records = []
    results_map = {}
    remaining_urls = list(urls)

    max_workers = 3
    
    def process_url(u):
        sess = get_session()
        rec = scrape_worker(u, sess)
        return u, rec

    logger.info(f"Launching scraper with {max_workers} worker threads...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_url, u): u for u in remaining_urls}
        done_count = 0
        for future in as_completed(futures):
            u, rec = future.result()
            done_count += 1
            if rec:
                results_map[u] = rec
            if done_count % 20 == 0 or done_count == total_urls:
                logger.info(f"Progress: [{done_count}/{total_urls}] completed. Successfully scraped: {len(results_map)}.")

    # Retry any failures sequentially
    failed_urls = [u for u in urls if u not in results_map]
    if failed_urls:
        logger.info(f"Retrying {len(failed_urls)} failed URLs sequentially...")
        sess = get_session()
        for u in failed_urls:
            time.sleep(2.0)
            rec = scrape_worker(u, sess)
            if rec:
                results_map[u] = rec
                logger.info(f"Recovered failed URL: {u}")

    records = list(results_map.values())
    def sort_key(r):
        try:
            return (0, int(r['id']))
        except ValueError:
            return (1, str(r['id']))
    records.sort(key=sort_key)
    
    elapsed = time.time() - start_time
    logger.info(f"Scraping completed in {elapsed:.1f} seconds. Total records extracted: {len(records)} / {total_urls}.")

    # 3. Save JSON
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(workspace_dir, 'bosworth_marrakech.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved JSON to: {json_path} ({os.path.getsize(json_path):,} bytes)")

    # 4. Save CSV
    csv_path = os.path.join(workspace_dir, 'bosworth_marrakech.csv')
    csv_headers = [
        'id', 'platform', 'title', 'url', 'transaction_type', 'house_type',
        'city', 'quartier', 'price_raw', 'price_mad', 'surface_m2',
        'bedrooms', 'bathrooms', 'features', 'description',
        'main_image', 'images_count', 'seller_type', 'scraped_at'
    ]
    
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
        for r in records:
            row = dict(r)
            row['features'] = ", ".join(row['features']) if isinstance(row['features'], list) else str(row['features'])
            writer.writerow(row)
    logger.info(f"Saved CSV to: {csv_path} ({os.path.getsize(csv_path):,} bytes)")

    # 5. Print Summary Analytics
    print("\n" + "="*60)
    print("           BOSWORTH PROPERTY MARRAKECH SUMMARY")
    print("="*60)
    print(f"Total Properties Scraped: {len(records)} / {total_urls} ({len(records)*100//total_urls if total_urls else 0}%)")
    print(f"JSON File: {json_path} ({os.path.getsize(json_path):,} bytes)")
    print(f"CSV File:  {csv_path} ({os.path.getsize(csv_path):,} bytes)")
    
    types_count = {}
    for r in records:
        types_count[r['house_type']] = types_count.get(r['house_type'], 0) + 1
    print("\nHouse Types Distribution:")
    for ht, cnt in sorted(types_count.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {ht:15}: {cnt:3} ({cnt*100//len(records):2}%)")

    quartier_count = {}
    for r in records:
        quartier_count[r['quartier']] = quartier_count.get(r['quartier'], 0) + 1
    print("\nTop 12 Quartiers / Zones:")
    for q, cnt in sorted(quartier_count.items(), key=lambda x: x[1], reverse=True)[:12]:
        print(f"  - {q:22}: {cnt:3} ({cnt*100//len(records):2}%)")

    priced = [r['price_mad'] for r in records if r['price_mad'] is not None]
    if priced:
        print(f"\nPrice Statistics (MAD):")
        print(f"  - Priced listings : {len(priced)} / {len(records)} ({len(priced)*100//len(records)}%)")
        print(f"  - Min price       : {min(priced):,d} MAD")
        print(f"  - Median price    : {sorted(priced)[len(priced)//2]:,d} MAD")
        print(f"  - Max price       : {max(priced):,d} MAD")
        print(f"  - Average price   : {int(sum(priced)/len(priced)):,d} MAD")

    beds = [r['bedrooms'] for r in records if r['bedrooms'] is not None]
    baths = [r['bathrooms'] for r in records if r['bathrooms'] is not None]
    surfs = [r['surface_m2'] for r in records if r['surface_m2'] is not None]
    imgs = [r['images_count'] for r in records if r['images_count'] is not None]

    print("\nPhysical Characteristics (Averages):")
    if beds:
        print(f"  - Avg Bedrooms    : {sum(beds)/len(beds):.1f} (Coverage: {len(beds)}/{len(records)})")
    if baths:
        print(f"  - Avg Bathrooms   : {sum(baths)/len(baths):.1f} (Coverage: {len(baths)}/{len(records)})")
    if surfs:
        print(f"  - Avg Surface     : {sum(surfs)/len(surfs):.1f} m² (Coverage: {len(surfs)}/{len(records)})")
    if imgs:
        print(f"  - Avg Images      : {sum(imgs)/len(imgs):.1f} photos per listing (Total: {sum(imgs):,} photos)")

    amenities = ['Patio', 'Terrasse panoramique', 'Piscine', 'Bassin', 'Titre Foncier', 'Climatisation', 'Hammam', 'Cheminée', 'Accès voiture / Parking']
    print("\nSignature Moroccan Amenities:")
    for amen in amenities:
        c = sum(1 for r in records if amen in r['features'])
        print(f"  - {amen:24}: {c:3} ({c*100//len(records):2}%)")

    print("="*60 + "\n")

if __name__ == '__main__':
    main()
