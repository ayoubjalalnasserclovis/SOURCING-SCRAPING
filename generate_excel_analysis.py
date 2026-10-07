"""
Générateur du Classeur Excel d'Analyse Immobilière de Marrakech.
Génère un fichier Excel professionnel et richement formaté :
'analyse_marche_immobilier_marrakech.xlsx'
comprenant toutes les données clés d'une étude de marché classique :
- Page 1 : 📊 Tableau de Bord Macro (KPIs, volumes, prix moyens, médianes)
- Page 2 : 🏢 Prix au m² & Rentabilité par Quartier (Appartements)
- Page 3 : 🏡 Villas & Domaines d'Exception (Par secteur & axe routier)
- Page 4 : 🏰 Marché des Riads en Médina (Habitation, Maisons d'Hôtes, Palais)
- Page 5 : 📍 Matrice Globale de Tous les Quartiers (Tous types de biens confondus)
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
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

DB_PATH = "sourcing_listings.db"
OUTPUT_XLSX = "analyse_marche_immobilier_marrakech.xlsx"

# Palette de couleurs professionnelle (Corporate Real Estate)
NAVY_DARK = "0F172A"      # Slate 900
NAVY_HEADER = "1E293B"    # Slate 800
BLUE_ACCENT = "2563EB"    # Blue 600
GREEN_EMERALD = "059669"  # Emerald 600
AMBER_GOLD = "D97706"     # Amber 600
PURPLE_ROYAL = "7C3AED"   # Violet 600
LIGHT_BG = "F8FAFC"       # Slate 50
BORDER_COLOR = "CBD5E1"   # Slate 300

font_title = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
font_subtitle = Font(name="Calibri", size=10, italic=True, color="94A3B8")
font_section = Font(name="Calibri", size=13, bold=True, color=NAVY_DARK)
font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
font_bold = Font(name="Calibri", size=10, bold=True, color=NAVY_DARK)
font_regular = Font(name="Calibri", size=10, color="1E293B")
font_muted = Font(name="Calibri", size=9, italic=True, color="64748B")

fill_header_navy = PatternFill(start_color=NAVY_HEADER, end_color=NAVY_HEADER, fill_type="solid")
fill_header_blue = PatternFill(start_color=BLUE_ACCENT, end_color=BLUE_ACCENT, fill_type="solid")
fill_header_green = PatternFill(start_color=GREEN_EMERALD, end_color=GREEN_EMERALD, fill_type="solid")
fill_header_amber = PatternFill(start_color=AMBER_GOLD, end_color=AMBER_GOLD, fill_type="solid")
fill_header_purple = PatternFill(start_color=PURPLE_ROYAL, end_color=PURPLE_ROYAL, fill_type="solid")
fill_zebra = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

thin_border = Border(
    left=Side(style="thin", color=BORDER_COLOR),
    right=Side(style="thin", color=BORDER_COLOR),
    top=Side(style="thin", color=BORDER_COLOR),
    bottom=Side(style="thin", color=BORDER_COLOR)
)

def format_sheet_headers(ws, title_text, subtitle_text, banner_fill):
    ws.merge_cells("A1:I1")
    cell_t = ws["A1"]
    cell_t.value = title_text
    cell_t.font = font_title
    cell_t.fill = banner_fill
    cell_t.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 35

    ws.merge_cells("A2:I2")
    cell_s = ws["A2"]
    cell_s.value = subtitle_text
    cell_s.font = font_subtitle
    cell_s.fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    cell_s.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 20

def auto_fit_columns(ws, min_width=12):
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            # Skip merged banner row 1 and 2
            if cell.row in [1, 2]:
                continue
            if cell.value:
                val_str = str(cell.value)
                max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = max(max_len + 3, min_width)

def generate_analysis_workbook():
    print("=" * 70)
    print("📊 GÉNÉRATION DE L'EXCEL D'ANALYSE IMMOBILIÈRE DE MARRAKECH")
    print("=" * 70)
    t0 = time.time()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # =========================================================================
    # FEUILLE 1 : SYNTHÈSE MACRO & KPIS
    # =========================================================================
    ws1 = wb.create_sheet(title="📊 Synthèse Macro Marché")
    ws1.views.sheetView[0].showGridLines = True
    format_sheet_headers(
        ws1, 
        "MARRAKECH IMMOBILIER - TABLEAU DE BORD MACRO",
        f"Étude de marché basée sur 46 954 biens unifiés - Éditée le {datetime.now().strftime('%d/%m/%Y')}",
        fill_header_navy
    )

    # Table 1: Volumes globaux
    ws1["A4"] = "1. INDICATEURS MACRO-ÉCONOMIQUES GLOBAUX"
    ws1["A4"].font = font_section

    headers_kpi = ["Métrique Globale", "Volume Ventes", "Volume Locations", "Marché Total", "Observation Clé"]
    for col_idx, h in enumerate(headers_kpi, start=1):
        c = ws1.cell(row=5, column=col_idx, value=h)
        c.font = font_header
        c.fill = fill_header_navy
        c.alignment = Alignment(horizontal="center")

    total_all = cur.execute("SELECT COUNT(*) FROM sourcing_listings").fetchone()[0]
    vente_all = cur.execute("SELECT COUNT(*) FROM sourcing_listings WHERE transaction_type = 'Vente'").fetchone()[0]
    loc_all = cur.execute("SELECT COUNT(*) FROM sourcing_listings WHERE transaction_type = 'Location'").fetchone()[0]
    avg_price_v = cur.execute("SELECT AVG(price_mad) FROM sourcing_listings WHERE transaction_type = 'Vente' AND price_mad > 0").fetchone()[0]
    avg_price_l = cur.execute("SELECT AVG(price_mad) FROM sourcing_listings WHERE transaction_type = 'Location' AND price_mad > 0").fetchone()[0]
    avg_surf_v = cur.execute("SELECT AVG(surface_m2) FROM sourcing_listings WHERE transaction_type = 'Vente' AND surface_m2 > 0").fetchone()[0]
    avg_surf_l = cur.execute("SELECT AVG(surface_m2) FROM sourcing_listings WHERE transaction_type = 'Location' AND surface_m2 > 0").fetchone()[0]

    macro_data = [
        ["Nombre total de biens répertoriés", f"{vente_all:,}", f"{loc_all:,}", f"{total_all:,}", "100% couverture multi-plateformes"],
        ["Part du marché (%)", f"{(vente_all/total_all)*100:.1f} %", f"{(loc_all/total_all)*100:.1f} %", "100.0 %", "Marché locatif très actif & dynamique"],
        ["Prix / Loyer moyen", f"{int(avg_price_v):,} DH", f"{int(avg_price_l):,} DH/mois", "N/A", "Forte valeur patrimoniale à l'achat"],
        ["Surface moyenne habitable / terrain", f"{int(avg_surf_v):,} m²", f"{int(avg_surf_l):,} m²", f"{int((avg_surf_v+avg_surf_l)/2):,} m²", "Grands volumes grâce aux villas et riads"],
    ]
    for row_idx, row in enumerate(macro_data, start=6):
        for col_idx, val in enumerate(row, start=1):
            c = ws1.cell(row=row_idx, column=col_idx, value=val)
            c.font = font_regular
            c.border = thin_border
            if col_idx in [2, 3, 4]:
                c.alignment = Alignment(horizontal="right")

    # Table 2: Répartition par Plateforme
    ws1["A12"] = "2. RÉPARTITION DES VOLUMES PAR PLATEFORME SOURCE"
    ws1["A12"].font = font_section

    headers_plat = ["Plateforme Source", "Volume de Biens", "% du Marché", "Prix Moyen (DH)", "Prix Médian (DH)", "Segment Couvert"]
    for col_idx, h in enumerate(headers_plat, start=1):
        c = ws1.cell(row=13, column=col_idx, value=h)
        c.font = font_header
        c.fill = fill_header_blue
        c.alignment = Alignment(horizontal="center")

    plat_rows = cur.execute("""
        SELECT platform, COUNT(*) as cnt, AVG(price_mad) as avg_p
        FROM sourcing_listings
        GROUP BY platform
        ORDER BY cnt DESC
    """).fetchall()

    for idx, p in enumerate(plat_rows, start=14):
        pct = (p["cnt"] / total_all) * 100
        avg_p = int(p["avg_p"]) if p["avg_p"] else 0
        med_row = cur.execute("SELECT price_mad FROM sourcing_listings WHERE platform = ? AND price_mad > 0 ORDER BY price_mad LIMIT 1 OFFSET ?", (p["platform"], p["cnt"] // 2)).fetchone()
        med_p = med_row[0] if med_row else 0
        segment_desc = {
            "Avito": "Particuliers, propriétaires directs, forte rotation",
            "Mubawab": "Référence nationale, promoteurs & agences certifiées",
            "Kensington Luxury": "Ultra-luxe, golfs & domaines d'exception (Christie's)",
            "Sarouty / Selektimmo": "Agences professionnelles, standing & prestige",
            "Bosworth Property": "Spécialiste Riads Médina & maisons d'hôtes"
        }.get(p["platform"], "Général")

        ws1.cell(row=idx, column=1, value=p["platform"]).font = font_bold
        ws1.cell(row=idx, column=2, value=f"{p['cnt']:,}").alignment = Alignment(horizontal="right")
        ws1.cell(row=idx, column=3, value=f"{pct:.1f} %").alignment = Alignment(horizontal="right")
        ws1.cell(row=idx, column=4, value=f"{avg_p:,} DH").alignment = Alignment(horizontal="right")
        ws1.cell(row=idx, column=5, value=f"{med_p:,} DH").alignment = Alignment(horizontal="right")
        ws1.cell(row=idx, column=6, value=segment_desc)
        for c_i in range(1, 7):
            ws1.cell(row=idx, column=c_i).border = thin_border

    # Table 3: Répartition par Type de Bien
    ws1["A21"] = "3. RÉPARTITION PAR TYPOLOGIE DE BIEN"
    ws1["A21"].font = font_section

    headers_type = ["Type de Propriété", "Volume d'Annonces", "% Total", "Prix Moyen (DH)", "Surface Moyenne (m²)", "Prix Moyen au m² (DH/m²)"]
    for col_idx, h in enumerate(headers_type, start=1):
        c = ws1.cell(row=22, column=col_idx, value=h)
        c.font = font_header
        c.fill = fill_header_green
        c.alignment = Alignment(horizontal="center")

    type_rows = cur.execute("""
        SELECT house_type, COUNT(*) as cnt, AVG(price_mad) as avg_p, AVG(surface_m2) as avg_s,
               AVG(CASE WHEN surface_m2 >= 15 AND price_mad > 0 THEN CAST(price_mad AS FLOAT) / surface_m2 END) as avg_pm2
        FROM sourcing_listings
        GROUP BY house_type
        ORDER BY cnt DESC
    """).fetchall()

    for idx, t in enumerate(type_rows, start=23):
        pct = (t["cnt"] / total_all) * 100
        avg_p = int(t["avg_p"]) if t["avg_p"] else 0
        avg_s = round(t["avg_s"], 1) if t["avg_s"] else 0
        avg_pm2 = int(t["avg_pm2"]) if t["avg_pm2"] else 0

        ws1.cell(row=idx, column=1, value=t["house_type"] or "Autre").font = font_bold
        ws1.cell(row=idx, column=2, value=f"{t['cnt']:,}").alignment = Alignment(horizontal="right")
        ws1.cell(row=idx, column=3, value=f"{pct:.1f} %").alignment = Alignment(horizontal="right")
        ws1.cell(row=idx, column=4, value=f"{avg_p:,} DH").alignment = Alignment(horizontal="right")
        ws1.cell(row=idx, column=5, value=f"{avg_s} m²").alignment = Alignment(horizontal="right")
        ws1.cell(row=idx, column=6, value=f"{avg_pm2:,} DH/m²" if avg_pm2 else "N/A").alignment = Alignment(horizontal="right")
        for c_i in range(1, 7):
            ws1.cell(row=idx, column=c_i).border = thin_border

    auto_fit_columns(ws1)

    # =========================================================================
    # FEUILLE 2 : APPARTEMENTS - PRIX AU M² & RENTABILITÉ PAR QUARTIER
    # =========================================================================
    ws2 = wb.create_sheet(title="🏢 Appartements & Rendement")
    ws2.views.sheetView[0].showGridLines = True
    format_sheet_headers(
        ws2,
        "MARCHÉ DES APPARTEMENTS À MARRAKECH : PRIX AU M² & RENDEMENT LOCATIF",
        "Analyse croisée des transactions de vente et loyers mensuels moyens par quartier",
        fill_header_blue
    )

    headers_app = [
        "Rang", "Quartier", "Volume Ventes", "Prix Total Moyen (DH)", 
        "Surface Moyenne (m²)", "Prix au m² Moyen (DH/m²)", "Loyer Mensuel Moyen (DH)", 
        "Loyer au m² (DH/m²/mois)", "Rendement Brut Estimé (%)", "Typologie Quartier"
    ]
    for col_idx, h in enumerate(headers_app, start=1):
        c = ws2.cell(row=4, column=col_idx, value=h)
        c.font = font_header
        c.fill = fill_header_navy
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws2.row_dimensions[4].height = 28

    query_app_data = """
    SELECT 
        v.quartier,
        v.nb_ventes,
        v.prix_moyen_vente,
        v.surf_moy_vente,
        v.prix_m2_moyen,
        COALESCE(l.loyer_moyen, 0) as loyer_moyen,
        COALESCE(l.loyer_m2_moyen, 0) as loyer_m2_moyen
    FROM (
        SELECT 
            quartier,
            COUNT(*) as nb_ventes,
            ROUND(AVG(price_mad), 0) as prix_moyen_vente,
            ROUND(AVG(surface_m2), 1) as surf_moy_vente,
            ROUND(AVG(CAST(price_mad AS FLOAT) / surface_m2), 0) as prix_m2_moyen
        FROM sourcing_listings
        WHERE transaction_type = 'Vente' AND house_type = 'Appartement'
          AND price_mad >= 150000 AND price_mad <= 20000000
          AND surface_m2 >= 25 AND surface_m2 <= 600
          AND quartier IS NOT NULL AND TRIM(quartier) != '' AND quartier != 'Autre / Centre' AND quartier != 'Marrakech'
        GROUP BY quartier
        HAVING COUNT(*) >= 10
    ) v
    LEFT JOIN (
        SELECT 
            quartier,
            ROUND(AVG(price_mad), 0) as loyer_moyen,
            ROUND(AVG(CAST(price_mad AS FLOAT) / surface_m2), 0) as loyer_m2_moyen
        FROM sourcing_listings
        WHERE transaction_type = 'Location' AND house_type = 'Appartement'
          AND price_mad >= 2000 AND price_mad <= 35000
          AND surface_m2 >= 25 AND surface_m2 <= 250
        GROUP BY quartier
    ) l ON v.quartier = l.quartier
    ORDER BY v.prix_m2_moyen DESC
    """
    rows_app = cur.execute(query_app_data).fetchall()

    for idx, r in enumerate(rows_app, start=5):
        # Calculate yield
        p_buy = r["prix_moyen_vente"]
        p_rent = r["loyer_moyen"]
        yld = round(((p_rent * 12) / p_buy) * 100, 2) if (p_rent > 0 and p_buy > 0) else "N/A"

        # Quartier classification
        pm2 = int(r["prix_m2_moyen"])
        if pm2 >= 23000:
            tier = "Ultra-Prestige & Hôtelier"
        elif pm2 >= 18000:
            tier = "Résidentiel Supérieur & Affaires"
        elif pm2 >= 14000:
            tier = "Intermédiaire Résidentiel"
        elif pm2 >= 10000:
            tier = "Moyen Standing / Familles"
        else:
            tier = "Économique / Accessible"

        row_vals = [
            idx - 4,
            r["quartier"],
            f"{r['nb_ventes']:,}",
            f"{int(r['prix_moyen_vente']):,} DH",
            f"{r['surf_moy_vente']} m²",
            f"{int(r['prix_m2_moyen']):,} DH/m²",
            f"{int(r['loyer_moyen']):,} DH/mois" if r["loyer_moyen"] > 0 else "N/A",
            f"{int(r['loyer_m2_moyen']):,} DH/m²" if r["loyer_m2_moyen"] > 0 else "N/A",
            f"{yld} %" if yld != "N/A" else "N/A",
            tier
        ]
        for col_idx, val in enumerate(row_vals, start=1):
            c = ws2.cell(row=idx, column=col_idx, value=val)
            c.font = font_regular
            c.border = thin_border
            if col_idx in [1]:
                c.alignment = Alignment(horizontal="center")
            elif col_idx in [3, 4, 5, 6, 7, 8, 9]:
                c.alignment = Alignment(horizontal="right")
            if col_idx == 2:
                c.font = font_bold

    auto_fit_columns(ws2)

    # =========================================================================
    # FEUILLE 3 : VILLAS & DOMAINES D'EXCEPTION
    # =========================================================================
    ws3 = wb.create_sheet(title="🏡 Villas & Domaines")
    ws3.views.sheetView[0].showGridLines = True
    format_sheet_headers(
        ws3,
        "MARCHÉ DES VILLAS ET DOMAINES À MARRAKECH & ENVIRONS",
        "Analyse par secteur géographique, axe routier et domaine de golf",
        fill_header_green
    )

    headers_villa = [
        "Rang", "Secteur / Axe Routier", "Offres Répertoriées", "Prix Total Moyen (DH)", 
        "Surface Moyenne (Bâti + Parc)", "Prix au m² Global (DH/m²)", "Part des Villas > 10M DH", "Segment & Environnement"
    ]
    for col_idx, h in enumerate(headers_villa, start=1):
        c = ws3.cell(row=4, column=col_idx, value=h)
        c.font = font_header
        c.fill = fill_header_navy
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws3.row_dimensions[4].height = 28

    query_villas_data = """
    SELECT 
        quartier,
        COUNT(*) as total_offres,
        ROUND(AVG(price_mad), 0) as prix_moyen,
        ROUND(AVG(surface_m2), 1) as surf_moyenne,
        ROUND(AVG(CAST(price_mad AS FLOAT) / surface_m2), 0) as prix_m2_moyen,
        ROUND((COUNT(CASE WHEN price_mad >= 10000000 THEN 1 END) * 100.0) / COUNT(*), 1) as pct_prestige
    FROM sourcing_listings
    WHERE transaction_type = 'Vente' AND house_type = 'Villa'
      AND price_mad >= 1000000 AND price_mad <= 90000000
      AND surface_m2 >= 150 AND surface_m2 <= 25000
      AND quartier IS NOT NULL AND TRIM(quartier) != '' AND quartier != 'Autre / Centre' AND quartier != 'Marrakech'
    GROUP BY quartier
    HAVING COUNT(*) >= 8
    ORDER BY prix_moyen DESC
    """
    rows_villas = cur.execute(query_villas_data).fetchall()

    for idx, r in enumerate(rows_villas, start=5):
        p_avg = int(r["prix_moyen"])
        if p_avg >= 14000000:
            env = "Ultra-Luxe / Parcs & Golfs fermés"
        elif p_avg >= 8000000:
            env = "Prestige & Villas d'architecte"
        elif p_avg >= 5000000:
            env = "Résidences fermées & Campagne prisée"
        else:
            env = "Villas urbaines familiales & Périurbain"

        row_vals = [
            idx - 4,
            r["quartier"],
            f"{r['total_offres']:,}",
            f"{p_avg:,} DH",
            f"{r['surf_moyenne']} m²",
            f"{int(r['prix_m2_moyen']):,} DH/m²",
            f"{r['pct_prestige']:.1f} %",
            env
        ]
        for col_idx, val in enumerate(row_vals, start=1):
            c = ws3.cell(row=idx, column=col_idx, value=val)
            c.font = font_regular
            c.border = thin_border
            if col_idx in [1]:
                c.alignment = Alignment(horizontal="center")
            elif col_idx in [3, 4, 5, 6, 7]:
                c.alignment = Alignment(horizontal="right")
            if col_idx == 2:
                c.font = font_bold

    auto_fit_columns(ws3)

    # =========================================================================
    # FEUILLE 4 : RIADS & MÉDINA HISTORIQUE
    # =========================================================================
    ws4 = wb.create_sheet(title="🏰 Riads & Médina")
    ws4.views.sheetView[0].showGridLines = True
    format_sheet_headers(
        ws4,
        "MARCHÉ DES RIADS, MAISONS D'HÔTES & DOUIRIAS EN MÉDINA",
        "Cartographie des prix et surfaces par quartier de la Médina et enclaves historiques",
        fill_header_amber
    )

    headers_riad = [
        "Rang", "District Médina", "Nombre de Riads", "Prix Moyen (DH)", 
        "Surface Moyenne au Sol / Habitable", "Prix au m² Moyen (DH/m²)", "Potentiel d'Exploitation Touristique"
    ]
    for col_idx, h in enumerate(headers_riad, start=1):
        c = ws4.cell(row=4, column=col_idx, value=h)
        c.font = font_header
        c.fill = fill_header_navy
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws4.row_dimensions[4].height = 28

    query_riads_data = """
    SELECT 
        COALESCE(NULLIF(quartier, ''), 'Médina Centrale') as district,
        COUNT(*) as total_riads,
        ROUND(AVG(price_mad), 0) as prix_moyen,
        ROUND(AVG(surface_m2), 1) as surf_moyenne,
        ROUND(AVG(CAST(price_mad AS FLOAT) / surface_m2), 0) as prix_m2_moyen
    FROM sourcing_listings
    WHERE transaction_type = 'Vente' AND house_type = 'Riad'
      AND price_mad >= 400000 AND price_mad <= 50000000
      AND surface_m2 >= 40 AND surface_m2 <= 2000
    GROUP BY district
    HAVING COUNT(*) >= 5
    ORDER BY total_riads DESC
    """
    rows_riads = cur.execute(query_riads_data).fetchall()

    for idx, r in enumerate(rows_riads, start=5):
        p_avg = int(r["prix_moyen"])
        if p_avg >= 10000000:
            pot = "Palais & Riads d'Hôtes de Luxe (10+ suites)"
        elif p_avg >= 5000000:
            pot = "Maison d'Hôtes titrée rentable (5 à 8 suites)"
        elif p_avg >= 2500000:
            pot = "Habitation privée / Rénovation de charme"
        else:
            pot = "Petite douiria / Opportunité rénovation"

        row_vals = [
            idx - 4,
            r["district"],
            f"{r['total_riads']:,}",
            f"{p_avg:,} DH",
            f"{r['surf_moyenne']} m²",
            f"{int(r['prix_m2_moyen']):,} DH/m²",
            pot
        ]
        for col_idx, val in enumerate(row_vals, start=1):
            c = ws4.cell(row=idx, column=col_idx, value=val)
            c.font = font_regular
            c.border = thin_border
            if col_idx in [1]:
                c.alignment = Alignment(horizontal="center")
            elif col_idx in [3, 4, 5, 6]:
                c.alignment = Alignment(horizontal="right")
            if col_idx == 2:
                c.font = font_bold

    auto_fit_columns(ws4)

    # =========================================================================
    # FEUILLE 5 : MATRICE COMPLÈTE DE TOUS LES QUARTIERS
    # =========================================================================
    ws5 = wb.create_sheet(title="📍 Matrice Tous Quartiers")
    ws5.views.sheetView[0].showGridLines = True
    format_sheet_headers(
        ws5,
        "MATRICE COMPLÈTE DU MARCHÉ IMMOBILIER PAR QUARTIER (TOUTES CATÉGORIES)",
        "Inventaire intégral des 46 954 biens : volumes, prix globaux, surfaces et ventilation par type",
        fill_header_purple
    )

    headers_all = [
        "Rang", "Quartier / Zone", "Total Annonces", "Part Marché (%)", "Prix Moyen Global (DH)", 
        "Surface Moyenne (m²)", "Prix au m² Moyen (DH/m²)", "Appartements", "Villas", "Riads", "Terrains", "Commerces/Bureaux"
    ]
    for col_idx, h in enumerate(headers_all, start=1):
        c = ws5.cell(row=4, column=col_idx, value=h)
        c.font = font_header
        c.fill = fill_header_navy
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws5.row_dimensions[4].height = 28

    query_all_quartiers = """
    SELECT 
        quartier,
        COUNT(*) as total_biens,
        ROUND(AVG(price_mad), 0) as prix_moyen,
        ROUND(AVG(surface_m2), 1) as surf_moyenne,
        ROUND(AVG(CASE WHEN surface_m2 >= 15 AND price_mad > 0 THEN CAST(price_mad AS FLOAT) / surface_m2 END), 0) as prix_m2_moyen,
        COUNT(CASE WHEN house_type = 'Appartement' THEN 1 END) as nb_appart,
        COUNT(CASE WHEN house_type = 'Villa' THEN 1 END) as nb_villa,
        COUNT(CASE WHEN house_type = 'Riad' THEN 1 END) as nb_riad,
        COUNT(CASE WHEN house_type = 'Terrain' THEN 1 END) as nb_terrain,
        COUNT(CASE WHEN house_type IN ('Commerce', 'Bureau') THEN 1 END) as nb_comm
    FROM sourcing_listings
    WHERE quartier IS NOT NULL AND TRIM(quartier) != '' AND quartier != 'Autre / Centre' AND quartier != 'Marrakech'
    GROUP BY quartier
    ORDER BY total_biens DESC
    """
    rows_all = cur.execute(query_all_quartiers).fetchall()

    for idx, r in enumerate(rows_all, start=5):
        pct = (r["total_biens"] / total_all) * 100
        p_avg = int(r["prix_moyen"]) if r["prix_moyen"] else 0
        s_avg = r["surf_moyenne"] if r["surf_moyenne"] else 0
        pm2_avg = int(r["prix_m2_moyen"]) if r["prix_m2_moyen"] else 0

        row_vals = [
            idx - 4,
            r["quartier"],
            f"{r['total_biens']:,}",
            f"{pct:.1f} %",
            f"{p_avg:,} DH",
            f"{s_avg} m²",
            f"{pm2_avg:,} DH/m²" if pm2_avg else "N/A",
            f"{r['nb_appart']:,}",
            f"{r['nb_villa']:,}",
            f"{r['nb_riad']:,}",
            f"{r['nb_terrain']:,}",
            f"{r['nb_comm']:,}"
        ]
        for col_idx, val in enumerate(row_vals, start=1):
            c = ws5.cell(row=idx, column=col_idx, value=val)
            c.font = font_regular
            c.border = thin_border
            if col_idx in [1]:
                c.alignment = Alignment(horizontal="center")
            elif col_idx in [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]:
                c.alignment = Alignment(horizontal="right")
            if col_idx == 2:
                c.font = font_bold

    auto_fit_columns(ws5)

    # Sauvegarde finale
    print(f"\n💾 Sauvegarde du classeur d'analyse : '{OUTPUT_XLSX}'...")
    wb.save(OUTPUT_XLSX)
    dur = time.time() - t0
    size_mb = os.path.getsize(OUTPUT_XLSX) / (1024 * 1024)
    print(f"✅ Classeur d'analyse généré avec succès en {dur:.1f}s ! Taille : {size_mb:.2f} MB")
    print("=" * 70)

if __name__ == "__main__":
    generate_analysis_workbook()
