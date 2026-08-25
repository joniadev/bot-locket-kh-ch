# 📖 Hướng Dẫn Cài Đặt & Lấy Token Locket Gold

Dự án này là Bot Telegram tự động nâng cấp tài khoản Locket Gold bằng cách bypass/inject receipt giao dịch thông qua API RevenueCat.

Dưới đây là hướng dẫn chi tiết từng bước để cấu hình, lấy token và vận hành bot trên Windows.

---

## 🛠️ Hướng Dẫn Cài Đặt Trên Windows

### Bước 1: Chuẩn bị môi trường Python
1. Đảm bảo máy tính của bạn đã cài đặt **Python 3.9+**. Bạn có thể tải từ [python.org](https://www.python.org/).
2. Mở PowerShell hoặc Command Prompt tại thư mục dự án (`c:\2004\Locket-Gold-main\Locket-Gold-main`) và chạy các lệnh sau:

```powershell
# Tạo môi trường ảo venv
python -m venv venv

# Kích hoạt môi trường ảo
.\venv\Scripts\activate

# Cập nhật pip và cài đặt thư viện cần thiết
python -m pip install --upgrade pip
pip install python-telegram-bot requests aiohttp python-dotenv
```

### Bước 2: Cấu hình biến môi trường (.env)
1. Copy file `.env.example` thành `.env`:
   ```powershell
   copy .env.example .env
   ```
2. Mở file `.env` bằng trình chỉnh sửa văn bản (Notepad, VS Code...) và điền các thông tin của bạn:
   - `BOT_TOKEN`: Token lấy từ [@BotFather](https://t.me/BotFather) khi tạo bot.
   - `NEXTDNS_KEY`: API Key lấy từ tài khoản NextDNS của bạn tại mục **Account Settings** / **Developer**.
   - `ADMIN_ID`: Telegram User ID của bạn (sử dụng các bot như `@userinfobot` để lấy ID).

### Bước 3: Cấu hình Receipt Tokens (tokens.json)
1. Copy file `tokens.json.example` thành `tokens.json`:
   ```powershell
   copy tokens.json.example tokens.json
   ```
2. Mở file `tokens.json` và điền bộ token Locket Gold của bạn. Xem hướng dẫn dump token bên dưới.

### Bước 4: Kiểm tra cấu hình
Trước khi chạy bot chính thức, hãy chạy script kiểm tra chẩn đoán:
```powershell
python test_config.py
```
Nếu script báo mọi thứ thành công (`✅`), bạn đã sẵn sàng chạy bot.

### Bước 5: Khởi động Bot
Chạy bot bằng lệnh:
```powershell
python main.py
```

---

## 🔑 Hướng Dẫn Lấy/Dump Locket Gold Token (Receipt Tokens)

Để bot có thể kích hoạt Gold cho người khác, bạn cần chuẩn bị một tài khoản Locket đã mua gói Gold (hoặc đang trong thời gian dùng thử miễn phí - Free Trial). Sau đó tiến hành dump gói dữ liệu từ thiết bị của bạn để lấy `fetch_token` và `app_transaction`.

### Cách 1: Sử dụng máy ảo iOS hoặc thiết bị đã Jailbreak (Khuyên dùng)
Nếu sử dụng thiết bị iOS đã Jailbreak hoặc dùng Frida:
1. Cài đặt các công cụ bắt gói tin như **HTTP Request Catcher** hoặc **Reqable** / **Charles Proxy**.
2. Đăng nhập tài khoản Locket đã mua Gold của bạn trên thiết bị.
3. Thực hiện thao tác **Restore Purchase** (Khôi phục giao dịch mua) trong ứng dụng Locket.
4. Lọc các request gửi tới domain `api.revenuecat.com/v1/receipts`.
5. Trong phần **Request Body (JSON payload)** của request, tìm các trường sau:
   - `"fetch_token"`: Chuỗi token mã hóa dạng Base64 (bắt đầu bằng `ey...` hoặc chuỗi dài).
   - `"app_transaction"`: Chuỗi Apple App Transaction receipt.
6. Sao chép 2 chuỗi này và điền vào file `tokens.json` tương ứng với các trường `fetch_token` và `app_transaction`.

### Cách 2: Sử dụng Reqable hoặc Charles Proxy trên máy tính & Điện thoại Android
Nếu bạn mua gói Locket Gold thông qua Google Play (Android):
1. Cài đặt **Reqable** hoặc **Charles Proxy** trên máy tính.
2. Cấu hình cài đặt chứng chỉ SSL của Reqable/Charles trên điện thoại Android của bạn để có thể giải mã gói tin HTTPS.
3. Mở app Locket trên Android đã mua Gold, thực hiện thao tác **Khôi phục giao dịch**.
4. Tìm kiếm gói tin POST gửi đến `api.revenuecat.com/v1/receipts` hoặc `api.revenuecat.com/v1/subscribers/...`.
5. Trích xuất thông tin receipt token và nạp vào file cấu hình.

---

## 🛡️ Cơ Chế Hoạt Động & Anti-Revoke (DNS)
1. Khi người dùng nhập Username/Link Locket vào Bot, Bot sẽ gọi API Locket để phân giải lấy UID của user đó.
2. Bot dùng bộ token Gold bạn đã cấu hình (`tokens.json`) và gửi yêu cầu giả lập giao dịch mua/khôi phục tới RevenueCat API cho UID đó.
3. Nếu thành công, RevenueCat sẽ kích hoạt gói **Gold** cho UID đó trong 30 ngày.
4. Để tránh ứng dụng Locket gửi yêu cầu kiểm tra lại hóa đơn gốc của UID đó và phát hiện bypass (dẫn đến mất Gold sau vài giờ), Bot sẽ tự động tạo một profile DNS cá nhân hóa thông qua NextDNS.
5. Profile DNS này sẽ tự động chặn kết nối từ thiết bị đến `revenuecat.com`.
6. Người dùng **bắt buộc** phải cài profile DNS này (thao tác rất đơn giản và an toàn) trên iOS hoặc Android theo hướng dẫn Bot gửi sau khi kích hoạt thành công để giữ trạng thái Locket Gold vĩnh viễn.
