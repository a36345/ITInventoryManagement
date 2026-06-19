"""
Classificação de dispositivos — regras determinísticas com prioridade explícita.
SNMP / WMI / modelo / hostname > OUI genérico.
"""

import re
from typing import Optional

# Fabricantes cujo OUI não define o tipo (PC vs switch vs impressora)
AMBIGUOUS_VENDORS = frozenset({
    "Dell Inc.", "HP Inc.", "Hewlett Packard", "Hewlett-Packard",
    "Lenovo", "ASUSTeK Computer", "Intel Corporate", "Realtek Semiconductor",
    "Microsoft Corporation", "VMware, Inc.", "Apple, Inc.",
})

# (regex no hostname, tipo, confiança)
HOSTNAME_RULES = [
    (r"^SW[\-_]|^SWITCH|^GSW[\-_]|^ESW[\-_]",              "Switch",       0.88),
    (r"^SRV[\-_]|^SERVER[\-_]|^SERV[\-_]|^DC[\-_]",        "Servidor",     0.88),
    (r"^PRN[\-_]|^PRINT|^MFP[\-_]|^IMP[\-_]|^MFC[\-_]",   "Impressora",   0.88),
    (r"^AP[\-_]|^WIFI[\-_]|^UAP[\-_]|^UNIFI|^EAP[\-_]",   "Access Point", 0.85),
    (r"^FORTISW|^FSW[\-_]",                                  "Switch",       0.90),
    (r"^FW[\-_]|^FORTI(?!SW)|^FG[\-_]|^PFSENSE",           "Firewall",     0.88),
    (r"^NAS[\-_]|^QNAP|^SYNO",                              "NAS",          0.88),
    (r"^LAP[\-_]|^LT[\-_]|^NB[\-_]|^LAPTOP(?:[\-_]|$)",     "Laptop",       0.82),
    (r"^PC[\-_]|^WS[\-_]|^DT[\-_]|^DESK|^CLIENT[\-_]",     "Desktop",      0.82),
    (r"CAM[\-_]|^CCTV|^DVR[\-_]|^NVR[\-_]",                "Câmara CCTV",  0.80),
]

# Palavras no modelo (model_db ou SNMP)
MODEL_TYPE_RULES = [
    (r"poweredge|proliant|thinksystem",                                                          "Servidor",     0.92),
    (r"optiplex|thinkcentre|elitedesk|prodesk|desktop",                                          "Desktop",      0.90),
    (r"latitude|thinkpad|thinkbook|elitebook|ideapad|laptop|notebook",                           "Laptop",       0.90),
    (r"networking\s+switch|powerconnect|n\d{4}|catalyst|procurve|comware|powerswitch|crs\d{3}",  "Switch",       0.92),
    (r"fortiswitch",                                                                              "Switch",       0.95),
    (r"fortigate|fortios|pfsense|sophos",                                                         "Firewall",     0.92),
    (r"laserjet|colorlaserjet|officejet|pagewide|imagerunner|bizhub|taskalfa"
     r"|mfp|\bmfc[\-\s]|multifunction|brother.*(?:hl|dcp)|lexmark|toshiba.*studio",              "Impressora",   0.92),
    (r"unifi\s+ap|uap[\-\s]|access\s+point|aironet|eap[\-\s]",                                  "Access Point", 0.90),
    (r"qnap|synology|readynas|terramaster",                                                       "NAS",          0.90),
    (r"zebra\s",                                                                                  "Impressora",   0.85),
]

