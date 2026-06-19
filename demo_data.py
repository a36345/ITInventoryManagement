"""
demo_data.py — Popula a base de dados com ativos de demonstração realistas.
Uso: venv\Scripts\python demo_data.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import core.database as db

db.init_db()

# ── Ativos ────────────────────────────────────────────────────────────────────

ASSETS = [
    # ── Desktops ──────────────────────────────────────────────────────────────
    dict(hostname="DTPG-ANABRAGA",     type="Desktop",   status="Online",
         ip_address="192.168.163.10",  mac_address="d4:be:d9:11:22:01",
         manufacturer="Dell",          model="OptiPlex 7090",
         serial_number="SML-D0001",   department="Financeiro",
         assigned_user="Ana Braga",   os_version="Windows 11 Pro",
         acquisition_year=2022,        purchase_price=899.00,
         purchase_date="15/03/2022",   supplier="PC Diga",
         warranty_years=3,             warranty_end="15/03/2025",
         confidence=0.99,              needs_review=0),

    dict(hostname="DTPG-JOAOSILVA",    type="Desktop",   status="Online",
         ip_address="192.168.163.11",  mac_address="d4:be:d9:11:22:02",
         manufacturer="Dell",          model="OptiPlex 7090",
         serial_number="SML-D0002",   department="Financeiro",
         assigned_user="João Silva",   os_version="Windows 11 Pro",
         acquisition_year=2022,        purchase_price=899.00,
         purchase_date="15/03/2022",   supplier="PC Diga",
         warranty_years=3,             warranty_end="15/03/2025",
         confidence=0.99,              needs_review=0),

    dict(hostname="DTRH-MARIAFARIA",   type="Desktop",   status="Online",
         ip_address="192.168.163.12",  mac_address="d4:be:d9:11:22:03",
         manufacturer="HP",            model="EliteDesk 800 G6",
         serial_number="SML-D0003",   department="Recursos Humanos",
         assigned_user="Maria Faria",  os_version="Windows 10 Pro",
         acquisition_year=2021,        purchase_price=849.00,
         purchase_date="10/06/2021",   supplier="Worten Empresas",
         warranty_years=3,             warranty_end="10/06/2024",
         confidence=0.99,              needs_review=0),

    dict(hostname="DTPROD-CARLOS",     type="Desktop",   status="Online",
         ip_address="192.168.163.13",  mac_address="d4:be:d9:11:22:04",
         manufacturer="Lenovo",        model="ThinkCentre M90q",
         serial_number="SML-D0004",   department="Produção",
         assigned_user="Carlos Matos", os_version="Windows 10 Pro",
         acquisition_year=2020,        purchase_price=749.00,
         purchase_date="05/01/2020",   supplier="Econocom",
         warranty_years=3,             warranty_end="05/01/2023",
         confidence=0.99,              needs_review=1),  # fora de garantia

    dict(hostname="DTPROD-FERNANDA",   type="Desktop",   status="Offline",
         ip_address="192.168.163.14",  mac_address="d4:be:d9:11:22:05",
         manufacturer="Dell",          model="OptiPlex 3080",
         serial_number="SML-D0005",   department="Produção",
         assigned_user="Fernanda Cruz",os_version="Windows 10 Pro",
         acquisition_year=2019,        purchase_price=649.00,
         purchase_date="20/09/2019",   supplier="PC Diga",
         warranty_years=3,             warranty_end="20/09/2022",
         confidence=0.99,              needs_review=1),  # antigo + offline

    dict(hostname="DTCOM-PEDRORIBEIRO",type="Desktop",   status="Online",
         ip_address="192.168.163.15",  mac_address="d4:be:d9:11:22:06",
         manufacturer="HP",            model="EliteDesk 880 G9",
         serial_number="SML-D0006",   department="Comercial",
         assigned_user="Pedro Ribeiro",os_version="Windows 11 Pro",
         acquisition_year=2023,        purchase_price=1049.00,
         purchase_date="12/01/2023",   supplier="Worten Empresas",
         warranty_years=3,             warranty_end="12/01/2026",
         confidence=0.99,              needs_review=0),

    dict(hostname="DTDIR-ANTONIOCOSTA",type="Desktop",   status="Online",
         ip_address="192.168.163.16",  mac_address="d4:be:d9:11:22:07",
         manufacturer="Dell",          model="OptiPlex 7000",
         serial_number="SML-D0007",   department="Direção",
         assigned_user="António Costa",os_version="Windows 11 Pro",
         acquisition_year=2023,        purchase_price=1199.00,
         purchase_date="03/03/2023",   supplier="PC Diga",
         warranty_years=3,             warranty_end="03/03/2026",
         confidence=0.99,              needs_review=0),

    dict(hostname="DTLOG-MIGUELSOUSA", type="Desktop",   status="Online",
         ip_address="192.168.163.17",  mac_address="d4:be:d9:11:22:08",
         manufacturer="Lenovo",        model="ThinkCentre M70q Gen 3",
         serial_number="SML-D0008",   department="Logística",
         assigned_user="Miguel Sousa", os_version="Windows 11 Pro",
         acquisition_year=2022,        purchase_price=799.00,
         purchase_date="22/07/2022",   supplier="XL Network",
         warranty_years=3,             warranty_end="22/07/2025",
         confidence=0.99,              needs_review=0),

    # ── Laptops ───────────────────────────────────────────────────────────────
    dict(hostname="NBPG-SILVIAVALENTE",type="Laptop",    status="Online",
         ip_address="192.168.163.20",  mac_address="dc:9f:db:aa:bb:01",
         manufacturer="Lenovo",        model="ThinkPad T14 Gen 3",
         serial_number="SML-L0001",   department="Financeiro",
         assigned_user="Sílvia Valente",os_version="Windows 11 Pro",
         acquisition_year=2022,        purchase_price=1299.00,
         purchase_date="18/04/2022",   supplier="PC Diga",
         warranty_years=3,             warranty_end="18/04/2025",
         confidence=0.99,              needs_review=0),

    dict(hostname="NBRH-LUCIAOLIVE",   type="Laptop",    status="Online",
         ip_address="192.168.163.21",  mac_address="dc:9f:db:aa:bb:02",
         manufacturer="HP",            model="EliteBook 840 G9",
         serial_number="SML-L0002",   department="Recursos Humanos",
         assigned_user="Lúcia Oliveira",os_version="Windows 11 Pro",
         acquisition_year=2023,        purchase_price=1449.00,
         purchase_date="07/02/2023",   supplier="Worten Empresas",
         warranty_years=3,             warranty_end="07/02/2026",
         confidence=0.99,              needs_review=0),

    dict(hostname="NBDIR-RTAVARES",    type="Laptop",    status="Online",
         ip_address="192.168.163.22",  mac_address="dc:9f:db:aa:bb:03",
         manufacturer="Dell",          model="Latitude 5430",
         serial_number="SML-L0003",   department="Direção",
         assigned_user="Rui Tavares",  os_version="Windows 11 Pro",
         acquisition_year=2022,        purchase_price=1349.00,
         purchase_date="30/05/2022",   supplier="PC Diga",
         warranty_years=3,             warranty_end="30/05/2025",
         confidence=0.99,              needs_review=0),

    dict(hostname="NBCOM-SANDRAPINTO", type="Laptop",    status="Online",
         ip_address="192.168.163.23",  mac_address="dc:9f:db:aa:bb:04",
         manufacturer="HP",            model="EliteBook 850 G8",
         serial_number="SML-L0004",   department="Comercial",
         assigned_user="Sandra Pinto", os_version="Windows 10 Pro",
         acquisition_year=2021,        purchase_price=1199.00,
         purchase_date="14/09/2021",   supplier="Econocom",
         warranty_years=3,             warranty_end="14/09/2024",
         confidence=0.99,              needs_review=0),

    dict(hostname="NBTI-DANIELGON",    type="Laptop",    status="Online",
         ip_address="192.168.163.24",  mac_address="dc:9f:db:aa:bb:05",
         manufacturer="Lenovo",        model="ThinkPad X1 Carbon Gen 10",
         serial_number="SML-L0005",   department="TI",
         assigned_user="Daniel Gonçalves",os_version="Windows 11 Pro",
         acquisition_year=2023,        purchase_price=1799.00,
         purchase_date="01/11/2023",   supplier="XL Network",
         warranty_years=3,             warranty_end="01/11/2026",
         confidence=0.99,              needs_review=0),

    # ── Servidores ────────────────────────────────────────────────────────────
    dict(hostname="SRV-DC01",          type="Servidor",  status="Online",
         ip_address="192.168.163.2",   mac_address="18:03:73:cc:dd:01",
         manufacturer="Dell",          model="PowerEdge R740",
         serial_number="SML-S0001",   department="TI",
         assigned_user="",             os_version="Windows Server 2022 Standard",
         acquisition_year=2021,        purchase_price=4899.00,
         purchase_date="15/02/2021",   supplier="XL Network",
         warranty_years=5,             warranty_end="15/02/2026",
         confidence=0.99,              needs_review=0,
         notes="Domain Controller principal — AD + DNS + DHCP"),

    dict(hostname="SRV-FILE01",        type="Servidor",  status="Online",
         ip_address="192.168.163.3",   mac_address="18:03:73:cc:dd:02",
         manufacturer="Dell",          model="PowerEdge R640",
         serial_number="SML-S0002",   department="TI",
         assigned_user="",             os_version="Windows Server 2019 Standard",
         acquisition_year=2020,        purchase_price=3799.00,
         purchase_date="10/06/2020",   supplier="XL Network",
         warranty_years=5,             warranty_end="10/06/2025",
         confidence=0.99,              needs_review=0,
         notes="Servidor de ficheiros — partilhas departamentais"),

    dict(hostname="SRV-ERP01",         type="Servidor",  status="Online",
         ip_address="192.168.163.4",   mac_address="18:03:73:cc:dd:03",
         manufacturer="HP",            model="ProLiant DL380 Gen10",
         serial_number="SML-S0003",   department="TI",
         assigned_user="",             os_version="Windows Server 2019 Standard",
         acquisition_year=2020,        purchase_price=5299.00,
         purchase_date="10/06/2020",   supplier="Econocom",
         warranty_years=5,             warranty_end="10/06/2025",
         confidence=0.99,              needs_review=0,
         notes="Servidor ERP — PHC CS Enterprise"),

    # ── Impressoras ───────────────────────────────────────────────────────────
    dict(hostname="PRN-FINANCAS",      type="Impressora",status="Online",
         ip_address="192.168.163.30",  mac_address="00:1b:a9:33:44:01",
         manufacturer="HP",            model="LaserJet Pro M404dn",
         serial_number="SML-P0001",   department="Financeiro",
         acquisition_year=2021,        purchase_price=349.00,
         purchase_date="08/03/2021",   supplier="Worten Empresas",
         warranty_years=1,             warranty_end="08/03/2022",
         confidence=0.99,              needs_review=0),

    dict(hostname="PRN-RH",            type="Impressora",status="Online",
         ip_address="192.168.163.31",  mac_address="00:1b:a9:33:44:02",
         manufacturer="Brother",       model="MFC-L8900CDW",
         serial_number="SML-P0002",   department="Recursos Humanos",
         acquisition_year=2022,        purchase_price=529.00,
         purchase_date="20/01/2022",   supplier="PC Diga",
         warranty_years=2,             warranty_end="20/01/2024",
         confidence=0.99,              needs_review=0),

    dict(hostname="PRN-PRODUCAO",      type="Impressora",status="Online",
         ip_address="192.168.163.32",  mac_address="00:1b:a9:33:44:03",
         manufacturer="Kyocera",       model="ECOSYS M3645dn",
         serial_number="SML-P0003",   department="Produção",
         acquisition_year=2020,        purchase_price=449.00,
         purchase_date="15/09/2020",   supplier="XL Network",
         warranty_years=2,             warranty_end="15/09/2022",
         confidence=0.99,              needs_review=0),

    dict(hostname="PRN-DIRECAO",       type="Impressora",status="Online",
         ip_address="192.168.163.33",  mac_address="00:1b:a9:33:44:04",
         manufacturer="HP",            model="Color LaserJet Pro M454dw",
         serial_number="SML-P0004",   department="Direção",
         acquisition_year=2023,        purchase_price=699.00,
         purchase_date="14/03/2023",   supplier="Worten Empresas",
         warranty_years=2,             warranty_end="14/03/2025",
         confidence=0.99,              needs_review=0),

    # ── Switches e APs ────────────────────────────────────────────────────────
    dict(hostname="SW-CORE",           type="Switch",    status="Online",
         ip_address="192.168.163.1",   mac_address="24:a4:3c:55:66:01",
         manufacturer="Ubiquiti",      model="UniFi Switch Pro 24",
         serial_number="SML-N0001",   department="TI",
         acquisition_year=2022,        purchase_price=599.00,
         purchase_date="05/01/2022",   supplier="XL Network",
         warranty_years=2,             warranty_end="05/01/2024",
         confidence=0.99,              needs_review=0,
         notes="Switch core — piso 1"),

    dict(hostname="SW-PISO2",          type="Switch",    status="Online",
         ip_address="192.168.163.50",  mac_address="24:a4:3c:55:66:02",
         manufacturer="Ubiquiti",      model="UniFi Switch 16 PoE",
         serial_number="SML-N0002",   department="TI",
         acquisition_year=2022,        purchase_price=299.00,
         purchase_date="05/01/2022",   supplier="XL Network",
         warranty_years=2,             warranty_end="05/01/2024",
         confidence=0.99,              needs_review=0,
         notes="Switch piso 2 — zona produção"),

    dict(hostname="AP-RECEPCAO",       type="Access Point",status="Online",
         ip_address="192.168.163.51",  mac_address="78:8a:20:77:88:01",
         manufacturer="Ubiquiti",      model="UniFi AP AC Pro",
         serial_number="SML-N0003",   department="TI",
         acquisition_year=2021,        purchase_price=139.00,
         purchase_date="12/04/2021",   supplier="XL Network",
         warranty_years=2,             warranty_end="12/04/2023",
         confidence=0.99,              needs_review=0),

    dict(hostname="AP-SALA-REUNIOES",  type="Access Point",status="Online",
         ip_address="192.168.163.52",  mac_address="78:8a:20:77:88:02",
         manufacturer="Ubiquiti",      model="UniFi AP AC Lite",
         serial_number="SML-N0004",   department="TI",
         acquisition_year=2021,        purchase_price=89.00,
         purchase_date="12/04/2021",   supplier="XL Network",
         warranty_years=2,             warranty_end="12/04/2023",
         confidence=0.99,              needs_review=0),

    dict(hostname="AP-PRODUCAO",       type="Access Point",status="Online",
         ip_address="192.168.163.53",  mac_address="78:8a:20:77:88:03",
         manufacturer="Ubiquiti",      model="UniFi AP HD",
         serial_number="SML-N0005",   department="TI",
         acquisition_year=2022,        purchase_price=189.00,
         purchase_date="18/02/2022",   supplier="XL Network",
         warranty_years=2,             warranty_end="18/02/2024",
         confidence=0.99,              needs_review=0),

    # ── NAS ───────────────────────────────────────────────────────────────────
    dict(hostname="NAS-BACKUP",        type="NAS",       status="Online",
         ip_address="192.168.163.55",  mac_address="00:11:32:99:aa:01",
         manufacturer="Synology",      model="DiskStation DS923+",
         serial_number="SML-N0006",   department="TI",
         acquisition_year=2023,        purchase_price=649.00,
         purchase_date="20/09/2023",   supplier="PC Diga",
         warranty_years=3,             warranty_end="20/09/2026",
         confidence=0.99,              needs_review=0,
         notes="NAS backup — 4x4TB RAID5 | Backup diário 02:00"),

    # ── Firewall ──────────────────────────────────────────────────────────────
    dict(hostname="FW-PRINCIPAL",      type="Firewall",  status="Online",
         ip_address="192.168.163.254", mac_address="08:00:27:ab:cd:ef",
         manufacturer="Fortinet",      model="FortiGate 60F",
         serial_number="SML-N0007",   department="TI",
         acquisition_year=2022,        purchase_price=799.00,
         purchase_date="10/01/2022",   supplier="XL Network",
         warranty_years=3,             warranty_end="10/01/2025",
         confidence=0.99,              needs_review=0,
         notes="Firewall perimetral + VPN SSL"),
]

# ── Inserir ativos ────────────────────────────────────────────────────────────

print("A inserir ativos...")
asset_ids = {}
for a in ASSETS:
    aid = db.upsert_asset(a)
    asset_ids[a["hostname"]] = aid
    print(f"  {a['hostname']:30s} [{a['type']:12s}] id={aid}")

# ── Dados de impressoras (toner) ──────────────────────────────────────────────

print("\nA inserir dados de toner...")
PRINTERS = [
    ("PRN-FINANCAS",   {"toner_black": 12, "toner_cyan": -1, "toner_magenta": -1, "toner_yellow": -1, "total_pages": 18432, "monthly_pages": 420}),
    ("PRN-RH",         {"toner_black": 67, "toner_cyan": 45, "toner_magenta": 72, "toner_yellow": 55, "total_pages": 9871,  "monthly_pages": 310}),
    ("PRN-PRODUCAO",   {"toner_black": 8,  "toner_cyan": -1, "toner_magenta": -1, "toner_yellow": -1, "total_pages": 31204, "monthly_pages": 890}),
    ("PRN-DIRECAO",    {"toner_black": 88, "toner_cyan": 91, "toner_magenta": 85, "toner_yellow": 93, "total_pages": 2105,  "monthly_pages": 95}),
]
for hostname, pdata in PRINTERS:
    aid = asset_ids.get(hostname)
    if aid:
        db.upsert_printer(aid, pdata)
        print(f"  {hostname:20s} K={pdata['toner_black']}%")

# ── Consumíveis ───────────────────────────────────────────────────────────────

print("\nA inserir consumíveis...")
CONSUMABLES = [
    dict(reference="CF259A",      type="Toner Preto",   compatible_with="HP LaserJet Pro M404dn PRN-FINANCAS", stock_qty=2, stock_min=2),
    dict(reference="TN-910BK",    type="Toner Preto",   compatible_with="Brother MFC-L8900CDW PRN-RH",         stock_qty=1, stock_min=2),
    dict(reference="TN-910C",     type="Toner Cyan",    compatible_with="Brother MFC-L8900CDW PRN-RH",         stock_qty=3, stock_min=1),
    dict(reference="TN-910M",     type="Toner Magenta", compatible_with="Brother MFC-L8900CDW PRN-RH",         stock_qty=2, stock_min=1),
    dict(reference="TN-910Y",     type="Toner Amarelo", compatible_with="Brother MFC-L8900CDW PRN-RH",         stock_qty=2, stock_min=1),
    dict(reference="TK-3190",     type="Toner Preto",   compatible_with="Kyocera ECOSYS M3645dn PRN-PRODUCAO", stock_qty=0, stock_min=3),
    dict(reference="W2210A",      type="Toner Preto",   compatible_with="HP Color LaserJet Pro M454dw PRN-DIRECAO", stock_qty=4, stock_min=1),
    dict(reference="W2211A",      type="Toner Cyan",    compatible_with="HP Color LaserJet Pro M454dw PRN-DIRECAO", stock_qty=2, stock_min=1),
    dict(reference="W2212A",      type="Toner Magenta", compatible_with="HP Color LaserJet Pro M454dw PRN-DIRECAO", stock_qty=2, stock_min=1),
    dict(reference="W2213A",      type="Toner Amarelo", compatible_with="HP Color LaserJet Pro M454dw PRN-DIRECAO", stock_qty=2, stock_min=1),
]
for c in CONSUMABLES:
    db.upsert_consumable(c)
    status = "SEM STOCK" if c["stock_qty"] == 0 else ("BAIXO" if c["stock_qty"] < c["stock_min"] else "OK")
    print(f"  {c['reference']:12s} {c['type']:15s} stock={c['stock_qty']}/{c['stock_min']} [{status}]")

# ── Alertas ───────────────────────────────────────────────────────────────────

print("\nA inserir alertas...")
db.create_alert("Warning", "LowToner",
    "Toner Preto baixo em PRN-FINANCAS (12%)",
    "IP: 192.168.163.30 | Nível: 12% (limiar: 15%)",
    asset_ids.get("PRN-FINANCAS"))

db.create_alert("Warning", "LowToner",
    "Toner Preto crítico em PRN-PRODUCAO (8%)",
    "IP: 192.168.163.32 | Nível: 8% (limiar: 15%) — substituição urgente",
    asset_ids.get("PRN-PRODUCAO"))

db.create_alert("Warning", "LowStock",
    "Stock esgotado: TK-3190 (0/3)",
    "Toner PRN-PRODUCAO em falta. Encomendar urgente.",
    asset_ids.get("PRN-PRODUCAO"))

db.create_alert("Warning", "Lifecycle",
    "Equipamento em fim de vida: DTPROD-FERNANDA (2019)",
    "Desktop Dell OptiPlex 3080 com 5 anos — substituição recomendada.",
    asset_ids.get("DTPROD-FERNANDA"))

db.create_alert("Info", "Lifecycle",
    "Garantia expirada: DTPROD-CARLOS (2020)",
    "ThinkCentre M90q — garantia expirou em Jan 2023.",
    asset_ids.get("DTPROD-CARLOS"))

print("  5 alertas criados")

# ── Definições de rede ────────────────────────────────────────────────────────

db.set_setting("subnet", "192.168.163.0/24")

db.invalidate_caches()
print(f"\nDemo concluido -- {len(ASSETS)} ativos, {len(CONSUMABLES)} consumiveis, 5 alertas")
print("  Abre a aplicação para ver os dados.")
