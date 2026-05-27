# Security Demo Guide

File này mô tả cách demo các lỗi có chủ đích trong web local. Chỉ dùng trong môi trường lab.

## 1. Man in the Middle

Điều kiện demo:

- Web chạy bằng HTTP: `http://127.0.0.1:5000`
- Login gửi username/password qua request HTTP.
- JWT được trả về trong response login và lưu ở `localStorage`.

Cách demo:

1. Mở Burp Suite hoặc OWASP ZAP.
2. Cấu hình browser proxy `127.0.0.1:8080`.
3. Đăng nhập trên web.
4. Quan sát request/response login trong proxy.

Điểm cần chỉ ra:

- Request body có username/password.
- Response có JWT.
- Các request checkout/webhook có thể bị xem và sửa nếu không dùng HTTPS.

## 2. XSS đánh cắp JWT

Endpoint vulnerable:

```text
POST /api/reviews
GET  /api/reviews
```

Payload mẫu:

```html
<img src=x onerror="alert(localStorage.getItem('mmh_jwt'))">
```

Cách demo bằng Burp/ZAP/Postman:

1. Đăng nhập để app lưu JWT vào `localStorage`.
2. Gửi request:

```http
POST /api/reviews
Content-Type: application/json

{
  "content": "<img src=x onerror=\"alert(localStorage.getItem('mmh_jwt'))\">"
}
```

3. Gọi `GET /api/reviews` để thấy payload đã được lưu.
4. Nếu bạn muốn trình diễn chạy payload trên trình duyệt, tạo tạm một trang/khung render response bằng `innerHTML`.

Lý do lỗi:

- Review lưu input người dùng.
- Frontend render lại bằng `innerHTML`.
- JWT nằm trong `localStorage`, JavaScript đọc được.

## 3. Giả mạo Webhook/Callback

Endpoint vulnerable:

```text
POST /api/payments/webhook
```

Body mẫu:

```json
{
  "order_id": 1,
  "status": "PAID",
  "provider": "ForgedGateway",
  "transaction_id": "FORGED-CALLBACK-001"
}
```

Cách demo bằng Burp/ZAP/Postman:

1. Đăng nhập.
2. Thêm sản phẩm và tạo đơn hàng.
3. Ghi lại order ID.
4. Gửi body mẫu vào `/api/payments/webhook`.
5. Đơn hàng chuyển sang `PAID` dù không có chữ ký webhook.

Lý do lỗi:

- Endpoint webhook không kiểm tra chữ ký HMAC.
- Không kiểm tra timestamp.
- Không chống replay.

## 4. SQL Injection trong Payment Search

Endpoint vulnerable:

```text
GET /api/payments/search-vulnerable?transaction_id=...
```

Payload mẫu:

```sql
' OR '1'='1
```

Cách demo bằng Burp/ZAP/Postman:

1. Tạo ít nhất một đơn và xác nhận thanh toán để có transaction ID.
2. Gọi endpoint:

```text
GET /api/payments/search-vulnerable?transaction_id=' OR '1'='1
```

3. Quan sát field `vulnerable_sql` trong response.
5. Kết quả trả nhiều dòng vì câu SQL bị biến thành điều kiện luôn đúng.

Lý do lỗi:

- Code nối trực tiếp input vào SQL string.
- Không dùng parameterized query.

## Hướng vá khi báo cáo

- Bật HTTPS/TLS.
- Không lưu JWT trong `localStorage`; ưu tiên cookie `HttpOnly`, `Secure`, `SameSite`.
- Escape/sanitize dữ liệu người dùng; không render input bằng `innerHTML`.
- Ký webhook bằng HMAC-SHA256 và kiểm tra timestamp.
- Dùng parameterized query cho mọi SQL statement.
