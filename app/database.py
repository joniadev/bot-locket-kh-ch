import os
import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone

DB_NAME = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=5000;")
    c.execute('''CREATE TABLE IF NOT EXISTS usage_logs (
                    user_id INTEGER,
                    date TEXT,
                    count INTEGER,
                    PRIMARY KEY (user_id, date)
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    language TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS bot_config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS request_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    uid TEXT,
                    status TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_req_status ON request_logs(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_req_user ON request_logs(user_id)")
    c.execute('''CREATE TABLE IF NOT EXISTS bot_users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pending_payments (
                    order_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    uid TEXT,
                    username TEXT,
                    chat_id INTEGER,
                    message_id INTEGER,
                    status TEXT,
                    used INTEGER DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
    try:
        c.execute("ALTER TABLE pending_payments ADD COLUMN used INTEGER DEFAULT 0")
    except Exception:
        pass
    c.execute('''CREATE TABLE IF NOT EXISTS vip_users (
                    user_id INTEGER PRIMARY KEY,
                    expires_at INTEGER
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS username_cache (
                    username TEXT PRIMARY KEY,
                    uid TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (
                    referrer_id INTEGER,
                    referred_id INTEGER PRIMARY KEY,
                    status TEXT DEFAULT 'completed',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_credits (
                    user_id INTEGER PRIMARY KEY,
                    credits INTEGER DEFAULT 0
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ctv_users (
                    user_id INTEGER PRIMARY KEY,
                    expires_at INTEGER,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )''')
    conn.commit()
    conn.close()
    
    sync_supabase_pull()
    restore_db_from_backup()

DB_BACKUP_FILE = "db_backup.json"

def sync_supabase_push(data_dict):
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.environ.get("SUPABASE_KEY", "")
    if not supabase_url or not supabase_key:
        return
    try:
        import urllib.request
        url = f"{supabase_url}/rest/v1/bot_backups?on_conflict=id"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }
        payload = json.dumps({"id": "db_backup", "data": json.dumps(data_dict), "updated_at": int(time.time())}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            pass
        print("☁️ [SUPABASE] Auto-synced database backup to Supabase Cloud!")
    except Exception as e:
        print(f"⚠️ [SUPABASE] Push failed: {e}")

def sync_supabase_pull():
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.environ.get("SUPABASE_KEY", "")
    if not supabase_url or not supabase_key:
        return
    try:
        import urllib.request
        url = f"{supabase_url}/rest/v1/bot_backups?id=eq.db_backup&select=data"
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}"
        }
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if res_data and isinstance(res_data, list) and len(res_data) > 0:
                raw_json = res_data[0].get("data")
                if raw_json:
                    parsed = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
                    with open(DB_BACKUP_FILE, "w", encoding="utf-8") as f:
                        json.dump(parsed, f, indent=2)
                    print("☁️ [SUPABASE] Successfully pulled latest database backup from Supabase Cloud!")
    except Exception as e:
        print(f"⚠️ [SUPABASE] Pull failed: {e}")

