"""Tests for the local catalog web UI. Uses Flask's test client and a
temp-dir copy of the config files - never touches the real config/ files."""

import shutil
from pathlib import Path

import pytest

from grocery_scraper import webui


@pytest.fixture
def client(tmp_path, monkeypatch):
    real_config_dir = Path(__file__).parent.parent / "config"
    tmp_config_dir = tmp_path / "config"
    shutil.copytree(real_config_dir, tmp_config_dir)

    monkeypatch.setattr(webui, "CATALOG_PATH", tmp_config_dir / "catalog.yaml")
    monkeypatch.setattr(webui, "SHOPPING_LIST_PATH", tmp_config_dir / "shopping_list.yaml")
    monkeypatch.setattr(webui, "STORES_PATH", tmp_config_dir / "stores.yaml")

    webui.app.config["TESTING"] = True
    with webui.app.test_client() as c:
        yield c


def test_index_shows_catalog_and_manual_store_column(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Onken Fat Free Vanilla Yogurt" in r.data
    assert b"Iceland price" in r.data


def test_add_product_appears_in_catalog(client):
    client.post("/catalog/add", data={
        "name": "Test Item XYZ", "unit": "each", "default_quantity": "3", "aliases": "a, b",
    })
    r = client.get("/")
    assert b"Test Item XYZ" in r.data


def test_update_manual_price_persists(client):
    client.post(
        "/catalog/Cravendale Filtered Fresh Whole Milk 2L/price",
        data={"store": "Iceland", "price": "2.75"},
    )
    r = client.get("/")
    assert b"2.75" in r.data


def test_delete_removes_product(client):
    client.post("/catalog/add", data={"name": "Delete Me", "unit": "each", "default_quantity": "1", "aliases": ""})
    client.post("/catalog/Delete Me/delete")
    r = client.get("/")
    assert b"Delete Me" not in r.data


def test_select_writes_shopping_list_with_chosen_quantity(client):
    r = client.post(
        "/select",
        data={
            "selected": ["Cravendale Filtered Fresh Whole Milk 2L"],
            "qty__Cravendale Filtered Fresh Whole Milk 2L": "4",
        },
        follow_redirects=True,
    )
    assert b"Wrote 1 items" in r.data
    written = webui.SHOPPING_LIST_PATH.read_text(encoding="utf-8")
    assert "Cravendale Filtered Fresh Whole Milk 2L" in written
    assert "quantity: 4" in written
