"""
Exportateur Multi-Pages Excel & CSV pour l'intégralité du marché immobilier de Marrakech.
Génère un classeur Excel (.xlsx) professionnel avec une page dédiée pour chaque plateforme,
ainsi qu'une page de synthèse globale.
Total : 46 954 biens immobiliers référencés.
"""

import sqlite3
import os
import sys
import time
from datetime import datetime

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import openpyxl
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

DB_PATH = "sourcing_listings.db"
OUTPUT_XLSX = "marrakech_immobilier_multi_plateformes.xlsx"

PLATFORMS_CONFIG = [
    {
        "name": "Avito",
        "sheet_title": "Avito (Particuliers & Ventes)",
        "query": "SELECT * FROM sourcing_listings WHERE platform = 'Avito' ORDER BY price_mad ASC",
        "color": "1E40AF"  # Blue
    },
    {
        "name": "Mubawab",
        "sheet_title": "Mubawab (Référence Maroc)",
        "query": "SELECT * FROM sourcing_listings WHERE platform = 'Mubawab' ORDER BY price_mad ASC",
        "color": "EA580C"  # Orange
    },
    {
        "name": "Kensington Luxury",
        "sheet_title": "Kensington (Ultra-Luxe & Golf)",
        "query": "SELECT * FROM sourcing_listings WHERE platform = 'Kensington Luxury' ORDER BY price_mad ASC",
        "color": "047857"  # Emerald
    },
    {
        "name": "Sarouty / Selektimmo",
        "sheet_title": "Barnes & Sarouty (Agences)",
        "query": "SELECT * FROM sourcing_listings WHERE platform = 'Sarouty / Selektimmo' ORDER BY price_mad ASC",
        "color": "7C3AED"  # Purple
    },
    {
        "name": "Bosworth Property",
        "sheet_title": "Bosworth (Riads & Médina)",
        "query": "SELECT * FROM sourcing_listings WHERE platform = 'Bosworth Property' ORDER BY price_mad ASC",
        "color": "92400E"  # Amber/Bronze
    },
]

HEADERS = [
    "ID",
    "Plateforme",
    "Titre du Bien",
    "Transaction",
    "Type de Bien",
    "Quartier / Zone",
    "Prix (MAD)",
    "Prix Affiché",
    "Surface (m²)",
    "Chambres",
    "Salles de bain",
    "Type Vendeur",
    "Lien Annonce Originale",
    "Photo Principale",
    "Date Extraction",
    "Description"
]

def safe_num(val):
    if val is None or val == "":
        return "N/A"
    try:
        n = int(float(str(val).replace(" ", "").replace("\xa0", "")))
        return n if n > 0 else "N/A"
    except Exception:
        return str(val) if str(val).strip() else "N/A"