def backup_db_to_json():
    """Backup entire SQLite state (VIP, payments, requests, config, CTV, credits) to db_backup.json"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        c.execute("SELECT user_id, expires_at FROM vip_users")
        vip_users = c.fetchall()
        
        c.execute("SELECT order_id, user_id, uid, username, chat_id, message_id, status, used, timestamp FROM pending_payments")
        pending_payments = c.fetchall()
        
        c.execute("SELECT user_id, uid, status, timestamp FROM request_logs ORDER BY id DESC LIMIT 100")
        request_logs = c.fetchall()
        
        c.execute("SELECT key, value FROM bot_config")
        bot_config = c.fetchall()
        
        c.execute("SELECT user_id, expires_at FROM ctv_users")
        ctv_users = c.fetchall()
        
        c.execute("SELECT user_id, credits FROM user_credits")
        user_credits = c.fetchall()
        
        conn.close()
        
        data = {
            "vip_users": vip_users,
            "pending_payments": pending_payments,
            "request_logs": request_logs,
            "bot_config": bot_config,
            "ctv_users": ctv_users,
            "user_credits": user_credits,
            "backup_timestamp": int(time.time())
        }
        
        with open(DB_BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        sync_supabase_push(data)
            
    except Exception as e:
        print(f"Error backing up DB to JSON: {e}")

def restore_db_from_backup():
    """Restore database tables from db_backup.json if SQLite instance restarts"""
    if not os.path.exists(DB_BACKUP_FILE):
        return
        
    try:
        with open(DB_BACKUP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        # Restore VIP Users
        for row in data.get("vip_users", []):
            c.execute("INSERT OR REPLACE INTO vip_users (user_id, expires_at) VALUES (?, ?)", (row[0], row[1]))
            
        # Restore Pending Payments
        for row in data.get("pending_payments", []):
            order_id, user_id, uid, username, chat_id, message_id, status = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
            used = row[7] if len(row) > 7 else 0
            ts = row[8] if len(row) > 8 else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute(
                "INSERT OR REPLACE INTO pending_payments (order_id, user_id, uid, username, chat_id, message_id, status, used, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (order_id, user_id, uid, username, chat_id, message_id, status, used, ts)
            )
            
        # Restore Request Logs
        for row in data.get("request_logs", []):
            c.execute(
                "INSERT INTO request_logs (user_id, uid, status, timestamp) VALUES (?, ?, ?, ?)",
                (row[0], row[1], row[2], row[3])
            )
            
        # Restore Bot Config
        for row in data.get("bot_config", []):
            c.execute("INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)", (row[0], row[1]))
            
        # Restore CTV Users
        for row in data.get("ctv_users", []):
            c.execute("INSERT OR REPLACE INTO ctv_users (user_id, expires_at) VALUES (?, ?)", (row[0], row[1]))
            
        # Restore User Credits
        for row in data.get("user_credits", []):
            c.execute("INSERT OR REPLACE INTO user_credits (user_id, credits) VALUES (?, ?)", (row[0], row[1]))
            
        conn.commit()
        conn.close()
        print("✅ Successfully restored entire database state from db_backup.json!")
    except Exception as e:
        print(f"Error restoring DB from backup: {e}")

def get_cached_uid(username):
    if not username:
        return None
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT uid FROM username_cache WHERE username = ?", (username.lower().strip(),))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None

def get_cached_username_by_uid(uid):
    if not uid:
        return None
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT username FROM username_cache WHERE uid = ? OR username = ?", (str(uid).strip(), str(uid).strip()))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None

def cache_username_uid(username, uid):
    if not username or not uid:
        return
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO username_cache (username, uid) VALUES (?, ?)", (username.lower().strip(), uid.strip()))
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_user_usage(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT count FROM usage_logs WHERE user_id = ? AND date = ?", (user_id, today))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def increment_usage(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    
    c.execute("SELECT count FROM usage_logs WHERE user_id = ? AND date = ?", (user_id, today))
    result = c.fetchone()
    
    if result:
        new_count = result[0] + 1
        c.execute("UPDATE usage_logs SET count = ? WHERE user_id = ? AND date = ?", (new_count, user_id, today))
    else:
        c.execute("INSERT INTO usage_logs (user_id, date, count) VALUES (?, ?, ?)", (user_id, today, 1))
        
    conn.commit()
    conn.close()

def check_can_request(user_id, max_limit=5):
    from app.config import ADMIN_ID
    if user_id == ADMIN_ID or str(user_id) in [str(ADMIN_ID), "7853835989"] or is_ctv(user_id):
        return True
    current = get_user_usage(user_id)
    return current < max_limit

def set_lang(user_id, lang):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO user_settings (user_id, language) VALUES (?, ?)", (user_id, lang))
    conn.commit()
    conn.close()

def get_lang(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT language FROM user_settings WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def register_user(user_id, username=None, first_name=None):
    if not user_id:
        return
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS bot_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            INSERT INTO bot_users (user_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = COALESCE(EXCLUDED.username, bot_users.username),
                first_name = COALESCE(EXCLUDED.first_name, bot_users.first_name)
        """, (user_id, username, first_name))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error registering bot user: {e}")

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT user_id FROM (
            SELECT user_id FROM bot_users
            UNION SELECT user_id FROM user_settings
            UNION SELECT user_id FROM usage_logs
            UNION SELECT user_id FROM request_logs
            UNION SELECT user_id FROM pending_payments
            UNION SELECT user_id FROM vip_users
            UNION SELECT user_id FROM ctv_users
            UNION SELECT referrer_id AS user_id FROM referrals
            UNION SELECT referred_id AS user_id FROM referrals
        ) WHERE user_id IS NOT NULL AND user_id != 0
    """)
    users = [row[0] for row in c.fetchall() if row[0]]
    conn.close()
    return users

def reset_usage(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("DELETE FROM usage_logs WHERE user_id = ? AND date = ?", (user_id, today))
    conn.commit()
    conn.close()

def set_config(key, value):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)", (str(key), str(value)))
    conn.commit()
    conn.close()
    backup_db_to_json()

def get_config(key, default=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM bot_config WHERE key = ?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else default

def log_request(user_id, uid, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO request_logs (user_id, uid, status) VALUES (?, ?, ?)", (user_id, uid, status))
    conn.commit()
    conn.close()
    if status == "SUCCESS":
        try:
            curr = int(get_config("cumulative_success_count", 0))
            set_config("cumulative_success_count", str(curr + 1))
        except Exception:
            pass
    backup_db_to_json()

def get_stats():
    return get_detailed_stats()

def get_detailed_stats():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Request stats
    c.execute("SELECT COUNT(*) FROM request_logs")
    total_requests = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM request_logs WHERE status = 'SUCCESS'")
    db_success = c.fetchone()[0]
    cum_success = int(get_config("cumulative_success_count", 0))
    success_requests = max(db_success, cum_success)
    
    c.execute("SELECT COUNT(*) FROM request_logs WHERE status != 'SUCCESS'")
    fail_requests = c.fetchone()[0]
    
    # Total unique users across all tables
    c.execute("SELECT DISTINCT user_id FROM (SELECT user_id FROM request_logs UNION SELECT user_id FROM pending_payments UNION SELECT user_id FROM user_settings UNION SELECT user_id FROM vip_users UNION SELECT user_id FROM usage_logs UNION SELECT referrer_id AS user_id FROM referrals UNION SELECT referred_id AS user_id FROM referrals)")
    all_user_ids = [row[0] for row in c.fetchall() if row[0]]
    total_users_count = len(all_user_ids)
    
    # Approved payments revenue
    c.execute("SELECT order_id FROM pending_payments WHERE status = 'APPROVED'")
    approved_orders = [row[0] for row in c.fetchall()]
    
    month_orders_count = sum(1 for oid in approved_orders if str(oid).startswith("M"))
    year_orders_count = sum(1 for oid in approved_orders if str(oid).startswith("Y") or str(oid).startswith("V"))
    lifetime_orders_count = sum(1 for oid in approved_orders if str(oid).startswith("L"))
    
    # Active VIP users
    import time
    now = int(time.time())
    c.execute("SELECT COUNT(*) FROM vip_users WHERE expires_at > ?", (now,))
    active_vips = c.fetchone()[0]
    
    conn.close()
    
    price_month = int(get_config("price_month", 79000))
    price_year = int(get_config("price_year", 79000))
    price_lifetime = int(get_config("price_lifetime", 89000))
    
    month_revenue = month_orders_count * price_month
    year_revenue = year_orders_count * price_year
    lifetime_revenue = lifetime_orders_count * price_lifetime
    total_revenue = month_revenue + year_revenue + lifetime_revenue
    
    return {
        "total_users": total_users_count,
        "user_ids": all_user_ids,
        "total_requests": total_requests,
        "success_requests": success_requests,
        "fail_requests": fail_requests,
        "active_vips": active_vips,
        "month_orders_count": month_orders_count,
        "single_orders_count": year_orders_count,
        "vip_orders_count": lifetime_orders_count,
        "month_revenue": month_revenue,
        "single_revenue": year_revenue,
        "vip_revenue": lifetime_revenue,
        "total_revenue": total_revenue
    }

def get_top_users(limit=10):
    """Get top customers/CTVs who performed the most successful Gold upgrades"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT user_id, COUNT(*) as count 
        FROM request_logs 
        WHERE status = 'SUCCESS' 
        GROUP BY user_id 
        ORDER BY count DESC 
        LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    
    top_list = []
    from app.config import ADMIN_ID
    for uid, count in rows:
        role = "Khách Hàng VIP"
        if uid == ADMIN_ID or str(uid) in [str(ADMIN_ID), "7853835989"]:
            role = "👑 Admin Server"
        elif is_ctv(uid):
            role = "⭐ Cộng Tác Viên"
            
        top_list.append({
            "user_id": uid,
            "count": count,
            "role": role
        })
    return top_list

