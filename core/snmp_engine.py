"""
snmp_engine.py — Motor SNMP completo.
Extrai modelo, S/N, firmware, portas, toner, páginas, uptime, interfaces.
Sem bibliotecas externas — UDP puro.
"""

import socket
import struct
import time
import re
from concurrent.futures import ThreadPoolExecutor


# ── OIDs standard (RFC 1213 / Printer MIB / Entity MIB) ──────────────────────
OIDS = {
    # System MIB
    "sysDescr":       "1.3.6.1.2.1.1.1.0",   # Descrição completa (modelo+firmware)
    "sysName":        "1.3.6.1.2.1.1.5.0",   # Hostname configurado
    "sysContact":     "1.3.6.1.2.1.1.4.0",   # Contacto
    "sysLocation":    "1.3.6.1.2.1.1.6.0",   # Localização
    "sysUptime":      "1.3.6.1.2.1.1.3.0",   # Uptime em ticks (1/100 seg)
    "sysObjectID":    "1.3.6.1.2.1.1.2.0",   # OID do produto
    "ifNumber":       "1.3.6.1.2.1.2.1.0",   # Nº de interfaces

    # Entity MIB — modelo e S/N (funciona em switches, APs, impressoras)
    "entPhysDescr":   "1.3.6.1.2.1.47.1.1.1.1.2.1",   # Descrição física
    "entPhysName":    "1.3.6.1.2.1.47.1.1.1.1.7.1",   # Nome do produto
    "entPhysSN":      "1.3.6.1.2.1.47.1.1.1.1.11.1",  # Número de série
    "entPhysFW":      "1.3.6.1.2.1.47.1.1.1.1.9.1",   # Versão firmware
    "entPhysHW":      "1.3.6.1.2.1.47.1.1.1.1.8.1",   # Versão hardware
    "entPhysModel":   "1.3.6.1.2.1.47.1.1.1.1.13.1",  # Model number

    # Printer MIB — toner níveis e capacidades (slots 1-5)
    # Slot 1-4 = standard CMYK; algumas impressoras têm drum no slot 1 e toner nos slots 2-5
    "tonerMax1":  "1.3.6.1.2.1.43.11.1.1.8.1.1",
    "tonerMax2":  "1.3.6.1.2.1.43.11.1.1.8.1.2",
    "tonerMax3":  "1.3.6.1.2.1.43.11.1.1.8.1.3",
    "tonerMax4":  "1.3.6.1.2.1.43.11.1.1.8.1.4",
    "tonerMax5":  "1.3.6.1.2.1.43.11.1.1.8.1.5",
    "tonerLevel1":"1.3.6.1.2.1.43.11.1.1.9.1.1",
    "tonerLevel2":"1.3.6.1.2.1.43.11.1.1.9.1.2",
    "tonerLevel3":"1.3.6.1.2.1.43.11.1.1.9.1.3",
    "tonerLevel4":"1.3.6.1.2.1.43.11.1.1.9.1.4",
    "tonerLevel5":"1.3.6.1.2.1.43.11.1.1.9.1.5",
    # Descrição de cada slot (identifica qual é toner vs drum/imaging unit)
    "tonerDesc1": "1.3.6.1.2.1.43.11.1.1.6.1.1",
    "tonerDesc2": "1.3.6.1.2.1.43.11.1.1.6.1.2",
    "tonerDesc3": "1.3.6.1.2.1.43.11.1.1.6.1.3",
    "tonerDesc4": "1.3.6.1.2.1.43.11.1.1.6.1.4",
    "tonerDesc5": "1.3.6.1.2.1.43.11.1.1.6.1.5",
    "pageCount":  "1.3.6.1.2.1.43.10.2.1.4.1.1",
    "printerModel":"1.3.6.1.2.1.25.3.2.1.3.1",      # hrDeviceDescr

    # Aruba
    "arubaModel": "1.3.6.1.4.1.14823.2.2.1.1.1.4.0",
    "arubaSN":    "1.3.6.1.4.1.14823.2.2.1.1.1.3.0",

    # Cisco
    "ciscoModel": "1.3.6.1.4.1.9.9.92.1.1.1.13.1",

    # HP Printer
    "hpModel":    "1.3.6.1.4.1.11.2.3.9.4.2.1.1.3.3.0",
    "hpSN":       "1.3.6.1.4.1.11.2.3.9.4.2.1.1.3.6.0",

    # OKI / Konica
    "prtGeneralPrinterName": "1.3.6.1.2.1.43.8.2.1.14.1.1",

    # Canon imageRUNNER
    "canonModel": "1.3.6.1.4.1.1602.1.2.3.0",

    # Ricoh
    "ricohModel": "1.3.6.1.4.1.367.3.2.1.2.1.4.0",

    # Brother
    "brotherModel": "1.3.6.1.4.1.2435.2.3.9.4.2.1.5.5.0",

    # Lexmark
    "lexmarkModel": "1.3.6.1.4.1.641.2.1.2.1.3.1",

    # Ubiquiti (UniFi APs — OID específico devolve modelo mesmo quando sysDescr é "Linux...")
    "ubntModel":  "1.3.6.1.4.1.41112.1.4.1.1.2.1",
}

