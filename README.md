# IT Inventory — SML Portugal

Sistema distribuído de gestão de inventário de TI.  
Trabalho Prático — Sistemas Operativos e Sistemas Distribuídos

---

## Arquitectura do Sistema

```
┌─────────────────────┐     HTTP REST      ┌──────────────────────┐
│  web/index.html     │ ◄────────────────► │  api.py  :8080       │
│  (Frontend Web SPA) │                    │  (API Service)       │
└─────────────────────┘                    └──────────┬───────────┘
                                                      │ SQLite WAL
┌─────────────────────┐     threads        ┌──────────▼───────────┐
│  main.py            │ ──────────────────►│  inventory.db        │
│  (Desktop UI)       │                    │  (Persistência)      │
│  PingMonitor        │                    └──────────▲───────────┘
│  NetworkMonitor     │                               │
│  SwitchMonitor      │                    ┌──────────┴───────────┐
│  JobScheduler       │                    │  discovery_worker.py │
└─────────────────────┘                    │  (Serviço Autónomo)  │
                                           └──────────────────────┘
```

### Componentes

| Componente | Ficheiro | Porta | Descrição |
|---|---|---|---|
| Frontend Web | `web/index.html` | — | SPA HTML/JS, serve via API |
| Desktop UI | `main.py` | — | Interface CustomTkinter |
| API Principal | `api.py` | 8080 | REST API Flask |
| Discovery Worker | `services/discovery_worker.py` | — | Processo autónomo de scan |
| Persistência | `inventory.db` (SQLite WAL) | — | Base de dados partilhada |

---

## Conceitos Distribuídos Implementados

### 1. Concorrência e Sincronização
- `ThreadPoolExecutor` no discovery (`core/discovery.py`) para ping paralelo de toda a subnet
- `PingMonitor`, `NetworkMonitor`, `SwitchMonitor` correm em threads independentes
- `threading.local()` — uma conexão SQLite por thread, elimina `check_same_thread=False`
- `threading.Lock` protege os caches partilhados de settings e estatísticas

### 2. Tolerância a Falhas
- Falha de SNMP, WMI ou AD sync não aborta o discovery global — cada protocolo tem tratamento de excepções independente
- `PRAGMA busy_timeout=5000` — SQLite espera até 5 s antes de falhar em escrita concorrente
- Discovery worker recomeça automaticamente ao fim de cada ciclo mesmo que o anterior falhe

### 3. Consistência de Dados
- SQLite em modo WAL (Write-Ahead Logging) permite leitores concorrentes durante escritas
- `PRAGMA foreign_keys=ON` garante integridade referencial
- Upsert por MAC e IP — evita duplicados mesmo que o mesmo dispositivo seja descoberto por caminhos diferentes
- Operações críticas (criação de alertas, verificação de utilizadores) são atómicas numa única transacção

### 4. Segurança e Controlo de Acessos
- Três roles de utilizador: `admin`, `printer_manager`, `normal`
- Passwords armazenadas com PBKDF2-HMAC-SHA256 + salt (100 000 iterações)
- API Key opcional via header `X-API-Key`
- CORS com origens configuráveis por base de dados
- Navegação filtrada por role — painéis inacessíveis ficam invisíveis na UI

### 5. Observabilidade e Monitorização
- Log estruturado em `~/ITInventory/app.log` (UI) e `~/ITInventory/worker.log` (worker)
- Endpoint `/api/health` — status e contagem de assets em tempo real
- Histórico de ping por dispositivo nas últimas 24 h (`device_history`)
- Métricas de rede (bandwidth, latência gateway/firewall) em `network_metrics` e `network_pings`
- Alertas automáticos com envio de email (SMTP configurável)

### 6. Componente Inteligente (valorizado)
- `core/ai_engine.py` — abstracção com duas implementações intercambiáveis:
  - **Anthropic Claude** (Haiku para classificação, Sonnet para OCR de faturas)
  - **Ollama local** (fallback offline — llama3.2, llava)
- Classificação automática de dispositivos descobertos por tipo, fabricante e confiança

---

## Estrutura de Ficheiros