from datetime import datetime, timedelta, timezone
VN_TZ = timezone(timedelta(hours=7))

def format_vn_time(ts_val):
    if not ts_val:
        return "N/A"
    try:
        if isinstance(ts_val, (int, float)):
            dt = datetime.fromtimestamp(ts_val, tz=timezone.utc).astimezone(VN_TZ)
            return dt.strftime("%H:%M:%S %d/%m/%Y")
        elif isinstance(ts_val, str):
            dt_utc = datetime.strptime(ts_val.split('.')[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            dt_vn = dt_utc.astimezone(VN_TZ)
            return dt_vn.strftime("%H:%M:%S %d/%m/%Y")
    except Exception:
        pass
    return str(ts_val)

def get_recent_transactions(limit=50):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT order_id, user_id, uid, username, status, timestamp FROM pending_payments ORDER BY rowid DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    
    price_month = int(get_config("price_month", 15000))
    price_year = int(get_config("price_year", 69000))
    price_lifetime = int(get_config("price_lifetime", 89000))
    
    result = []
    for r in rows:
        order_id = r[0]
        if str(order_id).startswith("L"):
            amount = price_lifetime
            pkg_name = f"VIP Vĩnh Viễn ({price_lifetime//1000}k)"
        elif str(order_id).startswith("M"):
            amount = price_month
            pkg_name = f"VIP 1 Tháng ({price_month//1000}k có huy hiệu)"
        else:
            amount = price_year
            pkg_name = f"VIP 1 Năm ({price_year//1000}k)"
            
        result.append({
            'order_id': order_id,
            'user_id': r[1],
            'uid': r[2],
            'username': r[3],
            'status': r[4],
            'timestamp': format_vn_time(r[5]),
            'package': pkg_name,
            'amount': amount
        })
    return result

def get_users_table_data(limit=100):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT DISTINCT user_id FROM (SELECT user_id FROM request_logs UNION SELECT user_id FROM pending_payments UNION SELECT user_id FROM user_settings UNION SELECT user_id FROM vip_users) LIMIT ?", (limit,))
    uids = [row[0] for row in c.fetchall() if row[0]]
    
    import time
    now = int(time.time())
    result = []
    for uid in uids:
        c.execute("SELECT expires_at FROM vip_users WHERE user_id = ?", (uid,))
        vip_row = c.fetchone()
        is_vip_user = False
        exp_str = "Chưa đăng ký"
        if vip_row and vip_row[0] > now:
            is_vip_user = True
            exp_str = format_vn_time(vip_row[0])
            
        c.execute("SELECT COUNT(*) FROM request_logs WHERE user_id = ?", (uid,))
        total_requests = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM pending_payments WHERE user_id = ? AND status = 'APPROVED'", (uid,))
        approved_payments = c.fetchone()[0]
        
        result.append({
            'user_id': uid,
            'is_vip': is_vip_user,
            'vip_expires': exp_str,
            'total_requests': total_requests,
            'approved_payments': approved_payments
        })
    conn.close()
    return result

def add_pending_payment(order_id, user_id, uid, username, chat_id, message_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO pending_payments (order_id, user_id, uid, username, chat_id, message_id, status) VALUES (?, ?, ?, ?, ?, ?, 'PENDING')",
              (order_id, user_id, uid, username, chat_id, message_id))
    conn.commit()
    conn.close()
    backup_db_to_json()

def get_pending_payment(order_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, uid, username, chat_id, message_id, status FROM pending_payments WHERE order_id = ?", (order_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            'user_id': row[0],
            'uid': row[1],
            'username': row[2],
            'chat_id': row[3],
            'message_id': row[4],
            'status': row[5]
        }
    return None

def update_payment_status(order_id, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE pending_payments SET status = ? WHERE order_id = ?", (status, order_id))
    conn.commit()
    conn.close()
    backup_db_to_json()

def get_unused_approved_order(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT order_id FROM pending_payments WHERE user_id = ? AND status = 'APPROVED' AND (used IS NULL OR used = 0) ORDER BY rowid ASC LIMIT 1", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {'order_id': row[0]}
    return None

def mark_order_used(order_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE pending_payments SET used = 1 WHERE order_id = ?", (order_id,))
    conn.commit()
    conn.close()
    backup_db_to_json()

def add_vip(user_id, days=365):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    import time
    c.execute("SELECT expires_at FROM vip_users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    now = int(time.time())
    
    if days >= 3000:
        new_expiry = now + (3650 * 86400)
    else:
        # If user currently has lifetime (> 3000 days), override to specified 1-year duration
        if row and row[0] > now + (3000 * 86400):
            new_expiry = now + (days * 86400)
        elif row and row[0] > now:
            new_expiry = row[0] + (days * 86400)
        else:
            new_expiry = now + (days * 86400)
            
    c.execute("INSERT OR REPLACE INTO vip_users (user_id, expires_at) VALUES (?, ?)", (user_id, new_expiry))
    conn.commit()
    conn.close()
    backup_db_to_json()
    return new_expiry

def remove_vip(user_id):
    """Remove VIP status for a specific user ID (Revoke VIP)"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM vip_users WHERE user_id = ?", (user_id,))
    c.execute("UPDATE pending_payments SET status = 'EXPIRED' WHERE user_id = ? AND status = 'APPROVED'", (user_id,))
    conn.commit()
    conn.close()
    backup_db_to_json()

def get_expired_vips():
    """Get all VIP users whose subscription has passed the expiration timestamp"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = int(time.time())
    c.execute("SELECT user_id, expires_at FROM vip_users WHERE expires_at < ?", (now,))
    expired = c.fetchall()
    conn.close()
    return expired

def is_vip(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    import time
    c.execute("SELECT expires_at FROM vip_users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0] > int(time.time())
    return False

def get_vip_expiry(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT expires_at FROM vip_users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        import time
        from datetime import datetime
        now = int(time.time())
        if row[0] > now + (3000 * 86400):
            return "Vĩnh Viễn (Trọn Đời)"
        dt = datetime.fromtimestamp(row[0])
        return dt.strftime("%d/%m/%Y %H:%M")
    return None

def process_referral(referrer_id, referred_id):
    if not referrer_id or not referred_id or str(referrer_id) == str(referred_id):
        return False, False
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT referrer_id FROM referrals WHERE referred_id = ?", (referred_id,))
        if c.fetchone():
            conn.close()
            return False, False
            
        c.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (referrer_id, referred_id))
        c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (referrer_id,))
        total_count = c.fetchone()[0]
        
        credit_rewarded = False
        if total_count % 5 == 0:
            c.execute("INSERT INTO user_credits (user_id, credits) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET credits = credits + 1", (referrer_id,))
            credit_rewarded = True
            
        conn.commit()
        conn.close()
        return True, credit_rewarded
    except Exception as e:
        print(f"Referral error: {e}")
        return False, False

def get_user_credits(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT credits FROM user_credits WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception:
        return 0

def use_credit(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT credits FROM user_credits WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row and row[0] > 0:
            c.execute("UPDATE user_credits SET credits = credits - 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            return True
        conn.close()
        return False
    except Exception:
        return False

def get_referral_stats(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
        total_invited = c.fetchone()[0]
        c.execute("SELECT credits FROM user_credits WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        credits = row[0] if row else 0
        conn.close()
        return {"total_invited": total_invited, "credits": credits}
    except Exception:
        return {"total_invited": 0, "credits": 0}

CTV_JSON_FILE = "ctv_data.json"
HARDCODED_CTV_IDS = ["5327204010", "6685744035", "5624402624"]

def sync_ctv_env():
    """Load CTV data from database, db_backup.json, ctv_data.json, and env into SQLite ctv_users table without losing any ID"""
    ctv_dict = {}
    now = int(time.time())
    default_exp = now + (29 * 86400)
    
    # 0. Always include Hardcoded CTV IDs from code
    for h_id in HARDCODED_CTV_IDS:
        ctv_dict[str(h_id)] = default_exp
    
    # 1. Read existing active CTVs directly from SQLite database
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id, expires_at FROM ctv_users WHERE expires_at > ?", (now,))
        for r in c.fetchall():
            ctv_dict[str(r[0])] = int(r[1])
        conn.close()
    except Exception:
        pass

    # 2. Read from db_backup.json
    if os.path.exists(DB_BACKUP_FILE):
        try:
            with open(DB_BACKUP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                b_ctvs = data.get("ctv_users", [])
                for item in b_ctvs:
                    if len(item) >= 2 and int(item[1]) > now:
                        ctv_dict[str(item[0])] = int(item[1])
        except Exception:
            pass

    # 3. Read from ctv_data.json
    if os.path.exists(CTV_JSON_FILE):
        try:
            with open(CTV_JSON_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                for k, v in d.items():
                    if int(v) > now:
                        ctv_dict[str(k)] = int(v)
        except Exception:
            pass
            
    # 4. Read from os.environ (CTV_DATA, CTV_IDS, etc.)
    env_ctv = os.environ.get("CTV_DATA", "")
    if env_ctv:
        try:
            env_dict = json.loads(env_ctv.strip("'\""))
            for k, v in env_dict.items():
                if int(v) > now:
                    ctv_dict[str(k)] = int(v)
        except Exception:
            pass

    for env_key in ["CTV_IDS", "CTV_USERS", "CTV_LIST"]:
        raw_val = os.environ.get(env_key, "")
        if raw_val:
            for item in raw_val.replace(";", ",").replace("\n", ",").split(","):
                item_clean = item.strip()
                if item_clean.isdigit():
                    if item_clean not in ctv_dict:
                        ctv_dict[item_clean] = default_exp

    env_path = ".env"
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if line_str.startswith("CTV_DATA="):
                        val_str = line_str.split("=", 1)[1].strip("'\"")
                        try:
                            d = json.loads(val_str)
                            for k, v in d.items():
                                if int(v) > now:
                                    ctv_dict[str(k)] = int(v)
                        except Exception:
                            pass
                    elif line_str.startswith("CTV_IDS=") or line_str.startswith("CTV_USERS=") or line_str.startswith("CTV_LIST="):
                        val_str = line_str.split("=", 1)[1].strip("'\"")
                        for item in val_str.replace(";", ",").split(","):
                            item_clean = item.strip()
                            if item_clean.isdigit() and item_clean not in ctv_dict:
                                ctv_dict[item_clean] = default_exp
        except Exception:
            pass

    if ctv_dict:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        for uid_str, exp_ts in ctv_dict.items():
            try:
                uid_int = int(uid_str)
                exp_int = int(exp_ts)
                if exp_int > now:
                    c.execute("INSERT OR REPLACE INTO ctv_users (user_id, expires_at) VALUES (?, ?)", (uid_int, exp_int))
            except Exception:
                pass
        conn.commit()
        conn.close()

def save_ctv_to_env_and_file(user_id=None, expires_at=None, action="add"):
    """Persist all active CTVs from database into .env file, os.environ, and ctv_data.json"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = int(time.time())
    c.execute("SELECT user_id, expires_at FROM ctv_users WHERE expires_at > ?", (now,))
    rows = c.fetchall()
    conn.close()

    ctv_dict = {str(r[0]): int(r[1]) for r in rows}
    
    if action == "add" and user_id and expires_at:
        ctv_dict[str(user_id)] = int(expires_at)
    elif action == "remove" and user_id:
        ctv_dict.pop(str(user_id), None)
        
    try:
        with open(CTV_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(ctv_dict, f, indent=2)
    except Exception as e:
        print(f"Error saving ctv_data.json: {e}")
        
    json_str = json.dumps(ctv_dict)
    os.environ["CTV_DATA"] = json_str
    
    env_path = ".env"
    if os.path.exists(env_path):
        try:
            lines = []
            found = False
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = []
            for line in lines:
                if line.startswith("CTV_DATA="):
                    new_lines.append(f"CTV_DATA='{json_str}'\n")
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f"CTV_DATA='{json_str}'\n")
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        except Exception as e:
            print(f"Error updating .env file for CTV: {e}")

def add_ctv(user_id, days=29):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = int(time.time())
    expires_at = now + (days * 86400)
    c.execute("INSERT OR REPLACE INTO ctv_users (user_id, expires_at) VALUES (?, ?)", (user_id, expires_at))
    conn.commit()
    conn.close()
    
    save_ctv_to_env_and_file(user_id, expires_at, action="add")
    backup_db_to_json()
    return expires_at

def remove_ctv(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM ctv_users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    save_ctv_to_env_and_file(user_id, 0, action="remove")
    backup_db_to_json()

def is_ctv(user_id):
    from app.config import ADMIN_ID
    if user_id == ADMIN_ID or str(user_id) in [str(ADMIN_ID), "7853835989"]:
        return True
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = int(time.time())
    c.execute("SELECT expires_at FROM ctv_users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        if row[0] > now:
            return True
        else:
            remove_ctv(user_id)
    return False

def get_ctv_info(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = int(time.time())
    c.execute("SELECT expires_at FROM ctv_users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0] > now:
        diff = row[0] - now
        days = diff // 86400
        hours = (diff % 86400) // 3600
        minutes = (diff % 3600) // 60
        seconds = diff % 60
        countdown_str = f"{days} Ngày {hours:02d} Giờ {minutes:02d} Phút {seconds:02d} Giây"
        return {
            "is_ctv": True,
            "expires_at": row[0],
            "remaining_seconds": diff,
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "countdown_str": countdown_str
        }
    return {"is_ctv": False}

def get_all_ctvs():
    try:
        sync_ctv_env()
    except Exception:
        pass
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = int(time.time())
    c.execute("SELECT user_id, expires_at FROM ctv_users WHERE expires_at > ? ORDER BY expires_at DESC", (now,))
    rows = c.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        uid = r[0]
        exp_ts = r[1]
        diff = exp_ts - now
        days = diff // 86400
        hours = (diff % 86400) // 3600
        minutes = (diff % 3600) // 60
        countdown_str = f"{days} Ngày {hours:02d} Giờ {minutes:02d} Phút"
        result.append({
            "user_id": uid,
            "expires_at": exp_ts,
            "remaining_str": countdown_str,
            "days": days
        })
    return result

init_db()
sync_ctv_env()
