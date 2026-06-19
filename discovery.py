import socket
import struct
import select
import os
import subprocess
import platform
import threading
import ipaddress
import re
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ── Ping sem janelas ─────────────────────────────────────────────────────────
# Estratégia: subprocess com CREATE_NO_WINDOW é o mais fiável no Windows.
# Raw socket ICMP é mais rápido mas precisa de admin.
# Detectamos automaticamente qual funciona.

_PING_METHOD = None   # "icmp" | "subprocess" | "tcp"
_CREATE_NO_WINDOW = 0x08000000  # flag Windows para ocultar janela CMD

def _detect_ping_method():
    """Detecta uma vez qual método de ping funciona nesta máquina."""
    global _PING_METHOD
    if _PING_METHOD:
        return _PING_METHOD

    # 1. Tenta ICMP raw socket (precisa admin no Windows)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        s.settimeout(0.5)
        s.sendto(b"\x08\x00\xf7\xff\x00\x01\x00\x01test", ("127.0.0.1", 0))
        s.close()
        _PING_METHOD = "icmp"
        return _PING_METHOD
    except:
        pass

    # 2. Tenta subprocess ping com CREATE_NO_WINDOW (sem janelas)
    try:
        kw = {"creationflags": _CREATE_NO_WINDOW} if platform.system() == "Windows" else {}
        r = subprocess.run(
            ["ping", "-n", "1", "-w", "300", "127.0.0.1"] if platform.system() == "Windows"
            else ["ping", "-c", "1", "-W", "1", "127.0.0.1"],
            capture_output=True, timeout=3, **kw
        )
        if r.returncode == 0:
            _PING_METHOD = "subprocess"
            return _PING_METHOD
    except:
        pass

    # 3. Fallback TCP
    _PING_METHOD = "tcp"
    return _PING_METHOD


def _icmp_ping(host, timeout=1.0):
    """Ping sem abrir janelas. Usa o melhor método disponível."""
    method = _detect_ping_method()

    if method == "icmp":
        # Raw ICMP socket — rápido, sem processos
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.settimeout(timeout)
            # ICMP Echo Request packet
            icmp_id  = os.getpid() & 0xFFFF
            header   = struct.pack("!BBHHH", 8, 0, 0, icmp_id, 1)
            payload  = b"itinventory_ping"
            data     = header + payload
            # Checksum
            cs = 0
            for i in range(0, len(data), 2):
                w = (data[i] << 8) + (data[i+1] if i+1 < len(data) else 0)
                cs += w
            cs = (cs >> 16) + (cs & 0xFFFF)
            cs = ~cs & 0xFFFF
            packet = struct.pack("!BBHHH", 8, 0, cs, icmp_id, 1) + payload
            t0 = time.time()
            sock.sendto(packet, (host, 0))
            ready = select.select([sock], [], [], timeout)
            sock.close()
            if ready[0]:
                return True, int((time.time()-t0)*1000)
            return False, None
        except:
            pass

    elif method == "subprocess":
        # subprocess com CREATE_NO_WINDOW — sem janelas visíveis
        try:
            kw = {"creationflags": _CREATE_NO_WINDOW} if platform.system() == "Windows" else {}
            ms_flag = str(int(timeout * 1000))
            cmd = ["ping", "-n", "1", "-w", ms_flag, host] if platform.system() == "Windows" \
                   else ["ping", "-c", "1", "-W", str(int(timeout)), host]
            t0 = time.time()
            r  = subprocess.run(cmd, capture_output=True, timeout=timeout+1, **kw)
            ms = int((time.time()-t0)*1000)
            return r.returncode == 0, ms if r.returncode == 0 else None
        except:
            pass

    # TCP fallback — funciona mesmo sem admin e sem ping
    for port in (135, 445, 80, 443, 22, 8080, 3389, 8443):
        try:
            t0 = time.time()
            s  = socket.create_connection((host, port), timeout=min(timeout, 0.5))
            ms = int((time.time()-t0)*1000)
            s.close()
            return True, ms
        except:
            pass

    # DNS UDP — detecta dispositivos que não têm TCP aberto mas estão na rede
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.3)
        # DNS query minimal packet
        s.sendto(b"\x00\x01\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
                 b"\x07example\x03com\x00\x00\x01\x00\x01", (host, 53))
        s.recvfrom(512)
        s.close()
        return True, 1
    except OSError as e:
        # ECONNREFUSED significa que o host existe mas não tem DNS
        import errno
        if hasattr(e, 'errno') and e.errno in (
            getattr(errno, 'ECONNREFUSED', 111),
            getattr(errno, 'WSAECONNRESET', 10054) if platform.system()=="Windows" else 999
        ):
            return True, 1
    except:
        pass

    return False, None

