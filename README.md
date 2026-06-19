IT Inventory  SML Portugal

Sistema de Gestão de Inventário IT desenvolvido para a SML Portugal.

Projeto académico CTeSP · Redes e Segurança Informática · IPCA 2025/2026.


Substitui processos manuais de inventariação por uma solução automatizada que descobre, classifica, monitoriza e alerta sobre todos os ativos IT da organização.




Índice


Funcionalidades
Arquitetura
Pré-requisitos
Instalação
Configuração
Utilização
API REST
Estrutura do Projeto
Testes
Equipa



Funcionalidades

Auto-Discovery


Ping sweep paralelo (até 100 threads) à subnet configurada (padrão 192.168.163.0/24)
Leitura da tabela ARP para obtenção de MAC addresses
Resolução de hostname via DNS reverso, mDNS e NetBIOS
SNMP walk (v2c) para extração de sysDescr, sysName, modelo, S/N, firmware, uptime
Identificação de fabricante por OUI (base local com 636+ entradas)
Identificação de modelo por prefixo MAC (400+ modelos)
Enriquecimento via AD/LDAP com departamento, OU e utilizador
Query WMI remota (PCs Windows): modelo, S/N, OS, CPU, RAM, disco
Sistema de confiança (01): OUI=0.90, SNMP=0.95, WMI=0.99
Classificação por IA (Ollama local) para dispositivos com confiança < 0.70
Scan agendado automático a cada 24 horas


Monitorização


Ping contínuo a todos os dispositivos (intervalo configurável, padrão 60s)
Histórico de pings para cálculo de uptime (últimas 24h)
Polling SNMP de impressoras a cada 15 minutos (toner + contadores)
Dashboard em tempo real: ativos, online/offline, alertas, PCs a substituir


Impressoras e Consumíveis


Níveis de toner K/C/M/Y via SNMP (Printer MIB RFC 1759)
Suporte HP LaserJet, OKI, Konica Minolta bizhub, Zebra, Brother MFC
Gestão de stock de consumíveis com stock mínimo configurável
Alerta automático abaixo do limiar (padrão 15%)


Alertas e Notificações


Severidades: Critical / Warning / Info
Tipos: Toner, Stock, Hardware (4.º ano), License, Network
Alerta de substituição para PCs no 4.º ano de uso
Envio de email via SMTP/STARTTLS


Inteligência Artificial


Leitor de faturas: extração de modelo, S/N, data, preço, fornecedor e garantia de PDF/imagem
Classificação por MAC: identificação de fabricante, tipo e sugestão de hostname
Agente de stock: análise de consumíveis em rutura, estimativa de preços e geração de email
Backend configurável: Ollama local (padrão, offline, sem custos) ou Anthropic Claude (opcional)


Relatórios e Interface


App desktop Windows (CustomTkinter, dark mode)
Interface web read-only (HTML5 puro, sem frameworks)  abrir index.html no browser
Exportação Excel (.xlsx, 5 folhas), CSV e JSON
Auto-refresh da interface web a cada 60 segundos



