"""
Master Multi-Platform Sourcing Orchestrator.
Runs scrapers across all 5 Marrakech platforms, unifies listings into SQLite,
and generates full JSON/CSV datasets + web intelligence bundle.
"""

import subprocess
import sys
import time

SCRAPERS = [
    ("Avito.ma", "scrape_avito.py"),
    ("Kensington Luxury", "scrape_kensington.py"),
    ("Bosworth Property", "scrape_bosworth.py"),
    ("Agency Portal (Sarouty/Barnes)", "scrape_sarouty_marrakech.py"),
]

def main():
    print("=" * 70)
    print("🚀 STARTING MARRAKECH MULTI-PLATFORM SOURCING PIPELINE")
    print("=" * 70)
    start_total = time.time()

    for name, script in SCRAPERS:
        print(f"\n▶️ Launching {name} scraper ({script})...")
        t0 = time.time()
        res = subprocess.run([sys.executable, script])
        dur = time.time() - t0
        status = "COMPLETED" if res.returncode == 0 else f"FAILED (code {res.returncode})"
        print(f"[{status}] {name} in {dur:.1f}s")

    print("\n" + "=" * 70)
    print("🔄 UNIFYING ALL PLATFORMS INTO SOURCING DATABASE...")
    print("=" * 70)
    subprocess.run([sys.executable, "unify_sourcing.py"], check=True)

    print("\n" + "=" * 70)
    print("🌐 REBUILDING WEB APPLICATION DATA BUNDLE...")
    print("=" * 70)
    subprocess.run([sys.executable, "build_site_data.py"], check=True)

    total_dur = time.time() - start_total
    print("\n" + "=" * 70)
    print(f"✅ PIPELINE FINISHED SUCCESSFULLY IN {total_dur:.1f}s")
    print("=" * 70)

if __name__ == "__main__":
    main()