# Regex pré-compiladas para extracção de modelo — evita recompilação por host
_RE_ARUBA   = re.compile(r"Aruba[OS\s]+([\w\-]+)", re.I)
_RE_CISCO   = re.compile(r"cisco\s+([\w\-]+)", re.I)
# HP: cobre LaserJet, Color LaserJet, OfficeJet, PageWide, DesignJet
_RE_HP      = re.compile(r"HP\s+((?:Color\s+)?(?:LaserJet|OfficeJet|PageWide|DesignJet|DeskJet)[\w\s\-]+?)(?:,|\s{2,}|$)", re.I)
_RE_DELL    = re.compile(r"Dell\s+((?:Networking|EMC|PowerSwitch|PowerConnect)\s+[\w\s]+?)(?:\s{2,}|,|$)", re.I)
_RE_OKI     = re.compile(r"OKI\s+([\w\-]+)", re.I)
_RE_KONICA  = re.compile(r"(bizhub[\s\w\-]+?)(?:\s{2,}|,|$)", re.I)
_RE_ZEBRA   = re.compile(r"Zebra\s+([\w\-]+)", re.I)
_RE_CANON   = re.compile(r"Canon\s+([\w\s\-]+?)(?:Series|,|\s{2,}|$)", re.I)
_RE_RICOH   = re.compile(r"Ricoh\s+([\w\s\-]+?)(?:,|\s{2,}|$)", re.I)
_RE_BROTHER = re.compile(r"Brother\s+([\w\-]+)", re.I)
_RE_LEXMARK = re.compile(r"Lexmark\s+([\w\s\-]+?)(?:,|\s{2,}|$)", re.I)
_RE_TOSHIBA = re.compile(r"Toshiba\s+(e[\-]?STUDIO[\w\s]+?)(?:,|\s{2,}|$)", re.I)
_RE_SHARP   = re.compile(r"Sharp\s+((?:MX|AR|BP)[\w\-]+)", re.I)
_RE_MIKROTIK= re.compile(r"RouterOS\s+([\w\-]+)", re.I)


