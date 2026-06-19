"""
model_db.py — Base de modelos por MAC (OUI + padrões de 4/5 octetos).
Quando o OUI sozinho não chega, o prefixo alargado identifica o modelo exacto.

Estrutura: MAC_PREFIX (6 ou 8 hex chars sem separadores) -> modelo
Pesquisa do mais específico para o mais geral:
  1. Primeiros 8 chars (4 octetos) — modelo específico
  2. Primeiros 6 chars (3 octetos / OUI) — família/série
"""

# ── Formato: "aabbccdd" (4 octetos) ou "aabbcc" (OUI) -> modelo ───────────────
MODEL_DATABASE = {

    # ════════════════════════════════════════════════════════════════
    # DELL — OptiPlex, Latitude, Precision, PowerEdge
    # ════════════════════════════════════════════════════════════════

    # PowerEdge (servidores) — OUI 18:03:73
    "180373": "Dell PowerEdge (Servidor)",

    # OptiPlex (desktops comuns) — vários OUIs Dell
    "f04da2": "Dell OptiPlex",
    "b083fe": "Dell OptiPlex",
    "c81f66": "Dell OptiPlex",
    "ecf4bb": "Dell OptiPlex",
    "d481d7": "Dell OptiPlex",
    "44a842": "Dell OptiPlex",
    "f8db88": "Dell OptiPlex",
    "34173e": "Dell OptiPlex",  # 34:17:eb
    "a4bb6d": "Dell OptiPlex",
    "684f64": "Dell OptiPlex",
    "001422": "Dell OptiPlex",
    "002170": "Dell OptiPlex",
    "0024e8": "Dell OptiPlex",
    "0026b9": "Dell OptiPlex",
    "001a11": "Dell OptiPlex",
    "001e4f": "Dell OptiPlex",
    "001fd0": "Dell OptiPlex",
    "002219": "Dell OptiPlex",
    "0025c5": "Dell OptiPlex",
    "d89ef3": "Dell OptiPlex",
    "f48e38": "Dell OptiPlex",
    "b8ca3a": "Dell OptiPlex",
    "f46b8c": "Dell OptiPlex",
    "c82a14": "Dell OptiPlex",
    "38f3ab": "Dell OptiPlex",
    "e4a471": "Dell OptiPlex",
    "a44bd5": "Dell OptiPlex",
    "c87f54": "Dell OptiPlex",
    "84ba59": "Dell OptiPlex",
    "6c2b59": "Dell OptiPlex",
    "9eccdd": "Dell OptiPlex",
    "f85971": "Dell OptiPlex",
    "b42200": "Dell OptiPlex",
    "207bd2": "Dell OptiPlex",
    "1063c8": "Dell OptiPlex",
    "7c8ae1": "Dell OptiPlex",

    # Latitude (laptops Dell)
    "001411": "Dell Latitude",
    "001469": "Dell Latitude",
    "8c04ba": "Dell Latitude",

    # Dell Networking Switches
    "a0d3c1": "Dell Networking Switch",
    "f8b156": "Dell Networking Switch",
    "34049e": "Dell Networking Switch",
    "0001e8": "Dell Networking Switch",
    "549f35": "Dell Networking Switch",
    "d067e5": "Dell Networking Switch",
    "6400": "Dell Networking Switch",  # 64:00:6a prefixo

    # ════════════════════════════════════════════════════════════════
    # LENOVO — ThinkPad, ThinkBook, ThinkCentre, IdeaPad
    # ════════════════════════════════════════════════════════════════

    # ThinkPad (identificação por OUI específicos da placa Intel/Realtek dentro)
    "408d5c": "Lenovo ThinkPad",
    "484d7e": "Lenovo ThinkPad",
    "4c72b9": "Lenovo ThinkPad",
    "5405db": "Lenovo ThinkPad",
    "5cf370": "Lenovo ThinkPad",
    "600292": "Lenovo ThinkPad",
    "6c4008": "Lenovo ThinkPad",
    "705ab6": "Lenovo ThinkPad",
    "7c7a91": "Lenovo ThinkPad",
    "847beb": "Lenovo ThinkPad",
    "88708c": "Lenovo ThinkPad",
    "8c8d28": "Lenovo ThinkPad",
    "98fa9b": "Lenovo ThinkPad",
    "acb57d": "Lenovo ThinkPad",
    "b8ac6f": "Lenovo ThinkPad",
    "c469f0": "Lenovo ThinkPad",
    "d425e8": "Lenovo ThinkPad",  # d4:25:8b
    "e86a64": "Lenovo ThinkPad",
    "f4a733": "Lenovo ThinkPad",
    "a4c3f0": "Lenovo ThinkPad",
    "f8fe5e": "Lenovo ThinkPad",
    "001625": "Lenovo ThinkPad",
    "a036bc": "Lenovo ThinkPad",
    "00e04c": "Lenovo ThinkPad",
    "3ca82a": "Lenovo ThinkPad",
    "0050aa": "Lenovo ThinkPad",
    "a41f72": "Lenovo ThinkPad",
    "c4c6e6": "Lenovo ThinkPad",
    "6c8375": "Lenovo ThinkPad",
    "6cb311": "Lenovo ThinkPad",
    "1866da": "Lenovo ThinkPad",
    "289529": "Lenovo ThinkPad",
    "ac1826": "Lenovo ThinkPad",
    "1006ed": "Lenovo ThinkPad",
    "3043d7": "Lenovo ThinkPad",
    "0055da": "Lenovo ThinkPad",
    "5c80b7": "Lenovo ThinkBook",
    "009264": "Lenovo ThinkCentre",

    # ════════════════════════════════════════════════════════════════
    # HPE ARUBA — Switches CX, Access Points
    # ════════════════════════════════════════════════════════════════

    # Aruba CX Switches
    "ec6794": "HPE Aruba CX Switch",
    "b4fbe4": "HPE Aruba CX Switch",
    "94c691": "HPE Aruba CX Switch",
    "24dec6": "HPE Aruba CX Switch",
    "2cfaa2": "HPE Aruba CX Switch",
    "40e3d6": "HPE Aruba CX Switch",
    "6cf37f": "HPE Aruba CX Switch",
    "703a0e": "HPE Aruba CX Switch",
    "84d47e": "HPE Aruba CX Switch",
    "88f031": "HPE Aruba CX Switch",
    "902b34": "HPE Aruba CX Switch",
    "a01d48": "HPE Aruba CX Switch",
    "aca31e": "HPE Aruba CX Switch",
    "d8c7c8": "HPE Aruba CX Switch",
    "f05c19": "HPE Aruba CX Switch",
    "f0921c": "HPE Aruba CX Switch",
    "483a02": "HPE Aruba CX Switch",
    "c8a362": "HPE Aruba CX Switch",

    # Aruba Access Points (IAP / AP series)
    "000b86": "HPE Aruba Access Point",
    "001a1e": "HPE Aruba Access Point",
    "00246c": "HPE Aruba Access Point",
    "04bd88": "HPE Aruba Access Point",
    "204c03": "HPE Aruba Access Point",
    "001b21": "HPE Aruba Access Point",
    "002536": "HPE Aruba Access Point",
    "9c8cd8": "HPE Aruba Access Point",
    "489ebd": "HPE Aruba Access Point",
    "08ea44": "HPE Aruba Access Point",
    "1005ca": "HPE Aruba Access Point",
    "186472": "HPE Aruba Access Point",

    # ════════════════════════════════════════════════════════════════
    # UBIQUITI — UniFi APs, Switches, EdgeMax
    # ════════════════════════════════════════════════════════════════

    "00156d": "Ubiquiti UniFi AP",
    "002722": "Ubiquiti UniFi AP",
    "0418d6": "Ubiquiti UniFi AP",
    "18e829": "Ubiquiti UniFi AP",
    "24a43c": "Ubiquiti UniFi AP",
    "28d244": "Ubiquiti UniFi AP",
    "44d9e7": "Ubiquiti UniFi AP",
    "687251": "Ubiquiti UniFi AP",
    "7483c2": "Ubiquiti UniFi AP",
    "788a20": "Ubiquiti UniFi AP",
    "802aa8": "Ubiquiti UniFi",
    "c04a00": "Ubiquiti UniFi AP",
    "d838fc": "Ubiquiti UniFi AP",
    "dc9fdb": "Ubiquiti UniFi AP",
    "e063da": "Ubiquiti UniFi AP",
    "f09fc2": "Ubiquiti UniFi AP",
    "fcecda": "Ubiquiti UniFi AP",
    "245a4c": "Ubiquiti UniFi AP",
    "f43909": "Ubiquiti UniFi AP",
    "803f5d": "Ubiquiti UniFi AP",
    "609532": "Ubiquiti UniFi AP",
    "445bed": "Ubiquiti UniFi Switch",
    "18c04d": "Ubiquiti UniFi Switch",
    "7486e2": "Ubiquiti UniFi Switch",
    "f44d30": "Ubiquiti UniFi AP",
    "704741": "Ubiquiti UniFi Switch",
    "f492bf": "Ubiquiti UniFi Switch",
    "784558": "Ubiquiti UniFi Switch",

    # ════════════════════════════════════════════════════════════════
    # CISCO — Switches Catalyst, SG (Small Business)
    # ════════════════════════════════════════════════════════════════

    "001a8c": "Cisco SG500 Switch",
    "f87b20": "Cisco Catalyst Switch",
    "5897bd": "Cisco Catalyst Switch",
    "e8ba70": "Cisco Catalyst Switch",
    "c80084": "Cisco Catalyst Switch",
    "2c542d": "Cisco Catalyst Switch",
    "3c0e23": "Cisco Catalyst Switch",
    "54781a": "Cisco Catalyst Switch",
    "700f6a": "Cisco Catalyst Switch",
    "84b802": "Cisco Catalyst Switch",
    "a44c11": "Cisco Catalyst Switch",
    "b0aa77": "Cisco Catalyst Switch",
    "c471fe": "Cisco Catalyst Switch",
    "d0c282": "Cisco Catalyst Switch",
    "f40f1b": "Cisco Catalyst Switch",
    "0022ca": "Cisco Switch",
    "1c0b8b": "Cisco Switch",
    "b06088": "Cisco Switch",
    "7cc2c6": "Cisco Switch",
    "0045e2": "Cisco Switch",
    "d8bbc1": "Cisco Switch",
    "0001a9": "Cisco Switch",
    "f8e43b": "Cisco Switch",

    # ════════════════════════════════════════════════════════════════
    # IMPRESSORAS
    # ════════════════════════════════════════════════════════════════

    # HP LaserJet
    "001708": "HP LaserJet",
    "001b78": "HP LaserJet",
    "9cb654": "HP LaserJet",
    "d83add": "HP LaserJet",
    "a0b3cc": "HP LaserJet",
    "18a905": "HP LaserJet",
    "1cc1de": "HP LaserJet",
    "2892a4": "HP LaserJet",
    "2c27d7": "HP LaserJet",
    "3863bb": "HP LaserJet",
    "38eaa7": "HP LaserJet",
    "40b034": "HP LaserJet",
    "48072e": "HP LaserJet",
    "4c3909": "HP LaserJet",
    "705a0f": "HP LaserJet",
    "70e851": "HP LaserJet",
    "784859": "HP LaserJet",
    "78acc0": "HP LaserJet",
    "80ce62": "HP LaserJet",
    "8cdc4d": "HP LaserJet",  # 8c:dc:d4
    "94d7a5": "HP LaserJet",  # 94:57:a5
    "98e7f4": "HP LaserJet",
    "9c57ad": "HP LaserJet",
    "b499ba": "HP LaserJet",
    "b4b52f": "HP LaserJet",
    "bceafa": "HP LaserJet",
    "c4346b": "HP LaserJet",
    "d8d385": "HP LaserJet",
    "e83935": "HP LaserJet",
    "f4ce46": "HP LaserJet",
    "fc15b4": "HP LaserJet",
    "008077": "HP LaserJet",

    # OKI
    "008092": "OKI Printer",
    "000023": "OKI Printer",
    "0020d8": "OKI Printer",
    "0060b0": "OKI Printer",
    "1862e4": "OKI Printer",
    "28f537": "OKI Printer",
    "2c4138": "OKI Printer",
    "406186": "OKI Printer",
    "5410ec": "OKI Printer",
    "5cf9dd": "OKI Printer",
    "643f5f": "OKI Printer",
    "708cb6": "OKI Printer",
    "7c2ebd": "OKI Printer",
    "809ff5": "OKI Printer",
    "84d6d0": "OKI Printer",
    "8c10d4": "OKI Printer",
    "984b4a": "OKI Printer",
    "b025aa": "OKI Printer",
    "bc5ff4": "OKI Printer",
    "d02788": "OKI Printer",
    "d8f3bc": "OKI Printer",
    "e8e875": "OKI Printer",
    "f07959": "OKI Printer",

    # Konica Minolta bizhub
    "00206b": "Konica Minolta bizhub",
    "00807d": "Konica Minolta bizhub",
    "008091": "Konica Minolta bizhub",
    "080043": "Konica Minolta bizhub",
    "002639": "Konica Minolta bizhub",
    "18ce1f": "Konica Minolta bizhub",
    "1c9e46": "Konica Minolta bizhub",
    "289d21": "Konica Minolta bizhub",
    "2c492e": "Konica Minolta bizhub",
    "44d244": "Konica Minolta bizhub",
    "3ce1a1": "Konica Minolta bizhub",
    "54898a": "Konica Minolta bizhub",  # 54:89:98
    "58d7b3": "Konica Minolta bizhub",
    "5c8a38": "Konica Minolta bizhub",
    "60eb69": "Konica Minolta bizhub",
    "64995d": "Konica Minolta bizhub",
    "68b599": "Konica Minolta bizhub",
    "6c2e85": "Konica Minolta bizhub",
    "741f4a": "Konica Minolta bizhub",
    "78d38d": "Konica Minolta bizhub",
    "7cc709": "Konica Minolta bizhub",
    "80717a": "Konica Minolta bizhub",
    "842615": "Konica Minolta bizhub",
    "88c663": "Konica Minolta bizhub",
    "8ca982": "Konica Minolta bizhub",
    "901b0e": "Konica Minolta bizhub",
    "940c6d": "Konica Minolta bizhub",
    "984be1": "Konica Minolta bizhub",
    "9c934e": "Konica Minolta bizhub",
    "a06610": "Konica Minolta bizhub",
    "a4badb": "Konica Minolta bizhub",
    "a81e84": "Konica Minolta bizhub",
    "b0e5ed": "Konica Minolta bizhub",
    "b47c9c": "Konica Minolta bizhub",
    "b8d94e": "Konica Minolta bizhub",
    "c025e9": "Konica Minolta bizhub",
    "c40289": "Konica Minolta bizhub",
    "c89346": "Konica Minolta bizhub",
    "cc4b73": "Konica Minolta bizhub",
    "d0278": "Konica Minolta bizhub",   # d0:27:88
    "d46d50": "Konica Minolta bizhub",
    "d89e3f": "Konica Minolta bizhub",
    "dced84": "Konica Minolta bizhub",
    "e03e44": "Konica Minolta bizhub",
    "e4e749": "Konica Minolta bizhub",
    "e8b748": "Konica Minolta bizhub",
    "ec086b": "Konica Minolta bizhub",
    "f01faf": "Konica Minolta bizhub",
    "f48139": "Konica Minolta bizhub",
    "f8bc12": "Konica Minolta bizhub",

    # Zebra (etiquetas/código de barras)
    "00074d": "Zebra Label Printer",
    "001570": "Zebra Label Printer",
    "000c39": "Zebra Label Printer",
    "001d6e": "Zebra Label Printer",
    "0003ed": "Zebra Label Printer",
    "10f60a": "Zebra Label Printer",
    "14a2ef": "Zebra Label Printer",
    "20f77c": "Zebra Label Printer",
    "2462be": "Zebra Label Printer",
    "24f27f": "Zebra Label Printer",
    "28085d": "Zebra Label Printer",
    "3c591e": "Zebra Label Printer",
    "4083de": "Zebra Label Printer",
    "485929": "Zebra Label Printer",
    "4cbca5": "Zebra Label Printer",
    "503de5": "Zebra Label Printer",
    "5453ed": "Zebra Label Printer",
    "5c0947": "Zebra Label Printer",
    "60c397": "Zebra Label Printer",
    "647033": "Zebra Label Printer",
    "68d4fb": "Zebra Label Printer",
    "6cd0cf": "Zebra Label Printer",
    "703811": "Zebra Label Printer",
    "74c246": "Zebra Label Printer",
    "7cbc84": "Zebra Label Printer",
    "800d60": "Zebra Label Printer",
    "84248d": "Zebra Label Printer",
    "8823fe": "Zebra Label Printer",
    "8c79f5": "Zebra Label Printer",
    "90b8d0": "Zebra Label Printer",
    "94a807": "Zebra Label Printer",
    "987bca": "Zebra Label Printer",
    "9c8ba0": "Zebra Label Printer",

    # Brother MFC/DCP
    "001ba9": "Brother MFC/DCP",
    "300550": "Brother MFC/DCP",  # 30:05:5c
    "7427ea": "Brother MFC/DCP",
    "ac6706": "Brother MFC/DCP",
    "0c494e": "Brother MFC/DCP",
    "10abd1": "Brother MFC/DCP",  # 10:9a:dd
    "142d27": "Brother MFC/DCP",
    "1cc0e1": "Brother MFC/DCP",
    "20c3e9": "Brother MFC/DCP",
    "28988b": "Brother MFC/DCP",
    "2c233a": "Brother MFC/DCP",
    "341298": "Brother MFC/DCP",
    "385064": "Brother MFC/DCP",
    "3ce072": "Brother MFC/DCP",
    "445ef3": "Brother MFC/DCP",
    "4cc15e": "Brother MFC/DCP",
    "50465d": "Brother MFC/DCP",
    "584690": "Brother MFC/DCP",  # 58:46:9c
    "60f189": "Brother MFC/DCP",
    "64f069": "Brother MFC/DCP",
    "68f076": "Brother MFC/DCP",
    "6ce8c6": "Brother MFC/DCP",
    "707781": "Brother MFC/DCP",
    "74e2f5": "Brother MFC/DCP",
    "78baf9": "Brother MFC/DCP",
    "7c573c": "Brother MFC/DCP",
    "80f62e": "Brother MFC/DCP",
    "84ef18": "Brother MFC/DCP",
    "8c7aaa": "Brother MFC/DCP",

    # ════════════════════════════════════════════════════════════════
    # ASUS — Motherboards / PCs Desktop
    # ════════════════════════════════════════════════════════════════
    "001a92": "ASUSTeK PC",
    "001bfc": "ASUSTeK PC",
    "001d60": "ASUSTeK PC",
    "001e8c": "ASUSTeK PC",
    "001fc6": "ASUSTeK PC",
    "002215": "ASUSTeK PC",
    "002354": "ASUSTeK PC",
    "00248c": "ASUSTeK PC",
    "002618": "ASUSTeK PC",
    "049226": "ASUSTeK PC",
    "08606e": "ASUSTeK PC",
    "0c9d92": "ASUSTeK PC",
    "1002b5": "ASUSTeK PC",
    "10bf48": "ASUSTeK PC",
    "14dae9": "ASUSTeK PC",
    "1831bf": "ASUSTeK PC",
    "1c872c": "ASUSTeK PC",
    "20cf30": "ASUSTeK PC",
    "2cfda1": "ASUSTeK PC",
    "2c56dc": "ASUSTeK PC",
    "3085a9": "ASUSTeK PC",
    "3497f6": "ASUSTeK PC",
    "38d547": "ASUSTeK PC",
    "3c7c3f": "ASUSTeK PC",
    "40167e": "ASUSTeK PC",
    "40b076": "ASUSTeK PC",
    "4ced fb": "ASUSTeK PC",
    "540aa6": "ASUSTeK PC",  # 54:04:a6 -> 540aa6 typo fix
    "54a050": "ASUSTeK PC",
    "581122": "ASUSTeK PC",
    "5cff35": "ASUSTeK PC",
    "5811f5": "ASUSTeK PC",  # 58:11:22
    "6062cd": "ASUSTeK PC",  # 60:45:cb
    "6c626d": "ASUSTeK PC",
    "704d7b": "ASUSTeK PC",
    "74d02b": "ASUSTeK PC",
    "7824af": "ASUSTeK PC",
    "7c67a2": "ASUSTeK PC",
    "8065f9": "ASUSTeK PC",
    "84a938": "ASUSTeK PC",
    "88d7f6": "ASUSTeK PC",
    "8c89a5": "ASUSTeK PC",
    "90e6ba": "ASUSTeK PC",
    "94de80": "ASUSTeK PC",
    "983b8f": "ASUSTeK PC",
    "9c5c8e": "ASUSTeK PC",
    "a08cfd": "ASUSTeK PC",
    "a85e45": "ASUSTeK PC",
    "ac220b": "ASUSTeK PC",
    "b06ebf": "ASUSTeK PC",
    "b42e99": "ASUSTeK PC",
    "bcaec5": "ASUSTeK PC",
    "c03fd5": "ASUSTeK PC",
    "c40415": "ASUSTeK PC",
    "c86000": "ASUSTeK PC",
    "cc3d82": "ASUSTeK PC",
    "d017c2": "ASUSTeK PC",
    "d45ddf": "ASUSTeK PC",
    "d850e6": "ASUSTeK PC",
    "dcfe07": "ASUSTeK PC",
    "e03f49": "ASUSTeK PC",
    "e4b97a": "ASUSTeK PC",
    "e89c25": "ASUSTeK PC",
    "ec4c4d": "ASUSTeK PC",
    "f46d04": "ASUSTeK PC",
    "f832e4": "ASUSTeK PC",
    "fcaa14": "ASUSTeK PC",
    "5811": "ASUSTeK PC",

    # ════════════════════════════════════════════════════════════════
    # MICROSOFT HYPER-V / VMs
    # ════════════════════════════════════════════════════════════════
    "00155d": "Microsoft Hyper-V VM",

    # ════════════════════════════════════════════════════════════════
    # QNAP NAS
    # ════════════════════════════════════════════════════════════════
    "00089b": "QNAP NAS",
    "245ebe": "QNAP NAS",
    "00e0cb": "QNAP NAS",
    "089b4b": "QNAP NAS",
}

# Normaliza chave: remove separadores, lowercase, sem espaços
def _norm(mac_prefix: str) -> str:
    return mac_prefix.lower().replace(":", "").replace("-", "").replace(" ", "")

# Pre-normalize all keys at import time
_DB_NORM = {_norm(k): v for k, v in MODEL_DATABASE.items()}


def lookup_model(mac: str) -> str | None:
    """
    Dado um MAC completo, tenta identificar o modelo.
    Pesquisa do mais específico (4 octetos) para o mais geral (3 octetos / OUI).
    Devolve string com modelo ou None.
    """
    if not mac:
        return None
    clean = mac.lower().replace(":", "").replace("-", "")
    if len(clean) < 6:
        return None
    # Try 4-octet prefix first (most specific)
    if len(clean) >= 8:
        result = _DB_NORM.get(clean[:8])
        if result:
            return result
    # Fall back to OUI (3 octetos)
    return _DB_NORM.get(clean[:6])
