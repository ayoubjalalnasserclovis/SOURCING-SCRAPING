# Mubawab Real Estate Scraper & Intelligence Platform

A high-performance, anti-bot resilient scraping and analysis platform built with [Scrapling](https://github.com/d4vinci/Scrapling) and `curl_cffi` to extract and filter real estate listings from [Mubawab.ma](https://www.mubawab.ma).

## 📊 Dataset Overview (As of Today)
- **Total Listings Collected**: **3,054** active properties
- **Transactions Covered**: Both **Vente** (Sales) and **Location** (Rentals)
- **Storage**: High-speed **SQLite Database** (`mubawab_listings.db`) with indexes on house type, quartier, price, and surface.
- **Full Exports**:
  - `mubawab_complete_listings.json` (4.0 MB, 3,054 records)
  - `mubawab_complete_listings.csv` (2.8 MB, 3,054 records)

---

## 🏷️ Breakdown by House Type

| House Type | Count | % of Market | Avg Price (DH) | Avg Surface |
| :--- | :--- | :--- | :--- | :--- |
| **Appartement** | 1,316 | 43.1% | 531,626 DH | 107 m² |
| **Villa** | 944 | 30.9% | 3,393,642 DH | 1,571 m² |
| **Riad** | 172 | 5.6% | 3,304,231 DH | 263 m² |
| **Studio** | 125 | 4.1% | 1,009,325 DH | 77 m² |
| **Terrain** | 111 | 3.6% | 5,898,073 DH | 23,596 m² |
| **Duplex** | 97 | 3.2% | 1,213,025 DH | 133 m² |
| **Bureau** | 95 | 3.1% | 153,704 DH | 105 m² |
| **Commerce** | 79 | 2.6% | 1,288,290 DH | 230 m² |
| **Maison** | 41 | 1.3% | 2,227,166 DH | 3,542 m² |
| **Penthouse** | 3 | 0.1% | 3,744,740 DH | 212 m² |

---

## 📍 Breakdown by Top Quartiers / Neighborhoods

| Quartier / Zone | Count | % of Market | Avg Price (DH) |
| :--- | :--- | :--- | :--- |
| **Guéliz** | 668 | 21.9% | 819,220 DH |
| **Targa** | 165 | 5.4% | 2,032,346 DH |
| **Palmeraie** | 121 | 4.0% | 3,232,476 DH |
| **Hivernage** | 112 | 3.7% | 552,560 DH |
| **Agdal** | 109 | 3.6% | 1,174,504 DH |
| **Prestigia** | 104 | 3.4% | 732,020 DH |
| **Médina** | 100 | 3.3% | 3,490,531 DH |
| **Route de l'Ourika** | 98 | 3.2% | 3,641,614 DH |
| **Route de Casablanca** | 86 | 2.8% | 1,025,706 DH |
| **Route de Tahanaout** | 75 | 2.5% | 4,587,844 DH |
| **Victor Hugo** | 65 | 2.1% | 373,595 DH |
| **Amelkis** | 61 | 2.0% | 3,414,885 DH |
| **Semlalia** | 47 | 1.5% | 483,278 DH |
| **M'hamid** | 40 | 1.3% | 661,852 DH |
| **Majorelle** | 29 | 0.9% | 648,974 DH |

---

## 📁 Pre-Filtered Datasets Available

### By House Type
- `listings_appartements.csv` (1,316 listings)
- `listings_villas.csv` (944 listings)
- `listings_riads.csv` (172 listings)
- `listings_studios.csv` (125 listings)
- `listings_duplexs.csv` (97 listings)
- `listings_terrains.csv` (111 listings)
- `listings_maisons.csv` (41 listings)

### By Quartier
- `listings_quartier_guliz.csv` (668 listings)
- `listings_quartier_targa.csv` (165 listings)
- `listings_quartier_palmeraie.csv` (121 listings)
- `listings_quartier_hivernage.csv` (112 listings)
- `listings_quartier_agdal.csv` (109 listings)
- `listings_quartier_mdina.csv` (100 listings)
- `listings_quartier_mhamid.csv` (40 listings)
- `listings_quartier_majorelle.csv` (29 listings)

---

## 🔍 How to Filter and Query

Use the included `filter_listings.py` CLI utility:

```powershell
# Display summary breakdown
.venv\Scripts\python filter_listings.py --summary

# Filter by house type and quartier
.venv\Scripts\python filter_listings.py --type Villa --quartier Palmeraie

# Filter by type, quartier, price limit, and export to CSV
.venv\Scripts\python filter_listings.py --type Appartement --quartier Guéliz --max-price 1000000 --export-csv my_selection.csv

# Filter riads in Médina
.venv\Scripts\python filter_listings.py --type Riad --quartier Médina --limit 10
```

---

## 🚀 Re-Scraping / Expanding

To scrape additional pages or re-run:
```powershell
.venv\Scripts\python scrape_all.py --max-pages 100 --workers 8
```
