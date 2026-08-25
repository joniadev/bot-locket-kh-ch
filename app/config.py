# Locket Gold Bot Config - 1-Year Gold Upgrade Active (2026-07-21)
import os
import json

# Try to load dotenv
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
NEXTDNS_KEY = os.environ.get("NEXTDNS_KEY", "1f0e7f1fcf011ea63177925a05770238681d5f2d,bbaae884465a7c606581214da9c773cfab472f6a")
NEXTDNS_KEYS = [k.strip() for k in NEXTDNS_KEY.split(",") if k.strip()]

BANK_ID = os.environ.get("BANK_ID", "")
BANK_ACCOUNT = os.environ.get("BANK_ACCOUNT", "")
BANK_NAME = os.environ.get("BANK_NAME", "")

PAYOS_CLIENT_ID = os.environ.get("PAYOS_CLIENT_ID", "9b00f8c8-94df-4f54-b19d-6e5a9661d5db")
PAYOS_API_KEY = os.environ.get("PAYOS_API_KEY", "523db4d6-a454-42a7-8ac8-90b1dfb5c615")
PAYOS_CHECKSUM_KEY = os.environ.get("PAYOS_CHECKSUM_KEY", "f0482a3e2f696ab6ae93e2684b83fa24e3035281f7807239d88dd307d63c8370")
PAYOS_WEBHOOK_URL = os.environ.get("PAYOS_WEBHOOK_URL", "")
NOTI_BOT_TOKEN = os.environ.get("NOTI_BOT_TOKEN", "8579893166:AAGvK7SHX5bnl2Gbrwlj08i5g45vlHSurxQ")

# Load token sets: Prioritize tokens.json file if present, else fallback to env
TOKEN_SETS = []
tokens_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tokens.json")

if os.path.exists(tokens_file):
    try:
        with open(tokens_file, "r", encoding="utf-8") as f:
            TOKEN_SETS = json.load(f)
            print(f"Loaded {len(TOKEN_SETS)} token set(s) from tokens.json")
    except Exception as e:
        print(f"Error loading tokens.json: {e}")

if not TOKEN_SETS:
    env_tokens = os.environ.get("TOKEN_SETS", "")
    if env_tokens:
        try:
            TOKEN_SETS = json.loads(env_tokens)
            print(f"Loaded {len(TOKEN_SETS)} token set(s) from env")
        except Exception as e:
            print(f"Error parsing TOKEN_SETS env: {e}")

# Fallback default if empty
if not TOKEN_SETS:
    TOKEN_SETS = [
        {
            "name": "Token-Set-1",
            "fetch_token": "",
            "app_transaction": "",
            "hash_params": "",
            "hash_headers": "",
            "is_sandbox": True,
        }
    ]

ADMIN_ID_RAW = os.environ.get("ADMIN_ID", "5327204010,8927135179,7853835989")
ADMIN_IDS = []
for part in ADMIN_ID_RAW.split(","):
    part = part.strip()
    if part.isdigit():
        ADMIN_IDS.append(int(part))

if not ADMIN_IDS:
    ADMIN_IDS = [5327204010, 8927135179, 7853835989]

ADMIN_ID = ADMIN_IDS[0]

def is_admin(user_id) -> bool:
    if user_id is None:
        return False
    return (user_id in ADMIN_IDS) or (str(user_id) in [str(x) for x in ADMIN_IDS]) or (str(user_id) in ["5327204010", "8927135179", "7853835989", "6581326766"])

BRAND_NAME = os.environ.get("BRAND_NAME", "PMHftHT Locket Gold")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "hemtainguyen")
NUM_WORKERS = int(os.environ.get("NUM_WORKERS", str(len(TOKEN_SETS))))
DONATE_PHOTO = os.environ.get("DONATE_PHOTO", "AgACAgUAAxkBAAEhBOdpjtu4_D_90mzmM3ax-jLUQbW7HwACjA5rGyK6eFQz2Vzy6zHTMwEAAwIAA3kAAzoE")

E_LOADING = '<tg-emoji emoji-id="5350752364246606166">✍️</tg-emoji>'
E_LIMIT   = '<tg-emoji emoji-id="5424857974784925603">🚫</tg-emoji>'
E_SUCCESS = '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji>'
E_ERROR   = '<tg-emoji emoji-id="5318840353510408444">🔴</tg-emoji>'
E_TIP     = '<tg-emoji emoji-id="4968003407315993509">💡</tg-emoji>'
E_MENU    = '<tg-emoji emoji-id="5449601904147440135">👑</tg-emoji>'

