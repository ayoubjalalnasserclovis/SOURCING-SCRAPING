import sqlite3
import json

conn = sqlite3.connect("sourcing_listings.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Overview counts
total = cur.execute("SELECT COUNT(*) FROM sourcing_listings").fetchone()[0]
vente_count = cur.execute("SELECT COUNT(*) FROM sourcing_listings WHERE transaction_type = 'Vente'").fetchone()[0]
loc_count = cur.execute("SELECT COUNT(*) FROM sourcing_listings WHERE transaction_type = 'Location'").fetchone()[0]

print(f"Total Listings: {total:,} (Vente: {vente_count:,}, Location: {loc_count:,})")

# 2. Neighborhood analysis for Ventes (Sales) where surface and price are valid
# Filter out extreme outliers: surface between 20 and 5000 m2, price between 100,000 and 100,000,000 MAD
query_ventes_quartier = """
SELECT 
    quartier,
    COUNT(*) as total_annonces,
    ROUND(AVG(price_mad), 0) as prix_moyen,
    ROUND(AVG(surface_m2), 1) as surface_moyenne,
    ROUND(AVG(CAST(price_mad AS FLOAT) / surface_m2), 0) as prix_m2_moyen,
    COUNT(CASE WHEN house_type = 'Appartement' THEN 1 END) as nb_appart,
    COUNT(CASE WHEN house_type = 'Villa' THEN 1 END) as nb_villa,
    COUNT(CASE WHEN house_type = 'Riad' THEN 1 END) as nb_riad,
    COUNT(CASE WHEN house_type = 'Terrain' THEN 1 END) as nb_terrain
FROM sourcing_listings
WHERE transaction_type = 'Vente'
  AND price_mad >= 150000 AND price_mad <= 80000000
  AND surface_m2 >= 25 AND surface_m2 <= 10000
  AND quartier IS NOT NULL AND TRIM(quartier) != '' AND quartier != 'Autre / Centre' AND quartier != 'Marrakech'
GROUP BY quartier
HAVING COUNT(*) >= 20
ORDER BY total_annonces DESC
"""

rows = cur.execute(query_ventes_quartier).fetchall()

print("\n--- ANALYSE PAR QUARTIER (VENTES) ---")
print(f"{'Quartier':<25} | {'Annonces':<8} | {'Prix Moyen (DH)':<16} | {'Surf Moy (m²)':<14} | {'Prix/m² Moyen (DH)':<18} | {'Appart':<6} | {'Villa':<6} | {'Riad':<6}")
print("-" * 105)

top_quartiers = []
for r in rows:
    top_quartiers.append(dict(r))
    print(f"{r['quartier']:<25} | {r['total_annonces']:<8} | {int(r['prix_moyen']):>12,d} DH | {r['surface_moyenne']:>10.1f} m² | {int(r['prix_m2_moyen']):>14,d} DH/m² | {r['nb_appart']:<6} | {r['nb_villa']:<6} | {r['nb_riad']:<6}")

# 3. Appartement specific analysis (Prix au m2 standard pour appartements à Marrakech)
query_apparts = """
SELECT 
    quartier,
    COUNT(*) as total_annonces,
    ROUND(AVG(price_mad), 0) as prix_moyen,
    ROUND(AVG(surface_m2), 1) as surface_moyenne,
    ROUND(AVG(CAST(price_mad AS FLOAT) / surface_m2), 0) as prix_m2_moyen
FROM sourcing_listings
WHERE transaction_type = 'Vente'
  AND house_type = 'Appartement'
  AND price_mad >= 150000 AND price_mad <= 20000000
  AND surface_m2 >= 30 AND surface_m2 <= 500
  AND quartier IS NOT NULL AND TRIM(quartier) != '' AND quartier != 'Autre / Centre' AND quartier != 'Marrakech'
GROUP BY quartier
HAVING COUNT(*) >= 15
ORDER BY prix_m2_moyen DESC
"""

rows_apparts = cur.execute(query_apparts).fetchall()
print("\n--- PRIX AU M² DES APPARTEMENTS PAR QUARTIER (VENTE) ---")
print(f"{'Quartier':<25} | {'Annonces':<8} | {'Prix Moyen':<15} | {'Surf Moy':<10} | {'Prix/m² Moyen':<15}")
print("-" * 80)
for r in rows_apparts:
    print(f"{r['quartier']:<25} | {r['total_annonces']:<8} | {int(r['prix_moyen']):>11,d} DH | {r['surface_moyenne']:>6.1f} m² | {int(r['prix_m2_moyen']):>11,d} DH/m²")

# 4. Villas specific analysis
query_villas = """
SELECT 
    quartier,
    COUNT(*) as total_annonces,
    ROUND(AVG(price_mad), 0) as prix_moyen,
    ROUND(AVG(surface_m2), 1) as surface_moyenne,
    ROUND(AVG(CAST(price_mad AS FLOAT) / surface_m2), 0) as prix_m2_moyen
FROM sourcing_listings
WHERE transaction_type = 'Vente'
  AND house_type = 'Villa'
  AND price_mad >= 1000000 AND price_mad <= 100000000
  AND surface_m2 >= 150 AND surface_m2 <= 20000
  AND quartier IS NOT NULL AND TRIM(quartier) != '' AND quartier != 'Autre / Centre' AND quartier != 'Marrakech'
GROUP BY quartier
HAVING COUNT(*) >= 10
ORDER BY prix_moyen DESC
"""

rows_villas = cur.execute(query_villas).fetchall()
print("\n--- PRIX DES VILLAS PAR QUARTIER (VENTE) ---")
print(f"{'Quartier':<25} | {'Annonces':<8} | {'Prix Moyen':<16} | {'Surf Moy (m²)':<13} | {'Prix/m² Moyen':<15}")
print("-" * 80)
for r in rows_villas:
    print(f"{r['quartier']:<25} | {r['total_annonces']:<8} | {int(r['prix_moyen']):>12,d} DH | {r['surface_moyenne']:>9.1f} m² | {int(r['prix_m2_moyen']):>11,d} DH/m²")

# 5. Riads in Medina
query_riads = """
SELECT 
    COUNT(*) as total_annonces,
    ROUND(AVG(price_mad), 0) as prix_moyen,
    ROUND(AVG(surface_m2), 1) as surface_moyenne,
    ROUND(AVG(CAST(price_mad AS FLOAT) / surface_m2), 0) as prix_m2_moyen
FROM sourcing_listings
WHERE transaction_type = 'Vente'
  AND house_type = 'Riad'
  AND price_mad >= 500000
  AND surface_m2 >= 50
"""
r_riad = cur.execute(query_riads).fetchone()
print(f"\n--- RIADS (MÉDINA & ENCLAVES) ---")
print(f"Total Riads analysés : {r_riad['total_annonces']} | Prix moyen : {int(r_riad['prix_moyen']):,d} DH | Surface moyenne : {r_riad['surface_moyenne']} m² | Prix/m² moyen : {int(r_riad['prix_m2_moyen']):,d} DH/m²")

# 6. Rental Market & Yield Analysis
query_locs = """
SELECT 
    quartier,
    COUNT(*) as total_locs,
    ROUND(AVG(price_mad), 0) as loyer_moyen,
    ROUND(AVG(surface_m2), 1) as surf_moyenne,
    ROUND(AVG(CAST(price_mad AS FLOAT) / surface_m2), 0) as loyer_m2_moyen
FROM sourcing_listings
WHERE transaction_type = 'Location'
  AND house_type = 'Appartement'
  AND price_mad >= 2000 AND price_mad <= 35000
  AND surface_m2 >= 30 AND surface_m2 <= 250
  AND quartier IS NOT NULL AND TRIM(quartier) != '' AND quartier != 'Autre / Centre' AND quartier != 'Marrakech'
GROUP BY quartier
HAVING COUNT(*) >= 15
ORDER BY total_locs DESC
LIMIT 12
"""
rows_locs = cur.execute(query_locs).fetchall()
print("\n--- MARCHÉ LOCATIF DES APPARTEMENTS (LOYERS MENSUELS & RENDEMENTS) ---")
print(f"{'Quartier':<22} | {'Offres Loc':<10} | {'Loyer Moyen':<14} | {'Loyer/m²':<10}")
print("-" * 65)
for r in rows_locs:
    print(f"{r['quartier']:<22} | {r['total_locs']:<10} | {int(r['loyer_moyen']):>9,d} DH | {int(r['loyer_m2_moyen']):>7,d} DH/m²")

