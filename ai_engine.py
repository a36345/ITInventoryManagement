"""
ai_engine.py — Motor de IA: Anthropic API (1.º) com fallback para Ollama local.

Prioridade:
  1. Anthropic (claude-haiku para classificação, claude-sonnet para faturas)
     → activo sempre que anthropic_key esteja configurada
  2. Ollama local (llama3.2 / mistral / phi3)
     → fallback se Anthropic não configurado ou falhar

Sem API keys → corre 100% offline com Ollama.
"""

import base64
import json
import logging
import re
import urllib.request
import urllib.error
from pathlib import Path
from core.database import get_setting

log = logging.getLogger("ITInventory.ai")

# Modelos Anthropic por tarefa
_ANTHROPIC_CLASSIFY_MODEL = "claude-haiku-4-5-20251001"   # rápido, barato — classificação
_ANTHROPIC_INVOICE_MODEL  = "claude-sonnet-4-6"           # mais capaz — faturas/OCR


# ── Backend selector ──────────────────────────────────────────────────────────

def _anthropic_key() -> str:
    """Devolve a chave Anthropic se válida, caso contrário string vazia."""
    key = (get_setting("anthropic_key", "") or "").strip()
    return key if key.startswith("sk-ant-") else ""

def _get_backend() -> str:
    """
    Anthropic é o 1.º método se a chave estiver configurada.
    Ollama é o fallback quando não há chave ou quando Anthropic falha.
    """
    return "anthropic" if _anthropic_key() else "ollama"


# ── Ollama call ───────────────────────────────────────────────────────────────

def _ollama_options(max_tokens: int) -> dict:
    opts = {
        "num_predict": max_tokens,
        "temperature": 0.1,
        "num_ctx": int(get_setting("ollama_num_ctx", "2048") or "2048"),
    }
    threads = (get_setting("ollama_num_threads", "") or "").strip()
    if threads.isdigit():
        opts["num_thread"] = int(threads)
    return opts


def _ollama(prompt, system, image_path=None, max_tokens=1500):
    """
    Chama Ollama local (http://localhost:11434).
    Modelos recomendados: llama3.2, mistral, phi3, qwen2.5
    Para faturas com imagem: llava ou llama3.2-vision
    """
    host  = get_setting("ollama_host", "http://localhost:11434")
    model = get_setting("ollama_model", "llama3.2")

    # Se tem imagem e o modelo suporta visão, usa endpoint multimodal
    if image_path:
        vision_model = get_setting("ollama_vision_model", "llava")
        path = Path(image_path)
        with open(path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode()

        payload = {
            "model":  vision_model,
            "prompt": f"{system}\n\n{prompt}",
            "images": [b64],
            "stream": False,
            "options": _ollama_options(max_tokens),
        }
        url = f"{host}/api/generate"
    else:
        payload = {
            "model":  model,
            "messages": [
                {"role": "system",  "content": system},
                {"role": "user",    "content": prompt},
            ],
            "stream": False,
            "options": _ollama_options(max_tokens),
        }
        url = f"{host}/api/chat"

    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read().decode())
            if image_path:
                return result.get("response", "")
            return result.get("message", {}).get("content", "")
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Ollama não está a correr em {host}.\n"
            f"Instala em ollama.com/download e corre: ollama pull {model}"
        ) from e


# ── Anthropic call ────────────────────────────────────────────────────────────