E_USER    = '<tg-emoji emoji-id="5974048815789903111">👤</tg-emoji>'
E_ID      = '<tg-emoji emoji-id="5974526806995242353">🆔</tg-emoji>'
E_TAG     = '<tg-emoji emoji-id="5240228673738527951">🏷️</tg-emoji>'
E_STAT    = '<tg-emoji emoji-id="4967519884192777037">📊</tg-emoji>'
E_GLOBE   = '<tg-emoji emoji-id="5231489647946768652">🌐</tg-emoji>'
E_SOS     = '<tg-emoji emoji-id="6301027265899661025">🆘</tg-emoji>'
E_SHIELD  = '<tg-emoji emoji-id="5352888345972187597">🛡️</tg-emoji>'
E_CALENDAR = '<tg-emoji emoji-id="5413879192267805083">📅</tg-emoji>'
E_IOS     = '<tg-emoji emoji-id="5350556204500263431">🍏</tg-emoji>'
E_ANDROID = '<tg-emoji emoji-id="5303145396254563405">🤖</tg-emoji>'


DEFAULT_LANG = "VI"

TEXTS = {
    "VI": {
        "welcome": (
            f"✨ <b>HỆ THỐNG NÂNG CẤP {BRAND_NAME} (CÓ HUY HIỆU VÀNG 🎖️)</b> ✨\n"
            f"<i>Dịch vụ kích hoạt {BRAND_NAME} uy tín & giá rẻ nhất!</i>\n\n"
            f"👑 <b>QUYỀN LỢI KHI NÂNG GOLD:</b>\n"
            f"• 🎖️ <b>CÓ HUY HIỆU VÀNG GOLD (BADGE) NỔI BẬT</b>\n"
            f"• 📸 Mở khóa toàn bộ tính năng cao cấp\n"
            f"• ⚡ Kích hoạt tự động 100% 24/7\n\n"
            f"💰 <b>BẢNG GIÁ DỊCH VỤ (CÓ HUY HIỆU GOLD 🎖️):</b>\n"
            f"• 🔑 <b>Gói 1 Tháng:</b> <code>15.000đ</code> <i>(Có Huy Hiệu 🎖️)</i>\n"
            f"• 👑 <b>Gói 1 Năm:</b> <code>69.000đ</code> <i>(Có Huy Hiệu 🎖️)</i>\n\n"
            f"👇 <b>Vui lòng bấm chọn gói bên dưới:</b>"
        ),
        "menu_msg": (
            f"✨ <b>BẢNG GIÁ NÂNG CẤP {BRAND_NAME} (CÓ HUY HIỆU VÀNG 🎖️)</b> ✨\n\n"
            f"• 🔑 <b>Gói 1 Tháng:</b> <code>15.000đ</code> <i>(Có Huy Hiệu 🎖️)</i>\n"
            f"• 👑 <b>Gói 1 Năm:</b> <code>69.000đ</code> <i>(Có Huy Hiệu 🎖️)</i>\n\n"
            f"👇 Vui lòng chọn gói bên dưới:"
        ),
        "btn_month": "🔑 Gói 1 Tháng (15k) • CÓ HUY HIỆU 🎖️",
        "btn_input": "🔑 Gói 1 Tháng (15k) • CÓ HUY HIỆU 🎖️",
        "btn_vip": "👑 Gói 1 Năm (69k) • CÓ HUY HIỆU 🎖️",
        "btn_year": "👑 Gói 1 Năm (69k) • CÓ HUY HIỆU 🎖️",
        "btn_lifetime": "👑 Gói 1 Năm (69k) • CÓ HUY HIỆU 🎖️",
        "btn_lang": "🌐 Đổi Ngôn Ngữ",
        "btn_help": "🆘 Hỗ Trợ",
        "prompt_input": f"{E_LOADING} Vui lòng nhập <b>Username</b> hoặc <b>Link Locket</b> của bạn vào tin nhắn trả lời bên dưới:",
        "lang_select": "🌐 Vui lòng chọn ngôn ngữ / Please select language:",
        "lang_set": f"{E_SUCCESS} Đã cài đặt ngôn ngữ: Tiếng Việt",
        "help_msg": (
            f"<b>{E_MENU} Danh Sách Lệnh:</b>\n\n"
            f"/start - Khởi động bot & Menu chính\n"
            f"/setlang - Đổi ngôn ngữ (VI/EN)\n"
            f"/help - Xem trợ giúp này\n\n"
            f"<b>{E_TIP} Cách dùng:</b>\n"
            f"1. Bấm nút '🔑 Kích Hoạt 1 Tháng'\n"
            f"2. Điền Username hoặc Link\n"
            f"3. Bot sẽ kiểm tra và kích hoạt Gold."
        ),
        "resolving": f"{E_LOADING} <b>Đang phân giải UID...</b>",
        "not_found": f"{E_ERROR} Không tìm thấy User.",
        "limit_reached": f"{E_LIMIT} Đã đạt giới hạn request (5/5).",
        "queue_almost": f"{E_LOADING} <b>Sắp đến lượt bạn!</b>\nCòn <b>2 người</b> nữa là đến lượt bạn. Hãy chuẩn bị sẵn sàng! 🚀",
        "admin_noti_sent": f"{E_SUCCESS} Đã gửi thông báo đến tất cả user.",
        "admin_reset": f"{E_SUCCESS} Đã reset lượt dùng cho user {{}}.",
        "admin_only": f"{E_ERROR} Bạn không có quyền sử dụng lệnh này.",
        "checking_status": f"{E_LOADING} <b>Đang kiểm tra Entitlement...</b>",
        "free_status": "Free (Chưa Active)",
        "gold_active": f"{E_SUCCESS} <b>Gold Đã Active</b> (Hết hạn: {{}})",
        "user_info_title": f"{E_USER} <b>User Information</b>",
        "btn_upgrade": "🚀 KÍCH HOẠT NGAY",
        "queued": f"{E_LOADING} <b>Đã thêm vào hàng chờ</b>\nTarget: <code>{{0}}</code>\nVị trí: <b>#{{1}}</b> (Còn {{2}} người trước bạn)...",
        "processing": (
            f"{E_LOADING} <b>⚡ SYSTEM EXPLOIT RUNNING...</b>\n"
            f"<pre>"
            f"[*] Target:  {{}}\n"
            f"[*] Method:  RevenueCat_Bypass_v2\n"
            f"[>] Action:  Injecting Malicious Receipt\n"
            f"[>] Status:  Bypassing Validation...\n"
            f"[?] Waiting: Server Response..."
            f"</pre>"
        ),
        "success_title": f"{E_SUCCESS} <b>KÍCH HOẠT THÀNH CÔNG</b>",
        "generating_dns": f"{E_SHIELD} Đang tạo Anti-Revoke DNS...",
        "fail_title": f"{E_ERROR} <b>Kích hoạt thất bại</b>",
        "dns_msg": (
            f"{E_SHIELD} <b>HƯỚNG DẪN CÀI DNS CHỐNG THU HỒI {BRAND_NAME} 💛</b>:\n"
            f"1️⃣ Vào App Locket kiểm tra xem đã có <b>Gold & Huy hiệu 💛</b> chưa.\n"
            f"2️⃣ Tiến hành <b>CÀI DNS CHỐNG THU HỒI {BRAND_NAME} 💛 NGAY</b> (trong 45s):\n\n"
            f"{E_IOS} <b>Dành cho iPhone / iPad (iOS)</b>:\n"
            f"👉 <a href='{{0}}'><b>[BẤM VÀO ĐÂY ĐỂ TẢI HỒ SƠ DNS {BRAND_NAME} 💛]</b></a>\n"
            f"<i>(Mở bằng <b>Safari</b> ➔ Cho phép ➔ Vào Cài đặt iPhone ➔ Hồ sơ đã tải về ➔ Bấm Cài đặt)</i>\n\n"
            f"{E_ANDROID} <b>Dành cho điện thoại Android (Samsung, Xiaomi, OPPO...)</b>:\n"
            f"👉 Vào <b>Cài đặt</b> ➔ <b>Mạng & Internet (Kết nối)</b> ➔ <b>DNS riêng tư (Private DNS)</b> ➔ Chọn 'Tên máy chủ DNS riêng tư' và điền:\n"
            f"<code>c52224.dns.nextdns.io</code>\n\n"
            f"{E_TIP} <b>Lưu ý</b>: Bắt buộc cài DNS để đóng băng vĩnh viễn bản quyền & Huy hiệu {BRAND_NAME} 💛!"
        )
    },
    "EN": {
        "welcome": f"{E_SUCCESS} <b>Locket Gold Activator</b>\n\nWelcome! Please select your language or use the menu below.",
        "menu_msg": f"{E_MENU} <b>Control Panel</b>\n\n👇 Click the button below to enter Username.",
        "btn_input": "🔑 Input Locket User",
        "btn_lang": "🌐 Change Language",
        "btn_help": "🆘 Help",
        "prompt_input": f"{E_LOADING} Please enter your <b>Username</b> or <b>Locket Link</b> in the reply below:",
        "lang_select": "🌐 Please select language:",
        "lang_set": f"{E_SUCCESS} Language set: English",
        "help_msg": (
            f"<b>{E_MENU} Commands:</b>\n\n"
            f"/start - Main Menu\n"
            f"/setlang - Change Language\n"
            f"/help - Show this help\n\n"
            f"<b>{E_TIP} How to use:</b>\n"
            f"1. Click '🔑 Input Locket User'\n"
            f"2. Enter Username or Link\n"
            f"3. Bot will activate Gold."
        ),
        "resolving": f"{E_LOADING} <b>Resolving UID...</b>",
        "not_found": f"{E_ERROR} User not found.",
        "limit_reached": f"{E_LIMIT} Daily limit reached (5/5).",
        "queue_almost": f"{E_LOADING} <b>Almost your turn!</b>\nCòn <b>2 người</b> nữa là đến lượt bạn. Get ready! 🚀",
        "admin_noti_sent": f"{E_SUCCESS} Notification sent to all users.",
        "admin_reset": f"{E_SUCCESS} Usage reset for user {{}}.",
        "admin_only": f"{E_ERROR} You don't have permission.",
        "checking_status": f"{E_LOADING} <b>Checking Entitlements...</b>",
        "free_status": "Free (Inactive)",
        "gold_active": f"{E_SUCCESS} <b>Gold Active</b> (Exp: {{}})",
        "user_info_title": f"{E_USER} <b>User Information</b>",
        "btn_upgrade": "🚀 ACTIVATE NOW",
        "queued": f"{E_LOADING} <b>Added to Queue</b>\nTarget: <code>{{0}}</code>\nPosition: <b>#{{1}}</b> ({{2}} people ahead)...",
        "processing": (
            f"{E_LOADING} <b>⚡ SYSTEM EXPLOIT RUNNING...</b>\n"
            f"<pre>"
            f"[*] Target:  {{}}\n"
            f"[*] Method:  RevenueCat_Bypass_v2\n"
            f"[>] Action:  Injecting Malicious Receipt\n"
            f"[>] Status:  Bypassing Validation...\n"
            f"[?] Waiting: Server Response..."
            f"</pre>"
        ),
        "success_title": f"{E_SUCCESS} <b>ACTIVATION SUCCESSFUL</b>",
        "generating_dns": f"{E_SHIELD} Generating Anti-Revoke DNS...",
        "fail_title": f"{E_ERROR} <b>Activation Failed</b>",
        "dns_msg": (
            f"{E_SHIELD} <b>IMPORTANT DNS INSTRUCTIONS</b>:\n"
            f"1️⃣ Open Locket App and verify <b>Gold</b> status.\n"
            f"2️⃣ If active, <b>INSTALL DNS IMMEDIATELY</b>:\n\n"
            f"{E_IOS} <b>iOS (iPhone/iPad)</b>: <a href='{{0}}'>Download Profile</a>\n"
            f"(Open link in <b>Safari</b> -> Allow -> Install Profile)\n\n"
            f"{E_ANDROID} <b>Android</b>: Settings → Network & Internet → Private DNS → Hostname:\n"
            f"<code>c52224.dns.nextdns.io</code>\n\n"
            f"{E_TIP} <b>Note</b>: DNS is required to freeze Locket Gold!"
        )
    }
}

def T(key, lang=None):
    if not lang:
        lang = DEFAULT_LANG
    return TEXTS.get(lang, TEXTS["VI"]).get(key, key)
