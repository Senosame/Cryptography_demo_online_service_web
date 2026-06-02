import json
import os
import sqlite3
import time
import uuid
from functools import wraps

import jwt
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", "group17-demo-secret")

DB_PATH = os.environ.get("SQLITE_DB_PATH", "local_shop.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "jwt-demo-secret")
JWT_ALGORITHM = "HS256"
UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads")
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

DEFAULT_PRODUCT_IMAGES = {
    "Bàn phím cơ F75": "/static/product-images/keyboard-f75.svg",
    "Chuột gaming X6": "/static/product-images/mouse-x6.svg",
    "Tai nghe học online": "/static/product-images/headset-online.svg",
    "USB Security Key": "/static/product-images/security-key.svg",
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
            seller_id INTEGER,
            store_name TEXT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            image_url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (seller_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total_price REAL NOT NULL,
            items_json TEXT NOT NULL,
            shipping_note TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            payment_method TEXT NOT NULL DEFAULT 'card',
            card_number TEXT,
            gateway_provider TEXT,
            gateway_transaction_id TEXT,
            order_date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cursor.execute("PRAGMA table_info(orders)")
    order_columns = {row["name"] for row in cursor.fetchall()}
    if "shipping_note" not in order_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN shipping_note TEXT")
    if "card_number" not in order_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN card_number TEXT")

    cursor.execute("PRAGMA table_info(products)")
    product_columns = {row["name"] for row in cursor.fetchall()}
    if "seller_id" not in product_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN seller_id INTEGER")
    if "store_name" not in product_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN store_name TEXT")
    if "stock" not in product_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN stock INTEGER NOT NULL DEFAULT 100")
    if "created_at" not in product_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN created_at TEXT")

    cursor.execute("SELECT COUNT(*) AS count FROM products")
    if cursor.fetchone()["count"] == 0:
        cursor.executemany(
            """
            INSERT INTO products (store_name, name, description, price, stock, image_url)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("Socrates Mall", "Bàn phím cơ F75", "Bàn phím cơ nhỏ gọn, LED RGB, phù hợp học tập và làm việc.", 890000, 20, DEFAULT_PRODUCT_IMAGES["Bàn phím cơ F75"]),
                ("Socrates Mall", "Chuột gaming X6", "Chuột không dây nhẹ, cảm biến ổn định, pin sử dụng lâu.", 420000, 35, DEFAULT_PRODUCT_IMAGES["Chuột gaming X6"]),
                ("Socrates Mall", "Tai nghe học online", "Tai nghe có mic lọc tiếng ồn, dùng tốt cho lớp học và họp nhóm.", 350000, 40, DEFAULT_PRODUCT_IMAGES["Tai nghe học online"]),
                ("Socrates Mall", "USB Security Key", "Khóa bảo mật dùng cho đăng nhập và demo xác thực.", 250000, 15, DEFAULT_PRODUCT_IMAGES["USB Security Key"]),
            ],
        )
    for product_name, image_url in DEFAULT_PRODUCT_IMAGES.items():
        cursor.execute(
            """
            UPDATE products
            SET image_url = ?
            WHERE name = ? AND (image_url IS NULL OR image_url = '')
            """,
            (image_url, product_name),
        )
    conn.commit()
    conn.close()


def publish_payment_event(event):
    # Local mode: no Kafka required. Events are printed so they still show in the terminal.
    app.logger.info("payment-event %s", json.dumps(event, ensure_ascii=False))
    return False


def row_to_dict(row):
    return dict(row) if row else None


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def save_product_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    if not filename or not allowed_image(filename):
        raise ValueError("Anh san pham chi ho tro PNG, JPG, JPEG, GIF hoac WEBP.")

    ext = filename.rsplit(".", 1)[1].lower()
    saved_name = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(UPLOAD_FOLDER, saved_name))
    return url_for("static", filename=f"uploads/{saved_name}")


def deduct_order_stock(conn, order):
    items = json.loads(order["items_json"] or "[]")
    if not items:
        return None

    for item in items:
        product_id = int(item["product_id"])
        quantity = int(item["quantity"])
        product = conn.execute(
            "SELECT name, stock FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if not product:
            return "Mot san pham trong don hang khong con ton tai."
        if int(product["stock"]) < quantity:
            return f"San pham {product['name']} chi con {product['stock']} trong kho."

    for item in items:
        conn.execute(
            "UPDATE products SET stock = stock - ? WHERE id = ?",
            (int(item["quantity"]), int(item["product_id"])),
        )
    return None


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


def require_login():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "Vui long dang nhap truoc."}), 401
    return None


@app.route("/")
def index():
    return render_template("index.html", user=session.get("username"))


@app.route("/seller")
def seller_page():
    return render_template("seller.html", user=session.get("username"))


@app.route("/checkout")
def checkout_page():
    return render_template("checkout.html", user=session.get("username"))


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
        """
        SELECT p.id, p.name, p.description, p.price, p.stock, p.image_url, p.store_name,
               u.username AS seller_username
        FROM products p
        LEFT JOIN users u ON u.id = p.seller_id
        ORDER BY p.id DESC
        """
    ).fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])


@app.get("/api/seller/products")
def seller_products():
    auth_error = require_login()
    if auth_error:
        return auth_error

    conn = get_db()
    user = conn.execute(
        "SELECT id, username, role FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    rows = conn.execute(
        """
        SELECT id, name, description, price, stock, image_url, store_name, created_at
        FROM products
        WHERE seller_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return jsonify(
        {
            "status": "success",
            "seller": row_to_dict(user),
            "products": [row_to_dict(row) for row in rows],
        }
    )


@app.post("/api/seller/products")
def create_seller_product():
    auth_error = require_login()
    if auth_error:
        return auth_error

    data = request.form if request.form else request.get_json(force=True)
    store_name = (data.get("store_name") or "").strip()
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    image_url = (data.get("image_url") or "").strip() or None

    try:
        uploaded_image_url = save_product_image(request.files.get("image"))
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    if uploaded_image_url:
        image_url = uploaded_image_url

    try:
        price = float(data.get("price", 0))
    except (TypeError, ValueError):
        price = 0

    try:
        stock = int(data.get("stock", 0))
    except (TypeError, ValueError):
        stock = 0

    if len(store_name) < 3:
        return jsonify({"status": "error", "message": "Ten shop phai co it nhat 3 ky tu."}), 400
    if len(name) < 3 or len(description) < 8 or price <= 0 or stock < 0:
        return jsonify({"status": "error", "message": "Thong tin san pham chua hop le."}), 400

    conn = get_db()
    cursor = conn.execute(
        """
        INSERT INTO products (seller_id, store_name, name, description, price, stock, image_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (session["user_id"], store_name, name, description, price, stock, image_url),
    )
    conn.execute(
        "UPDATE users SET role = 'seller' WHERE id = ? AND role != 'admin'",
        (session["user_id"],),
    )
    conn.commit()
    product_id = cursor.lastrowid
    conn.close()

    return jsonify(
        {
            "status": "success",
            "id": product_id,
            "message": "San pham da duoc dang len san.",
        }
    )


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
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError as exc:
        return jsonify({"status": "error", "message": f"JWT khong hop le: {exc}"}), 401

    if claims.get("role") != "admin":
        return jsonify(
            {
                "status": "error",
                "message": "Can role=admin voi JWT hop le da duoc server verify chu ky.",
                "claims_seen": claims,
            }
        ), 403

    return jsonify(
        {
            "status": "success",
            "message": "JWT hop le va co role=admin.",
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
        f"SELECT id, name, price, stock FROM products WHERE id IN ({placeholders})",
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
        if quantity > int(product["stock"]):
            conn.close()
            return jsonify(
                {
                    "status": "error",
                    "message": f"San pham {product['name']} chi con {product['stock']} trong kho.",
                }
            ), 400
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
        INSERT INTO orders (user_id, total_price, items_json, shipping_note, status, payment_method, card_number)
        VALUES (?, ?, ?, ?, 'PENDING', ?, ?)
        """,
        (
            session["user_id"],
            total,
            json.dumps(normalized_items, ensure_ascii=False),
            data.get("shipping_note", ""),
            data.get("payment_method", "card"),
            data.get("card_number", ""),
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
            "card_number": data.get("card_number", ""),
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
    order = conn.execute(
        "SELECT id, status, items_json FROM orders WHERE id = ?",
        (order_id,),
    ).fetchone()
    if not order:
        conn.close()
        return jsonify({"status": "error", "message": "Khong tim thay don hang."}), 404

    stock_error = None
    if status == "PAID" and order["status"] != "PAID":
        stock_error = deduct_order_stock(conn, order)

    if stock_error:
        conn.rollback()
        conn.close()
        return jsonify({"status": "error", "message": stock_error}), 400

    conn.execute(
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
    conn.close()

    event = {
        "type": "PAYMENT_STATUS_UPDATED",
        "order_id": order_id,
        "status": status,
        "provider": data.get("provider", "MockPay"),
        "transaction_id": data.get("transaction_id"),
    }
    kafka_sent = publish_payment_event(event)

    return jsonify(
        {
            "status": "success",
            "order_status": status,
            "kafka_sent": kafka_sent,
            "message": "Payment Service da cap nhat trang thai. Local mode khong can Kafka.",
        }
    )


@app.get("/api/payments/search-vulnerable")
def vulnerable_payment_search():
    transaction_id = request.args.get("transaction_id", "")
    # Vulnerable on purpose for the lab: raw string interpolation enables SQL injection.
    sql = (
        "SELECT id, total_price, status, payment_method, card_number, gateway_provider, "
        "gateway_transaction_id, order_date FROM orders "
        f"WHERE gateway_transaction_id = '{transaction_id}'"
    )

    conn = get_db()
    try:
        rows = conn.execute(sql).fetchall()
        return jsonify(
            {
                "status": "success",
                "vulnerable_sql": sql,
                "rows": [row_to_dict(row) for row in rows],
            }
        )
    except sqlite3.Error as exc:
        return jsonify({"status": "error", "vulnerable_sql": sql, "message": str(exc)}), 400
    finally:
        conn.close()


@app.post("/api/reviews")
def create_review():
    data = request.get_json(force=True)
    content = data.get("content", "")
    username = session.get("username", "guest")
    user_id = session.get("user_id")

    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO reviews (user_id, username, content) VALUES (?, ?, ?)",
        (user_id, username, content),
    )
    conn.commit()
    review_id = cursor.lastrowid
    conn.close()
    return jsonify({"status": "success", "id": review_id, "message": "Review saved."})


@app.get("/api/reviews")
def reviews():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, username, content, created_at FROM reviews ORDER BY id DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])


@app.get("/api/orders/latest")
def latest_orders():
    if "user_id" not in session:
        return jsonify([])

    conn = get_db()
    rows = conn.execute(
        """
        SELECT id, total_price, shipping_note, status, payment_method, card_number, gateway_provider,
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
