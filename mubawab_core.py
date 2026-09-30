"""
Production Scraper for Mubawab using Scrapling and curl_cffi with ThreadPoolExecutor.
Features:
- Fast concurrent scraping
- SQLite database storage with automatic indexing
- Precise House Type & Quartier extraction
- Resilient retry logic
- Export to JSON & CSV
"""

import sys
import io
import time
import json
import csv
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from curl_cffi import requests
from scrapling import Selector

# ---------------------------------------------------------------------------
# Constants & Dictionaries
# ---------------------------------------------------------------------------

MARRAKECH_QUARTIERS = [
    # Major districts & Surrounding zones
    "Guéliz", "Gueliz", "Hivernage", "Palmeraie", "Médina", "Medina",
    "Majorelle", "Agdal", "Targa", "Mhamid", "M'hamid", "Sidi Youssef Ben Ali",
    "Semlalia", "Samlalia", "Izdihar", "Daoudiate", "Massira", "Victor Hugo",
    "Amelkis", "Route de Casablanca", "Route de l'Ourika", "Route d'Amizmiz",
    "Route de Fès", "Route de Tahanaout", "Route de Safi", "Chrifia", "Camp El Ghoul",
    "Al Fadl", "Mabrouka", "Bab Doukkala", "Bab Atlas", "Kasbah",
    "Sidi Ghanem", "Amerchich", "Annakhil", "Ennakhil", "Ain Mezouar",
    "Al Massar", "Socco Alto", "Golf City", "Prestigia", "Arsat Sbaia",
    "Menara", "Ménara", "Assif", "Riad Zitoun", "Bab Taghzout", "Mellah",
    "Koutoubia", "Tamansourt", "Harbil", "Ourika", "Tahanaout", "Tassoultante",
    "Tameslohte", "Aït Ourir", "Ait Ourir", "Amizmiz", "Agafay", "Chrifia"
]

def normalize_quartier(q: str) -> str:
    ql = q.lower()
    if ql in ["gueliz", "guéliz"]:
        return "Guéliz"
    if ql in ["medina", "médina"]:
        return "Médina"
    if ql in ["mhamid", "m'hamid"]:
        return "M'hamid"
    if ql in ["semlalia", "samlalia"]:
        return "Semlalia"
    if ql in ["menara", "ménara"]:
        return "Ménara"
    if ql in ["annakhil", "ennakhil"]:
        return "Palmeraie / Annakhil"
    if ql in ["route de fès", "route de fes"]:
        return "Route de Fès"
    if ql in ["harbil", "tamansourt"]:
        return "Tamansourt"
    if ql in ["tahanaout", "route de tahanaout"]:
        return "Route de Tahanaout"
    if ql in ["ourika", "route de l'ourika"]:
        return "Route de l'Ourika"
    if ql in ["ait ourir", "aït ourir"]:
        return "Aït Ourir"
    if ql in ["amizmiz", "route d'amizmiz"]:
        return "Route d'Amizmiz"
    return q

def detect_house_type(title: str, url: str, desc: str) -> str:
    """Detect specific property/house type from text."""
    text = f"{title} {url} {desc}".lower()
    if re.search(r'\b(riad|riads)\b', text):
        return 'Riad'
    elif re.search(r'\b(duplex)\b', text):
        return 'Duplex'
    elif re.search(r'\b(studio|studios)\b', text):
        return 'Studio'
    elif re.search(r'\b(penthouse|penthouses)\b', text):
        return 'Penthouse'
    elif re.search(r'\b(villa|villas)\b', text):
        return 'Villa'
    elif re.search(r'\b(appartement|appartements|appart|apparts)\b', text):
        return 'Appartement'
    elif re.search(r'\b(maison|maisons)\b', text):
        return 'Maison'
    elif re.search(r'\b(terrain|terrains|lot de terrain)\b', text):
        return 'Terrain'
    elif re.search(r'\b(bureau|bureaux|plateau bureau)\b', text):
        return 'Bureau'
    elif re.search(r'\b(local commercial|commerce|magasin|fond de commerce)\b', text):
        return 'Commerce'
    return 'Autre'

def detect_quartier(title: str, url: str, desc: str) -> str:
    """Detect neighborhood in Marrakech."""
    combined = f"{title} {url} {desc}"
    for q in MARRAKECH_QUARTIERS:
        if re.search(r'\b' + re.escape(q) + r'\b', combined, re.I):
            return normalize_quartier(q)
    return "Autre / Centre"

def clean_text(text: Optional[str]) -> str:
    """Normalize whitespace and remove non-breaking spaces."""
    if not text:
        return ""
    text = re.sub(r"[\s\u00a0\u202f]+", " ", text)
    return text.strip()

def parse_price(raw_price: str) -> Optional[int]:
    """Parse numeric price from raw text e.g. '1 152 000 DH' -> 1152000."""
    if not raw_price:
        return None
    digits = re.sub(r"[^\d]", "", raw_price)
    return int(digits) if digits else None

def parse_surface(raw_surface: str) -> Optional[int]:
    """Parse numeric surface in m² from raw text e.g. '48m²' -> 48."""
    if not raw_surface:
        return None
    m = re.search(r"(\d+)\s*m²", raw_surface, re.I)
    return int(m.group(1)) if m else None

# ---------------------------------------------------------------------------
# Database Management
# ---------------------------------------------------------------------------

