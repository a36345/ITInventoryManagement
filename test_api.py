"""
Testes de integração — Flask REST API.
Usa base de dados temporária isolada por teste.
"""

import pytest
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def test_db(tmp_path):
    """Base de dados SQLite temporária cifrada com SQLCipher; descartada após cada teste."""
    import core.database as db_mod
    db_file = tmp_path / "test.db"
    original_path = db_mod.DB_PATH
    # Use a fixed test key so the temp DB stays consistent within the session
    original_key = db_mod._CIPHER_KEY
    db_mod._CIPHER_KEY = "deadbeef" * 8   # 64-char hex test key
    db_mod.close_connections()
    db_mod.DB_PATH = db_file
    db_mod.invalidate_caches()
    db_mod.init_db()
    yield db_file
    db_mod.close_connections()
    db_mod.DB_PATH = original_path
    db_mod._CIPHER_KEY = original_key
    db_mod.invalidate_caches()


@pytest.fixture
def client(test_db):
    """Flask test client sem API key configurada."""
    import api as api_mod
    api_mod.API_KEY = None
    api_mod.app.config["TESTING"] = True
    import core.database as db_mod
    db_mod.init_db()
    with api_mod.app.test_client() as c:
        yield c


@pytest.fixture
def client_with_key(test_db):
    """Flask test client com API key obrigatória."""
    import api as api_mod
    api_mod.API_KEY = "test-secret-key"
    api_mod.app.config["TESTING"] = True
    with api_mod.app.test_client() as c:
        yield c
        api_mod.API_KEY = None


# ── Health ─────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.get_json()
        assert data["status"] == "ok"
        assert "assets" in data
        assert "ts" in data

    def test_health_no_auth_required(self, client_with_key):
        r = client_with_key.get("/api/health")
        assert r.status_code == 200


# ── Stats ──────────────────────────────────────────────────────────────────────

