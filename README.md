# 🏰 Marrakech Multi-Platform Real Estate Sourcing & Intelligence (`SOURCING-SCRAPING`)

> **Comprehensive multi-source real estate scraping, data unification, and market exploration platform for Marrakech and surrounding regions.**  
> Powered by [Scrapling](https://github.com/d4vinci/Scrapling), `curl_cffi` (Chrome TLS fingerprint impersonation), SQLite, and modern vanilla web technologies.

---

## 🌟 Executive Summary & Full Inventory Coverage

This platform crawls the **integrality** of Marrakech property listings across **5 distinct market ecosystems**, capturing all active homes, apartments, luxury villas, riads, and land plots in and near Marrakech:

| Source Platform | Market Segment Covered | Total Active Volume | Primary Asset Classes |
| :--- | :--- | :--- | :--- |
| **Avito.ma** | Direct Owners, P2P & Volume Sales/Rentals | **33,743 listings** | Appartements, Maisons, Terrains, Studios |
| **Mubawab.ma** | Moroccan Commercial Benchmark | **11,450 listings** | Villas, Appartements, Riads, Commerces |
| **Kensington Morocco** | Ultra-Luxury & Christie's Affiliate | **882 listings** | Palatial Villas, Golf Domains, Riads |
| **Sarouty / Barnes / Selektimmo** | Professional Agencies & Prime Developments | **705 listings** | Agency residences, Modern developments |
| **Bosworth Property** | Authentic Medina & Historic Riads | **180 listings** | Riads, Maisons d'Hôtes, Historic Palaces |
| **TOTAL UNIFIED** | **100% Marrakech Market Coverage** | **46,954 listings** | **Complete Regional Real Estate Inventory** |

> [!NOTE]
> **Strict Storage Constraint**: Exactly **one photo max** (`main_image`) is retained per listing across all 46,954 properties to guarantee ultra-fast loading, lightweight payloads, and zero media bloat.

---

## 📊 Market Breakdown (46,954 Unified Listings)

### 🏷️ Breakdown by Asset / House Type

| House Type | Total Listings | % of Market | Key Regions & Sub-markets |
| :--- | :--- | :--- | :--- |
| **Appartement** | **25,372** | 54.0% | Guéliz, Hivernage, Centre Ville, Agdal, Victor Hugo, Majorelle |
| **Villa & Domaine** | **7,820** | 16.7% | Palmeraie, Amelkis, Al Maaden, Route de l'Ourika, Route d'Amizmiz |
| **Terrain & Ferme** | **3,893** | 8.3% | Route de Tahanaout, Route de Casablanca, Route de Fès, Tamansourt |
| **Riad & Maison d'Hôtes** | **2,217** | 4.7% | Médina, Kasbah, Mouassine, Bab Doukkala, Riad Laarous |
| **Maison** | **1,784** | 3.8% | Targa, Semlalia, M'hamid, Daoudiate |
| **Commerce & Local** | **1,841** | 3.9% | Guéliz, Av. Mohammed V, Allal El Fassi, Massira |
| **Studio** | **1,551** | 3.3% | Guéliz, Centre Ville, Majorelle, Semlalia |
| **Bureau & Plateau** | **1,010** | 2.2% | Guéliz, Hivernage, Avenue Mohammed VI |
| **Duplex & Penthouse** | **829** | 1.8% | Hivernage, Guéliz, Prestigia, Targa |
| **Autre / Résidence** | **637** | 1.4% | Périphérie & Communes satellites |

---

## 📍 Geographic & Neighborhood Coverage (Top Zones)

- **Guéliz & Centre Ville:** 10,200+ listings
- **Route de l'Ourika & Vallée:** 2,350+ listings
- **M'Hamid & Aéroport:** 2,050+ listings
- **Médina & Kasbah:** 1,600+ listings
- **Route de Casablanca:** 1,630+ listings
- **Targa & Massira:** 1,550+ listings
- **Agdal & Prestigia:** 1,400+ listings
- **Palmeraie & Environs:** 1,100+ listings
- **Hivernage:** 850+ listings
- **Route de Fès & Route d'Amizmiz:** 1,600+ listings

---

## 🗄️ Dataset Formats & Deliverables

All datasets are normalized with validated coordinates, types, dirham prices (`price_mad`), surface in square meters, and direct links to original listing pages.

### 🌐 Unified Master Datasets & Multi-Page Exports
- **📑 ANALYSE GLOBALE (1 Feuille par Quartier)** : `ANALYSE_GLOBALE.xlsx` / `ANALYSE GLOBALE.xlsx` (7.57 MB, 46 954 biens)
  - 📑 **Page 1 : 📑 Sommaire Interactif** (Index cliquable des 212 quartiers avec volumes, prix moyens, surfaces, ventilation par type et liens d'accès direct).
  - 📑 **Pages 2 à 213 : 🏘️ 212 Feuilles Dédiées par Quartier** (Guéliz, Hivernage, Palmeraie, Targa, Agdal, Médina, Prestigia, Route de l'Ourika, etc.).
  - 🔍 **Spécifications Complètes de Chaque Bien** : ID, Titre, Lien direct cliquable vers l'annonce, Type (Villa, Appartement, Riad, Terrain, Commerce...), Transaction (Vente/Location), Prix (DH), Surface (m²), Prix au m² (DH/m²), Chambres, Salles de Bain, Plateforme, Vendeur, Atouts, et Description.
  - 🔙 **Bouton Retour Sommaire** sur chaque feuille pour navigation instantanée.
- **📈 Étude de Marché & Rendements (.xlsx)**: `analyse_marche_immobilier_marrakech.xlsx` (Tableau de bord Macro, Prix/m² & Rendements locatifs appartements, Villas & Domaines d'exception, Marché des Riads en Médina, Matrice Tous Quartiers).
- **Classeur Excel Multi-Pages par Plateforme (.xlsx)**: `marrakech_immobilier_multi_plateformes.xlsx` (8.27 MB, 46,954 biens)
  - 📑 **Page 1 : 📊 Synthèse Globale** (KPIs, parts de marché, prix moyens, médianes, répartition par type)
  - 📑 **Page 2 : 🔵 Avito.ma** (33,743 biens)
  - 📑 **Page 3 : 🟠 Mubawab.ma** (11,450 biens)
  - 📑 **Page 4 : 🟢 Kensington Luxury** (882 biens)
  - 📑 **Page 5 : 🟣 Barnes & Sarouty** (705 biens)
  - 📑 **Page 6 : 🟤 Bosworth Property** (180 biens)
- **Générateurs Python**: `build_analyse_globale.py`, `generate_excel_analysis.py`, `export_multi_pages.py`
- **SQLite Database**: `sourcing_listings.db` (Indexed on `platform`, `house_type`, `quartier`, `price_mad`, `surface_m2`)
- **JSON Master Export**: `sourcing_all_listings.json` (46,954 records)
- **CSV Master Export**: `sourcing_all_listings.csv` (46,954 records)

### 📁 Individual Platform Datasets
- **Avito.ma**: `avito_marrakech.json` (33.5 MB) & `avito_marrakech.csv` (20.7 MB) — 33,743 properties
- **Mubawab.ma**: `mubawab_complete_listings.json` (13.8 MB) & `mubawab_complete_listings.csv` (9.5 MB) — 11,450 properties
- **Kensington Luxury**: `kensington_marrakech.json` (2.09 MB) & `kensington_marrakech.csv` (1.65 MB) — 882 properties
- **Sarouty / Barnes / Selektimmo**: `sarouty_marrakech.json` (0.98 MB) & `sarouty_marrakech.csv` (0.68 MB) — 705 properties
- **Bosworth Property**: `bosworth_marrakech.json` (0.45 MB) & `bosworth_marrakech.csv` (0.37 MB) — 180 properties

---

## 🖥️ Interactive Web Intelligence Explorer

- **Live URL**: [https://ayoubjalalnasserclovis.github.io/SOURCING-SCRAPING/](https://ayoubjalalnasserclovis.github.io/SOURCING-SCRAPING/)
- **Multi-Source Filter**: Toggle between `Avito`, `Mubawab`, `Kensington`, `Sarouty`, and `Bosworth`.
- **Search & Filters**: Type, Quartier, Vente vs Location, Price Min/Max (MAD), Surface Min/Max (m²).
- **Sorting**: Price (asc/desc), Surface, or Natural Rank.
- **Detailed Modal**: Inspect complete property description, amenities, and click through to original listing on each respective platform.

---

## 🛠️ Architecture & Scraping Engine

```
                      ┌────────────────────────────────────────────────────────┐
                      │          5 Autonomous Specialized Subagents            │
                      └───────────────────────────┬────────────────────────────┘
                                                  │
      ┌───────────────────┬───────────────────────┼───────────────────────┬───────────────────┐
      ▼                   ▼                       ▼                       ▼                   ▼
┌───────────┐       ┌───────────┐           ┌───────────┐           ┌───────────┐       ┌───────────┐
│   Avito   │       │  Mubawab  │           │Kensington │           │  Sarouty  │       │ Bosworth  │
│ 33,743 ads│       │ 11,450 ads│           │  882 ads  │           │  705 ads  │       │  180 ads  │
└─────┬─────┘       └─────┬─────┘           └─────┬─────┘           └─────┬─────┘       └─────┬─────┘
      │                   │                       │                       │                   │
      └───────────────────┴───────────────────────┼───────────────────────┴───────────────────┘
                                                  ▼
                                      ┌───────────────────────┐
                                      │   unify_sourcing.py   │
                                      │ Normalization & Dedupe│
                                      └───────────┬───────────┘
                                                  ▼
                                      ┌───────────────────────┐
                                      │  sourcing_listings.db │
                                      │ 46,954 Unified Records│
                                      └───────────┬───────────┘
                                                  ▼
                                      ┌───────────────────────┐
                                      │ Interactive Web App   │
                                      │ (index.html + data.js)│
                                      └───────────────────────┘
```

---

## 🚀 Quickstart

```bash
# Clone the repository
git clone https://github.com/ayoubjalalnasserclovis/SOURCING-SCRAPING.git
cd SOURCING-SCRAPING

# Install dependencies
pip install scrapling curl_cffi

# Run full sourcing pipeline across all 5 platforms
python run_all_sourcing.py

# Launch web explorer
python -m http.server 8000
```