def init_db(db_path: str = "mubawab_listings.db") -> sqlite3.Connection:
    """Initialize SQLite database with proper schema and indexes."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            title TEXT,
            url TEXT,
            transaction_type TEXT,
            house_type TEXT,
            city TEXT,
            quartier TEXT,
            price_raw TEXT,
            price_numeric INTEGER,
            surface_raw TEXT,
            surface_m2 INTEGER,
            rooms TEXT,
            bedrooms TEXT,
            bathrooms TEXT,
            features TEXT,
            description TEXT,
            main_image TEXT,
            images_count INTEGER,
            scraped_date TEXT
        )
    """)
    # Create indexes for ultra-fast filtering
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_house_type ON listings(house_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quartier ON listings(quartier)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_type ON listings(transaction_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_price ON listings(price_numeric)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_surface ON listings(surface_m2)")
    conn.commit()
    return conn

def save_listings_to_db(conn: sqlite3.Connection, listings: List[Dict[str, Any]]):
    """Upsert listings into SQLite database."""
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT OR REPLACE INTO listings (
            id, title, url, transaction_type, house_type, city, quartier,
            price_raw, price_numeric, surface_raw, surface_m2,
            rooms, bedrooms, bathrooms, features, description,
            main_image, images_count, scraped_date
        ) VALUES (
            :id, :title, :url, :transaction_type, :house_type, :city, :quartier,
            :price_raw, :price_numeric, :surface_raw, :surface_m2,
            :rooms, :bedrooms, :bathrooms, :features, :description,
            :main_image, :images_count, :scraped_date
        )
    """, listings)
    conn.commit()

# ---------------------------------------------------------------------------
# HTML Parsing with Scrapling
# ---------------------------------------------------------------------------

def parse_page_listings(html_content: bytes, transaction_type: str = "Vente", city: str = "Marrakech", default_quartier: str = "Autre / Centre") -> List[Dict[str, Any]]:
    """Parse listing boxes using Scrapling Selector."""
    page = Selector(html_content)
    boxes = page.xpath("//*[contains(@class, 'listingBox')]")
    items = []
    scraped_date = datetime.now().strftime("%Y-%m-%d")

    for box in boxes:
        # Link & Title
        link_el = box.xpath(".//a[contains(@href, '/a/') or contains(@href, '/pa/')]")
        if not link_el:
            continue
        url = link_el[0].attrib.get("href", "")
        if url.startswith("/"):
            url = "https://www.mubawab.ma" + url
        
        title = clean_text(link_el[0].text if link_el[0].text else link_el[0].attrib.get("title", ""))
        
        # ID
        id_match = re.search(r"/(?:pa|a)/(\d+)/", url)
        listing_id = id_match.group(1) if id_match else ""
        if not listing_id:
            continue

        # Price
        bdi_el = box.xpath(".//bdi")
        if bdi_el and bdi_el[0].text:
            raw_price = f"{clean_text(bdi_el[0].text)} DH"
        else:
            price_tags = box.xpath(".//*[contains(@class, 'price') or contains(@class, 'Price')]//text()").getall()
            raw_price = clean_text(" ".join(price_tags)) if price_tags else ""
        price_num = parse_price(raw_price)

        # Description
        desc_el = box.xpath(".//p[contains(@class, 'descLi') or contains(@class, 'listingP')]")
        description = clean_text(desc_el[0].text) if desc_el and desc_el[0].text else ""

        # Specifications
        spans = box.xpath(".//span//text()").getall()
        surface_raw = ""
        rooms = ""
        bedrooms = ""
        bathrooms = ""
        for s in spans:
            sc = clean_text(s)
            if re.search(r"\d+\s*m²", sc, re.I):
                surface_raw = sc
            elif re.search(r"\d+\s*Pièce", sc, re.I):
                rooms = sc
            elif re.search(r"\d+\s*(?:Ch\b|Chambre)", sc, re.I):
                bedrooms = sc
            elif re.search(r"\d+\s*Salle", sc, re.I):
                bathrooms = sc
        surface_num = parse_surface(surface_raw)

        # Features
        feature_spans = box.xpath(".//span[contains(@class, 'fSize12')]//text()").getall()
        features = [clean_text(f) for f in feature_spans if clean_text(f)]
        features_str = ", ".join(features)

        # House Type & Quartier
        house_type = detect_house_type(title, url, description)
        quartier = detect_quartier(title, url, description)
        if quartier == "Autre / Centre" and default_quartier != "Autre / Centre":
            quartier = default_quartier

        # Images
        images = []
        for img in box.xpath(".//img"):
            src = img.attrib.get("data-lazy") or img.attrib.get("data-url") or img.attrib.get("data-src") or img.attrib.get("src")
            if src and "mubawab-media" in src and src not in images:
                images.append(src)

        item = {
            "id": listing_id,
            "title": title,
            "url": url,
            "transaction_type": transaction_type,
            "house_type": house_type,
            "city": city,
            "quartier": quartier,
            "price_raw": raw_price,
            "price_numeric": price_num,
            "surface_raw": surface_raw,
            "surface_m2": surface_num,
            "rooms": rooms,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "features": features_str,
            "description": description,
            "main_image": images[0] if images else "",
            "images_count": len(images),
            "scraped_date": scraped_date,
        }
        items.append(item)

    return items
