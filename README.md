# Socrates Shop

## HTTPS va chung chi public

Du an co san endpoint `/certificate` de nguoi khac xem/tai file chung chi `certs/server.crt`.

Chay HTTPS trong cung mang LAN:

```powershell
$env:JWT_SECRET="your-strong-demo-secret-123456"
$env:SSL_CERT_FILE="certs\server.crt"
$env:SSL_KEY_FILE="certs\server.key"
.\.venv\Scripts\python.exe app.py
```

Sau do nguoi khac co the truy cap:

```text
https://192.168.1.164:5000
https://192.168.1.164:5000/certificate
```

Chi chia se file `certs/server.crt`. Khong chia se `certs/server.key`.

Trang web bán hàng local bằng Flask + SQLite. Bản này không cần Docker, MySQL hoặc Kafka.

## Chạy local

```powershell
cd D:\ProjectMMH
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

Mở trình duyệt:

```text
http://127.0.0.1:5000
```

Database SQLite sẽ tự tạo tại:

```text
local_shop.db
```

## Chức năng hiện có

- Đăng ký tài khoản.
- Đăng nhập và đăng xuất.
- Xem danh sách sản phẩm.
- Thêm sản phẩm vào giỏ hàng.
- Tạo đơn hàng.
- Xác nhận hoặc hủy thanh toán giả lập.
- Xem các đơn hàng gần đây.
- Các endpoint lab để demo MitM, XSS đánh cắp JWT, webhook giả mạo và SQL Injection bằng Burp/ZAP/Postman.

## Demo lỗi bảo mật

Các demo bảo mật không hiển thị trên UI chính. Dùng tool như Burp Suite, OWASP ZAP, Postman hoặc curl theo hướng dẫn:

```text
SECURITY_DEMO.md
```

## Reset dữ liệu local

Tắt server rồi xóa file:

```powershell
Remove-Item .\local_shop.db
```

Sau đó chạy lại:

```powershell
python app.py
```

Các route JWT thử nghiệm vẫn còn trong backend để bạn phát triển phần mật mã sau, nhưng giao diện chính hiện chỉ là web bán hàng bình thường.
