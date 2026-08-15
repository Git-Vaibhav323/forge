"""
Generates one-page "spec sheet" PDFs for the ForgeData test catalog.

Two deliberate data problems are baked in, matching the risks called out
in the project plan:
  1. TEMPLATE ERROR (bulk-fix target): 5 Meridian Flow Controls gate valves
     all carry the exact same wrong "Max Working Pressure: 285 PSI" line,
     copied from the wrong template. Correcting one should find the other 4.
  2. GENUINE CONFLICTS: 3 products each have two source documents that
     disagree on one numeric spec, for real conflict-detection testing.
"""
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import os

OUT = "/home/claude/seed_data/datasheets"
os.makedirs(OUT, exist_ok=True)


def make_sheet(filename, manufacturer, doc_label, model, size, body_material,
                end_connection, pressure_psi, temp_c, standard, page_note=""):
    path = os.path.join(OUT, filename)
    c = canvas.Canvas(path, pagesize=letter)
    width, height = letter
    y = height - 1 * inch

    c.setFont("Helvetica-Bold", 16)
    c.drawString(1 * inch, y, manufacturer)
    y -= 0.3 * inch
    c.setFont("Helvetica", 10)
    c.drawString(1 * inch, y, doc_label)
    y -= 0.5 * inch

    c.setFont("Helvetica-Bold", 13)
    c.drawString(1 * inch, y, f"Model: {model}")
    y -= 0.4 * inch

    rows = [
        ("Nominal Size", size),
        ("Body Material", body_material),
        ("End Connection", end_connection),
        ("Max Working Pressure", f"{pressure_psi} PSI"),
        ("Max Temperature Rating", f"{temp_c}\u00b0C"),
        ("Standard", standard),
    ]
    c.setFont("Helvetica", 11)
    for label, value in rows:
        c.drawString(1 * inch, y, f"{label}:")
        c.drawString(3.2 * inch, y, str(value))
        y -= 0.3 * inch

    if page_note:
        y -= 0.2 * inch
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(1 * inch, y, page_note)

    c.setFont("Helvetica", 8)
    c.drawString(1 * inch, 0.7 * inch, f"{manufacturer} — Page 1")
    c.save()
    return filename


generated = []

# --- 1. TEMPLATE ERROR GROUP -------------------------------------------
# 5 gate valves, same manufacturer/template. All wrongly say 285 PSI.
# (kept for the seed_data/fixtures/attributes.json "correct" values below)
template_group = [
    ("MFC-GV-100", "1\"", 285),
    ("MFC-GV-150", "1.5\"", 285),
    ("MFC-GV-200", "2\"", 285),
    ("MFC-GV-250", "2.5\"", 285),
    ("MFC-GV-300", "3\"", 285),
]
for model, size, wrong_psi in template_group:
    fn = f"Meridian_{model}_Datasheet.pdf"
    make_sheet(
        fn, "Meridian Flow Controls", "Gate Valve Series — Product Datasheet",
        model, size, "Ductile Iron", "Flanged (ANSI 125)", wrong_psi, 200,
        "API 600",
        page_note="Spec table generated from master template rev. 4.2",
    )
    generated.append(fn)

# --- 2. GENUINE CONFLICT GROUP ------------------------------------------
conflict_group = [
    dict(
        model="VB-220", manufacturer="Vantage Valves", size="2\"",
        body_material="316 Stainless Steel", end_connection="Threaded NPT",
        temp_c=180, standard="ASME B16.34",
        source_a=("Vantage_VB220_Datasheet.pdf", "Product Datasheet", 600),
        source_b=("Vantage_VB220_DistributorCatalog.pdf", "Distributor Catalog Listing", 720),
    ),
    dict(
        model="ICV-45", manufacturer="Ironclad Industrial", size="4\"",
        body_material="Cast Steel", end_connection="Flanged (ANSI 300)",
        pressure_psi=450, standard="API 594",
        source_a=("Ironclad_ICV45_Datasheet.pdf", "Product Datasheet", 180),
        source_b=("Ironclad_ICV45_TechBulletin.pdf", "Technical Bulletin", 210),
    ),
    dict(
        model="TBV-12", manufacturer="Titan Flow Systems", size="12\"",
        body_material="Ductile Iron", end_connection="Wafer",
        temp_c=120, standard="API 609",
        source_a=("Titan_TBV12_Datasheet.pdf", "Product Datasheet", 232),
        source_b=("Titan_TBV12_SubmittalSheet.pdf", "Engineering Submittal Sheet", 275),
    ),
]

for item in conflict_group:
    if "pressure_psi" in item:
        # temperature is the conflicting field
        fa, label_a, temp_a = item["source_a"]
        fb, label_b, temp_b = item["source_b"]
        make_sheet(fa, item["manufacturer"], label_a, item["model"], item["size"],
                   item["body_material"], item["end_connection"], item["pressure_psi"],
                   temp_a, item["standard"])
        make_sheet(fb, item["manufacturer"], label_b, item["model"], item["size"],
                   item["body_material"], item["end_connection"], item["pressure_psi"],
                   temp_b, item["standard"])
    else:
        # pressure is the conflicting field
        fa, label_a, psi_a = item["source_a"]
        fb, label_b, psi_b = item["source_b"]
        make_sheet(fa, item["manufacturer"], label_a, item["model"], item["size"],
                   item["body_material"], item["end_connection"], psi_a,
                   item["temp_c"], item["standard"])
        make_sheet(fb, item["manufacturer"], label_b, item["model"], item["size"],
                   item["body_material"], item["end_connection"], psi_b,
                   item["temp_c"], item["standard"])
    generated.extend([item["source_a"][0], item["source_b"][0]])

print(f"Generated {len(generated)} PDFs in {OUT}:")
for g in generated:
    print(" -", g)