class SNMPEngine:
    """SNMP v2c GET engine — sem dependências externas."""

    def __init__(self, community="public", timeout=3.0, retries=2):
        self.community = community
        self.timeout   = timeout
        self.retries   = retries

    # ── Public API ────────────────────────────────────────────────────────────

    def full_scan(self, ip: str) -> dict:
        """
        Scan completo com pre-probe e OIDs paralelos.

        1. Testa sysDescr com timeout curto (1s) — se não responder, sai já
           e evita N×timeout de espera para hosts sem SNMP.
        2. Se responder, faz GET de todos os restantes OIDs em paralelo
           (ThreadPoolExecutor), reduzindo tempo de ~50s → ~2s por host.
        """
        # 1. Pre-probe rápido — 1 único OID para confirmar que SNMP existe
        sys_descr = self._snmp_get(ip, OIDS["sysDescr"], timeout=1.0)
        if not sys_descr:
            return {"ip": ip, "_raw": {}}   # sem SNMP — sai imediatamente

        raw = {"sysDescr": sys_descr}

        # 2. Restantes OIDs em paralelo
        remaining = [(name, oid) for name, oid in OIDS.items() if name != "sysDescr"]

        def _fetch(name_oid):
            name, oid = name_oid
            return name, self.get(ip, oid)

        with ThreadPoolExecutor(max_workers=8) as pool:
            for name, val in pool.map(_fetch, remaining):
                if val is not None:
                    raw[name] = val

        return self._process(ip, raw)

    def get(self, ip: str, oid: str) -> str | int | None:
        """GET de um OID único."""
        for _ in range(self.retries):
            result = self._snmp_get(ip, oid)
            if result is not None:
                return result
        return None

    # ── Processing — extrai campos estruturados ───────────────────────────────

    def _process(self, ip: str, raw: dict) -> dict:
        result = {"ip": ip, "_raw": raw}

        # sysDescr — fonte principal de modelo
        sys_descr = str(raw.get("sysDescr", "")).strip()
        result["sys_descr"]   = sys_descr
        result["sys_name"]    = str(raw.get("sysName", "")).strip()
        result["sys_location"]= str(raw.get("sysLocation", "")).strip()

        # Uptime — converte ticks para hh:mm
        uptime_ticks = raw.get("sysUptime")
        if uptime_ticks and str(uptime_ticks).isdigit():
            secs = int(uptime_ticks) // 100
            days = secs // 86400
            hrs  = (secs % 86400) // 3600
            result["uptime"] = f"{days}d {hrs}h"
        else:
            result["uptime"] = None

        # Número de interfaces
        ifaces = raw.get("ifNumber")
        result["interface_count"] = int(ifaces) if ifaces and str(ifaces).isdigit() else None

        # Tipo inferido do sysDescr — usado para escolher a prioridade dos OIDs de modelo
        # _infer_type devolve (tipo, confiança); desempacota para uso local
        inferred_type, inferred_conf = self._infer_type(sys_descr, raw)

        if inferred_type == "Impressora":
            # Para impressoras: OIDs vendor-específicos têm modelo limpo;
            # entPhysName/Descr costumam devolver "Chassis" ou lixo
            model = (
                raw.get("hpModel") or
                raw.get("canonModel") or
                raw.get("ricohModel") or
                raw.get("brotherModel") or
                raw.get("lexmarkModel") or
                raw.get("printerModel") or
                raw.get("prtGeneralPrinterName") or
                raw.get("entPhysName") or
                raw.get("entPhysModel") or
                self._extract_model_from_descr(sys_descr)
            )
        elif inferred_type == "Access Point":
            # UniFi APs com sysDescr "Linux..." — usar OID Ubiquiti específico
            model = (
                raw.get("ubntModel") or
                raw.get("arubaModel") or
                raw.get("entPhysName") or
                raw.get("entPhysModel") or
                self._extract_model_from_descr(sys_descr)
            )
        else:
            # Dispositivos de rede e outros: Entity MIB primeiro
            model = (
                raw.get("entPhysName") or
                raw.get("entPhysModel") or
                raw.get("entPhysDescr") or
                raw.get("arubaModel") or
                raw.get("ciscoModel") or
                raw.get("ubntModel") or
                raw.get("hpModel") or
                raw.get("printerModel") or
                raw.get("prtGeneralPrinterName") or
                self._extract_model_from_descr(sys_descr)
            )
        result["model"] = self._clean_model(str(model)) if model else None

        # Número de série
        sn = (
            raw.get("entPhysSN") or
            raw.get("arubaSN") or
            raw.get("hpSN")
        )
        result["serial_number"] = str(sn).strip() if sn else None

        # Firmware
        fw = raw.get("entPhysFW")
        result["firmware"] = str(fw).strip() if fw else None

        # Tipo de dispositivo e confiança — inferidos acima durante a selecção do modelo
        result["device_type"]      = inferred_type
        result["device_type_conf"] = inferred_conf

        # Toner (impressoras)
        result["toner"] = self._process_toner(raw)

        # Páginas
        pages = raw.get("pageCount")
        result["total_pages"] = int(pages) if pages and str(pages).isdigit() else None

        return result

    def _extract_model_from_descr(self, descr: str) -> str | None:
        """Extrai modelo da string sysDescr. Usa regex pré-compiladas."""
        if not descr:
            return None
        descr = descr.strip()

        checks = [
            (_RE_ARUBA,    lambda m: m.group(1)),
            (_RE_CISCO,    lambda m: m.group(1)),
            (_RE_HP,       lambda m: "HP " + m.group(1).strip()),
            (_RE_DELL,     lambda m: "Dell " + m.group(1).strip()),
            (_RE_OKI,      lambda m: "OKI " + m.group(1)),
            (_RE_KONICA,   lambda m: "Konica Minolta " + m.group(1).strip()),
            (_RE_ZEBRA,    lambda m: "Zebra " + m.group(1)),
            (_RE_CANON,    lambda m: "Canon " + m.group(1).strip()),
            (_RE_RICOH,    lambda m: "Ricoh " + m.group(1).strip()),
            (_RE_BROTHER,  lambda m: "Brother " + m.group(1)),
            (_RE_LEXMARK,  lambda m: "Lexmark " + m.group(1).strip()),
            (_RE_TOSHIBA,  lambda m: "Toshiba " + m.group(1).strip()),
            (_RE_SHARP,    lambda m: "Sharp " + m.group(1)),
            (_RE_MIKROTIK, lambda m: "MikroTik " + m.group(1)),
        ]
        for regex, fmt in checks:
            m = regex.search(descr)
            if m:
                return fmt(m)

        # Genérico — primeiros 40 chars
        return descr[:40] if len(descr) > 5 else None

    def _clean_model(self, model: str) -> str | None:
        """Remove lixo da string de modelo."""
        model = re.sub(r'\s+', ' ', model).strip()
        model = re.sub(r'^["\']|["\']$', '', model)
        if len(model) < 2:
            return None
        return model[:80]

    def _infer_type(self, descr: str, raw: dict) -> tuple:
        """Infere tipo e confiança de dispositivo a partir do sysDescr.
        Retorna (tipo, confiança) ou (None, 0.0) se não houver match."""
        from core.device_classifier import classify_from_snmp_descr
        ifaces = int(raw.get("ifNumber") or 0)
        hit = classify_from_snmp_descr(descr, ifaces)
        return hit if hit else (None, 0.0)

    def _process_toner(self, raw: dict) -> dict | None:
        """
        Converte níveis de toner em percentagem.

        Usa a OID de descrição de cada slot para identificar a cor correctamente.
        Isto é crítico porque algumas impressoras têm o drum/imaging unit no slot 1
        e os cartuchos de toner a partir do slot 2 (ex: certos HP Color LaserJet).
        Sem este mapeamento, lería o drum como toner preto.
        """
        # Keywords para identificar cor pela description SNMP
        _COLOR_PAT = [
            ("black",   re.compile(r"black|preto|negro|noir|schwarz|\bk\b|cyan.*magenta.*yellow", re.I)),
            ("cyan",    re.compile(r"cyan|ciano|bleu|blau",   re.I)),
            ("magenta", re.compile(r"magenta|rouge|rot",      re.I)),
            ("yellow",  re.compile(r"yellow|amarelo|jaune|gelb", re.I)),
        ]

        # Tenta mapear slot → cor via description
        slot_color: dict[int, str] = {}
        for idx in range(1, 6):
            desc = str(raw.get(f"tonerDesc{idx}") or "").strip()
            if not desc:
                continue
            for color, pat in _COLOR_PAT:
                if pat.search(desc):
                    slot_color[idx] = color
                    break
            # Se a descrição não bate nenhuma cor (ex: "Drum", "Imaging Unit"), o slot é ignorado

        # Sem descriptions → assume mapeamento padrão K=1, C=2, M=3, Y=4
        if not slot_color:
            slot_color = {1: "black", 2: "cyan", 3: "magenta", 4: "yellow"}

        toner: dict[str, int] = {}
        for idx in range(1, 6):
            color = slot_color.get(idx)
            if not color:
                continue
            cur = raw.get(f"tonerLevel{idx}")
            mx  = raw.get(f"tonerMax{idx}")
            if cur is None:
                continue
            try:
                cur_i = int(cur)
                mx_i  = int(mx) if mx else 100
                if mx_i <= 0:
                    mx_i = 100
                # -3 = not supported, -2 = unknown, -1 = no restriction (já é %)
                if cur_i < 0:
                    toner[color] = -1
                else:
                    pct = round(cur_i / mx_i * 100)
                    toner[color] = min(100, max(0, pct))
            except Exception:
                pass

        return toner if toner else None

    # ── SNMP UDP packet builder ───────────────────────────────────────────────

    def _snmp_get(self, ip: str, oid: str, timeout: float = None) -> str | int | None:
        """Minimal SNMPv2c GET over raw UDP. timeout sobrepõe self.timeout se fornecido."""
        t = timeout if timeout is not None else self.timeout
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(t)
                packet = self._build_get(oid)
                sock.sendto(packet, (ip, 161))
                data, _ = sock.recvfrom(4096)
            return self._parse_response(data)
        except Exception:
            return None

    def _encode_oid(self, oid_str: str) -> bytes:
        parts = [int(x) for x in oid_str.split(".") if x]
        encoded = bytes([40 * parts[0] + parts[1]])
        for p in parts[2:]:
            if p == 0:
                encoded += b"\x00"
                continue
            buf = []
            v = p
            while v:
                buf.append(v & 0x7f)
                v >>= 7
            buf.reverse()
            for i, b in enumerate(buf):
                encoded += bytes([b | (0x80 if i < len(buf) - 1 else 0)])
        return encoded

    def _tlv(self, tag: int, value: bytes) -> bytes:
        ln = len(value)
        if ln < 128:
            return bytes([tag, ln]) + value
        elif ln < 256:
            return bytes([tag, 0x81, ln]) + value
        else:
            return bytes([tag, 0x82, ln >> 8, ln & 0xff]) + value

    def _build_get(self, oid: str) -> bytes:
        oid_enc   = self._encode_oid(oid)
        oid_tlv   = self._tlv(0x06, oid_enc)
        null_tlv  = b"\x05\x00"
        varbind   = self._tlv(0x30, oid_tlv + null_tlv)
        vblist    = self._tlv(0x30, varbind)
        req_id    = self._tlv(0x02, b"\x00\x01")
        err_st    = self._tlv(0x02, b"\x00")
        err_idx   = self._tlv(0x02, b"\x00")
        pdu       = self._tlv(0xa0, req_id + err_st + err_idx + vblist)
        version   = self._tlv(0x02, b"\x01")  # v2c
        community = self._tlv(0x04, self.community.encode())
        return self._tlv(0x30, version + community + pdu)

    def _parse_response(self, data: bytes) -> str | int | None:
        """
        Extrai o valor de uma resposta SNMP GET.

        Percorre a árvore BER de forma correcta:
        - Desce DENTRO de contentor TLVs (SEQUENCE, PDUs)
        - Quando encontra um OID (tag 0x06), lê o TLV imediatamente a seguir
          como o valor da variável — este é sempre o padrão VarBind do SNMP.

        Suporta todos os tipos necessários:
            OctetString, Integer, Counter32, Gauge32, TimeTicks, Counter64
        """
        if len(data) < 10:
            return None

        # Tags que são "contentor" (encapsulam outros TLVs) — descemos para dentro
        _CONTAINERS = frozenset({0x30, 0xa0, 0xa1, 0xa2, 0xa3, 0xa4, 0xa5, 0xa6, 0xa7})

        def read_len(pos: int):
            """Lê comprimento BER, devolve (length, first_byte_after_len)."""
            b = data[pos]
            if b & 0x80:
                n = b & 0x7f
                if n == 0 or pos + n >= len(data):
                    raise ValueError("BER length invalid")
                ln = int.from_bytes(data[pos + 1: pos + 1 + n], "big")
                return ln, pos + 1 + n
            return b, pos + 1

        def decode_val(tag: int, content: bytes):
            """Converte bytes BER no tipo Python correspondente."""
            if tag == 0x04:  # OctetString
                s = content.decode("utf-8", errors="replace").strip("\x00").strip()
                return s if s else None
            if tag == 0x02:  # Integer (signed)
                return int.from_bytes(content, "big", signed=True) if content else 0
            if tag in (0x41, 0x42, 0x47):  # Counter32, Gauge32, Unsigned32
                return int.from_bytes(content, "big") if len(content) <= 4 else None
            if tag == 0x43:  # TimeTicks
                return int.from_bytes(content, "big") if len(content) <= 4 else None
            if tag == 0x46:  # Counter64 — essencial para ifHCInOctets/OutOctets
                return int.from_bytes(content, "big") if len(content) <= 8 else None
            if tag == 0x40:  # IpAddress
                return ".".join(str(b) for b in content) if len(content) == 4 else None
            if tag == 0x05:  # Null / noSuchObject / noSuchInstance
                return None
            return None

        try:
            pos = 0
            while pos < len(data) - 1:
                tag = data[pos]
                ln, val_start = read_len(pos + 1)
                val_end = val_start + ln

                if tag in _CONTAINERS:
                    # Desce para dentro do contentor
                    pos = val_start
                    continue

                if tag == 0x06:  # OID — o valor segue imediatamente (padrão VarBind)
                    if val_end < len(data):
                        vtag = data[val_end]
                        vln, vstart = read_len(val_end + 1)
                        vend = vstart + vln
                        if vend <= len(data):
                            return decode_val(vtag, data[vstart:vend])
                    return None  # OID encontrado mas valor ausente

                # Leaf TLV que não é OID — avança para o próximo
                pos = val_end
        except Exception:
            pass
        return None