def _anthropic(prompt, system, image_path=None, max_tokens=1500, model=None):
    """
    Chama a Anthropic API.
    model=None → usa _ANTHROPIC_CLASSIFY_MODEL (Haiku) para texto,
                     _ANTHROPIC_INVOICE_MODEL (Sonnet) se houver imagem/PDF.
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic não instalado. Corre: pip install anthropic")

    key = _anthropic_key()
    if not key:
        raise ValueError("Anthropic API Key não configurada em Configurações.")

    # Escolha de modelo: Sonnet para documentos (faturas/imagens), Haiku para texto
    if model is None:
        model = _ANTHROPIC_INVOICE_MODEL if image_path else _ANTHROPIC_CLASSIFY_MODEL

    client = anthropic.Anthropic(api_key=key)

    if image_path:
        path = Path(image_path)
        suffix = path.suffix.lower()
        media_map = {
            ".pdf":  "application/pdf",
            ".png":  "image/png",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }
        media_type = media_map.get(suffix, "image/jpeg")
        with open(path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode()
        content = [
            {"type": "document" if suffix == ".pdf" else "image",
             "source": {"type": "base64", "media_type": media_type, "data": b64}},
            {"type": "text", "text": prompt},
        ]
    else:
        content = prompt

    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
    )
    return msg.content[0].text.strip()


# ── Unified call — Anthropic 1.º, Ollama fallback ────────────────────────────

def _ai(prompt, system, image_path=None, max_tokens=1500, model=None):
    """
    Chama Anthropic se a chave estiver configurada; caso contrário Ollama.
    Se Anthropic falhar por erro de rede/quota, tenta Ollama automaticamente.
    """
    if _anthropic_key():
        try:
            return _anthropic(prompt, system, image_path, max_tokens, model)
        except Exception as e:
            log.warning("Anthropic falhou (%s) — a usar Ollama como fallback", e)
    return _ollama(prompt, system, image_path, max_tokens)


def _parse_json(raw):
    """Extrai JSON de resposta que pode ter texto à volta."""
    # Tenta extrair bloco ```json ... ```
    m = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    if m:
        return json.loads(m.group(1).strip())
    # Tenta encontrar { ... } ou [ ... ] directamente
    m = re.search(r"(\{[\s\S]+\}|\[[\s\S]+\])", raw)
    if m:
        return json.loads(m.group(1))
    return json.loads(raw.strip())


# ── 1. Leitura de Faturas ─────────────────────────────────────────────────────

def read_invoice(file_path=None, text=None):
    """
    Extrai dados de ativo a partir de fatura (PDF, imagem ou texto).
    Devolve dict com: hostname, type, manufacturer, model, serial_number,
    purchase_date, purchase_price, supplier, warranty_years, department,
    confidence, missing_fields[]
    """
    system = """És um assistente especializado em leitura de faturas de equipamento IT.
Extrai os campos em JSON (sem markdown, só JSON puro):
{
  "hostname_sugerido": string,
  "type": "PC Desktop|Laptop|Servidor|Switch|Impressora|Access Point|NAS|Outro",
  "manufacturer": string,
  "model": string,
  "serial_number": string ou null,
  "purchase_date": "DD/MM/YYYY" ou null,
  "purchase_price": numero ou null,
  "supplier": string ou null,
  "warranty_years": numero ou null,
  "department": string ou null,
  "os_version": string ou null,
  "notes": string ou null,
  "confidence": "alta|media|baixa",
  "missing_fields": []
}
Se um campo nao existe na fatura, usa null. Nunca inventes valores."""

    prompt = (
        "Analisa esta fatura e extrai todos os campos do equipamento IT."
        if file_path else
        f"Analisa este texto de fatura e extrai os campos:\n\n{text}"
    )

    raw    = _ai(prompt, system, image_path=file_path, max_tokens=900)
    result = _parse_json(raw)

    return {
        "hostname":       result.get("hostname_sugerido"),
        "type":           result.get("type", "Outro"),
        "manufacturer":   result.get("manufacturer"),
        "model":          result.get("model"),
        "serial_number":  result.get("serial_number"),
        "purchase_date":  result.get("purchase_date"),
        "purchase_price": result.get("purchase_price"),
        "supplier":       result.get("supplier"),
        "warranty_years": result.get("warranty_years"),
        "department":     result.get("department"),
        "os_version":     result.get("os_version"),
        "notes":          result.get("notes"),
        "confidence":     1.0 if result.get("confidence") == "alta" else
                          0.7 if result.get("confidence") == "media" else 0.4,
        "missing_fields": result.get("missing_fields", []),
    }


# ── 2. Classificação por MAC ──────────────────────────────────────────────────

def classify_macs(mac_list, context=""):
    """
    Classifica MACs por OUI + IA (Anthropic ou Ollama).
    Devolve lista de dicts: mac, manufacturer, type, hostname, confidence, notes

    Processado em lotes de 40 para cobrir redes grandes.
    """
    system = """Es especialista em hardware e redes IT. Para cada MAC address dado:

1. Identifica o FABRICANTE REAL do equipamento (nao do chip NIC) pelo OUI (primeiros 3 octetos hex).
   - MACs Cisco/HP/Dell podem ser NICs integrados em PCs — NAO assumes automaticamente que e um switch/impressora.
   - MACs Intel/Realtek/Broadcom sao sempre NICs em PCs — manufacturer deve ser o fabricante do PC se conhecido, ou null.
2. Classifica o TIPO de equipamento:
   Desktop, Laptop, Servidor, Switch, Impressora, Access Point, NAS, Firewall, Camara CCTV, Outro
3. Sugere hostname curto no formato TIPO-NNN (ex: SW-001, PC-042, PRN-001, AP-001, SRV-001)
4. Indica confianca entre 0.0 e 1.0:
   - OUI exclusivo de impressora (Brother/OKI/Zebra/Canon/Ricoh) → 0.90+
   - OUI exclusivo de switch/AP (Ubiquiti/MikroTik/Ruckus) → 0.85+
   - OUI de PC (Lenovo/Dell/ASUS) → 0.80+
   - OUI generico (Intel/Realtek) → 0.50

Regras criticas:
- OUI Lenovo → manufacturer="Lenovo", type="Desktop" ou "Laptop"
- OUI Dell → manufacturer="Dell", type="Desktop" ou "Servidor"
- OUI ASUSTeK → manufacturer="ASUS", type="Desktop"
- OUI Brother/OKI/Zebra/Konica/Ricoh/Canon → type="Impressora"
- OUI Ubiquiti (sem mais info) → type="Access Point" ou "Switch"
- OUI Intel/Realtek/Broadcom → manufacturer=null (e NIC, nao o equipamento)

Devolve APENAS array JSON valido, sem markdown, sem texto extra:
[{"mac": "xx:xx:xx:xx:xx:xx", "manufacturer": "Nome ou null", "type": "Tipo",
  "hostname": "TIPO-NNN", "confidence": 0.0}]"""

    all_results = []
    batch_size  = 40

    for start in range(0, len(mac_list), batch_size):
        batch = mac_list[start:start + batch_size]
        # ~50 tokens de saida por MAC; 30 de entrada
        max_tok = min(4000, 300 + 50 * len(batch))
        prompt  = (f"MACs:\n{json.dumps(batch)}\n\n"
                   f"Contexto: {context or 'rede empresarial portuguesa'}")
        raw = _ai(prompt, system, max_tokens=max_tok)
        try:
            all_results.extend(_parse_json(raw))
        except Exception:
            pass   # lote falhou silenciosamente

    return all_results


# ── 3. Classificação por dispositivo (MAC + OUI + hostname + IP) ─────────────

def classify_devices(devices, context=""):
    """
    Classifica dispositivos de rede via IA com contexto rico.

    devices: lista de dicts {mac, ip, oui_vendor, hostname}
    context: descrição da rede (ex: "Rede industrial portuguesa, subnet 192.168.1.0/24")

    Devolve: lista de dicts {mac, ip, manufacturer, type, hostname, confidence}

    Diferença de classify_macs: recebe hostname DNS e IP além do MAC,
    permitindo classificação muito mais precisa sem port scan.
    Processado em lotes de 40 para cobrir redes grandes.
    """
    system = """És especialista IT em redes. Classifica cada dispositivo pelo tipo real.