# sysDescr SNMP (ordem importa — mais específica primeiro)
SNMP_DESCR_RULES = [
    # Impressoras — ANTES de qualquer regra Linux (printers embebidos correm Linux)
    (r"laserjet|colorlaserjet|officejet|pagewide|imagerunner|bizhub|taskalfa"
     r"|mfp|\bmfc[\-\s]|multifunction|oki[\s\-]|ricoh|xerox|canon.*print|konica"
     r"|toshiba.*studio|lexmark|sharp.*(?:mx|ar|bp)",
     "Impressora", 0.96),
    (r"brother.*(?:mfc|hl|dcp)",   "Impressora", 0.95),
    (r"zebra\s|zebra technologies", "Impressora", 0.94),

    # FortiSwitch ANTES de FortiGate — ambos correm FortiOS; distinguir pelo nome exacto
    (r"fortiswitch",  "Switch",   0.97),
    (r"fortigate|fortios|pfsense|sophos\s+(?:xg|utm|sg)|checkpoint|firewall\s+os", "Firewall", 0.96),

    # Access Points — regras específicas antes de Aruba/Cisco genérico
    (r"arubaos.*(?:ap|iap|access)|instant[\s\-]ap|unifi.*(?:ap|uap)|aironet.*ap|uap[\-\s]",
     "Access Point", 0.94),
    (r"tp[\-\s]?link.*eap|engenius.*eap|ruckus.*r\d{3}",
     "Access Point", 0.90),

    # Switches
    (r"aruba\s+cx|arubaos|procurve|comware|catalyst|nexus|powerconnect"
     r"|dell\s+networking|dell\s+emc\s+s\d|dell.*powerswitch"
     r"|cisco\s+ios.*switch|sg\d{3,4}|ws[\-\s]?c\d|mikrotik.*crs",
     "Switch", 0.95),
    (r"ubiquiti|unifi(?!.*ap)|edgeswitch|mikrotik", "Switch", 0.88),

    # NAS
    (r"qnap|synology|readynas|terramaster", "NAS", 0.95),

    # Servidores / desktops
    (r"vmware\s+esxi|esxi\s+\d|proxmox|hyper[\-\s]?v|windows\s+server|win\s*server\s+\d",
     "Servidor", 0.94),
    (r"microsoft windows nt|windows 10|windows 11|win\d{2,}", "Desktop", 0.82),
    (r"linux.*server|ubuntu.*server|debian.*server|centos.*server", "Servidor", 0.80),
    (r"linux|raspberry", "Outro", 0.65),
]

# ── Port-based fingerprinting ────────────────────────────────────────────────
# SINAIS "DEFINITIVAMENTE WINDOWS" (impressoras e APs não têm estes):
#   445  — SMB: partilha de ficheiros/impressoras Windows
#   135  — Microsoft RPC/DCOM Endpoint Mapper (quasi-exclusivo Windows)
#   139  — NetBIOS Session Service
#
# FALSOS POSITIVOS CONHECIDOS:
#   • Porta 631 (IPP): Windows 10/11 abre por defeito → invalida se 445/135/139 presentes
#   • Porta 9100: HP Smart / print spooler partilha via JetDirect → invalida se Windows
#   • Portátil com adaptador Ubiquiti: OUI diz "Access Point" mas é Windows → WMI confirma
#
# Regra de ouro: qualquer de 445/135/139 aberto → é Windows, NÃO é impressora.