# ── Interface table (switches) ────────────────────────────────────────────────

# OID bases para a interface MIB (RFC 2863 / IF-MIB)
_IF_DESCR_BASE    = "1.3.6.1.2.1.2.2.1.2"    # ifDescr
_IF_STATUS_BASE   = "1.3.6.1.2.1.2.2.1.8"    # ifOperStatus (1=up, 2=down)
_IF_HIGHSPEED_BASE= "1.3.6.1.2.1.31.1.1.1.15" # ifHighSpeed (Mbps, 32-bit)
_IF_ALIAS_BASE    = "1.3.6.1.2.1.31.1.1.1.18" # ifAlias (descrição configurada)
_IF_HC_IN_BASE    = "1.3.6.1.2.1.31.1.1.1.6"  # ifHCInOctets (64-bit)
_IF_HC_OUT_BASE   = "1.3.6.1.2.1.31.1.1.1.10" # ifHCOutOctets (64-bit)


def get_interfaces(ip: str, community: str = "public",
                   max_if: int = 64, timeout: float = 2.0) -> list:
    """
    Obtém todas as interfaces de um switch via SNMP.

    Devolve lista de dicts com:
        index, name, alias, oper_status (1=up/2=down),
        speed_mbps, in_octets, out_octets

    Faz GETs em paralelo para minimizar latência.
    max_if limita o número de interfaces (evita switches com 1000+ VLANs).
    """
    engine = SNMPEngine(community=community, timeout=timeout, retries=1)

    # Confirmar que o host tem SNMP e descobrir quantas interfaces tem
    raw_count = engine.get(ip, OIDS["ifNumber"])
    if raw_count is None:
        return []
    try:
        if_count = int(raw_count)
    except (TypeError, ValueError):
        return []

    if_count = min(if_count, max_if)
    if if_count <= 0:
        return []

    # Construir lista de (índice, campo, OID) para busca paralela
    fetch_list = []
    for idx in range(1, if_count + 1):
        fetch_list.extend([
            (idx, "name",    f"{_IF_DESCR_BASE}.{idx}"),
            (idx, "alias",   f"{_IF_ALIAS_BASE}.{idx}"),
            (idx, "status",  f"{_IF_STATUS_BASE}.{idx}"),
            (idx, "speed",   f"{_IF_HIGHSPEED_BASE}.{idx}"),
            (idx, "in",      f"{_IF_HC_IN_BASE}.{idx}"),
            (idx, "out",     f"{_IF_HC_OUT_BASE}.{idx}"),
        ])

    # Fetch em paralelo — 16 workers = ~10x mais rápido que sequencial em 48 portas
    raw: dict = {}

    def _fetch(item):
        idx, field, oid = item
        return idx, field, engine.get(ip, oid)

    with ThreadPoolExecutor(max_workers=16) as pool:
        for idx, field, val in pool.map(_fetch, fetch_list):
            if val is not None:
                raw.setdefault(idx, {})[field] = val

    # Construir resultado
    interfaces = []
    for idx in range(1, if_count + 1):
        data = raw.get(idx, {})
        name  = str(data.get("name",  f"if{idx}")).strip()
        alias = str(data.get("alias", "")).strip()
        try:   status = int(data.get("status", 2))
        except: status = 2
        try:   speed_mbps = int(data.get("speed", 0))
        except: speed_mbps = 0
        try:   in_octets  = int(data.get("in",  0))
        except: in_octets = 0
        try:   out_octets = int(data.get("out", 0))
        except: out_octets = 0

        interfaces.append({
            "index":       idx,
            "name":        name,
            "alias":       alias,
            "oper_status": status,
            "speed_mbps":  speed_mbps,
            "in_octets":   in_octets,
            "out_octets":  out_octets,
        })

    return interfaces


