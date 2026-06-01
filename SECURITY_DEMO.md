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

## 3. Token Replay bằng JWT bị đánh cắp

Mục tiêu demo:

- Chứng minh JWT lấy được từ `localStorage` có thể bị dùng lại ở một client khác.
- Chỉ thực hiện trong môi trường lab/local với tài khoản kiểm thử.

Endpoint dùng cho demo JWT trong code hiện tại:

```text
GET /api/jwt/profile
GET /api/jwt/insecure-admin
```

Lưu ý: trong code hiện tại, `/api/orders` và `/api/payments/mock` đang dựa vào Flask session cookie, không dựa vào Bearer JWT. Vì vậy replay bằng header `Authorization: Bearer <token>` nên demo trực tiếp với `/api/jwt/profile`. Nếu hệ thống được đổi sang xác thực Bearer JWT cho order/payment, cùng kỹ thuật này có thể áp dụng cho các API đó.

Cách trích xuất token trong lab:

1. Đăng nhập bằng tài khoản nạn nhân trên web local.
2. Mở DevTools Console trong cùng origin `http://127.0.0.1:5000`.
3. Chạy lệnh:

```js
localStorage.getItem('mmh_jwt')
```

4. Copy chuỗi JWT trả về.

Cách replay bằng Postman/Burp/ZAP:

1. Tạo request mới:

```http
GET http://127.0.0.1:5000/api/jwt/profile
Authorization: Bearer <JWT_VUA_COPY>
```

2. Gửi request từ một client khác, ví dụ trình duyệt ẩn danh, Postman, Burp Repeater hoặc ZAP Manual Request.
3. Quan sát response trả về `claims` của nạn nhân.
4. Kết luận demo: server chấp nhận token bị copy vì token là bearer credential; ai cầm token thì được xem như chủ phiên.

Cách replay bằng PowerShell:

```powershell
$token = "PASTE_JWT_VAO_DAY"
Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/jwt/profile" `
  -Headers @{ Authorization = "Bearer $token" }
```

Kết quả mong đợi:

- Request từ client khác vẫn thành công.
- Response chứa thông tin claim như `sub`, `username`, `role`, `iat`.
- Nếu API nghiệp vụ dùng cùng Bearer JWT và không có kiểm soát bổ sung, kẻ có token có thể gọi API dưới danh nghĩa nạn nhân cho đến khi token hết hạn hoặc bị thu hồi.

Lý do lỗi:

- JWT được lưu trong `localStorage`, nên JavaScript chạy trong origin có thể đọc được.
- Payload XSS ở phần trước có thể lấy token ra khỏi trình duyệt nạn nhân.
- Token không có ràng buộc thiết bị, không có cơ chế thu hồi theo phiên và không có kiểm tra replay.
- JWT demo không có claim `exp`, nên token có thể sống quá lâu trong môi trường lab.

Hướng vá:

- Không lưu access token trong `localStorage`; ưu tiên cookie `HttpOnly`, `Secure`, `SameSite`.
- Dùng access token thời hạn ngắn, có `exp`, `iss`, `aud`, `jti` và kiểm tra đầy đủ ở server.
- Cân nhắc opaque token cho phiên đăng nhập để server có thể thu hồi ngay khi phát hiện bất thường.
- Áp dụng refresh token rotation; nếu refresh token cũ bị dùng lại, thu hồi cả token family.
- Ràng buộc refresh token với thiết bị hoặc client bằng thumbprint phù hợp với mô hình OAuth2/OIDC + PKCE.
- Ghi log và cảnh báo khi cùng một token xuất hiện từ IP, user-agent hoặc thiết bị bất thường.

## 4. Giả mạo Webhook/Callback

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

## 5. SQL Injection trong Payment Search

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
- Dùng access token ngắn hạn hoặc opaque token; bật refresh token rotation và cơ chế thu hồi token.
- Ràng buộc refresh token với thiết bị/client khi phù hợp, ví dụ thumbprint trong luồng OAuth2/OIDC + PKCE.
- Escape/sanitize dữ liệu người dùng; không render input bằng `innerHTML`.
- Ký webhook bằng HMAC-SHA256 và kiểm tra timestamp.
- Dùng parameterized query cho mọi SQL statement.
