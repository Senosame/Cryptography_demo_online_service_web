# Huong dan chay Socrates Shop

## 1. Mo terminal tai thu muc du an

```powershell
cd D:\ProjectMMH
```

## 2. Tao moi truong ao

Chi can chay buoc nay lan dau tien.

```powershell
python -m venv .venv
```

## 3. Cai thu vien

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 4. Chay chuong trinh

Tu ban da sua JWT de bat buoc co secret, can set bien moi truong `JWT_SECRET` truoc khi chay app:

```powershell
$env:JWT_SECRET="your-strong-demo-secret-123456"
.\.venv\Scripts\python.exe app.py
```

Luu y: cach set bang `$env:JWT_SECRET=...` chi co hieu luc trong cua so PowerShell hien tai. Neu dong terminal va mo lai, can set lai bien nay.

Neu chay thanh cong, terminal se hien Flask server dang lang nghe o cong `5000`.

Mo trinh duyet va truy cap:

```text
http://127.0.0.1:5000
```

Trang thanh toan rieng nam tai:

```text
http://127.0.0.1:5000/checkout
```

## 5. Dung chuong trinh

Trong terminal dang chay Flask, nhan:

```text
Ctrl + C
```

## Loi thuong gap

### Chua set `JWT_SECRET`

Neu gap loi:

```text
RuntimeError: JWT_SECRET is required
```

Hay set bien moi truong truoc khi chay app:

```powershell
$env:JWT_SECRET="your-strong-demo-secret-123456"
.\.venv\Scripts\python.exe app.py
```

Neu muon luu lau dai cho user Windows:

```powershell
setx JWT_SECRET "your-strong-demo-secret-123456"
```

Sau khi chay `setx`, dong PowerShell va mo lai terminal moi.

### Thieu module `jwt`

Neu gap loi:

```text
ModuleNotFoundError: No module named 'jwt'
```

Hay dam bao ban dang chay bang Python trong `.venv`:

```powershell
.\.venv\Scripts\python.exe app.py
```

Va da cai thu vien:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Cong 5000 da duoc su dung

Neu cong `5000` dang bi chiem, dung chuong trinh Flask dang chay truoc do hoac doi port trong cuoi file `app.py`:

```python
app.run(host="127.0.0.1", port=5001, debug=True)
```

Sau do truy cap:

```text
http://127.0.0.1:5001
```