from core.database import (upsert_asset, upsert_printer, create_alert,
                            get_setting, get_conn)
from core.snmp_engine import enrich_device_snmp
from core.oui_db import lookup as _oui_lookup
from core.device_classifier import is_valid_mac, merge_classification, classify_from_model


class DiscoveryEngine:
    def __init__(self, progress_callback=None, log_callback=None):
        self.progress_cb = progress_callback or (lambda pct, msg: None)
        self.log_cb      = log_callback      or (lambda msg, level="info": None)
        self._stop       = threading.Event()

    def stop(self):
        self._stop.set()

    def log(self, msg, level="info"):
        self.log_cb(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", level)

    # ── Full discovery cycle ──────────────────────────────────────────────────
    #
    # Pipeline simplificado:
    #   1. Ping sweep + ARP  — identifica hosts activos
    #   2. DNS reverse       — hostname para contexto da IA (grátis, paralelo)
    #   3. IA               — classifica todos os dispositivos (MAC + OUI + hostname + IP)
    #   4. SNMP             — só impressoras, switches, NAS, APs e dispositivos incertos
    #   5. WMI              — só PCs Windows classificados (Desktop/Laptop/Servidor)
    #   6. Finalização      — aceita Desktop/Laptop sem SNMP (≈ Windows Firewall)
    #   7. AD sync          — departamento + hostname
    #   8. Hostname fallback
    #   9. Save + alertas

    def run_full_discovery(self, subnet=None):
        self._stop.clear()
        subnet = subnet or get_setting("subnet", "192.168.163.0/24")
        self._snmp_community = get_setting("snmp_community", "public")

        self.log(f"Iniciando discovery em {subnet}...")
        self.progress_cb(2, "A preparar scan...")

        # 1. Ping sweep + ARP
        self.progress_cb(5, "Ping sweep + ARP — a descobrir hosts activos...")
        alive = self._ping_sweep(subnet)
        self.log(f"Ping sweep concluído: {len(alive)} hosts activos", "ok")

        # 2. DNS reverse — paralelo, grátis, melhora contexto para IA
        self.progress_cb(22, f"DNS reverse para {len(alive)} hosts...")
        self._resolve_dns_batch(alive)

        # 3. IA classifica todos os dispositivos
        self.progress_cb(30, f"IA a classificar {len(alive)} dispositivos...")
        results = self._build_and_classify(alive, subnet)

        # 4. SNMP — impressoras, switches, NAS, APs, incertos, E Desktop/Servidor com conf < 0.82
        #    O limiar 0.82 garante que servidores Windows com hostname genérico (que a IA
        #    classifica como "Desktop" com ~0.55–0.75) recebem SNMP. O sysDescr
        #    "Windows Server 2019" / "Linux Ubuntu Server" corrige a classificação.
        snmp_targets = [r for r in results if
                        r.get("type") in ("Impressora", "Switch", "NAS", "Access Point",
                                          "Firewall", "Câmara CCTV", "Desconhecido", "Outro")
                        or float(r.get("confidence", 0)) < 0.82]
        self.log(f"SNMP em {len(snmp_targets)} dispositivos...", "info")
        self.progress_cb(55, f"SNMP em {len(snmp_targets)} dispositivos...")
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(self._run_snmp, d): d for d in snmp_targets}
            done = 0
            for f in as_completed(futures):
                if self._stop.is_set():
                    break
                try:
                    f.result()
                except Exception as e:
                    self.log(f"SNMP erro: {e}", "warn")
                done += 1
                pct = 55 + int(done / max(len(snmp_targets), 1) * 20)
                self.progress_cb(pct, f"SNMP {done}/{len(snmp_targets)}...")

        # 5. WMI — só PCs Windows (Desktop/Laptop/Servidor)
        wmi_targets = [r for r in results if r.get("type") in ("Desktop", "Laptop", "Servidor")]
        if wmi_targets:
            self.log(f"WMI em {len(wmi_targets)} PCs Windows...", "info")
            self.progress_cb(76, f"WMI em {len(wmi_targets)} PCs Windows...")
            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = {pool.submit(self._run_wmi, d): d for d in wmi_targets}
                for f in as_completed(futures):
                    if self._stop.is_set():
                        break
                    try:
                        f.result()
                    except Exception as e:
                        self.log(f"WMI erro: {e}", "warn")

        # 6. Finalização pós-pipeline — resolve incertezas após SNMP + WMI
        #    Princípio: dispositivos de rede (switch, impressora, AP, NAS) respondem SEMPRE
        #    a SNMP. Um Desktop/Laptop que não respondeu a SNMP é quase certamente um PC
        #    com Windows Firewall a bloquear UDP 161. Aceitar essa classificação.
        self.progress_cb(80, "A finalizar classificações...")
        self._finalize_post_pipeline(results)

        # 7. Hostname fallback para dispositivos sem hostname
        for device in results:
            if not device.get("hostname"):
                prefix = {
                    "Switch": "SW", "Servidor": "SRV", "Impressora": "PRN",
                    "Access Point": "AP", "NAS": "NAS", "Laptop": "LAP",
                    "Desktop": "PC", "Firewall": "FW", "Câmara CCTV": "CAM",
                }.get(device.get("type", ""), "DEV")
                ip = device.get("ip_address", "0.0.0.0")
                device["hostname"] = f"{prefix}-{ip.split('.')[-1].zfill(3)}"

        # 8. AD sync
        if get_setting("ad_sync_enabled", "1") == "1":
            self.progress_cb(85, "A sincronizar Active Directory...")
            try:
                from core.ad_sync import sync_ad_to_inventory
                stats = sync_ad_to_inventory()
                self.log(
                    f"AD: {stats.get('matched', 0)} correspondências, "
                    f"{stats.get('updated', 0)} actualizados", "ok")
            except Exception as e:
                self.log(f"AD sync: {e}", "warn")

        # 9. Save + alertas
        self.progress_cb(90, "A guardar no inventário...")
        new_count = 0
        for device in results:
            if self._stop.is_set():
                break
            is_new = self._save_device(device)
            if is_new:
                new_count += 1

        self._check_and_generate_alerts()

        self.progress_cb(100, f"Concluído — {len(results)} dispositivos, {new_count} novos")
        self.log(f"Discovery completo: {len(results)} dispositivos, {new_count} novos", "ok")
        return results

    # ── Ping sweep ────────────────────────────────────────────────────────────

    def _ping_sweep(self, subnet):
        network = ipaddress.IPv4Network(subnet, strict=False)
        hosts   = list(network.hosts())
        alive   = []
        seen    = set()

        # 1. Pré-popular com tabela ARP local (já sabemos quem está online)
        arp_hosts = self._get_arp_table()
        for ip, mac in arp_hosts.items():
            try:
                if ipaddress.IPv4Address(ip) in network:
                    if ip not in seen:
                        alive.append({"ip": ip, "mac": mac, "rtt_ms": 0})
                        seen.add(ip)
                        self.log(f"ARP: {ip} ({mac})", "ok")
            except Exception:
                pass

        self.log(f"ARP table: {len(alive)} hosts pré-encontrados, a fazer ping ao resto...", "info")

        # 2. Ping sweep — usa ARP já lida em cache; sem subprocess por IP
        def ping_one(ip):
            ip_str = str(ip)
            if ip_str in seen:
                return None
            online, ms = _icmp_ping(ip_str, timeout=1.5)
            if online:
                mac = arp_hosts.get(ip_str)
                return {"ip": ip_str, "mac": mac, "rtt_ms": ms}
            return None

        with ThreadPoolExecutor(max_workers=100) as pool:
            futures = [pool.submit(ping_one, ip) for ip in hosts]
            for f in as_completed(futures):
                if self._stop.is_set():
                    break
                r = f.result()
                if r and r["ip"] not in seen:
                    if r.get("mac") and not is_valid_mac(r["mac"]):
                        continue
                    alive.append(r)
                    seen.add(r["ip"])
                    self.log(f"Ping: {r['ip']} activo", "ok")

        # 3. Re-lê ARP uma única vez para hosts sem MAC
        no_mac = [h for h in alive if not h.get("mac")]
        if no_mac:
            arp2  = self._get_arp_table()
            found = 0
            for h in no_mac:
                mac = arp2.get(h["ip"])
                if mac and is_valid_mac(mac):
                    h["mac"] = mac
                    found += 1
            if found:
                self.log(f"ARP re-leitura: {found} MACs adicionais resolvidos", "info")

        return alive

    def _get_arp_table(self):
        """Lê toda a tabela ARP do sistema — muito mais rápido que pingar tudo."""
        result = {}
        try:
            kw = {"creationflags": _CREATE_NO_WINDOW} if platform.system() == "Windows" else {}
            out = subprocess.check_output(
                ["arp", "-a"], capture_output=False,
                stderr=subprocess.DEVNULL, timeout=5, **kw
            ).decode(errors="replace")
            for line in out.split("\n"):
                # Windows: "  192.168.1.1          aa-bb-cc-dd-ee-ff     dynamic"
                # Linux:   "192.168.1.1 ether aa:bb:cc:dd:ee:ff"
                ip_m  = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                mac_m = re.search(r"([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}", line)
                if ip_m and mac_m:
                    ip  = ip_m.group(1)
                    mac = mac_m.group(0).lower().replace("-", ":")
                    if not ip.endswith(".255") and ip != "255.255.255.255":
                        result[ip] = mac
        except Exception as e:
            self.log(f"ARP table error: {e}", "warn")
        return result

    # ── DNS reverse ───────────────────────────────────────────────────────────

    def _resolve_dns_batch(self, alive):
        """
        DNS reverse lookup paralelo para todos os hosts.
        Adiciona _dns_name a cada dict da lista alive.
        Grátis, rápido (~0.5s para /24) e melhora muito o contexto para a IA.
        """
        def resolve(h):
            try:
                name = socket.gethostbyaddr(h["ip"])[0].split(".")[0].upper()
                h["_dns_name"] = name
            except OSError:
                h["_dns_name"] = None

        with ThreadPoolExecutor(max_workers=50) as pool:
            list(pool.map(resolve, alive))

        resolved = sum(1 for h in alive if h.get("_dns_name"))
        self.log(f"DNS: {resolved}/{len(alive)} hostnames resolvidos", "info")

    # ── IA classifica todos os dispositivos ──────────────────────────────────

    def _build_and_classify(self, alive, subnet):
        """
        Cria dicts de dispositivo e classifica todos via IA numa única passagem.

        Contexto enviado à IA por dispositivo:
          • mac        — OUI identifica fabricante/tipo exclusivos (Brother → Impressora)
          • oui_vendor — nome do fabricante do chip de rede (contexto adicional)
          • hostname   — padrão DNS é o sinal mais fiável (SW-PISO2, PRN-COPIA, etc.)
          • ip         — padrão de endereço dentro da subnet (sinal fraco)

        Dispositivos sem IA configurada ficam com tipo "Desconhecido" e needs_review=1.
        SNMP irá depois classificar impressoras/switches correctamente.
        """
        from core.ai_engine import classify_devices

        results       = []
        device_map_ip  = {}   # ip  → device dict
        device_map_mac = {}   # mac → device dict
        devices_info   = []   # input para IA

        for h in alive:
            mac    = h.get("mac") if is_valid_mac(h.get("mac")) else None
            vendor, _ = _oui_lookup(mac) if mac else (None, None)
            hostname = h.get("_dns_name")

            device = {
                "ip_address":  h["ip"],
                "mac_address": mac,
                "hostname":    hostname,
                "status":      "Online",
                "last_seen":   datetime.utcnow().isoformat(),
                "type":        "Desconhecido",
                "confidence":  0.0,
                "needs_review": 1,
            }
            if vendor:
                device["manufacturer"] = vendor

            results.append(device)
            device_map_ip[h["ip"]] = device
            if mac:
                device_map_mac[mac.lower()] = device

            devices_info.append({
                "mac":        mac or "",
                "ip":         h["ip"],
                "oui_vendor": vendor or "desconhecido",
                "hostname":   hostname or "",
            })

        # IA classifica em lote
        if get_setting("discovery_use_ai", "1") == "1":
            context = f"Rede industrial portuguesa, subnet {subnet}"
            try:
                ai_results = classify_devices(devices_info, context)
                classified = 0

                for ai in (ai_results or []):
                    ip  = (ai.get("ip")  or "").strip()
                    mac = (ai.get("mac") or "").lower().strip()

                    # Match por IP primeiro (mais fiável); fallback por MAC
                    device = device_map_ip.get(ip) or device_map_mac.get(mac)
                    if not device:
                        continue

                    ai_type = ai.get("type") or "Desconhecido"
                    ai_conf = float(ai.get("confidence") or 0.5)
                    ai_mfr  = (ai.get("manufacturer") or "").strip()
                    ai_hn   = (ai.get("hostname") or "").upper().strip()

                    device["type"]          = ai_type
                    device["confidence"]    = round(ai_conf, 2)
                    device["needs_review"]  = 0 if ai_conf >= 0.72 else 1
                    device["_class_source"] = "ai"

                    # Fabricante: IA sobrepõe só NICs genéricos; preserva OUI específico
                    if ai_mfr and ai_mfr.lower() not in ("null", "none", "desconhecido", ""):
                        cur_mfr = (device.get("manufacturer") or "").lower()
                        generic = any(g in cur_mfr for g in
                                      ("intel", "realtek", "broadcom", "atheros", "qualcomm"))
                        if not device.get("manufacturer") or generic:
                            device["manufacturer"] = ai_mfr

                    # Hostname sugerido pela IA só se não existe já (DNS tem prioridade)
                    if ai_hn and not device.get("hostname"):
                        device["hostname"] = ai_hn[:32]

                    classified += 1

                self.log(f"IA classificou {classified}/{len(alive)} dispositivos", "ok")
            except Exception as e:
                self.log(f"IA classificação falhou: {e}", "warn")
        else:
            self.log("IA desactivada — dispositivos ficam como 'Desconhecido' até SNMP/WMI", "warn")

        # Log resumo por dispositivo
        for device in results:
            self.log(
                f"{device['ip_address']:16s} → "
                f"{(device.get('hostname') or '?'):20s} "
                f"[{device.get('type', '?')}]  "
                f"conf={float(device['confidence']):.0%}",
                "ok" if float(device["confidence"]) >= 0.75 else "warn",
            )

        return results

    # ── SNMP — impressoras, switches e incertos ───────────────────────────────

    def _run_snmp(self, device):
        """
        SNMP enrich selectivo.

        Corre em:
          • Impressoras — toner%, páginas, modelo real
          • Switches    — interfaces, modelo, firmware
          • NAS / AP / Firewall / Câmara — modelo, confirmação de tipo
          • Desconhecido / Outro / conf < 0.70 — tenta confirmar ou desambiguar

        Usa merge_classification (via enrich_device_snmp) para não sobrepor
        classificações de IA correctas com alta confiança.
        Tenta as communities configurada + "public" + "private".
        """
        ip = device.get("ip_address", "")
        communities = [self._snmp_community]
        for c in ("public", "private"):
            if c not in communities:
                communities.append(c)

        for comm in communities:
            enrich_device_snmp(device, community=comm)
            if device.get("snmp_available"):
                self.log(
                    f"SNMP {ip}: {device.get('model', '?')} "
                    f"[{device.get('type', '?')}]  "
                    f"conf={float(device.get('confidence', 0)):.0%}",
                    "ok"
                )
                break

    # ── WMI — PCs Windows classificados pela IA ───────────────────────────────

    def _run_wmi(self, device):
        """
        WMI recolhe specs de hardware de PCs Windows.

        Só corre em dispositivos que a IA classificou como Desktop/Laptop/Servidor.
        Confirma/refina o tipo (Desktop vs Laptop via modelo) e preenche:
          modelo, S/N, RAM, disco, CPU, utilizador activo, OS.
        """
        ip = device.get("ip_address", "")
        wmi_data = self._try_wmi(ip)
        if not wmi_data:
            return

        device["model"]         = wmi_data.get("model")        or device.get("model")
        device["manufacturer"]  = wmi_data.get("manufacturer") or device.get("manufacturer")
        device["serial_number"] = wmi_data.get("serial_number")
        device["os_version"]    = wmi_data.get("os_version")
        device["assigned_user"] = wmi_data.get("assigned_user")
        if wmi_data.get("hostname"):
            device["hostname"] = wmi_data["hostname"].upper()

        specs = []
        if wmi_data.get("cpu"):
            specs.append(wmi_data["cpu"][:40])
        if wmi_data.get("total_ram_gb"):
            specs.append(f"{wmi_data['total_ram_gb']}GB RAM")
        if wmi_data.get("total_disk_gb"):
            specs.append(f"{wmi_data['total_disk_gb']}GB Disco")
        if specs:
            device["notes"] = " | ".join(specs)

        # WMI confirma/refina tipo: Desktop vs Laptop vs Servidor
        wmi_type = "Servidor" if "server" in (wmi_data.get("os_version") or "").lower() else "Desktop"
        merged_model = wmi_data.get("model") or device.get("model") or ""
        model_hit = classify_from_model(merged_model)
        if model_hit and model_hit[0] == "Laptop":
            wmi_type = "Laptop"
        merge_classification(device, wmi_type, 0.99, "wmi")

        self.log(f"WMI {ip}: {device.get('model', '?')} [{wmi_type}]  "
                 f"SN:{device.get('serial_number', '?')}", "ok")

    # ── Finalização pós-pipeline ──────────────────────────────────────────────

    def _finalize_post_pipeline(self, results):
        """
        Pós-processamento após SNMP + WMI — resolve incertezas remanescentes.

        Axioma central: dispositivos de rede (switch, impressora, AP, NAS, firewall)
        respondem SEMPRE a SNMP community "public" — é garantia básica de funcionamento.

        Corolários:
          • Desktop/Laptop sem SNMP = PC com Windows Firewall → aceitar (conf 0.76)
          • Desconhecido/Outro sem SNMP + MAC = provavelmente PC/IoT → Desktop (conf 0.65)
          • Desconhecido sem SNMP + sem MAC = dispositivo com firewall total → aceitar (conf 0.60)
          • Servidor sem SNMP + hostname SRV/DC → aceitar (conf 0.78)

        Aplicado também:
          • Hostname pós-WMI ("DESKTOP-A1B2C3D", "SRV-PRODUCAO") → classify_from_hostname
          • Modelo pós-SNMP/WMI ("Dell OptiPlex 7090") → classify_from_model
        """
        from core.device_classifier import (
            classify_from_hostname, classify_from_model, merge_classification,
        )

        accepted_pc       = 0
        accepted_srv      = 0
        accepted_unknown  = 0
        model_reclassed   = 0
        hn_reclassed      = 0

        for device in results:
            conf     = float(device.get("confidence") or 0)
            dtype    = device.get("type") or "Desconhecido"
            src      = device.get("_class_source", "")
            has_snmp = bool(device.get("snmp_available"))
            hn       = (device.get("hostname") or "").strip()

            # Não tocar em dispositivos já resolvidos com alta certeza
            if src in ("wmi", "snmp_engine") and conf >= 0.90:
                continue

            # ── 1. Hostname pós-WMI ──────────────────────────────────────────
            # WMI preenche o hostname real (ex: "DESKTOP-A1B2C3D", "SRV-PRODUCAO").
            # classify_from_hostname reconhece estes padrões com confiança ≥ 0.82.
            if hn:
                hn_hit = classify_from_hostname(hn)
                if hn_hit:
                    before = dtype
                    merge_classification(device, hn_hit[0], hn_hit[1], "hostname")
                    if device.get("type") != before:
                        hn_reclassed += 1
                    conf  = float(device.get("confidence") or 0)
                    dtype = device.get("type") or dtype
                    src   = device.get("_class_source", "")

            # ── 2. Modelo pós-SNMP/WMI ──────────────────────────────────────
            # SNMP/WMI preenche modelo; classify_from_model pode reclassificar.
            model = (device.get("model") or "").strip()
            if model:
                model_hit = classify_from_model(model)
                if model_hit:
                    before = dtype
                    merge_classification(device, model_hit[0], model_hit[1], "model")
                    if device.get("type") != before:
                        model_reclassed += 1
                    conf  = float(device.get("confidence") or 0)
                    dtype = device.get("type") or dtype
                    src   = device.get("_class_source", "")

            # Após os re-checks, se já ficou needs_review=0, seguir em frente
            if not device.get("needs_review", 1):
                continue

            # ── 3. Desktop/Laptop sem SNMP → inferir PC ─────────────────────
            if (dtype in ("Desktop", "Laptop")
                    and not has_snmp
                    and conf < 0.80):
                device["confidence"]    = max(conf, 0.76)
                device["needs_review"]  = 0
                device["_class_source"] = (src + "+inferred") if src else "inferred"
                accepted_pc += 1

            # ── 4. Servidor sem SNMP + hostname padrão SRV/DC ───────────────
            elif (dtype == "Servidor"
                    and not has_snmp
                    and conf < 0.80):
                if hn and re.search(r"^(?:SRV|SERVER|DC|SERV|AD|VCENTER|ESX|HV)[\-_]", hn, re.I):
                    device["confidence"]    = max(conf, 0.78)
                    device["needs_review"]  = 0
                    device["_class_source"] = (src + "+hostname") if src else "hostname"
                    accepted_srv += 1

            # ── 5. Desconhecido/Outro sem SNMP → inferir PC ou IoT ──────────
            # Dispositivos de rede respondem SEMPRE a SNMP.
            # "Desconhecido" sem SNMP = provavelmente PC/IoT/telefone.
            # Com MAC → melhor contexto; sem MAC → muito incerto mas ainda útil inferir.
            elif (dtype in ("Desconhecido", "Outro")
                    and not has_snmp):
                has_mac = bool(device.get("mac_address"))
                if has_mac:
                    # Com MAC + sem SNMP → PC ou IoT; Desktop é melhor hipótese em empresa
                    device["type"]          = "Desktop"
                    device["confidence"]    = 0.65
                    device["needs_review"]  = 0
                    device["_class_source"] = "inferred_no_snmp"
                else:
                    # Sem MAC → muito incerto; mantém tipo mas aceita (nada mais a fazer)
                    device["type"]          = "Desconhecido"
                    device["confidence"]    = max(conf, 0.55)
                    device["needs_review"]  = 0
                    device["_class_source"] = "inferred_no_mac"
                accepted_unknown += 1

        msgs = []
        if accepted_pc:
            msgs.append(f"{accepted_pc} PCs (sem SNMP)")
        if accepted_srv:
            msgs.append(f"{accepted_srv} servidores (hostname confirma)")
        if accepted_unknown:
            msgs.append(f"{accepted_unknown} desconhecidos inferidos")
        if hn_reclassed:
            msgs.append(f"{hn_reclassed} reclassificados por hostname")
        if model_reclassed:
            msgs.append(f"{model_reclassed} reclassificados por modelo")
        if msgs:
            self.log(f"Finalização: {', '.join(msgs)}", "info")

    # ── WMI Query (Windows PCs / Servers) ────────────────────────────────────

    def _try_wmi(self, ip: str) -> dict | None:
        """
        Recolhe modelo, S/N, RAM, disco, OS e utilizador via WMI.
        Requer: pip install wmi pywin32
        Requer: firewall WMI aberto nos PCs + permissões AD
        Domínio: sml.com
        """
        try:
            import wmi
            ad_user = get_setting("ad_user", "")
            ad_pass = get_setting("ad_password", "")

            # Ligação WMI remota com credenciais AD
            c = wmi.WMI(
                computer=ip,
                user=ad_user,
                password=ad_pass,
                namespace="root/cimv2"
            )

            result = {}

            # Modelo e fabricante (Win32_ComputerSystem)
            for cs in c.Win32_ComputerSystem():
                result["manufacturer"] = cs.Manufacturer
                result["model"]        = cs.Model
                result["total_ram_gb"] = round(int(cs.TotalPhysicalMemory or 0) / 1e9, 1)
                result["hostname"]     = cs.Name
                result["domain"]       = cs.Domain

            # Número de série (Win32_BIOS)
            for bios in c.Win32_BIOS():
                sn = bios.SerialNumber
                if sn and sn.lower() not in ("to be filled by o.e.m.", "default string", ""):
                    result["serial_number"] = sn

            # Sistema operativo
            for os_info in c.Win32_OperatingSystem():
                result["os_version"]  = os_info.Caption
                result["os_build"]    = os_info.BuildNumber
                result["last_boot"]   = os_info.LastBootUpTime

            # CPU
            for cpu in c.Win32_Processor():
                result["cpu"] = cpu.Name.strip()
                break

            # Disco principal
            total_disk = 0
            for disk in c.Win32_LogicalDisk(DriveType=3):  # Fixed drives
                total_disk += int(disk.Size or 0)
            if total_disk:
                result["total_disk_gb"] = round(total_disk / 1e9)

            # Utilizador com sessão activa
            users = []
            for session in c.Win32_LoggedOnUser():
                try:
                    account = session.Antecedent
                    name_match = re.search(r'Name="([^"]+)"', str(account))
                    if name_match and name_match.group(1) not in ("SYSTEM","LOCAL SERVICE","NETWORK SERVICE"):
                        users.append(name_match.group(1))
                except:
                    pass
            if users:
                result["assigned_user"] = users[0]

            self.log(f"WMI {ip}: {result.get('model','?')} SN:{result.get('serial_number','?')}", "ok")
            return result

        except ImportError as e:
            # Mostra o erro real — pode ser pywin32 não registado mesmo estando instalado
            if not getattr(DiscoveryEngine, '_wmi_import_warned', False):
                DiscoveryEngine._wmi_import_warned = True
                try:
                    import win32api  # verifica se pywin32 base está ok
                    self.log(
                        f"WMI: módulo 'wmi' não encontrado ({e}). "
                        f"Reinstala: pip install wmi", "warn")
                except ImportError:
                    self.log(
                        f"WMI: pywin32 não registado ({e}). "
                        f"Corre no terminal como administrador: "
                        f"python Scripts/pywin32_postinstall.py -install", "warn")
            return None
        except Exception as e:
            err = str(e)
            if "0x80070005" in err:
                self.log(f"WMI {ip}: sem permissão (verifica GPO)", "warn")
            elif "0x800706ba" in err or "RPC" in err:
                pass  # PC offline ou sem WMI — silencioso
            else:
                self.log(f"WMI {ip}: {err[:60]}", "warn")
            return None

    # ── Save to DB ────────────────────────────────────────────────────────────

    def _save_device(self, device):
        # Não guardar dispositivos marcados para ignorar
        if device.get("type") == "Ignorar":
            return False

        # Extrair dados de impressora ANTES de limpar chaves internas (_)
        toner       = device.pop("_toner", None)
        total_pages = device.pop("total_pages", None)

        # Remover chaves internas (começam por _) — não vão para a BD
        for k in list(device.keys()):
            if k.startswith("_"):
                device.pop(k, None)

        fields = {k: v for k, v in device.items()
                  if k in ("hostname","type","status","ip_address","mac_address",
                            "manufacturer","model","serial_number","department",
                            "assigned_user","os_version","acquisition_year",
                            "confidence","needs_review","last_seen","notes")}

        # Verifica se o dispositivo já existe antes do upsert
        with get_conn() as c:
            existing = None
            if fields.get("mac_address"):
                existing = c.execute(
                    "SELECT 1 FROM assets WHERE mac_address=?",
                    (fields["mac_address"],)).fetchone()
            if not existing and fields.get("ip_address"):
                existing = c.execute(
                    "SELECT 1 FROM assets WHERE ip_address=?",
                    (fields["ip_address"],)).fetchone()
        is_new = existing is None

        asset_id = upsert_asset(fields)

        # Dados SNMP de impressora — criar/actualizar registo na tabela printers
        if device.get("type") == "Impressora":
            upsert_printer(asset_id, {
                "toner_black":   toner.get("black",   -1) if toner else -1,
                "toner_cyan":    toner.get("cyan",    -1) if toner else -1,
                "toner_magenta": toner.get("magenta", -1) if toner else -1,
                "toner_yellow":  toner.get("yellow",  -1) if toner else -1,
                "total_pages":   total_pages or 0,
            })

        return is_new

    # ── Alert generation ──────────────────────────────────────────────────────

    def _check_and_generate_alerts(self):
        from core.database import get_critical_printers, get_low_stock_consumables

        thr = int(get_setting("toner_alert_pct", "15"))
        for printer in get_critical_printers():
            for color, val in [("Preto", printer["toner_black"]),
                                ("Ciano", printer["toner_cyan"]),
                                ("Magenta", printer["toner_magenta"]),
                                ("Amarelo", printer["toner_yellow"])]:
                if 0 <= val <= thr:
                    create_alert("Critical", "Toner",
                        f"Toner {color} {val}% — {printer['hostname']}",
                        f"Impressora {printer['ip_address']} com toner crítico",
                        printer["asset_id"])

        for item in get_low_stock_consumables():
            create_alert("Warning", "Stock",
                f"Stock baixo: {item['reference']} ({item['stock_qty']} un.)",
                f"Stock mínimo: {item['stock_min']} un.",
                None)

        with get_conn() as c:
            year_threshold = datetime.now().year - 4
            old_pcs = c.execute(
                "SELECT id, hostname FROM assets WHERE type IN ('Desktop','Laptop') AND acquisition_year<=? AND acquisition_year IS NOT NULL",
                (year_threshold,)).fetchall()
            for pc in old_pcs:
                create_alert("Warning", "Hardware",
                    f"PC no 4.º ano: {pc['hostname']}",
                    "Planeamento de substituição recomendado", pc["id"])

# ── Continuous ping monitor ───────────────────────────────────────────────────

class PingMonitor:
    def __init__(self, status_callback=None):
        self.status_cb = status_callback or (lambda: None)
        self._thread   = None
        self._stop     = threading.Event()

    def start(self):
        if get_setting("background_monitors", "1") != "1":
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="PingMonitor")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        from core.database import get_ping_targets, record_pings_batch
        while not self._stop.is_set():
            interval = max(60, int(get_setting("ping_interval_s", "300")))
            max_workers = max(2, min(16, int(get_setting("ping_max_workers", "8"))))
            targets = get_ping_targets()
            ips = [(a["id"], a["ip_address"]) for a in targets]
            batch = []

            if ips:
                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    futures = {pool.submit(self._ping, ip): (aid, ip) for aid, ip in ips}
                    for future in as_completed(futures):
                        aid, _ip = futures[future]
                        online, ms = future.result()
                        batch.append((aid, online, ms))
                record_pings_batch(batch)
                try:
                    self.status_cb()
                except TypeError:
                    pass

            self._stop.wait(interval)

    def _ping(self, ip):
        return _icmp_ping(ip, timeout=1.0)