Arquitetura


                   App Desktop (main.py)                  
                   CustomTkinter GUI                      
         
  Discovery   Monitor     Scheduler   AI Panel  
  Engine      (Ping/SNMP  (24h scan)  (Ollama)  
         
            
                                                         
                   core/database.py                       
                   SQLite WAL                             
                                                         
                   api.py (Flask :5050)                   

                                       
   Web Browser                    Rede 192.168.163.0/24
   (index.html)                   SNMP / ICMP / WMI / LDAP

Módulos

MóduloDescriçãomain.pyPonto de entrada  UI desktop + arranque da APIapi.pyREST API Flask (read-only, porta 5050)core/database.pyModelos SQLite WAL, init, helperscore/discovery.pyPing sweep, ARP, DNS, SNMP, WMI, ADcore/device_classifier.pyClassificação por OUI + confiançacore/oui_db.pyBase OUI com 636+ fabricantescore/model_db.pyMapeamento prefixo MAC  modelocore/snmp_engine.pySNMP v2c walk e polling de impressorascore/network_monitor.pyPing monitor contínuocore/switch_monitor.pyMonitorização de switches via SNMPcore/ad_sync.pySincronização Active Directory / LDAPcore/ai_engine.pyIntegração Ollama + Anthropic Claudecore/notifications.pyAlertas, email SMTP/STARTTLScore/scheduler.pyAgendamento de jobs (scan, polling)core/jobs.pyJobs de background (relatórios, limpeza)services/discovery_worker.pyWorker de discovery em processo separado


Pré-requisitos


Windows 10/11 ou Windows Server 2019+
Python 3.11+ (com "Add to PATH" ativado na instalação)
Ollama instalado e modelo llama3.2 descarregado (para funcionalidades de IA)
Acesso à rede 192.168.163.0/24 a partir do servidor
Controlador de domínio acessível via LDAP (porta 389)  opcional
SNMP v2c com community public nos dispositivos de rede  opcional
GPO com WMI habilitado nos PCs Windows alvo  opcional



Instalação

Método recomendado (Windows)

batch# 1. Clonar o repositório
git clone https://github.com/SML-Portugal/ITInventory.git
cd ITInventory

# 2. Executar o instalador (cria venv + instala dependências)
instalar.bat

# 3. Arrancar a aplicação
executar.bat

Instalação manual

batchpython -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Só em Windows, após instalar pywin32:
python venv\Scripts\pywin32_postinstall.py -install

python main.py

Gerar executável standalone (.exe)

batchgerar_exe.bat
# Saída em: dist\ITInventory.exe


Configuração

Toda a configuração é feita através do painel Definições da app desktop e guardada na base de dados SQLite (%USERPROFILE%\ITInventory\inventory.db).

ParâmetroPadrãoDescriçãosubnet192.168.163.0/24Subnet a descobrirsnmp_communitypublicCommunity SNMP v2cping_interval60Intervalo de ping (segundos)snmp_poll_interval900Polling SNMP impressoras (segundos)toner_threshold15Limiar de alerta de toner (%)ad_serverIP/hostname do controlador de domínioad_domainsml.comDomínio ADsmtp_hostServidor SMTP para alertassmtp_port587Porta SMTP (STARTTLS)ollama_hosthttp://localhost:11434URL do servidor Ollamaollama_modelllama3.2Modelo Ollama para classificaçãoweb_api_keyChave X-API-Key para a REST API (opcional)


API REST

A API corre em http://<servidor>:5050 e é read-only.

Autenticação via header X-API-Key (opcional, configurável).

MétodoEndpointDescriçãoGET/api/healthEstado do sistema (sem auth)GET/api/statsDashboard: totais, lifecycle, alertasGET/api/assetsListar ativos (filtros: type, dept, status, search)GET/api/assets/<id>Detalhe de um ativoGET/api/assets/stats/by-typeContagem por tipoGET/api/printersImpressoras com dados SNMPGET/api/alertsAlertas em aberto (filtro: severity)GET/api/consumablesTodos os consumíveisGET/api/lifecyclePCs por ano de aquisiçãoGET/api/reports/inventory.xlsxRelatório Excel completo (5 folhas)GET/api/reports/summary.jsonSnapshot JSON completo

Exemplo:

bashcurl -H "X-API-Key: a-tua-chave" http://192.168.163.83:5050/api/stats


Estrutura do Projeto

ITInventory/
 main.py                  # Ponto de entrada  UI desktop
 api.py                   # REST API Flask
 requirements.txt         # Dependências Python
 instalar.bat             # Instalador automático (Windows)
 executar.bat             # Atalho de execução
 debug.bat                # Execução com consola visível
 gerar_exe.bat            # Gera ITInventory.exe (PyInstaller)
 audit_macs.py            # Ferramenta de auditoria de MACs
 diagnostico_rede.py      # Diagnóstico de conectividade

 core/                    # Módulos de lógica de negócio
    database.py          # SQLite WAL  modelos e helpers
    discovery.py         # Auto-discovery: ping, ARP, SNMP, WMI, AD
    device_classifier.py # Classificação por OUI e confiança
    oui_db.py            # Base OUI (636+ fabricantes)
    model_db.py          # Prefixo MAC  modelo (400+ entradas)
    snmp_engine.py       # SNMP v2c + Printer MIB
    network_monitor.py   # Ping monitor contínuo
    switch_monitor.py    # Monitorização de switches
    ad_sync.py           # Sync Active Directory / LDAP
    ai_engine.py         # IA: Ollama + Anthropic Claude
    notifications.py     # Alertas + email SMTP
    scheduler.py         # Agendamento de jobs
    jobs.py              # Jobs de background

 services/                # Processos de background
    discovery_worker.py  # Worker de discovery independente

 tests/                   # Testes automatizados (pytest)
     test_classifier.py


Testes

batchvenv\Scripts\activate
python -m pytest tests/ -v

Os testes cobrem a lógica de classificação de dispositivos (OUI lookup, cálculo de confiança, detecção de tipo).


Equipa

NºNomeFunçãoA36345José Daniel M. GonçalvesGestor de Projeto / Infra / BackendA36357Jorge Manuel V. DuarteDesenvolvedorA36359Albino BarretoDesenvolvedorA36353João MachadoAnalista / Dev

Orientador: Helder Jordão

Instituição: IPCA  Instituto Politécnico do Cávado e do Ave

Curso: CTeSP em Redes e Segurança Informática

Ano letivo: 2025/2026


Licença

Uso interno  SML Portugal. Projeto académico IPCA.

Não autorizada a distribuição fora do contexto do grupo SML.
