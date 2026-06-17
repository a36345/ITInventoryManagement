"""
tests/test_classifier.py — Smoke tests para core/device_classifier.py

Cobre:
  • classify_from_snmp_descr  — sysDescr → tipo
  • classify_from_hostname    — padrão DNS → tipo
  • classify_from_model       — modelo → tipo
  • classify_from_ports       — portas TCP → tipo
  • classify_from_http        — título HTTP → tipo
  • merge_classification      — prioridade de fontes
  • is_valid_mac              — validação de MAC

Correr:
  cd C:\\ITInventory
  venv\\Scripts\\python -m pytest tests/ -v
  ou
  venv\\Scripts\\python -m pytest tests/ -v --tb=short
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.device_classifier import (
    classify_from_snmp_descr,
    classify_from_hostname,
    classify_from_model,
    classify_from_ports,
    classify_from_http,
    classify_from_oui,
    merge_classification,
    is_valid_mac,
    AMBIGUOUS_VENDORS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# is_valid_mac
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsValidMac:
    def test_broadcast_invalid(self):
        assert not is_valid_mac("ff:ff:ff:ff:ff:ff")

    def test_zero_invalid(self):
        assert not is_valid_mac("00:00:00:00:00:00")

    def test_multicast_invalid(self):
        assert not is_valid_mac("01:00:5e:00:00:01")

    def test_none_invalid(self):
        assert not is_valid_mac(None)

    def test_empty_invalid(self):
        assert not is_valid_mac("")

    def test_real_mac_valid(self):
        assert is_valid_mac("aa:bb:cc:dd:ee:ff")

    def test_dashes_valid(self):
        assert is_valid_mac("aa-bb-cc-dd-ee-ff")

    def test_vmware_vsphere_valid(self):
        assert is_valid_mac("00:50:56:12:34:56")

    def test_uppercase_valid(self):
        assert is_valid_mac("AA:BB:CC:DD:EE:FF")


# ═══════════════════════════════════════════════════════════════════════════════
# classify_from_snmp_descr
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifyFromSnmpDescr:
    # Impressoras
    def test_hp_laserjet(self):
        t, c = classify_from_snmp_descr("HP LaserJet Pro M404dn")
        assert t == "Impressora"
        assert c >= 0.90

    def test_brother_mfc(self):
        t, c = classify_from_snmp_descr("Brother MFC-L8900CDW Series")
        assert t == "Impressora"
        assert c >= 0.90

    def test_kyocera_taskalfa(self):
        t, c = classify_from_snmp_descr("KYOCERA TASKalfa 3253ci")
        assert t == "Impressora"
        assert c >= 0.90

    def test_konica_bizhub(self):
        t, c = classify_from_snmp_descr("KONICA MINOLTA bizhub C308")
        assert t == "Impressora"
        assert c >= 0.90

    def test_ricoh_printer(self):
        t, c = classify_from_snmp_descr("Ricoh Aficio MP C5503")
        assert t == "Impressora"
        assert c >= 0.90

    def test_zebra(self):
        t, c = classify_from_snmp_descr("Zebra Technologies ZT410")
        assert t == "Impressora"
        assert c >= 0.90

    # Switches
    def test_cisco_catalyst(self):
        t, c = classify_from_snmp_descr("Cisco IOS Software, Catalyst 2960 Series")
        assert t == "Switch"
        assert c >= 0.90

    def test_fortiswitch(self):
        t, c = classify_from_snmp_descr("FortiSwitch-148E-POE v6.4.6")
        assert t == "Switch"
        assert c >= 0.95

    def test_procurve(self):
        t, c = classify_from_snmp_descr("ProCurve Switch 1810G-24")
        assert t == "Switch"
        assert c >= 0.90

    def test_mikrotik_crs(self):
        t, c = classify_from_snmp_descr("MikroTik CRS326-24G-2S+RM")
        assert t == "Switch"
        assert c >= 0.90

    # Firewalls
    def test_fortigate(self):
        t, c = classify_from_snmp_descr("FortiGate-60F v7.0.14")
        assert t == "Firewall"
        assert c >= 0.90

    def test_pfsense(self):
        t, c = classify_from_snmp_descr("pfSense 2.7.2-RELEASE")
        assert t == "Firewall"
        assert c >= 0.90

    # Servidores
    def test_windows_server_2019(self):
        t, c = classify_from_snmp_descr("Windows Server 2019 Standard 10.0")
        assert t == "Servidor"
        assert c >= 0.90

    def test_windows_server_2022(self):
        t, c = classify_from_snmp_descr("Microsoft Windows Server 2022 Datacenter")
        assert t == "Servidor"
        assert c >= 0.90

    def test_esxi(self):
        t, c = classify_from_snmp_descr("VMware ESXi 7.0.0 build-15843807")
        assert t == "Servidor"
        assert c >= 0.90

    def test_linux_server(self):
        t, c = classify_from_snmp_descr("Linux ubuntu-server 5.15.0-generic")
        assert t == "Servidor"
        assert c >= 0.75

    # Desktop
    def test_windows_10(self):
        t, c = classify_from_snmp_descr("Microsoft Windows NT 10.0")
        assert t == "Desktop"

    # NAS
    def test_synology(self):
        t, c = classify_from_snmp_descr("Synology DiskStation DS920+")
        assert t == "NAS"
        assert c >= 0.90

    def test_qnap(self):
        t, c = classify_from_snmp_descr("QNAP NAS TS-453D")
        assert t == "NAS"
        assert c >= 0.90

    # Access Points
    def test_unifi_ap(self):
        t, c = classify_from_snmp_descr("UniFi Access Point AP-AC-PRO", interface_count=2)
        assert t == "Access Point"
        assert c >= 0.85

    # None / empty
    def test_none_returns_none(self):
        assert classify_from_snmp_descr(None) is None

    def test_empty_returns_none(self):
        assert classify_from_snmp_descr("") is None

    # Printers don't get misclassified as Linux/Outro
    def test_printer_beats_linux(self):
        """Uma impressora com Linux embutido deve ser classificada como Impressora, não Linux."""
        t, c = classify_from_snmp_descr("HP Color LaserJet MFP M479fdw Linux embedded")
        assert t == "Impressora"


# ═══════════════════════════════════════════════════════════════════════════════
# classify_from_hostname
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifyFromHostname:
    def test_switch_sw(self):
        t, c = classify_from_hostname("SW-PISO2")
        assert t == "Switch"
        assert c >= 0.85

    def test_switch_gsw(self):
        t, c = classify_from_hostname("GSW-PRODUCAO")
        assert t == "Switch"

    def test_server_srv(self):
        t, c = classify_from_hostname("SRV-DC01")
        assert t == "Servidor"
        assert c >= 0.85

    def test_server_dc(self):
        t, c = classify_from_hostname("DC-PRINCIPAL")
        assert t == "Servidor"

    def test_printer_prn(self):
        t, c = classify_from_hostname("PRN-FINANCAS")
        assert t == "Impressora"
        assert c >= 0.85

    def test_printer_mfp(self):
        t, c = classify_from_hostname("MFP-PISO1")
        assert t == "Impressora"

    def test_ap(self):
        t, c = classify_from_hostname("AP-SALA-REUNIOES")
        assert t == "Access Point"
        assert c >= 0.80

    def test_unifi(self):
        t, c = classify_from_hostname("UNIFI-AP-001")
        assert t == "Access Point"

    def test_nas(self):
        t, c = classify_from_hostname("NAS-BACKUP01")
        assert t == "NAS"

    def test_firewall(self):
        t, c = classify_from_hostname("FW-PERIMETRO")
        assert t == "Firewall"

    def test_forti(self):
        t, c = classify_from_hostname("FORTIGATE-01")
        assert t == "Firewall"

    def test_desktop_pc(self):
        t, c = classify_from_hostname("PC-JOAO")
        assert t == "Desktop"

    def test_laptop(self):
        t, c = classify_from_hostname("LAP-MARIA")
        assert t == "Laptop"

    def test_camera(self):
        t, c = classify_from_hostname("CAM-ENTRADA")
        assert t == "Câmara CCTV"

    def test_generic_no_match(self):
        assert classify_from_hostname("WORKPC01") is None

    def test_none_returns_none(self):
        assert classify_from_hostname(None) is None

    def test_lowercase_works(self):
        """Regras devem funcionar em minúsculas."""
        t, c = classify_from_hostname("sw-piso2")
        assert t == "Switch"


# ═══════════════════════════════════════════════════════════════════════════════
# classify_from_model
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifyFromModel:
    def test_dell_poweredge(self):
        t, c = classify_from_model("Dell PowerEdge R740")
        assert t == "Servidor"
        assert c >= 0.90

    def test_hp_proliant(self):
        t, c = classify_from_model("HP ProLiant DL380 Gen10")
        assert t == "Servidor"
        assert c >= 0.90

    def test_dell_optiplex(self):
        t, c = classify_from_model("Dell OptiPlex 7090")
        assert t == "Desktop"
        assert c >= 0.85

    def test_hp_elitedesk(self):
        t, c = classify_from_model("HP EliteDesk 800 G6")
        assert t == "Desktop"

    def test_lenovo_thinkpad(self):
        t, c = classify_from_model("Lenovo ThinkPad T490")
        assert t == "Laptop"
        assert c >= 0.85

    def test_hp_elitebook(self):
        t, c = classify_from_model("HP EliteBook 840 G8")
        assert t == "Laptop"

    def test_cisco_catalyst_switch(self):
        t, c = classify_from_model("Catalyst WS-C2960X-24")
        assert t == "Switch"
        assert c >= 0.90

    def test_fortiswitch(self):
        t, c = classify_from_model("FortiSwitch 148E")
        assert t == "Switch"
        assert c >= 0.90

    def test_hp_laserjet_model(self):
        t, c = classify_from_model("HP LaserJet Pro M404dn")
        assert t == "Impressora"
        assert c >= 0.90

    def test_brother_mfc_model(self):
        t, c = classify_from_model("Brother MFC-L8900CDW")
        assert t == "Impressora"
        assert c >= 0.90

    def test_synology_nas(self):
        t, c = classify_from_model("Synology DS920+")
        assert t == "NAS"
        assert c >= 0.85

    def test_unifi_ap_model(self):
        t, c = classify_from_model("UniFi AP-AC-Pro")
        assert t == "Access Point"

    def test_unknown_returns_none(self):
        assert classify_from_model("XYZ-9999-UNKNOWN") is None

    def test_none_returns_none(self):
        assert classify_from_model(None) is None


# ═══════════════════════════════════════════════════════════════════════════════
# classify_from_ports
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifyFromPorts:
    def test_jetdirect_9100_is_printer(self):
        t, c = classify_from_ports({9100})
        assert t == "Impressora"
        assert c >= 0.95

    def test_jetdirect_9100_with_smb_is_not_printer(self):
        """Porta 9100 + SMB (445) = Windows a partilhar impressora, não impressora real."""
        result = classify_from_ports({9100, 445})
        assert result is None or result[0] != "Impressora"

    def test_smb_rpc_is_windows(self):
        t, c = classify_from_ports({445, 135})
        assert t == "Desktop"
        assert c >= 0.88

    def test_rdp_is_desktop(self):
        t, c = classify_from_ports({3389})
        assert t == "Desktop"
        assert c >= 0.85

    def test_smb_only(self):
        t, c = classify_from_ports({445})
        assert t == "Desktop"
        assert c >= 0.80

    def test_nas_synology(self):
        t, c = classify_from_ports({5000, 5001})
        assert t == "NAS"
        assert c >= 0.90

    def test_lpd_is_printer(self):
        t, c = classify_from_ports({515})
        assert t == "Impressora"

    def test_ipp_no_windows_is_printer(self):
        t, c = classify_from_ports({631})
        assert t == "Impressora"

    def test_ipp_with_smb_not_printer(self):
        """IPP (631) + SMB (445) = Windows com partilha, não impressora."""
        result = classify_from_ports({631, 445})
        assert result is None or result[0] != "Impressora"

    def test_empty_ports_none(self):
        assert classify_from_ports(set()) is None

    def test_random_port_none(self):
        assert classify_from_ports({8080}) is None


# ═══════════════════════════════════════════════════════════════════════════════
# classify_from_http
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifyFromHttp:
    def test_hp_laserjet_title(self):
        t, c = classify_from_http("HP LaserJet Pro M404dn", "")
        assert t == "Impressora"
        assert c >= 0.90

    def test_pfsense_title(self):
        t, c = classify_from_http("pfSense - Status: Dashboard", "")
        assert t == "Firewall"
        assert c >= 0.95

    def test_synology_title(self):
        t, c = classify_from_http("Synology DiskStation", "")
        assert t == "NAS"
        assert c >= 0.95

    def test_esxi_title(self):
        t, c = classify_from_http("VMware ESXi - Virtual Infrastructure", "")
        assert t == "Servidor"
        assert c >= 0.85

    def test_empty_returns_none(self):
        assert classify_from_http("", "") is None

    def test_unknown_title_returns_none(self):
        assert classify_from_http("My Custom App", "") is None


# ═══════════════════════════════════════════════════════════════════════════════
# merge_classification
# ═══════════════════════════════════════════════════════════════════════════════

class TestMergeClassification:
    def _make_device(self, dtype="Desconhecido", conf=0.0, source=""):
        return {
            "type": dtype,
            "confidence": conf,
            "_class_source": source,
            "needs_review": 1,
        }

    # Caso base: aplica classificação nova quando é melhor
    def test_applies_better_classification(self):
        d = self._make_device("Desconhecido", 0.0)
        merge_classification(d, "Impressora", 0.95, "snmp_engine")
        assert d["type"] == "Impressora"
        assert d["confidence"] == 0.95

    # WMI protegido: não é sobrescrito por IA
    def test_wmi_not_overridden_by_ai(self):
        d = self._make_device("Desktop", 0.99, "wmi")
        merge_classification(d, "Servidor", 0.85, "ai")
        assert d["type"] == "Desktop"   # WMI mantém prioridade

    # SNMP com alta confiança não é sobrescrito por ai
    def test_snmp_engine_not_overridden_by_ai(self):
        d = self._make_device("Impressora", 0.97, "snmp_engine")
        merge_classification(d, "Desktop", 0.80, "ai")
        assert d["type"] == "Impressora"

    # WMI pode ser sobrescrito por outro WMI (mesma fonte, melhor confiança)
    def test_wmi_overridden_by_better_wmi(self):
        d = self._make_device("Desktop", 0.90, "wmi")
        merge_classification(d, "Servidor", 0.99, "wmi")
        assert d["type"] == "Servidor"

    # IA não muda tipo com confiança baixa
    def test_ai_low_conf_no_type_change(self):
        d = self._make_device("Switch", 0.80, "snmp_descr")
        merge_classification(d, "Desktop", 0.60, "ai")
        assert d["type"] == "Switch"

    # IA pode confirmar mesmo tipo com confiança maior
    def test_ai_confirms_same_type_higher_conf(self):
        d = self._make_device("Desktop", 0.55, "ai_mac")
        merge_classification(d, "Desktop", 0.75, "ai")
        assert d["confidence"] == 0.75

    # needs_review reflecte confiança
    def test_needs_review_high_conf(self):
        d = self._make_device()
        merge_classification(d, "Switch", 0.92, "snmp_engine")
        assert d["needs_review"] == 0

    def test_needs_review_mid_conf_accepted(self):
        """Limiar 0.72: Dell/HP/Lenovo (0.72) e Intel+inferido (0.76) → needs_review=0."""
        d = self._make_device()
        merge_classification(d, "Desktop", 0.72, "ai")
        assert d["needs_review"] == 0

    def test_needs_review_low_conf(self):
        d = self._make_device()
        merge_classification(d, "Desconhecido", 0.50, "ai")
        assert d["needs_review"] == 1

    # Classificação não aplicada se confiança pior
    def test_worse_confidence_not_applied(self):
        d = self._make_device("Firewall", 0.90, "snmp_descr")
        merge_classification(d, "Firewall", 0.70, "model")
        assert d["confidence"] == 0.90   # não piora

    # Classificação IA muda tipo com confiança >= 0.72
    def test_ai_changes_type_with_enough_conf(self):
        d = self._make_device("Desktop", 0.55, "oui")
        merge_classification(d, "Servidor", 0.75, "ai")
        assert d["type"] == "Servidor"


# ═══════════════════════════════════════════════════════════════════════════════
# Integração: SNMP printer antes de Linux genérico
# ═══════════════════════════════════════════════════════════════════════════════

class TestSnmpPrinterBeforeLinux:
    """
    Garante que a ordem das regras SNMP_DESCR_RULES coloca impressoras
    ANTES de Linux/Outro — uma impressora HP com Linux embutido deve ser
    classificada como Impressora, não como Linux/Outro.
    """

    def test_hp_mfp_linux_embedded(self):
        descr = "HP Color LaserJet MFP Linux embedded 2.6.32"
        t, c = classify_from_snmp_descr(descr)
        assert t == "Impressora", f"Esperava Impressora, obteve {t}"

    def test_canon_imagerunner_linux(self):
        descr = "Canon imageRUNNER C3520 Linux 3.4.0"
        t, c = classify_from_snmp_descr(descr)
        assert t == "Impressora"

    def test_fortiswitch_before_fortigate(self):
        """FortiSwitch deve ser Switch, não Firewall."""
        t, c = classify_from_snmp_descr("FortiSwitch-248E-FPOE v7.0.4")
        assert t == "Switch"

    def test_unifi_ap_with_few_ifaces(self):
        """UniFi com <= 4 interfaces → Access Point, não Switch."""
        t, c = classify_from_snmp_descr("UniFi AP AC Pro", interface_count=2)
        assert t == "Access Point"

    def test_unifi_switch_with_many_ifaces(self):
        """UniFi com muitas interfaces pode ser Switch."""
        # Com 24 interfaces e descr genérica "unifi" (sem "ap" ou "uap")
        # a regra ubiquiti/unifi aplica-se → Switch, 0.88
        t, c = classify_from_snmp_descr("Ubiquiti UniFi Switch US-24", interface_count=24)
        assert t == "Switch"


# ═══════════════════════════════════════════════════════════════════════════════
# classify_from_oui
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifyFromOui:
    def test_ambiguous_vendor_low_conf(self):
        """Fabricantes ambíguos como Dell devem ter confiança baixa."""
        t, c = classify_from_oui("Dell Inc.", "Desktop")
        assert t == "Desktop"
        assert c <= 0.60

    def test_non_ambiguous_vendor_higher_conf(self):
        """Fabricante não-ambíguo → confiança mais alta."""
        t, c = classify_from_oui("Brother Industries", "Impressora")
        assert t == "Impressora"
        assert c >= 0.80

    def test_none_vendor_returns_none(self):
        assert classify_from_oui(None, "Desktop") is None

    def test_none_type_returns_none(self):
        assert classify_from_oui("Brother Industries", None) is None

    def test_ambiguous_vendors_set(self):
        """Intel e Realtek devem estar no conjunto de ambíguos."""
        assert "Intel Corporate" in AMBIGUOUS_VENDORS
        assert "Realtek Semiconductor" in AMBIGUOUS_VENDORS


# ═══════════════════════════════════════════════════════════════════════════════
# Regressões específicas — bugs corrigidos na refactorização
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegressions:
    """Testa bugs específicos corrigidos durante a refactorização do discovery."""

    def test_printer_port9100_no_smb(self):
        """Bug: porta 9100 com SMB era classificada como impressora. Corrigido."""
        result = classify_from_ports({9100, 445, 135})
        # Não deve ser impressora quando há SMB + RPC
        assert result is None or result[0] != "Impressora"

    def test_empty_string_not_in_generic_nic_tuple(self):
        """
        Bug: ("intel", "realtek", ..., "") → "" é sempre substring → qualquer fabricante
        classificava como NIC genérico. Corrigido removendo "" da tupla.
        Verificado: classify_from_oui("Brother Industries", "Impressora") deve dar conf >= 0.80
        """
        t, c = classify_from_oui("Brother Industries", "Impressora")
        assert c >= 0.80, "'' na tupla causaria conf=0.55 para Brother (falso positivo)"

    def test_snmp_windows_server_not_desktop(self):
        """Bug: 'Windows Server 2022' no sysDescr ficava como Desktop. Corrigido."""
        t, c = classify_from_snmp_descr("Microsoft Windows Server 2022 Standard 10.0.20348")
        assert t == "Servidor", f"Windows Server deve ser Servidor, obteve {t}"

    def test_fortiswitch_not_firewall(self):
        """Bug: FortiSwitch (que corre FortiOS) era classificado como Firewall. Corrigido."""
        t, c = classify_from_snmp_descr("FortiSwitch-124E-F v6.4.10")
        assert t == "Switch", f"FortiSwitch deve ser Switch, obteve {t}"

    def test_hostname_case_insensitive(self):
        """Hostname em minúsculas deve funcionar igual a maiúsculas."""
        t1, _ = classify_from_hostname("SW-PISO1")
        t2, _ = classify_from_hostname("sw-piso1")
        assert t1 == t2

    def test_merge_snmp_engine_protected(self):
        """
        Bug: enrich_device_snmp usava confiança hardcoded 0.95 que podia ser
        sobrescrita por classificações de IA. Corrigido com merge_classification.
        """
        device = {
            "type": "Impressora",
            "confidence": 0.97,
            "_class_source": "snmp_engine",
            "needs_review": 0,
        }
        # IA tenta reclassificar como "Outro" com confiança 0.65
        merge_classification(device, "Outro", 0.65, "ai")
        assert device["type"] == "Impressora"  # snmp_engine com 0.97 não deve ser sobrescrito

    def test_merge_source_tracking(self):
        """Verifica que _class_source é actualizado correctamente."""
        d = {"type": "Desconhecido", "confidence": 0.0, "_class_source": "", "needs_review": 1}
        merge_classification(d, "Switch", 0.95, "snmp_engine")
        assert d["_class_source"] == "snmp_engine"


if __name__ == "__main__":
    # Permite correr directamente: python tests/test_classifier.py
    import pytest
    pytest.main([__file__, "-v"])