```
ITInventory/
├── main.py                  # UI desktop (CustomTkinter)
├── api.py                   # REST API Flask (porta 8080)
├── core/
│   ├── database.py          # SQLite WAL, schema, helpers thread-safe
│   ├── discovery.py         # Scan de rede: ICMP/subprocess/TCP, SNMP, WMI
│   ├── ai_engine.py         # Anthropic Claude + fallback Ollama
│   ├── device_classifier.py # Classificação de dispositivos
│   ├── snmp_engine.py       # Polling SNMP (impressoras, switches)
│   ├── jobs.py              # Tarefas agendadas (discovery, SNMP, AD sync)
│   ├── scheduler.py         # Agendador de jobs com threads
│   ├── ad_sync.py           # Sincronização LDAP / Active Directory
│   ├── network_monitor.py   # Monitorização de banda e latência
│   ├── switch_monitor.py    # Monitorização de portas de switch
│   ├── notifications.py     # Envio de email via SMTP
│   └── oui_db.py            # Identificação de fabricante por MAC (OUI)
├── services/
│   ├── discovery_worker.py  # Worker autónomo (processo separado)
│   └── README.md            # Diagrama de arquitectura e conceitos SO/SD
├── web/
│   └── index.html           # Frontend SPA (HTML/CSS/JS puro)
├── tests/
│   ├── test_classifier.py   # 108 testes unitários do classificador
│   └── test_api.py          # Testes de integração da REST API
├── Dockerfile.api           # Container da API Flask
├── Dockerfile.worker        # Container do discovery worker
├── docker-compose.yml       # Orquestração dos serviços
└── requirements.txt         # Dependências Python (Windows)
```

---

## Requisitos

- Python 3.11+ (ou Docker)
- Windows: `pywin32` + `wmi` para inventário remoto via WMI (opcional)
- Ollama local (opcional — necessário para IA offline)

---

## Instalação e Execução

### Opção A — Windows (com UI desktop)

```powershell
# 1. Instalar dependências (cria venv automaticamente)
.\instalar.bat

# 2. Iniciar aplicação
.\executar.bat
# ou directamente:
venv\Scripts\python main.py
```

A API REST inicia automaticamente em `http://localhost:8080`.

### Opção B — Docker Compose (arquitectura distribuída)

```bash
# Configurar subnet (opcional)
export ITINV_SUBNET=192.168.1.0/24

# Iniciar todos os serviços
docker compose up -d

# Verificar estado
docker compose ps
docker compose logs -f

# Parar
docker compose down
```

Serviços disponíveis:
- **API + Web UI**: `http://localhost:8080`
- **Health check**: `http://localhost:8080/api/health`

### Worker autónomo (sem Docker)

```powershell
# Uma execução
venv\Scripts\python services\discovery_worker.py

# Loop a cada 24 h
venv\Scripts\python services\discovery_worker.py --loop 24 --subnet 192.168.1.0/24
```

---

## API REST — Endpoints Principais

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/health` | Estado da API (sem autenticação) |
| GET | `/api/stats` | Totais, alertas, ciclo de vida |
| GET | `/api/assets` | Lista de ativos (filtros: type, status, department, search) |
| GET | `/api/assets/<id>` | Ativo por ID |
| GET | `/api/assets/<id>/uptime` | Histórico de ping 24 h |
| DELETE | `/api/assets/<id>` | Eliminar ativo |
| GET | `/api/printers` | Impressoras |
| GET | `/api/printers/critical` | Impressoras com toner crítico |
| GET | `/api/alerts` | Alertas abertos |
| GET | `/api/consumables` | Consumíveis |
| GET | `/api/consumables/low-stock` | Consumíveis abaixo do mínimo |
| GET | `/api/consumables/movements` | Histórico de movimentos de stock |
| GET | `/api/consumables/<id>/movements` | Movimentos de um consumível |
| POST | `/api/consumables/<id>/movements` | Registar entrada/saída de stock |
| GET | `/api/network/status` | Estado actual da rede |
| GET | `/api/network/history` | Histórico de métricas de rede |
| GET | `/api/reports/inventory.xlsx` | Exportar inventário em Excel |
| GET | `/api/lifecycle` | Relatório de ciclo de vida |

**Autenticação (opcional):** header `X-API-Key: <chave>` se configurado nas definições.

---

## Testes

```powershell
# Todos os testes (unitários + integração)
venv\Scripts\python -m pytest tests/ -v

# Só testes de integração da API
venv\Scripts\python -m pytest tests/test_api.py -v