class TestStats:
    def test_stats_returns_counts(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200
        data = r.get_json()
        assert "stats" in data
        assert data["stats"]["total"] == 0
        assert "alerts" in data
        assert "lifecycle" in data

    def test_stats_reflect_inserted_asset(self, client, test_db):
        import core.database as db_mod
        db_mod.upsert_asset({"hostname": "PC-TEST", "type": "Desktop", "status": "Online"})
        r = client.get("/api/stats")
        assert r.get_json()["stats"]["total"] == 1


# ── Assets ─────────────────────────────────────────────────────────────────────

class TestAssets:
    def test_assets_empty_initially(self, client):
        r = client.get("/api/assets")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_asset_appears_after_insert(self, client, test_db):
        import core.database as db_mod
        db_mod.upsert_asset({"hostname": "SRV-01", "type": "Servidor", "status": "Online",
                              "ip_address": "10.0.0.1"})
        r = client.get("/api/assets")
        data = r.get_json()
        assert len(data) == 1
        assert data[0]["hostname"] == "SRV-01"

    def test_filter_by_type(self, client, test_db):
        import core.database as db_mod
        db_mod.upsert_asset({"hostname": "PC-01", "type": "Desktop", "status": "Online"})
        db_mod.upsert_asset({"hostname": "NB-01", "type": "Laptop",  "status": "Online"})
        r = client.get("/api/assets?type=Desktop")
        data = r.get_json()
        assert len(data) == 1
        assert data[0]["hostname"] == "PC-01"

    def test_filter_by_status(self, client, test_db):
        import core.database as db_mod
        db_mod.upsert_asset({"hostname": "PC-ON",  "type": "Desktop", "status": "Online"})
        db_mod.upsert_asset({"hostname": "PC-OFF", "type": "Desktop", "status": "Offline"})
        r = client.get("/api/assets?status=Offline")
        data = r.get_json()
        assert len(data) == 1
        assert data[0]["hostname"] == "PC-OFF"

    def test_search_by_hostname(self, client, test_db):
        import core.database as db_mod
        db_mod.upsert_asset({"hostname": "ALPHA-01", "type": "Desktop", "status": "Online"})
        db_mod.upsert_asset({"hostname": "BETA-01",  "type": "Desktop", "status": "Online"})
        r = client.get("/api/assets?search=ALPHA")
        data = r.get_json()
        assert len(data) == 1
        assert data[0]["hostname"] == "ALPHA-01"

    def test_get_asset_by_id(self, client, test_db):
        import core.database as db_mod
        aid = db_mod.upsert_asset({"hostname": "PC-ID", "type": "Desktop", "status": "Online"})
        r = client.get(f"/api/assets/{aid}")
        assert r.status_code == 200
        assert r.get_json()["hostname"] == "PC-ID"

    def test_get_asset_not_found(self, client):
        r = client.get("/api/assets/99999")
        assert r.status_code == 404

    def test_delete_asset(self, client, test_db):
        import core.database as db_mod
        aid = db_mod.upsert_asset({"hostname": "DEL-01", "type": "Desktop", "status": "Online"})
        r = client.delete(f"/api/assets/{aid}")
        assert r.status_code == 200
        assert r.get_json()["ok"] is True
        assert client.get(f"/api/assets/{aid}").status_code == 404

    def test_delete_asset_not_found(self, client):
        r = client.delete("/api/assets/99999")
        assert r.status_code == 404

    def test_assets_by_type_stats(self, client, test_db):
        import core.database as db_mod
        db_mod.upsert_asset({"hostname": "D1", "type": "Desktop", "status": "Online"})
        db_mod.upsert_asset({"hostname": "D2", "type": "Desktop", "status": "Online"})
        db_mod.upsert_asset({"hostname": "L1", "type": "Laptop",  "status": "Online"})
        r = client.get("/api/assets/stats/by-type")
        data = r.get_json()
        by_type = {row["type"]: row["count"] for row in data}
        assert by_type["Desktop"] == 2
        assert by_type["Laptop"] == 1


# ── Printers ──────────────────────────────────────────────────────────────────

class TestPrinters:
    def test_printers_empty(self, client):
        r = client.get("/api/printers")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_critical_printers_empty(self, client):
        r = client.get("/api/printers/critical")
        assert r.status_code == 200
        assert r.get_json() == []


# ── Alerts ────────────────────────────────────────────────────────────────────

class TestAlerts:
    def test_alerts_empty(self, client):
        r = client.get("/api/alerts")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_alert_appears_after_create(self, client, test_db):
        import core.database as db_mod
        db_mod.create_alert("High", "toner_low", "Toner baixo", "Cyan a 5%")
        r = client.get("/api/alerts")
        data = r.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Toner baixo"

    def test_duplicate_open_alert_not_created(self, client, test_db):
        import core.database as db_mod
        aid = db_mod.upsert_asset({"hostname": "PRT-01", "type": "Impressora", "status": "Online"})
        id1 = db_mod.create_alert("High", "toner_low", "Toner baixo", asset_id=aid)
        id2 = db_mod.create_alert("High", "toner_low", "Toner baixo", asset_id=aid)
        assert id1 == id2
        r = client.get("/api/alerts")
        assert len(r.get_json()) == 1


# ── Consumables ───────────────────────────────────────────────────────────────

class TestConsumables:
    def _create_consumable(self):
        import core.database as db_mod
        db_mod.upsert_consumable({
            "reference": "TN-2420",
            "type": "Toner Preto",
            "compatible_with": "Brother MFC-L2710",
            "stock_qty": 5,
            "stock_min": 2,
        })
        rows = db_mod.get_all_consumables()
        return rows[0]["id"]

    def test_consumables_empty(self, client):
        r = client.get("/api/consumables")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_consumable_appears_after_upsert(self, client, test_db):
        self._create_consumable()
        r = client.get("/api/consumables")
        assert len(r.get_json()) == 1

    def test_low_stock_empty_when_ok(self, client, test_db):
        self._create_consumable()
        r = client.get("/api/consumables/low-stock")
        assert r.get_json() == []

    def test_low_stock_detected(self, client, test_db):
        import core.database as db_mod
        db_mod.upsert_consumable({
            "reference": "TN-LOW", "type": "Toner", "stock_qty": 1, "stock_min": 3
        })
        r = client.get("/api/consumables/low-stock")
        assert len(r.get_json()) == 1

    def test_add_movement_entrada(self, client, test_db):
        cid = self._create_consumable()
        r = client.post(f"/api/consumables/{cid}/movements",
                        json={"qty_delta": 10, "reason": "compra", "reference_doc": "FT-001"})
        assert r.status_code == 201
        assert r.get_json()["ok"] is True

    def test_add_movement_saida(self, client, test_db):
        cid = self._create_consumable()
        r = client.post(f"/api/consumables/{cid}/movements",
                        json={"qty_delta": -2, "reason": "utilização"})
        assert r.status_code == 201

    def test_movement_updates_stock(self, client, test_db):
        import core.database as db_mod
        cid = self._create_consumable()
        client.post(f"/api/consumables/{cid}/movements", json={"qty_delta": 3, "reason": "compra"})
        rows = db_mod.get_all_consumables()
        assert rows[0]["stock_qty"] == 8  # 5 + 3

    def test_get_movements_for_consumable(self, client, test_db):
        cid = self._create_consumable()
        client.post(f"/api/consumables/{cid}/movements", json={"qty_delta": 5, "reason": "compra"})
        client.post(f"/api/consumables/{cid}/movements", json={"qty_delta": -1, "reason": "utilização"})
        r = client.get(f"/api/consumables/{cid}/movements")
        assert r.status_code == 200
        assert len(r.get_json()) == 2

    def test_movement_invalid_delta(self, client, test_db):
        cid = self._create_consumable()
        r = client.post(f"/api/consumables/{cid}/movements", json={"qty_delta": 0})
        assert r.status_code == 400

    def test_movement_missing_delta(self, client, test_db):
        cid = self._create_consumable()
        r = client.post(f"/api/consumables/{cid}/movements", json={"reason": "teste"})
        assert r.status_code == 400

    def test_movement_consumable_not_found(self, client, test_db):
        r = client.post("/api/consumables/99999/movements", json={"qty_delta": 1})
        assert r.status_code == 404

    def test_all_movements_endpoint(self, client, test_db):
        cid = self._create_consumable()
        client.post(f"/api/consumables/{cid}/movements", json={"qty_delta": 2})
        r = client.get("/api/consumables/movements")
        assert r.status_code == 200
        assert len(r.get_json()) == 1


# ── Segurança / API Key ────────────────────────────────────────────────────────

class TestSecurity:
    def test_unauthorized_without_key(self, client_with_key):
        r = client_with_key.get("/api/assets")
        assert r.status_code == 401

    def test_authorized_with_correct_key(self, client_with_key):
        r = client_with_key.get("/api/assets",
                                headers={"X-API-Key": "test-secret-key"})
        assert r.status_code == 200

    def test_unauthorized_with_wrong_key(self, client_with_key):
        r = client_with_key.get("/api/assets",
                                headers={"X-API-Key": "wrong-key"})
        assert r.status_code == 401

    def test_health_always_public(self, client_with_key):
        r = client_with_key.get("/api/health")
        assert r.status_code == 200


# ── Lifecycle ─────────────────────────────────────────────────────────────────

class TestLifecycle:
    def test_lifecycle_empty(self, client):
        r = client.get("/api/lifecycle")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_lifecycle_shows_old_asset(self, client, test_db):
        import core.database as db_mod
        db_mod.upsert_asset({"hostname": "OLD-PC", "type": "Desktop",
                              "status": "Online", "acquisition_year": 2018})
        r = client.get("/api/lifecycle")
        data = r.get_json()
        assert len(data) == 1
        assert data[0]["replace_due"] is True