def classify_from_ports(open_ports: set) -> Optional[tuple]:
    """
    Classifica pelo conjunto de portas TCP abertas.

    Sinais "definitivamente Windows" (impressoras e APs NÃO têm estes):
      • 445  — SMB (partilha de ficheiros/impressoras Windows)
      • 135  — Microsoft RPC / DCOM Endpoint Mapper
      • 139  — NetBIOS Session Service

    Qualquer um destes invalida a classificação como impressora via porta 9100/631.

    Falsos positivos eliminados:
      • Portátil com HP Smart a abrir 9100 mas sem SMB → RPC (135) identifica Windows
      • Windows 10/11 a abrir 631 (IPP) por defeito → SMB ou RPC invalida
      • Windows com print spooler a partilhar via 9100 → SMB ou RPC invalida
    """
    has_smb     = 445 in open_ports   # SMB → Windows
    has_rpc     = 135 in open_ports   # Microsoft RPC/DCOM → Windows (impressoras não têm)
    has_netbios = 139 in open_ports   # NetBIOS Session → Windows
    is_windows  = has_smb or has_rpc or has_netbios

    # JetDirect 9100 — impressoras HP e similares
    # Se qualquer sinal Windows estiver presente → é partilha de impressora, não impressora real
    if 9100 in open_ports and not is_windows:
        return "Impressora", 0.97

    # LPD 515 — idem
    if 515 in open_ports and not is_windows:
        return "Impressora", 0.88

    # IPP 631 — Windows 10/11 abre por defeito → só classifica quando não há Windows E não há SSH
    if 631 in open_ports and not is_windows and 22 not in open_ports:
        return "Impressora", 0.80

    # NAS Synology — DSM usa 5000 (http) + 5001 (https) em conjunto
    if 5000 in open_ports and 5001 in open_ports:
        return "NAS", 0.92

    # RDP → Windows Desktop (alta confiança — switches e impressoras não têm RDP)
    if 3389 in open_ports:
        return "Desktop", 0.88

    # SMB + RPC juntos → Windows definitivo (quasi impossível num switch ou impressora)
    if has_smb and has_rpc:
        return "Desktop", 0.90

    # SMB (445) sozinho → quase sempre Windows; switches empresariais raramente expõem SMB
    if has_smb:
        return "Desktop", 0.85

    # RPC/DCOM (135) sem SMB → Windows com firewall a bloquear 445
    if has_rpc:
        return "Desktop", 0.82

    # NetBIOS Session (139) sem os anteriores → provavelmente Windows
    if has_netbios:
        return "Desktop", 0.72

    return None

# HTTP <title> / Server header → tipo de dispositivo
HTTP_TITLE_RULES = [
    (r"HP.{0,40}(?:LaserJet|OfficeJet|PageWide|DeskJet|DesignJet|Color\s+Laser)",
     "Impressora", 0.97),
    (r"Embedded Web Server|HP EWS|HP Embedded",         "Impressora", 0.93),
    (r"Brother.*(?:MFC|HL|DCP)|MFC-\w+|HL-\w+",        "Impressora", 0.96),
    (r"Canon.*(?:imageRUNNER|Printer|PIXMA|MF\d|UFR)",  "Impressora", 0.96),
    (r"Ricoh|bizhub|Konica\s+Minolta|OKI.*Web|Lexmark", "Impressora", 0.95),
    (r"Toshiba.*e[\-\s]?STUDIO|Sharp.*MX|Xerox.*(?:WorkCentre|AltaLink|VersaLink)",
     "Impressora", 0.95),
    (r"pfSense|OPNsense",                               "Firewall",   0.97),
    (r"FortiGate|Fortinet",                             "Firewall",   0.96),
    (r"Sophos\s+(?:XG|UTM|SG|Firewall)",                "Firewall",   0.96),
    (r"Synology DiskStation|Synology NAS",              "NAS",        0.98),
    (r"QNAP\s+(?:NAS|Turbo|QTS)",                       "NAS",        0.97),
    (r"ReadyNAS|TerraMaster",                           "NAS",        0.95),
    (r"NETGEAR|ProSAFE|Managed Switch",                 "Switch",     0.91),
    (r"Cisco.*Switch|Catalyst\s+\d",                    "Switch",     0.92),
    (r"MikroTik RouterOS",                              "Switch",     0.88),
    (r"Ubiquiti.*(?:Edge|Network)|UniFi.*Network",      "Switch",     0.82),
    (r"Microsoft-IIS|Windows.*Server",                  "Servidor",   0.82),
    (r"VMware|ESXi|vSphere",                            "Servidor",   0.91),
    (r"Proxmox",                                        "Servidor",   0.91),
]


def classify_from_http(title: str, server: str) -> Optional[tuple]:
    """Classifica pelo título HTML e header Server da interface web."""
    combined = f"{title} {server}".strip()
    if not combined:
        return None
    for pattern, dtype, conf in HTTP_TITLE_RULES:
        if re.search(pattern, combined, re.I):
            return dtype, conf
    return None


