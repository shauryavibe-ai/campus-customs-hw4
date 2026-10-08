"""Bag + pickup reservations (temporary database copy)."""

import shutil
import sqlite3

import pytest
from fastapi.testclient import TestClient

import db
import main
import security

HOODIE = "basic-hoodie-big-yale"  # stock: XS 15, S 5, M 5, L 8, XL 2, XXL 25; $68
ICE = "ice-hockey-left-chest-hoodie"  # M sold out


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    copy = tmp_path / "campus_customs.db"
    shutil.copy(db.DB_PATH, copy)
    monkeypatch.setattr(db, "DB_PATH", copy)
    monkeypatch.setattr(security, "ITERATIONS", 1_000)
    monkeypatch.setattr(main, "throttle", security.LoginThrottle())


def shopper(email="grace@yale.edu") -> TestClient:
    c = TestClient(main.app)
    c.post("/api/auth/signup", json={"first_name": "Grace", "last_name": "Hopper", "email": email, "password": "Compiler1952"})
    return c


def stock(product_id, size):
    conn = sqlite3.connect(db.DB_PATH)
    q = conn.execute("SELECT quantity FROM inventory WHERE product_id = ? AND size = ?", (product_id, size)).fetchone()[0]
    conn.close()
    return q


def set_stock(product_id, size, qty):
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute("UPDATE inventory SET quantity = ? WHERE product_id = ? AND size = ?", (qty, product_id, size))
    conn.commit()
    conn.close()


def test_guest_check_prices_and_caps_without_saving():
    body = TestClient(main.app).post(
        "/api/bag/check",
        json={"items": [{"product_id": HOODIE, "size": "XL", "quantity": 5}, {"product_id": ICE, "size": "M", "quantity": 1}]},
    ).json()
    hoodie, ice = body["items"]
    assert hoodie["quantity"] == stock(HOODIE, "XL") == 2 and hoodie["status"] == "reduced" and hoodie["line_total"] == 136.0
    assert ice["status"] == "sold_out" and ice["line_total"] == 0
    assert body["count"] == 2 and body["subtotal"] == 136.0
    assert hoodie["image_url"] == f"/media/products/{HOODIE}.jpg" and hoodie["product_url"] == f"/products/{HOODIE}"


def test_unknown_products_and_bad_input():
    c = TestClient(main.app)
    body = c.post("/api/bag/check", json={"items": [{"product_id": "not-a-thing", "size": "M", "quantity": 1}]}).json()
    assert body["items"] == []
    assert c.post("/api/bag/check", json={"items": [{"product_id": HOODIE, "size": "XXXL", "quantity": 1}]}).status_code == 422
    assert c.post("/api/bag/check", json={"items": [{"product_id": HOODIE, "size": "M", "quantity": 0}]}).status_code == 422
    assert c.post("/api/bag/check", json={"items": [{"product_id": "../etc", "size": "M", "quantity": 1}]}).status_code == 422


def test_saved_bag_needs_login():
    guest = TestClient(main.app)
    assert guest.get("/api/bag").status_code == 401
    assert guest.put("/api/bag", json={"items": []}).status_code == 401
    assert guest.post("/api/bag/reserve").status_code == 401


def test_logged_in_bag_is_saved_and_merged_lines():
    c = shopper()
    c.put("/api/bag", json={"items": [{"product_id": HOODIE, "size": "M", "quantity": 2}, {"product_id": HOODIE, "size": "M", "quantity": 1}]})
    body = c.get("/api/bag").json()
    assert len(body["items"]) == 1 and body["items"][0]["quantity"] == 3 and body["subtotal"] == 204.0


def test_bags_are_private():
    a, b = shopper("a@yale.edu"), shopper("b@yale.edu")
    a.put("/api/bag", json={"items": [{"product_id": HOODIE, "size": "M", "quantity": 1}]})
    assert b.get("/api/bag").json()["items"] == []


def test_reserve_creates_reservation_and_empties_bag():
    c = shopper()
    c.put("/api/bag", json={"items": [{"product_id": HOODIE, "size": "L", "quantity": 2}]})
    res = c.post("/api/bag/reserve")
    assert res.status_code == 200
    r = res.json()
    assert r["code"].startswith("CC-") and r["total"] == 136.0 and r["name"] == "Grace Hopper"
    assert "57 Broadway" in r["pickup_address"]
    assert c.get("/api/bag").json()["items"] == []
    conn = sqlite3.connect(db.DB_PATH)
    saved = conn.execute("SELECT code, total, status FROM reservations").fetchall()
    conn.close()
    assert saved == [(r["code"], 136.0, "pending")]
    assert stock(HOODIE, "L") == 8  # inventory is not changed by a reservation


def test_reserve_refuses_when_stock_changed():
    c = shopper()
    c.put("/api/bag", json={"items": [{"product_id": HOODIE, "size": "L", "quantity": 4}]})
    set_stock(HOODIE, "L", 1)  # someone bought most of them meanwhile
    res = c.post("/api/bag/reserve")
    assert res.status_code == 409 and "changed" in res.json()["detail"]
    assert res.json()["bag"]["items"][0]["quantity"] == 1  # bag updated to what's left
    assert c.post("/api/bag/reserve").status_code == 200  # now it goes through


def test_reserve_refuses_sold_out_and_empty():
    c = shopper()
    assert c.post("/api/bag/reserve").status_code == 409  # empty
    c.put("/api/bag", json={"items": [{"product_id": ICE, "size": "M", "quantity": 1}]})
    res = c.post("/api/bag/reserve")
    assert res.status_code == 409 and res.json()["bag"]["items"][0]["status"] == "sold_out"


def test_per_line_cap():
    c = shopper()
    body = c.put("/api/bag", json={"items": [{"product_id": HOODIE, "size": "XXL", "quantity": 10}, {"product_id": HOODIE, "size": "XXL", "quantity": 10}]}).json()
    assert body["items"][0]["quantity"] == 10