def generate_multi_sheet_excel():
    print("=" * 70)
    print("📊 GÉNÉRATION DU CLASSEUR MULTI-PAGES EXCEL (46 954 BIENS)")
    print("=" * 70)
    t0 = time.time()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    total_count = cur.execute("SELECT COUNT(*) FROM sourcing_listings").fetchone()[0]
    print(f"[+] Total des annonces en base de données : {total_count:,}")

    wb = openpyxl.Workbook(write_only=True)

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    regular_font = Font(name="Calibri", size=10)

    # 1. PAGE DE SYNTHÈSE GLOBALE
    ws_summary = wb.create_sheet(title="📊 Synthèse Globale")
    
    # Titre synthèse
    title_font = Font(name="Calibri", size=16, bold=True, color="1E293B")
    subtitle_font = Font(name="Calibri", size=11, italic=True, color="64748B")
    
    c_title = WriteOnlyCell(ws_summary, value="MARRAKECH IMMOBILIER - SYNTHÈSE MULTI-PLATEFORMES")
    c_title.font = title_font
    ws_summary.append([c_title])
    
    c_sub = WriteOnlyCell(ws_summary, value=f"Extraction exhaustive au {datetime.now().strftime('%d/%m/%Y')} - 46 954 biens unifiés sur 5 plateformes")
    c_sub.font = subtitle_font
    ws_summary.append([c_sub])
    ws_summary.append([])

    # Table récapitulative des plateformes
    th_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    summary_headers = ["Plateforme Source", "Volume de Biens", "Part du Marché (%)", "Prix Moyen (MAD)", "Prix Médian (MAD)", "Onglet Dédié"]
    hdr_row = []
    for h in summary_headers:
        c = WriteOnlyCell(ws_summary, value=h)
        c.font = header_font
        c.fill = th_fill
        hdr_row.append(c)
    ws_summary.append(hdr_row)

    plat_stats = cur.execute("""
        SELECT platform, COUNT(*) as cnt, AVG(price_mad) as avg_p
        FROM sourcing_listings
        GROUP BY platform
        ORDER BY cnt DESC
    """).fetchall()

    for p in plat_stats:
        pct = (p["cnt"] / total_count) * 100
        avg_p = int(p["avg_p"]) if p["avg_p"] else 0
        
        # Get median
        med_row = cur.execute("""
            SELECT price_mad FROM sourcing_listings 
            WHERE platform = ? AND price_mad > 0 
            ORDER BY price_mad LIMIT 1 OFFSET ?
        """, (p["platform"], p["cnt"] // 2)).fetchone()
        med_p = med_row[0] if med_row else 0

        # Sheet name match
        matched_sheet = next((cfg["sheet_title"] for cfg in PLATFORMS_CONFIG if cfg["name"] == p["platform"]), p["platform"])

        row_cells = [
            WriteOnlyCell(ws_summary, value=p["platform"]),
            WriteOnlyCell(ws_summary, value=f"{p['cnt']:,}"),
            WriteOnlyCell(ws_summary, value=f"{pct:.1f} %"),
            WriteOnlyCell(ws_summary, value=f"{avg_p:,} DH"),
            WriteOnlyCell(ws_summary, value=f"{med_p:,} DH"),
            WriteOnlyCell(ws_summary, value=matched_sheet)
        ]
        for c in row_cells:
            c.font = regular_font
        ws_summary.append(row_cells)

    ws_summary.append([])
    
    # Top Types
    c_t2 = WriteOnlyCell(ws_summary, value="RÉPARTITION PAR TYPE DE BIEN")
    c_t2.font = Font(name="Calibri", size=13, bold=True, color="1E293B")
    ws_summary.append([c_t2])
    
    type_hdr_row = []
    for h in ["Type de Propriété", "Nombre de Biens", "% Total", "Prix Moyen (MAD)"]:
        c = WriteOnlyCell(ws_summary, value=h)
        c.font = header_font
        c.fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        type_hdr_row.append(c)
    ws_summary.append(type_hdr_row)

    type_stats = cur.execute("""
        SELECT house_type, COUNT(*) as cnt, AVG(price_mad) as avg_p
        FROM sourcing_listings
        GROUP BY house_type
        ORDER BY cnt DESC
    """).fetchall()

    for t in type_stats:
        pct = (t["cnt"] / total_count) * 100
        avg_p = int(t["avg_p"]) if t["avg_p"] else 0
        r_cells = [
            WriteOnlyCell(ws_summary, value=t["house_type"] or "Non spécifié"),
            WriteOnlyCell(ws_summary, value=f"{t['cnt']:,}"),
            WriteOnlyCell(ws_summary, value=f"{pct:.1f} %"),
            WriteOnlyCell(ws_summary, value=f"{avg_p:,} DH" if avg_p else "N/A"),
        ]
        for c in r_cells:
            c.font = regular_font
        ws_summary.append(r_cells)

    # 2. PAGES DÉDIÉES PAR PLATEFORME
    for cfg in PLATFORMS_CONFIG:
        plat_name = cfg["name"]
        sheet_title = cfg["sheet_title"]
        query = cfg["query"]
        color_hex = cfg["color"]
        
        print(f"\n▶️ Génération de la page : '{sheet_title}'...")
        ws = wb.create_sheet(title=sheet_title)
        
        # En-têtes stylisés
        fill_header = PatternFill(start_color=color_hex, end_color=color_hex, fill_type="solid")
        header_cells = []
        for h in HEADERS:
            c = WriteOnlyCell(ws, value=h)
            c.font = header_font
            c.fill = fill_header
            header_cells.append(c)
        ws.append(header_cells)

        rows = cur.execute(query).fetchall()
        print(f"   Writing {len(rows):,} rows for {plat_name}...")

        for r in rows:
            p_val = safe_num(r["price_mad"])
            s_val = safe_num(r["surface_m2"])
            b_val = safe_num(r["bedrooms"])
            ba_val = safe_num(r["bathrooms"])

            row_data = [
                r["id"],
                r["platform"],
                r["title"] or "",
                r["transaction_type"] or "Vente",
                r["house_type"] or "Autre",
                r["quartier"] or "Marrakech",
                p_val,
                r["price_raw"] or "",
                s_val,
                b_val,
                ba_val,
                r["seller_type"] or "Professionnel",
                r["url"] or "",
                r["main_image"] or "",
                r["scraped_at"] or "",
                (r["description"] or "")[:250]  # Concise description for Excel row
            ]
            
            cells = []
            for val in row_data:
                c = WriteOnlyCell(ws, value=val)
                c.font = regular_font
                cells.append(c)
            ws.append(cells)

    print(f"\n💾 Sauvegarde du classeur Excel : '{OUTPUT_XLSX}'...")
    wb.save(OUTPUT_XLSX)
    dur = time.time() - t0
    size_mb = os.path.getsize(OUTPUT_XLSX) / (1024 * 1024)
    print(f"✅ Classeur généré avec succès en {dur:.1f}s ! Taille : {size_mb:.2f} MB")
    print("=" * 70)

if __name__ == "__main__":
    generate_multi_sheet_excel()
