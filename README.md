# IT Inventory

Aplicação de inventário de IT para ambientes Windows com interface desktop e API REST integrada.

## Funcionalidades

- **Auto-discovery de rede** — scan automático de dispositivos (intervalo de 24h configurável)
- **SNMP para impressoras** — polling automático a cada 15 minutos
- **Sync Active Directory / LDAP** — sincronização de departamentos, hostnames e IPs
- **Classificação IA** — classificação automática de dispositivos via Anthropic Claude + Ollama
- **API REST** — interface web para clientes na rede (porta 5050)
- **Alertas por email** — notificações SMTP automáticas
- **Exportação Excel** — relatórios via openpyxl
- **Inventário remoto de PCs Windows** — recolha de RAM, CPU e disco via WMI
- **Gestão de utilizadores e roles** — admin, printer\_manager, normal
- **Monitorização de rede em tempo real** — ping monitor e switch monitor

## Tecnologias

- Python 3.11+
- CustomTkinter (interface desktop)
- Flask + Flask-CORS (API REST)
- SQLite (base de dados local)
- Anthropic Claude API (IA)
- ldap3 (Active Directory)
- pywin32 / WMI (inventário remoto Windows)

## Instalação (Windows)

### Pré-requisitos

- Python 3.11 ou 3.12 com "Add Python to PATH" activado
- Windows 10/11

### Passos

1. Extrai o conteúdo para `C:\ITInventory\`
2. Faz duplo clique em `instalar.bat` — cria o ambiente virtual e instala todas as dependências (~2-4 min)
3. Faz duplo clique em `executar.bat` — abre a app e arranca a API na porta 5050

### Instalação manual (alternativa)

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python venv\Scripts\pywin32_postinstall.py -install
python main.py
```

## Configuração inicial

Na app desktop, acede a **Configurações** e preenche:

| Secção | Parâmetros principais |
|---|---|
| Rede | Subnet, SNMP community, intervalos de discovery |
| Active Directory | DC Host, domínio, service account |
| Email / SMTP | Host, porta, email de alertas |
| IA | Anthropic API Key (`sk-ant-...`) |
| Interface Web | API Key, CORS origins |

Depois vai a **Auto-Discovery → Iniciar scan** para o primeiro scan de rede.

## Estrutura do Projeto

```
ITInventory/
├── main.py               # Aplicação desktop (entry point)
├── api.py                # API REST Flask
├── core/
│   ├── database.py       # Base de dados SQLite
│   ├── discovery.py      # Motor de descoberta de rede
│   ├── ai_engine.py      # Classificação IA (Claude + Ollama)
│   ├── ad_sync.py        # Sincronização Active Directory
│   ├── snmp_engine.py    # Motor SNMP (impressoras)
│   ├── device_classifier.py
│   ├── network_monitor.py
│   ├── switch_monitor.py
│   ├── scheduler.py
│   ├── jobs.py
│   └── notifications.py
├── services/             # Workers distribuídos
├── web/                  # Interface web (clientes)
├── tests/                # Testes (pytest)
├── requirements.txt
├── instalar.bat          # Instalador automático
└── executar.bat          # Lançador da aplicação
```

## Testes

```bash
venv\Scripts\python -m pytest tests/ -v
```

107 testes, 0 falhas.

## Arquitectura

A aplicação corre num servidor central (máquina com a app desktop) que expõe a API REST na porta 5050. Os clientes acedem via interface web no browser. A descoberta de rede, sync AD e polling SNMP correm em background via scheduler.

Para ambientes distribuídos, existe um worker autónomo em `services/discovery_worker.py`.

## Requisitos de Rede

- Porta **5050** aberta no firewall do Windows (configurada automaticamente pelo `instalar.bat`)
- Acesso SNMP (porta 161 UDP) aos dispositivos de rede
- Acesso LDAP (porta 389) ao Domain Controller