PRIORIDADE DE SINAIS (da maior para menor):

1. hostname — sinal mais fiável quando presente:
   SW-*, SWITCH-*, GSW-*, ESW-* → Switch (conf 0.88)
   SRV-*, SERVER-*, SERV-*, DC-* → Servidor (conf 0.88)
   PRN-*, IMP-*, MFP-*, PRINT-* → Impressora (conf 0.88)
   AP-*, WIFI-*, UAP-*, UNIFI-* → Access Point (conf 0.85)
   PC-*, DT-*, WS-*, DESK-* → Desktop (conf 0.82)
   LT-*, LAP-*, NB-* → Laptop (conf 0.82)
   NAS-*, QNAP-*, SYNO-* → NAS (conf 0.88)
   FW-*, FORTI-*, PFSENSE-*, FG-* → Firewall (conf 0.88)
   CAM-*, CCTV-*, DVR-*, NVR-* → Câmara CCTV (conf 0.80)

2. mac (primeiros 3 octetos) — MACs de hipervisores são sinal forte:
   00:50:56 (VMware vSphere/ESXi — atribuído pelo servidor vCenter) → Servidor, conf 0.72
   00:0c:29 (VMware Workstation auto-gerado — tipicamente VM de desenvolvimento) → Desktop, conf 0.45
   00:15:5d (Microsoft Hyper-V) → usa hostname; sem hostname → Desktop, conf 0.48
   52:54:00 (QEMU/KVM) → Servidor, conf 0.65
   NOTA: para VMware 00:0c:29 e Hyper-V 00:15:5d com hostname de servidor → Servidor

3. oui_vendor — ATENÇÃO: NIC genérico aparece tanto em PCs como em servidores:
   EXCLUSIVOS impressora: Brother Industries, OKI Data, Zebra Technologies, Canon, Ricoh, Kyocera, Konica Minolta → Impressora, conf 0.90+
   EXCLUSIVOS rede: Ubiquiti Networks → Access Point ou Switch; MikroTik, Ruckus, Aruba → AP/Switch; Fortinet → Firewall
   GENÉRICOS — REGRA CRÍTICA: Intel Corporate, Realtek Semiconductor, Broadcom, Atheros, Qualcomm
     → São NIC embutido; aparecem em PCs E em servidores Dell/HP com Intel I350/I210
     → SEM hostname: type "Desktop", confidence MÁXIMO 0.65 (manter abaixo de 0.82 — SNMP/WMI vai confirmar)
     → COM hostname de servidor (SRV*, DC*, SERVER*): type "Servidor", conf 0.82
     → manufacturer: null (sempre)
   AMBÍGUOS (PC + equipamento rede): Cisco Systems → usa hostname; sem hostname → Desktop, conf 0.55
   PC CORPORATIVO: Dell Inc., HP Inc., Lenovo → fabricantes PC predominantes em empresa; sem hostname → Desktop, conf 0.72

4. IP — sinal muito fraco, usa só como último desempate

REGRAS CRÍTICAS:
- Intel/Broadcom/Realtek SEM hostname → confidence MÁXIMO 0.65 (manter abaixo de 0.82 para SNMP correr)
- VMware 00:0c:29 → Desktop conf 0.45 (VM de workstation; WMI vai confirmar o OS)
- VMware 00:50:56 → Servidor conf 0.72 (VM atribuída por vCenter)
- oui_vendor "Brother Industries"/"Zebra Technologies"/Kyocera/Ricoh/Canon/OKI → Impressora
- Sem sinais claros → Desktop, confidence 0.50

FABRICANTE: indica só com evidência clara (OUI exclusivo de impressora/equipamento de rede).
Intel/Realtek/Broadcom/Atheros/Qualcomm → manufacturer: null.
VMware, Inc. → manufacturer: null (é o fabricante do NIC virtual, não do servidor).

