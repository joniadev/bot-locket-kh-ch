import hmac
import hashlib
import json
import urllib.parse
import aiohttp
import os

PAYOS_CLIENT_ID = os.environ.get("PAYOS_CLIENT_ID", "")
PAYOS_API_KEY = os.environ.get("PAYOS_API_KEY", "")
PAYOS_CHECKSUM_KEY = os.environ.get("PAYOS_CHECKSUM_KEY", "")

def get_signature(data, key):
    # Sort keys alphabetically and exclude 'signature' key and null/empty values
    sorted_keys = sorted([k for k in data.keys() if k != "signature"])
    query_parts = []
    for k in sorted_keys:
        val = data[k]
        if val is None or val == "":
            continue
        if isinstance(val, (dict, list)):
            val = json.dumps(val, separators=(',', ':'))
        query_parts.append(f"{k}={val}")
    
    query_string = "&".join(query_parts)
    # Compute HMAC SHA256
    return hmac.new(
        key.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

async def create_payment_link(order_code: int, amount: int, description: str, return_url: str, cancel_url: str):
    if not PAYOS_CLIENT_ID or not PAYOS_API_KEY or not PAYOS_CHECKSUM_KEY:
        return None
        
    url = "https://api-merchant.payos.vn/v2/payment-requests"
    
    body = {
        "orderCode": order_code,
        "amount": amount,
        "description": description[:25],
        "cancelUrl": cancel_url,
        "returnUrl": return_url
    }
    
    # Calculate signature
    body["signature"] = get_signature(body, PAYOS_CHECKSUM_KEY)
    
    headers = {
        "x-client-id": PAYOS_CLIENT_ID,
        "x-api-key": PAYOS_API_KEY,
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body, headers=headers) as resp:
            if resp.status == 200:
                result = await resp.json()
                if result.get("code") == "00":
                    return result.get("data")
            # Log error
            text = await resp.text()
            print(f"PayOS Create Link Error: Status {resp.status}, Response: {text}")
            return None

def verify_webhook_data(payload):
    if not PAYOS_CHECKSUM_KEY:
        return False
        
    data = payload.get("data")
    signature = payload.get("signature")
    
    if not data or not signature:
        return False
        
    expected_sig = get_signature(data, PAYOS_CHECKSUM_KEY)
    return hmac.compare_digest(expected_sig, signature)

async def get_payment_link_information(order_code: int):
    if not PAYOS_CLIENT_ID or not PAYOS_API_KEY:
        return None
        
    url = f"https://api-merchant.payos.vn/v2/payment-requests/{order_code}"
    
    headers = {
        "x-client-id": PAYOS_CLIENT_ID,
        "x-api-key": PAYOS_API_KEY,
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("code") == "00":
                        return result.get("data")
                else:
                    text = await resp.text()
                    print(f"PayOS Get Link Info Error: Status {resp.status}, Response: {text}")
        except Exception as e:
            print(f"PayOS Get Link Info Exception: {e}")
    return None
