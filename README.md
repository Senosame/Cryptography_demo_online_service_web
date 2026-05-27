# Socrates Shop

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
