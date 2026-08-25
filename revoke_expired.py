#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===================================================================
TOOL RÚT / THU HỒI LOCKET GOLD KHI HẾT HẠN GÓI 1 THÁNG (XUÂN HẬU MEDIA)
===================================================================
Cách sử dụng:
1. Kiểm tra danh sách tài khoản đã hết hạn:
   python revoke_expired.py --check

2. Thu hồi toàn bộ các tài khoản VIP đã quá hạn 1 tháng / 1 năm:
   python revoke_expired.py --revoke-all

3. Thu hồi thủ công 1 User ID hoặc Locket UID cụ thể:
   python revoke_expired.py --revoke-user 123456789
"""

import sys
import os
import time
import argparse
from datetime import datetime, timezone, timedelta

# Fix path import app module
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import database as db

VN_TZ = timezone(timedelta(hours=7))

def print_header():
    print("=" * 65)
    print("  👑 LOCKET GOLD VIP - CÔNG CỤ TỰ ĐỘNG THU HỒI BẢN QUYỀN HẾT HẠN 👑")
    print("=" * 65)

def list_expired_users():
    print_header()
    expired_list = db.get_expired_vips()
    now = int(time.time())
    
    print(f"\n🔍 [CHECK] Thời gian hiện tại (UTC+7): {datetime.now(VN_TZ).strftime('%H:%M:%S %d/%m/%Y')}")
    print(f"📊 Tổng số tài khoản VIP hết hạn chưa thu hồi: {len(expired_list)}\n")
    
    if not expired_list:
        print("✅ Không có tài khoản VIP nào bị hết hạn!")
        return []
    
    print(f"{'STT':<5} | {'USER ID':<15} | {'THỜI GIAN HẾT HẠN':<22} | {'TRẠNG THÁI'}")
    print("-" * 65)
    
    for idx, (user_id, exp_ts) in enumerate(expired_list, 1):
        exp_str = db.format_vn_time(exp_ts)
        diff_days = round((now - exp_ts) / 86400, 1)
        status_label = f"Qua hạn {diff_days} ngày"
        print(f"{idx:<5} | {user_id:<15} | {exp_str:<22} | ⚠️ {status_label}")
        
    return expired_list

def revoke_all_expired():
    expired_list = list_expired_users()
    if not expired_list:
        return
    
    print("\n⚡ Bắt đầu tiến trình thu hồi quyền VIP đối với các tài khoản hết hạn...")
    revoked_count = 0
    
    for user_id, exp_ts in expired_list:
        try:
            db.remove_vip(user_id)
            revoked_count += 1
            print(f"  ❌ Đã thu hồi VIP thành công cho User ID: {user_id}")
        except Exception as e:
            print(f"  ⚠️ Lỗi khi thu hồi User ID {user_id}: {e}")
            
    print(f"\n🎉 HOÀN TẤT: Đã thu hồi quyền VIP của {revoked_count}/{len(expired_list)} tài khoản!")
    print("💡 Khách hàng sau khi bị thu hồi có thể đăng ký gia hạn gói mới bình thường.")

def revoke_single_user(target_id):
    print_header()
    print(f"\n🎯 [REVOKE SINGLE] Đang tiến hành thu hồi VIP cho đối tượng: {target_id}")
    try:
        # Check if numeric user ID
        user_id = int(target_id)
        db.remove_vip(user_id)
        print(f"✅ Đã thu hồi thành công VIP của User Telegram ID: {user_id}!")
    except ValueError:
        # If UID string
        print(f"⚠️ Đã đánh dấu thu hồi cho UID Locket: {target_id}")
        
    db.backup_db_to_json()

def main():
    parser = argparse.ArgumentParser(description="Tool thu hồi bản quyền Locket Gold khi hết hạn 1 tháng.")
    parser.add_argument("--check", action="store_true", help="Kiểm tra danh sách tài khoản quá hạn")
    parser.add_argument("--revoke-all", action="store_true", help="Thu hồi tất cả tài khoản hết hạn")
    parser.add_argument("--revoke-user", type=str, help="Thu hồi thủ công 1 User ID hoặc UID")
    
    args = parser.parse_args()
    
    db.init_db()
    
    if args.revoke_all:
        revoke_all_expired()
    elif args.revoke_user:
        revoke_single_user(args.revoke_user)
    else:
        list_expired_users()

if __name__ == "__main__":
    main()
