"""
audit_macs.py — Mostra todos os MACs da rede e o resultado do lookup OUI.
Corre: venv\Scripts\python audit_macs.py
"""
import subprocess, platform, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.oui_db import lookup, OUI_DATABASE

CREATE_NO_WINDOW = 0x08000000 if platform.system() == "Windows" else 0

print("=" * 70)
print("  IT Inventory — Auditoria de MACs")
print("=" * 70)

# Ler tabela ARP completa
try:
    out = subprocess.check_output(
        ["arp", "-a"], stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW
    ).decode(errors="replace")
except Exception as e:
    print(f"Erro ARP: {e}")
    sys.exit(1)

# Parse
entries = []
for line in out.split("\n"):
    ip_m  = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
    mac_m = re.search(r"([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}", line)
    if ip_m and mac_m:
        ip  = ip_m.group(1)
        mac = mac_m.group(0).lower().replace("-",":")
        if not ip.endswith(".255") and ip != "255.255.255.255":
            entries.append((ip, mac))

print(f"\nTotal de entradas ARP: {len(entries)}")
print(f"OUIs na base de dados: {len(OUI_DATABASE)}\n")

identified   = []
unidentified = []

for ip, mac in sorted(entries):
    vendor, dtype = lookup(mac)
    oui = ":".join(mac.split(":")[:3])
    if vendor:
        identified.append((ip, mac, oui, vendor, dtype))
    else:
        unidentified.append((ip, mac, oui))

print(f"{'─'*70}")
print(f"  IDENTIFICADOS: {len(identified)}   NÃO IDENTIFICADOS: {len(unidentified)}")
print(f"{'─'*70}")

if identified:
    print(f"\n{'IP':<18} {'MAC':<20} {'Fabricante':<25} {'Tipo'}")
    print("─" * 70)
    for ip, mac, oui, vendor, dtype in identified:
        print(f"{ip:<18} {mac:<20} {vendor:<25} {dtype}")

if unidentified:
    print(f"\n{'─'*70}")
    print(f"  NÃO IDENTIFICADOS — OUIs a adicionar à base:")
    print(f"{'─'*70}")
    print(f"\n{'IP':<18} {'MAC':<20} {'OUI'}")
    print("─" * 50)
    # Group by OUI to show how many devices share it
    from collections import Counter
    oui_count = Counter(oui for _,_,oui in unidentified)
    shown = set()
    for ip, mac, oui in unidentified:
        print(f"{ip:<18} {mac:<20} {oui}  ({oui_count[oui]} dispositivo(s) com este OUI)")
        shown.add(oui)

    print(f"\n  OUIs únicos por identificar: {len(set(o for _,_,o in unidentified))}")
    print(f"\n  Copia estes OUIs e envia — adicionamos à base de dados:")
    for oui in sorted(set(o for _,_,o in unidentified)):
        print(f"    {oui}")

print("\n" + "=" * 70)
input("\nPrime ENTER para fechar...")