Tipos válidos: Desktop, Laptop, Servidor, Switch, Impressora, Access Point, NAS, Firewall, Câmara CCTV, Outro.
Devolve APENAS array JSON válido, sem markdown, sem texto extra:
[{"mac":"xx:xx","ip":"y.y.y.y","manufacturer":null,"type":"Tipo","hostname":"SUGESTAO","confidence":0.0}]"""

    all_results = []
    batch_size  = 40

    for start in range(0, len(devices), batch_size):
        batch   = devices[start:start + batch_size]
        max_tok = min(4000, 400 + 65 * len(batch))
        prompt  = (
            f"Dispositivos:\n{json.dumps(batch, ensure_ascii=False)}\n\n"
            f"Contexto: {context or 'rede empresarial portuguesa'}"
        )
        try:
            raw = _ai(prompt, system, max_tokens=max_tok)
            all_results.extend(_parse_json(raw))
        except Exception:
            pass   # lote falhou — dispositivos ficam como Desconhecido

    return all_results


# ── 4. Agente de Stock ────────────────────────────────────────────────────────

def run_stock_agent(low_stock_items, vendor_pref="PC Diga / Staples / Amazon PT",
                    email_to="it@empresa.pt"):
    """
    Analisa consumíveis em rutura, estima preços e gera email de encomenda.
    """
    system = """Es um agente de aprovisionamento IT para empresa industrial portuguesa.
Para consumiveis em rutura/stock baixo:
1. Estima precos de mercado realistas em euros (Amazon PT, PC Diga, Staples)
2. Calcula quantidade sugerida = stock_min * 2
3. Redige email profissional em portugues europeu ao responsavel IT

Devolve APENAS JSON (sem markdown):
{
  "items": [{"reference": string, "unit_price": numero, "qty": numero,
             "total": numero, "urgency": "urgente|normal", "vendor": string}],
  "total_order": numero,
  "email_subject": string,
  "email_body": string,
  "agent_notes": string
}"""

    items_json = json.dumps([
        {"referencia": i["reference"], "tipo": i.get("type",""),
         "compativel": i.get("compatible_with",""),
         "stock_atual": i["stock_qty"], "stock_minimo": i["stock_min"]}
        for i in low_stock_items
    ], ensure_ascii=False)

    prompt = f"Consumiveis:\n{items_json}\n\nFornecedor: {vendor_pref}\nEmail: {email_to}"
    raw    = _ai(prompt, system, max_tokens=1200)
    return _parse_json(raw)


# ── 5. Envio de email ─────────────────────────────────────────────────────────

def send_email(subject, body, to_addr=None):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    host     = get_setting("smtp_host")
    port     = int(get_setting("smtp_port", "587"))
    user     = get_setting("smtp_user")
    password = get_setting("smtp_password")
    to       = to_addr or get_setting("email_to")

    if not all([host, user, password, to]):
        raise ValueError("SMTP não configurado. Vai a Configurações → Email.")

    msg           = MIMEMultipart()
    msg["From"]   = user
    msg["To"]     = to
    msg["Subject"]= subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(host, port, timeout=10) as srv:
        srv.ehlo(); srv.starttls(); srv.login(user, password)
        srv.sendmail(user, to, msg.as_string())


# ── 6. Verificar se Ollama está disponível ────────────────────────────────────

def check_ollama_status():
    """Devolve dict com status, modelos disponíveis e modelo configurado."""
    host = get_setting("ollama_host", "http://localhost:11434")
    try:
        req = urllib.request.Request(f"{host}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data   = json.loads(resp.read().decode())
            models = [m["name"] for m in data.get("models", [])]
            return {"running": True, "models": models, "host": host}
    except Exception as e:
        return {"running": False, "models": [], "host": host, "error": str(e)}