NETBIOS_SKIP = re.compile(
    r"^(MS\d{4}|WORKGROUP|IS~|SMB|PRINTERS|PRINTER)", re.I
)


def is_valid_mac(mac: Optional[str]) -> bool:
    if not mac:
        return False
    m = mac.lower().replace("-", ":")
    if m in ("ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00"):
        return False
    if m.startswith("01:00:5e"):
        return False
    return True


def classify_from_hostname(hostname: Optional[str]) -> Optional[tuple]:
    if not hostname:
        return None
    h = hostname.upper().strip()
    for pattern, dtype, conf in HOSTNAME_RULES:
        if re.search(pattern, h, re.I):
            return dtype, conf
    return None


def classify_from_model(model: Optional[str]) -> Optional[tuple]:
    if not model:
        return None
    m = model.lower()
    for pattern, dtype, conf in MODEL_TYPE_RULES:
        if re.search(pattern, m, re.I):
            return dtype, conf
    return None


def classify_from_snmp_descr(descr: Optional[str], interface_count: int = 0) -> Optional[tuple]:
    if not descr:
        return None
    d = descr.lower()
    for pattern, dtype, conf in SNMP_DESCR_RULES:
        if re.search(pattern, d, re.I):
            if dtype == "Switch" and "unifi" in d and interface_count and interface_count <= 4:
                return "Access Point", 0.90
            return dtype, conf
    return None


def classify_from_oui(vendor: Optional[str], dtype: Optional[str]) -> Optional[tuple]:
    """OUI só é fiável para fabricantes de produto único (Cisco switch, Brother printer…)."""
    if not vendor or not dtype:
        return None
    if vendor in AMBIGUOUS_VENDORS:
        return dtype, 0.55
    return dtype, 0.82


def should_try_wmi(device: dict) -> bool:
    """
    WMI só em candidatos a PC Windows — evita timeouts em switches/impressoras.

    Tenta WMI sempre que a confiança é < 0.88, mesmo que o tipo seja AP ou
    Impressora — porque OUI/portas podem ter classificado errado um PC.
    Se WMI falhar no dispositivo real (switch/AP), o erro é silencioso.
    """
    dtype  = (device.get("type") or "").strip()
    conf   = float(device.get("confidence") or 0)
    src    = device.get("_class_source", "")
    vendor = (device.get("manufacturer") or "").lower()

    # Alta confiança via SNMP — sysDescr identificou claramente o dispositivo
    if conf >= 0.90 and src in ("snmp_engine", "snmp_descr", "wmi", "http"):
        if dtype in ("Switch", "Impressora", "Firewall", "NAS", "Câmara CCTV"):
            return False

    # Alta confiança via port scan na porta 9100 → provável impressora real…
    # EXCEPTO se o fabricante OUI é de PC (Ubiquiti, Dell, Lenovo, etc.) —
    # nesse caso é provavelmente um Windows a partilhar uma impressora via HP Smart.
    if conf >= 0.90 and src == "ports" and dtype == "Impressora":
        # Fabricantes que NÃO fazem impressoras → 9100 é print sharing de PC
        _not_printer_vendors = (
            "ubiquiti", "dell", "lenovo", "asus", "acer", "toshiba",
            "fujitsu", "samsung", "intel", "realtek", "vmware", "microsoft",
            "apple", "asustek", "giga-byte",
        )
        if any(v in vendor for v in _not_printer_vendors):
            return True   # WMI para confirmar que é PC
        return False      # Fabricante de impressora + porta 9100 → impressora real

    # Confiança baixa/média → sempre tenta WMI; se for um AP real o RPC vai falhar em silêncio
    if conf < 0.88:
        return True

    # Tipo claramente PC
    if dtype in ("Desktop", "Laptop", "Servidor", "Desconhecido", ""):
        return True

    # Fabricante é claramente PC
    pc_vendors = ("dell", "hp", "hewlett", "lenovo", "microsoft", "intel", "asus",
                  "acer", "toshiba", "fujitsu", "samsung")
    return any(v in vendor for v in pc_vendors)