# ── Integração com discovery ──────────────────────────────────────────────────

def enrich_device_snmp(device: dict, community: str = "public") -> dict:
    """
    Enriquece um dispositivo com dados SNMP.
    Actualiza model, serial_number, firmware, toner, type, uptime.
    Retorna o device modificado.
    """
    ip = device.get("ip_address") or device.get("ip")
    if not ip:
        return device

    engine = SNMPEngine(community=community, timeout=2.0, retries=1)
    data   = engine.full_scan(ip)

    if not data.get("sys_descr"):
        return device  # sem resposta SNMP

    device["snmp_available"] = True

    # Modelo — SNMP devolve o modelo real do equipamento; prefere sempre ao model_db/OUI/AI.
    # WMI (que corre depois) irá sobrepor para PCs Windows se necessário.
    if data.get("model"):
        device["model"] = data["model"]

    # S/N — alta prioridade
    if data.get("serial_number"):
        device["serial_number"] = data["serial_number"]

    # Hostname SNMP — guarda sempre para contexto AI; sobrescreve só se não temos
    if data.get("sys_name"):
        device["_snmp_name"] = data["sys_name"]
        if not device.get("hostname"):
            device["hostname"] = data["sys_name"].upper()

    # Firmware / OS
    if data.get("firmware"):
        device["os_version"] = data["firmware"]
    elif data.get("sys_descr"):
        # Extrai versão do sysDescr para switches/APs
        fw_match = re.search(r"[Vv]ersion\s+([\d\.]+)", data["sys_descr"])
        if fw_match:
            device["os_version"] = fw_match.group(1)

    # Tipo — usa merge_classification com a confiança REAL do classify_from_snmp_descr.
    # Isto evita que um match fraco (ex: "linux" → Outro, 0.65) sobrescreva uma
    # classificação de porta de alta confiança (ex: porta 9100 → Impressora, 0.97).
    if data.get("device_type"):
        from core.device_classifier import merge_classification
        snmp_conf = float(data.get("device_type_conf") or 0.90)
        merge_classification(device, data["device_type"], snmp_conf, "snmp_engine")

    # Toner (impressoras)
    if data.get("toner"):
        device["_toner"]     = data["toner"]
        device["total_pages"]= data.get("total_pages")

    # Uptime
    if data.get("uptime"):
        device["_uptime"] = data["uptime"]

    # Interface count — ajuda a distinguir switch de AP
    if data.get("interface_count"):
        device["_interface_count"] = data["interface_count"]

    # sysDescr para finalize_device e IA — aumentado para 200 chars (era 100)
    device["_sys_descr"] = data.get("sys_descr", "")[:200]

    return device
