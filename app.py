import json
import os
import sqlite3
import time
from functools import wraps

import jwt
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", "group17-demo-secret")

DB_PATH = os.environ.get("SQLITE_DB_PATH", "local_shop.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "jwt-demo-secret")
JWT_ALGORITHM = "HS256"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL,
            image_url TEXT
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total_price REAL NOT NULL,
            items_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            payment_method TEXT NOT NULL DEFAULT 'card',
            gateway_provider TEXT,
            gateway_transaction_id TEXT,
            order_date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )
    cursor.execute("SELECT COUNT(*) AS count FROM products")
    if cursor.fetchone()["count"] == 0:
        cursor.executemany(
            """
            INSERT INTO products (name, description, price, image_url)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("Ban phim co F75", "Ban phim co nho gon, led RGB, phu hop hoc tap va lam viec.", 890000, None),
                ("Chuot gaming X6", "Chuot khong day nhe, cam bien on dinh, pin su dung lau.", 420000, None),
                ("Tai nghe hoc online", "Tai nghe co mic loc tieng on, dung tot cho lop hoc va hop nhom.", 350000, None),
                ("USB Security Key", "Khoa bao mat dung cho dang nhap va demo xac thuc.", 250000, None),
            ],
        )
    conn.commit()
    conn.close()


def publish_payment_event(event):
    # Local mode: no Kafka required. Events are printed so they still show in the terminal.
    app.logger.info("payment-event %s", json.dumps(event, ensure_ascii=False))
    return False


def row_to_dict(row):
    return dict(row) if row else None


def create_jwt(user):
    # Intentionally weak for the lab: static secret, no exp, role is trusted by the client demo.
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "role": user["role"],
        "iat": int(time.time()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def require_jwt(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ").strip()
        if not token:
            return jsonify({"status": "error", "message": "Thieu Bearer token."}), 401
        try:
            claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.InvalidTokenError as exc:
            return jsonify({"status": "error", "message": f"JWT khong hop le: {exc}"}), 401
        request.jwt_claims = claims
        return fn(*args, **kwargs)

    return wrapper


@app.route("/")
def index():
    return render_template("index.html", user=session.get("username"))


@app.get("/api/health")
def health():
    try:
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        sqlite_ok = True
    except sqlite3.Error:
        sqlite_ok = False
    return jsonify({"app": "ok", "db": "sqlite", "sqlite": sqlite_ok, "kafka": "disabled-local"})


@app.get("/api/products")
def products():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, description, price, image_url FROM products ORDER BY id"
    ).fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])


@app.post("/api/register")
def register():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if len(username) < 3 or len(password) < 4:
        return jsonify({"status": "error", "message": "Ten dang nhap hoac mat khau qua ngan."}), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'user')",
            (username, generate_password_hash(password)),
        )
        conn.commit()
        return jsonify({"status": "success", "message": "Dang ky thanh cong."})
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "Ten dang nhap da ton tai."}), 409
    finally:
        conn.close()


@app.post("/api/login")
def login():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    conn = get_db()
    user = conn.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()

    if user and check_password_hash(user["password_hash"], password):
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        token = create_jwt(user)
        return jsonify({"status": "success", "username": user["username"], "jwt": token})

    return jsonify({"status": "error", "message": "Sai tai khoan hoac mat khau."}), 401


@app.post("/api/jwt/login")
def jwt_login():
    return login()


@app.get("/api/jwt/profile")
@require_jwt
def jwt_profile():
    return jsonify({"status": "success", "claims": request.jwt_claims})


@app.get("/api/jwt/insecure-admin")
def insecure_admin():
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return jsonify({"status": "error", "message": "Thieu Bearer token."}), 401

    try:
        # Vulnerable on purpose: signature is not verified for the lab.
        claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.InvalidTokenError as exc:
        return jsonify({"status": "error", "message": f"JWT decode loi: {exc}"}), 401

    if claims.get("role") != "admin":
        return jsonify(
            {
                "status": "error",
                "message": "Can role=admin. Hay thu sua payload JWT va gui lai request bang Burp/ZAP.",
                "claims_seen": claims,
            }
        ), 403

    return jsonify(
        {
            "status": "success",
            "message": "Ban da vao endpoint admin vi server decode JWT ma khong verify chu ky.",
            "claims_seen": claims,
        }
    )


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.post("/api/orders")
def create_order():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "Vui long dang nhap truoc khi thanh toan."}), 401

    data = request.get_json(force=True)
    items = data.get("items") or []
    if not items:
        return jsonify({"status": "error", "message": "Gio hang trong."}), 400

    conn = get_db()
    product_ids = [int(item["id"]) for item in items]
    placeholders = ",".join(["?"] * len(product_ids))
    rows = conn.execute(
        f"SELECT id, name, price FROM products WHERE id IN ({placeholders})",
        tuple(product_ids),
    ).fetchall()
    products_by_id = {row["id"]: row for row in rows}

    normalized_items = []
    total = 0.0
    for item in items:
        product = products_by_id.get(int(item["id"]))
        quantity = max(1, int(item.get("quantity", 1)))
        if not product:
            continue
        total += float(product["price"]) * quantity
        normalized_items.append(
            {
                "product_id": product["id"],
                "name": product["name"],
                "price": float(product["price"]),
                "quantity": quantity,
            }
        )

    if not normalized_items:
        conn.close()
        return jsonify({"status": "error", "message": "Khong tim thay san pham hop le."}), 400

    cursor = conn.execute(
        """
        INSERT INTO orders (user_id, total_price, items_json, status, payment_method)
        VALUES (?, ?, ?, 'PENDING', ?)
        """,
        (
            session["user_id"],
            total,
            json.dumps(normalized_items, ensure_ascii=False),
            data.get("payment_method", "card"),
        ),
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    publish_payment_event(
        {
            "type": "ORDER_PENDING",
            "order_id": order_id,
            "amount": total,
            "payment_method": data.get("payment_method", "card"),
        }
    )

    return jsonify(
        {
            "status": "success",
            "order_id": order_id,
            "amount": total,
            "message": "Don hang da tao o trang thai PENDING.",
        }
    )


@app.post("/api/payments/mock")
def mock_payment_gateway():
    data = request.get_json(force=True)
    order_id = int(data.get("order_id", 0))
    result = data.get("result", "success")
    status = "PAID" if result == "success" else "FAILED"

    payload = {
        "order_id": order_id,
        "status": status,
        "provider": data.get("provider", "MockPay"),
        "transaction_id": f"MOCK-{int(time.time())}-{order_id}",
    }
    return payment_webhook(payload)


@app.post("/api/payments/webhook")
def payment_webhook(payload=None):
    data = payload or request.get_json(force=True)
    order_id = int(data.get("order_id", 0))
    status = data.get("status", "FAILED")
    if status not in {"PAID", "FAILED"}:
        return jsonify({"status": "error", "message": "Trang thai khong hop le."}), 400

    conn = get_db()
    cursor = conn.execute(
        """
        UPDATE orders
        SET status = ?, gateway_provider = ?, gateway_transaction_id = ?
        WHERE id = ?
        """,
        (
            status,
            data.get("provider", "MockPay"),
            data.get("transaction_id"),
            order_id,
        ),
    )
    conn.commit()
    updated = cursor.rowcount
    conn.close()

    event = {
        "type": "PAYMENT_STATUS_UPDATED",
        "order_id": order_id,
        "status": status,
        "provider": data.get("provider", "MockPay"),
        "transaction_id": data.get("transaction_id"),
    }
    kafka_sent = publish_payment_event(event)

    if not updated:
        return jsonify({"status": "error", "message": "Khong tim thay don hang."}), 404

    return jsonify(
        {
            "status": "success",
            "order_status": status,
            "kafka_sent": kafka_sent,
            "message": "Payment Service da cap nhat trang thai. Local mode khong can Kafka.",
        }
    )


@app.get("/api/orders/latest")
def latest_orders():
    if "user_id" not in session:
        return jsonify([])

    conn = get_db()
    rows = conn.execute(
        """
        SELECT id, total_price, status, payment_method, gateway_provider,
               gateway_transaction_id, order_date
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 10
        """,
        (session["user_id"],),
    ).fetchall()
    conn.close()

    return jsonify([row_to_dict(row) for row in rows])


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