def should_use_netbios(device: dict) -> bool:
    if device.get("type") in ("Switch", "Impressora", "Firewall", "Access Point", "NAS"):
        return False
    if float(device.get("confidence") or 0) >= 0.85:
        return False
    return True


def netbios_name_ok(name: str) -> bool:
    return name and not NETBIOS_SKIP.match(name)


def merge_classification(device: dict, dtype: str, confidence: float, source: str):
    """
    Aplica classificação se for melhor que a actual.

    Prioridade de fontes (da maior para a menor):
      wmi / snmp_engine (≥ 0.90) > ports > http > snmp_descr > model > ai > ai_mac > dns > oui

    Regras:
    • WMI e SNMP com confiança ≥ 0.90 nunca são sobrescritos por fontes não-determinísticas.
    • IA com contexto rico ("ai") pode corrigir classificações OUI/ai_mac erradas se tiver
      confiança ≥ 0.75 e estiver a MUDAR o tipo, ou confiança > actual se confirmar o mesmo tipo.
    • IA por MAC ("ai_mac") aplica-se após OUI; SNMP/ports/WMI sobrepõem-se depois.
    """
    cur_conf   = float(device.get("confidence") or 0)
    cur_source = device.get("_class_source", "")
    cur_type   = device.get("type") or ""

    # Fontes de alta certeza — nunca deixar sobrescrever por fontes mais fracas
    HIGH_CERTAINTY = ("wmi", "snmp_engine")
    if cur_source in HIGH_CERTAINTY and cur_conf >= 0.90 and source not in HIGH_CERTAINTY:
        return

    # IA com contexto rico pode corrigir classificações erradas
    if source == "ai":
        undetermined = cur_type in (None, "", "Desconhecido", "Outro")
        same_type    = dtype == cur_type
        if not undetermined:
            if same_type and confidence <= cur_conf:
                return   # Mesmo tipo mas confiança pior — nada a fazer
            if not same_type and confidence < 0.72:
                return   # Mudança de tipo requer confiança razoável

    if confidence > cur_conf or (confidence >= cur_conf - 0.05 and cur_type in (None, "", "Desconhecido")):
        device["type"]         = dtype
        device["confidence"]   = round(confidence, 2)
        # Limiar 0.72: cobre Dell/HP/Lenovo (0.72), Intel+finalização (0.76),
        # SNMP/WMI/hostname (0.82-0.99). Abaixo de 0.72 = genuinamente incerto.
        device["needs_review"] = 0 if confidence >= 0.72 else 1
        device["_class_source"] = source


def finalize_device(device: dict) -> dict:
    """Consolida sinais já recolhidos no dict do dispositivo."""
    # 1. SNMP sysDescr (já pode ter vindo de enrich_device_snmp)
    descr = device.get("_sys_descr") or ""
    ifaces = int(device.get("_interface_count") or 0)
    hit = classify_from_snmp_descr(descr, ifaces)
    if hit:
        merge_classification(device, hit[0], hit[1], "snmp_descr")

    # 2. Modelo local / SNMP
    hit = classify_from_model(device.get("model"))
    if hit:
        merge_classification(device, hit[0], hit[1], "model")

    # 3. Hostname (DNS ou SNMP)
    for hn in (device.get("hostname"), device.get("_dns_hostname")):
        hit = classify_from_hostname(hn)
        if hit:
            merge_classification(device, hit[0], hit[1], "hostname")
            break

    # 4. Tipo já definido pelo snmp_engine em enrich
    if device.get("snmp_available") and device.get("type") and float(device.get("confidence") or 0) >= 0.9:
        device["needs_review"] = 0

    device.setdefault("type", "Desconhecido")
    conf = float(device.get("confidence") or 0.4)
    if conf < 0.70:
        device["needs_review"] = 1
    elif conf >= 0.80:
        device["needs_review"] = 0

    return device
