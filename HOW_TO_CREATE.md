# Cách tạo web bán hàng local cho đồ án

Tài liệu này mô tả cách dựng lại web bán hàng demo bằng Flask, SQLite, HTML và CSS.

## 1. Cấu trúc thư mục

```text
.
├── app.py
├── requirements.txt
├── README.md
├── HOW_TO_CREATE.md
├── templates/
│   └── index.html
└── static/
    └── style.css
```

## 2. Tạo môi trường Python

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

File `requirements.txt` cần các thư viện:

```text
Flask
Werkzeug
PyJWT
```

## 3. Backend Flask

File `app.py` chịu trách nhiệm:

- Tạo database SQLite `local_shop.db`.
- Tạo bảng `users`, `products`, `orders`.
- Seed sản phẩm mẫu nếu database chưa có dữ liệu.
- Cung cấp API đăng ký, đăng nhập, lấy sản phẩm, tạo đơn hàng và thanh toán giả lập.
- Render giao diện chính từ `templates/index.html`.

Các route chính:

```text
GET  /
GET  /api/products
POST /api/register
POST /api/login
POST /api/orders
POST /api/payments/mock
GET  /api/orders/latest
```

## 4. Frontend HTML/CSS

File `templates/index.html` là giao diện chính:

- Header và form đăng nhập/đăng ký.
- Hero giới thiệu shop.
- Danh sách sản phẩm.
- Giỏ hàng.
- Tạo đơn hàng.
- Xác nhận hoặc hủy thanh toán.
- Danh sách đơn hàng gần đây.

File `static/style.css` chứa toàn bộ giao diện:

- Layout responsive.
- Product cards.
- Cart panel.
- Order status badge.
- Header, hero và footer.

## 5. Chạy web local

```powershell
python app.py
```

Mở trình duyệt:

```text
http://127.0.0.1:5000
```

## 6. Reset dữ liệu

Nếu muốn tạo lại database từ đầu:

```powershell
Remove-Item .\local_shop.db
python app.py
```

## 7. Gợi ý phát triển phần mật mã sau

Sau khi giao diện bán hàng ổn định, có thể bổ sung các phần mật mã:

- JWT login và kiểm tra chữ ký token.
- HTTPS/TLS để chống nghe lén MITM.
- HMAC-SHA256 cho webhook thanh toán.
- CSRF token cho form/API state-changing.
- Hash mật khẩu bằng thuật toán phù hợp và cấu hình mạnh.
