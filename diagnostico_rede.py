"""
diagnostico_rede.py
Corre este script para perceber porque o discovery nao encontra dispositivos.
Uso: venv\Scripts\python diagnostico_rede.py
"""

import socket
import struct
import os
import time
import subprocess
import platform
import ipaddress
import sys

print("=" * 60)
print("  IT Inventory — Diagnóstico de Rede")
print("=" * 60)
print()

# ── 1. Info basica ────────────────────────────────────────────────────────────
print("[1] Sistema operativo:", platform.system(), platform.release())
print("[1] Python:", sys.version.split()[0])
print()

# ── 2. IP local ───────────────────────────────────────────────────────────────
print("[2] IPs locais desta máquina:")
try:
    hostname = socket.gethostname()
    ips = socket.getaddrinfo(hostname, None)
    seen = set()
    for item in ips:
        ip = item[4][0]
        if ip not in seen and not ip.startswith("127") and ":" not in ip:
            print(f"    {ip}  (hostname: {hostname})")
            seen.add(ip)
except Exception as e:
    print(f"    Erro: {e}")
print()

# ── 3. Testar ICMP raw socket ─────────────────────────────────────────────────
print("[3] Testar ICMP raw socket:")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    s.settimeout(1)
    # Build minimal ICMP echo
    import struct as st
    header = st.pack("bbHHh", 8, 0, 0, 1, 1)
    payload = b"test"
    cs = 0
    data = header + payload
    for i in range(0, len(data), 2):
        w = data[i] + (data[i+1] if i+1 < len(data) else 0) * 256
        cs += w
    cs = (cs >> 16) + (cs & 0xFFFF)
    cs = ~cs & 0xFFFF
    header = st.pack("bbHHh", 8, 0, cs, 1, 1)
    s.sendto(header + payload, ("127.0.0.1", 0))
    s.close()
    print("    OK - raw socket ICMP disponível (admin OK)")
    ICMP_OK = True
except PermissionError:
    print("    SEM PERMISSÃO - precisa de 'Executar como Administrador'")
    ICMP_OK = False
except Exception as e:
    print(f"    Erro: {e}")
    ICMP_OK = False
print()

# ── 4. Testar subprocess ping ─────────────────────────────────────────────────
print("[4] Testar ping via subprocess (127.0.0.1):")
try:
    CREATE_NO_WINDOW = 0x08000000
    result = subprocess.run(
        ["ping", "-n", "1", "-w", "1000", "127.0.0.1"],
        capture_output=True, timeout=5,
        creationflags=CREATE_NO_WINDOW if platform.system() == "Windows" else 0
    )
    if result.returncode == 0:
        print("    OK - subprocess ping funciona")
        SUBPROCESS_OK = True
    else:
        print("    FALHOU - returncode:", result.returncode)
        SUBPROCESS_OK = False
except Exception as e:
    print(f"    Erro: {e}")
    SUBPROCESS_OK = False
print()

# ── 5. Testar TCP connect ─────────────────────────────────────────────────────
print("[5] Testar TCP connect ao gateway:")
try:
    # Descobrir gateway
    if platform.system() == "Windows":
        out = subprocess.check_output(
            ["ipconfig"], capture_output=False,
            creationflags=0x08000000
        ).decode(errors="replace")
        gw = None
        for line in out.split("\n"):
            if "Gateway" in line and "." in line:
                parts = line.strip().split(":")
                if len(parts) > 1:
                    ip = parts[-1].strip()
                    if ip and ip[0].isdigit():
                        gw = ip
                        break
    else:
        gw = "192.168.1.1"

    if gw:
        print(f"    Gateway detectado: {gw}")
        for port in (80, 443, 22, 445, 135):
            try:
                t0 = time.time()
                s = socket.create_connection((gw, port), timeout=1)
                ms = int((time.time()-t0)*1000)
                s.close()
                print(f"    OK - TCP:{port} responde em {ms}ms")
                break
            except:
                print(f"    TCP:{port} sem resposta")
    else:
        print("    Não consegui detectar gateway")
except Exception as e:
    print(f"    Erro: {e}")
print()

# ── 6. Testar ARP ─────────────────────────────────────────────────────────────
print("[6] Testar ARP table:")
try:
    out = subprocess.check_output(
        ["arp", "-a"], capture_output=False,
        creationflags=0x08000000 if platform.system()=="Windows" else 0
    ).decode(errors="replace")
    lines = [l for l in out.split("\n") if "dynamic" in l.lower() or
             (":" in l and not l.strip().startswith("Interface"))]
    print(f"    {len(lines)} entradas ARP encontradas")
    for l in lines[:5]:
        print(f"    {l.strip()}")
    if len(lines) > 5:
        print(f"    ... e mais {len(lines)-5}")
except Exception as e:
    print(f"    Erro: {e}")
print()

# ── 7. Scan de 5 IPs de teste ─────────────────────────────────────────────────
print("[7] Teste rápido de ping a 5 IPs da rede (192.168.163.1-5):")
for i in range(1, 6):
    ip = f"192.168.163.{i}"
    # Tenta ICMP se disponível, senão subprocess
    found = False
    if ICMP_OK:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            s.settimeout(0.5)
            header = st.pack("bbHHh", 8, 0, cs, 1, 1)
            s.sendto(header + payload, (ip, 0))
            s.recvfrom(1024)
            s.close()
            found = True
        except:
            pass
    elif SUBPROCESS_OK:
        try:
            r = subprocess.run(
                ["ping", "-n", "1", "-w", "500", ip],
                capture_output=True, timeout=3,
                creationflags=0x08000000
            )
            found = r.returncode == 0
        except:
            pass
    else:
        for port in (80, 443, 445):
            try:
                s = socket.create_connection((ip, port), timeout=0.5)
                s.close()
                found = True
                break
            except:
                pass

    status = "ONLINE" if found else "offline"
    print(f"    {ip}: {status}")
print()

# ── 8. Recomendação ───────────────────────────────────────────────────────────
print("=" * 60)
print("  RECOMENDAÇÃO:")
if ICMP_OK:
    print("  Raw ICMP OK — discovery deve funcionar normalmente.")
elif SUBPROCESS_OK:
    print("  Subprocess ping OK — vamos usar esse método.")
    print("  SOLUÇÃO: ver abaixo para activar modo subprocess (sem janelas)")
else:
    print("  Nenhum método de ping funciona!")
    print("  Verifica se a firewall do Windows bloqueia ICMP.")
    print("  Tenta: executar a app como Administrador")
print("=" * 60)
print()
print("Guarda este output e envia para diagnóstico.")
input("\nPrime ENTER para fechar...")
