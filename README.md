# 🏰 Marrakech Multi-Platform Real Estate Sourcing & Intelligence (`SOURCING-SCRAPING`)

> **Comprehensive multi-source real estate scraping, data unification, and market exploration platform for Marrakech, Morocco.**  
> Powered by [Scrapling](https://github.com/d4vinci/Scrapling), `curl_cffi` (browser fingerprint impersonation), SQLite, and modern vanilla web technologies.

---

## 🌟 Executive Summary

This repository aggregates and normalizes property listings across **5 distinct market ecosystems** in Marrakech to provide complete coverage of the local real estate landscape:

| Source Platform | Market Segment | Captured Volume | Primary Asset Classes |
| :--- | :--- | :--- | :--- |
| **Mubawab.ma** | Moroccan Market Benchmark | **3,054 listings** | Appartements, Villas, Terrains, Bureaux |
| **Kensington Morocco** | Ultra-Luxury & Christie's Affiliate | **798 listings** | Palatial Villas, Golf Estates, Luxury Riads |
| **Avito.ma** | Direct Owners & Peer-to-Peer | **250 listings** | High-yield apartments, Studios, Townhouses |
| **Sarouty.ma / Barnes** | Professional Agencies & Prestige | **231 listings** | Agency residences, Modern developments |
| **Bosworth Property** | Authentic Medina & Historic Riads | **179 listings** | Riads, Maisons d'Hôtes, Historic Palaces |
| **TOTAL UNIFIED** | **All 5 Platforms** | **4,508 listings** | **Complete Marrakech Real Estate Inventory** |

---

## 📊 Unified Market Breakdown (4,508 Listings)

### 🏷️ Breakdown by Asset / House Type

| House Type | Total Listings | Average Price (MAD) | Key Segments Covered |
| :--- | :--- | :--- | :--- |
| **Villa / Domaine** | **1,595** | 6,850,000 DH | Palmeraie, Amelkis, Al Maaden, Route de l'Ourika |
| **Appartement** | **1,524** | 780,000 DH | Guéliz, Hivernage, Majorelle, Agdal |
| **Riad / Maison d'Hôtes** | **445** | 4,250,000 DH | Médina, Kasbah, Mouassine, Bab Doukkala |
| **Studio** | **148** | 520,000 DH | Centre-ville, Guéliz, Victor Hugo |
| **Terrain** | **238** | 7,120,000 DH | Route de Fès, Route de Tahanaout, Palmeraie |
| **Duplex / Penthouse** | **112** | 1,890,000 DH | Hivernage, Guéliz, Targa |
| **Commerce & Bureau** | **198** | 940,000 DH | Guéliz, Avenue Mohammed V, Allal Al Fassi |
| **Autre / Maison** | **248** | 2,150,000 DH | Targa, Semlalia, M'hamid |

---

## 🗄️ Dataset Artifacts & Formats

All datasets are structured with normalized schemas, validated numbers (`price_mad`, `surface_m2`, `bedrooms`, `bathrooms`), cleaned neighborhood tags, high-resolution media URLs, and direct links to original listings.

### 🌐 Unified Master Datasets
- **SQLite Database**: `sourcing_listings.db` (Indexed on `platform`, `house_type`, `quartier`, `price_mad`, `surface_m2`)
- **JSON Full Export**: `sourcing_all_listings.json` (4,508 records, ~6.3 MB)
- **CSV Full Export**: `sourcing_all_listings.csv` (4,508 records, ~4.5 MB)

### 📁 Platform-Specific Datasets
- **Avito.ma**: `avito_marrakech.json` & `avito_marrakech.csv` (250 records)
- **Kensington Luxury**: `kensington_marrakech.json` & `kensington_marrakech.csv` (798 records)
- **Bosworth Property**: `bosworth_marrakech.json` & `bosworth_marrakech.csv` (179 records)
- **Sarouty / Barnes**: `sarouty_marrakech.json` & `sarouty_marrakech.csv` (231 records)
- **Mubawab.ma**: `mubawab_complete_listings.json` & `mubawab_complete_listings.csv` (3,054 records)

---

## 🖥️ Interactive Web Intelligence Explorer

The repository contains a lightweight, zero-dependency, ultra-fast web application (`index.html`, `style.css`, `app.js`, `data.js`):

- **Multi-Source Filter**: Toggle between all platforms (`Mubawab`, `Kensington`, `Avito`, `Sarouty`, `Bosworth`).
- **Granular Real Estate Search**: Filter by Transaction (`Vente` vs `Location`), Property Type (`Villa`, `Riad`, `Appartement`, etc.), Quartier, Price range (MAD), and Surface (m²).
- **Sorting Engine**: Sort by Price (Ascending/Descending), Surface, or Relevance.
- **Detailed Modal Inspector**: View full descriptions, amenities tags, photo counts, and one-click redirection to official platform ad pages.
- **Responsive & Standalone**: Self-contained client-side architecture with responsive mobile drawer filters and instant client-side pagination.

---

## 🛠️ Architecture & Anti-Bot Strategy

```
                      ┌──────────────────────────────────────────────┐
                      │        Multi-Platform Scraping Suite         │
                      └──────────────────────┬───────────────────────┘
                                             │
      ┌──────────────────┬───────────────────┼───────────────────┬──────────────────┐
      ▼                  ▼                   ▼                   ▼                  ▼
┌───────────┐      ┌───────────┐       ┌───────────┐       ┌───────────┐      ┌───────────┐
│  Mubawab  │      │ Kensington│       │   Avito   │       │  Sarouty  │      │ Bosworth  │
│  Scraper  │      │  Luxury   │       │  Direct   │       │  Agency   │      │  Medina   │
└─────┬─────┘      └─────┬─────┘       └─────┬─────┘       └─────┬─────┘      └─────┬─────┘
      │                  │                   │                   │                  │
      └──────────────────┼───────────────────┼───────────────────┼──────────────────┘
                         ▼                   ▼                   ▼
             ┌────────────────────────────────────────────────────────┐
             │       unify_sourcing.py (Currency, Normalization)      │
             └───────────────────────────┬────────────────────────────┘
                                         ▼
             ┌────────────────────────────────────────────────────────┐
             │   sourcing_listings.db (SQLite) + Master JSON & CSV    │
             └───────────────────────────┬────────────────────────────┘
                                         ▼
             ┌────────────────────────────────────────────────────────┐
             │  Web Intelligence Explorer (index.html + data.js)      │
             └────────────────────────────────────────────────────────┘
```

1. **Anti-Bot Defense**:
   - `curl_cffi` TLS fingerprinting (`impersonate="chrome120"`) replicates real browser TLS client hellos, HTTP/2 frames, and header orders.
   - Bypasses Cloudflare, Datadome, and Akamai rate limiting without headful browser overhead.
2. **Selector Engine**:
   - Built on `Scrapling` CSS/XPath selector engine with resilient fallbacks for dynamic layouts and Next.js hydration scripts (`__NEXT_DATA__`).
3. **Normalization & Quality Control**:
   - Automatic currency exchange conversion for foreign riad and villa portals (EUR & GBP to Moroccan Dirhams MAD).
   - Standardized neighborhood taxonomy (e.g. *Guéliz*, *Palmeraie*, *Hivernage*, *Médina*, *Amelkis*, *Targa*).

---

## 🚀 Quickstart & Usage

### 1. Installation & Environment Setup

```bash
# Clone the repository
git clone https://github.com/ayoubjalalnasserclovis/SOURCING-SCRAPING.git
cd SOURCING-SCRAPING

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install required dependencies
pip install scrapling curl_cffi
```

### 2. Run Individual Scrapers

```bash
# Scrape Kensington Luxury Properties
python scrape_kensington.py

# Scrape Avito Marrakech
python scrape_avito.py

# Scrape Bosworth Medina Riads
python scrape_bosworth.py

# Scrape Sarouty / Barnes Agencies
python scrape_sarouty_marrakech.py
```

### 3. Orchestrate Full Sourcing & Web Build

```bash
# Runs all scrapers, unifies datasets, and rebuilds data.js for the web app:
python run_all_sourcing.py
```

### 4. Launch Local Web Dashboard

Simply open `index.html` in any modern web browser or start a local server:

```bash
python -m http.server 8000
# Then navigate to: http://localhost:8000
```

---

## ⚖️ License & Disclaimer

This project is created for market research, sourcing intelligence, and academic exploration. All intellectual property, property descriptions, photographs, and trademarks belong to their respective platforms and listing owners.
