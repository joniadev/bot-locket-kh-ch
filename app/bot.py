import asyncio
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from app.config import *
from app import database as db
from app.services import locket, nextdns, payos_service

logger = logging.getLogger(__name__)

request_queue = None
pending_items = []
queue_lock = None

def get_queue():
    global request_queue
    if request_queue is None:
        request_queue = asyncio.Queue()
    return request_queue

def get_lock():
    global queue_lock
    if queue_lock is None:
        queue_lock = asyncio.Lock()
    return queue_lock

class Clr:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

async def send_noti_bot_message(text):
    noti_token = NOTI_BOT_TOKEN
    session = locket.get_session()
    for chat_id in ADMIN_IDS:
        url = f"https://api.telegram.org/bot{noti_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            async with session.post(url, json=payload, timeout=5) as resp:
                await resp.read()
        except Exception as e:
            print(f"Failed to send admin notification via noti bot to {chat_id}: {e}")

async def update_pending_positions(app):
    for i, item in enumerate(pending_items):
        position = i + 1
        ahead = i
        try:
            # Update position text
            await app.bot.edit_message_text(
                chat_id=item['chat_id'],
                message_id=item['message_id'],
                text=T("queued", item['lang']).format(item['username'], position, ahead),
                parse_mode=ParseMode.HTML
            )
            
            # Notify if almost turn (ahead == 2)
            if ahead == 2:
                try:
                    await app.bot.send_message(
                        chat_id=item['chat_id'],
                        text=T("queue_almost", item['lang']),
                        parse_mode=ParseMode.HTML
                    )
                except:
                    pass
        except:
            pass

def get_main_menu_keyboard(lang="VI"):
    price_year = int(db.get_config("price_year", 79000))
    k_year = f"{price_year//1000}k" if price_year >= 1000 and price_year % 1000 == 0 else f"{price_year:,}đ"
    
    admin_handle = ADMIN_USERNAME.lstrip('@') if ADMIN_USERNAME else "hemtainguyen"
    admin_url = f"https://t.me/{admin_handle}"
    
    keyboard = [
        [InlineKeyboardButton(f"👑 Gói VIP 1 Năm ({k_year}) • HUY HIỆU 🎖️", callback_data="buy_vip_year")],
        [InlineKeyboardButton("🆘 Hỗ Trợ Direct", url=admin_url)]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = db.get_lang(user_id) or DEFAULT_LANG
    
    # Auto register user to CSDL for broadcast messaging
    db.register_user(user_id, update.effective_user.username, update.effective_user.first_name)
    
    # Process viral referral links (e.g. /start ref_123456)
    if context.args and len(context.args) > 0:
        arg0 = context.args[0]
        if arg0.startswith("ref_"):
            try:
                referrer_id = int(arg0.replace("ref_", ""))
                success, rewarded = db.process_referral(referrer_id, user_id)
                if success:
                    try:
                        stats = db.get_referral_stats(referrer_id)
                        total_inv = stats["total_invited"]
                        ref_credits = stats["credits"]
                        
                        if rewarded:
                            text_msg = (
                                f"🎉 <b>BẠN ĐÃ MỜI THÀNH CÔNG ĐỦ 5 BẠN NÊN ĐƯỢC THƯỞNG!</b>\n\n"
                                f"🎁 Bạn vừa được nhận <b>+1 Lượt Nâng Locket Gold Miễn Phí</b>!\n"
                                f"⭐ Tổng lượt nâng miễn phí hiện có: <b>{ref_credits} lượt</b>."
                            )
                        else:
                            needed = 5 - (total_inv % 5)
                            text_msg = (
                                f"👥 <b>1 BẠN MỚI VỪA THAM GIA QUA LINK CỦA BẠN!</b>\n\n"
                                f"📊 Tiến độ hiện tại: <b>{total_inv} bạn</b>\n"
                                f"🎯 Cần thêm <b>{needed} bạn nữa</b> để nhận +1 Lượt Nâng Gold Miễn Phí!"
                            )
                        await context.bot.send_message(chat_id=referrer_id, text=text_msg, parse_mode=ParseMode.HTML)
                    except Exception as e_ref:
                        print(f"Failed to notify referrer {referrer_id}: {e_ref}")
            except Exception as e_parse:
                print(f"Error processing ref: {e_parse}")

    price_year = int(db.get_config("price_year", 79000))
    is_admin_user = is_admin(user_id)

    if is_admin_user:
        stats = db.get_detailed_stats()
        admin_welcome = (
            f"👑 <b>ADMIN CONTROL PANEL</b>\n\n"
            f"📊 <b>THỐNG KÊ HỆ THỐNG:</b>\n"
            f"• 👤 <b>Tổng số người dùng Bot:</b> <code>{stats['total_users']}</code> Telegram Users\n"
            f"• 👑 <b>VIP Active:</b> <code>{stats['active_vips']}</code> thành viên\n"
            f"• ⭐ <b>Cộng Tác Viên (CTV):</b> <code>{len(db.get_all_ctvs())}</code> người\n"
            f"• ✅ <b>Gold đã nâng thành công:</b> <code>{stats['success_requests']}</code> lượt\n\n"
            f"⚡ <b>Quyền Hạn Admin:</b> Kích Hoạt Locket Gold Không Giới Hạn 24/7\n"
            f"🌐 <a href='https://locket-gold-bot-ptp6.onrender.com/quantridev'>Web Admin Dashboard</a>\n\n"
            f"👇 <b>Nhập Username hoặc Link Locket để nâng Gold ngay:</b>"
        )
        await update.message.reply_text(
            admin_welcome,
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True)
        )
        return

    # Check if user is an active CTV (Collaborator)
    if db.is_ctv(user_id):
        ctv_info = db.get_ctv_info(user_id)
        ctv_welcome = (
            f"⭐ <b>HỆ THỐNG CỘNG TÁC VIÊN (CTV) PMHftHT LOCKET GOLD</b> ⭐\n\n"
            f"👑 <b>Trạng Thái:</b> CỘNG TÁC VIÊN (NÂNG GOLD KHÔNG GIỚI HẠN)\n"
            f"⏳ <b>Thời Gian Gói CTV Còn Lại:</b> <b>{ctv_info.get('countdown_str', 'Đang hoạt động')}</b>\n"
            f"⚡ <b>Quyền Hạn:</b> Nâng Locket Gold tự động 24/7 không giới hạn số lượng trong tháng!\n\n"
            f"👇 <b>Nhập Username hoặc Link Locket của khách để nâng Gold ngay:</b>"
        )
        await update.message.reply_text(
            ctv_welcome,
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True, input_field_placeholder="Username hoặc Link Locket...")
        )
        return

    active_order = db.get_unused_approved_order(user_id)
    if active_order:
        exp_str = db.get_vip_expiry(user_id) or "N/A"
        user_welcome = (
            f"🎉 <b>CHÚC MỪNG! BẠN ĐÃ ĐĂNG KÝ GÓI VIP 1 NĂM!</b>\n\n"
            f"Thanh toán thành công! Gói VIP đã tự động kích hoạt!\n"
            f"📅 Hạn dùng VIP: <b>{exp_str}</b>\n\n"
            f"🚀 Vui lòng gửi Username hoặc Link Locket để nâng Gold ngay!"
        )
        await update.message.reply_text(
            user_welcome,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard(lang)
        )
        return

    welcome_text = (
        f"✨ <b>HỆ THỐNG NÂNG CẤP PMHftHT LOCKET GOLD (CÓ HUY HIỆU VÀNG 🎖️)</b> ✨\n"
        f"<i>Dịch vụ kích hoạt Locket Gold uy tín & giá rẻ nhất!</i>\n\n"
        f"👑 <b>QUYỀN LỢI KHI NÂNG GOLD:</b>\n"
        f"• 🎖️ <b>CÓ HUY HIỆU VÀNG GOLD (BADGE) NỔI BẬT</b>\n"
        f"• 📸 Mở khóa toàn bộ tính năng cao cấp 1 NĂM\n"
        f"• ⚡ Kích hoạt tự động 100% 24/7\n\n"
        f"💰 <b>BẢNG GIÁ DỊCH VỤ (CÓ HUY HIỆU GOLD 🎖️):</b>\n"
        f"• 👑 <b>Gói VIP 1 Năm:</b> <code>{price_year:,}đ / 1 Năm</code> <i>(Có Huy Hiệu 🎖️)</i>\n\n"
        f"👇 <b>Vui lòng bấm nút bên dưới để thanh toán và nhận Gold ngay:</b>"
    )

    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard(lang)
    )

async def setlang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_language_select(update)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = db.get_lang(user_id) or DEFAULT_LANG
    
    help_text = T("help_msg", lang)
    if is_admin(user_id):
        help_text += (
            f"\n\n<b>👑 Admin Control & Cài Đặt:</b>\n"
            f"/setprice [lẻ] [vip] - Cài giá nạp (VD: /setprice 15000 79000)\n"
            f"/setbank [bank] [stk] [ten] - Cài tài khoản nhận tiền\n"
            f"/addvip [id] - Cấp 30 ngày VIP cho User\n"
            f"/noti [msg] - Gửi thông báo hàng loạt\n"
            f"/rs [id] - Reset giới hạn dùng\n"
            f"/setdonate - Cài ảnh thành công mới\n"
            f"/stats - Xem thống kê hệ thống"
        )
        
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def setbank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "❌ <b>Cú pháp:</b> <code>/setbank [mã_ngân_hàng] [số_tài_khoản] [tên_chủ_tài_khoản]</code>\n"
            "👉 <b>Ví dụ:</b> <code>/setbank vietcombank 1032591781 NGUYEN XUAN HAU</code>",
            parse_mode=ParseMode.HTML
        )
        return
        
    bank_id = args[0]
    bank_acc = args[1]
    bank_name = " ".join(args[2:]).upper()
    
    db.set_config("bank_id", bank_id)
    db.set_config("bank_account", bank_acc)
    db.set_config("bank_name", bank_name)
    
    await update.message.reply_text(
        f"✅ <b>Đã cập nhật thông tin tài khoản nhận tiền!</b>\n\n"
        f"- Ngân hàng: <code>{bank_id}</code>\n"
        f"- Số tài khoản: <code>{bank_acc}</code>\n"
        f"- Chủ tài khoản: <code>{bank_name}</code>",
        parse_mode=ParseMode.HTML
    )

async def addctv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin_user = is_admin(user_id)
    if not is_admin_user:
        return

    target_uid = None
    days = 29

    # Method 1: Reply to a user's message
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_uid = update.message.reply_to_message.from_user.id
        if context.args and context.args[0].isdigit():
            days = int(context.args[0])
    # Method 2: Pass arguments directly (/addctv 123456789 29)
    elif context.args:
        if context.args[0].isdigit():
            target_uid = int(context.args[0])
        if len(context.args) > 1 and context.args[1].isdigit():
            days = int(context.args[1])

    if not target_uid:
        help_msg = (
            f"❌ <b>CÚ PHÁP THÊM CỘNG TÁC VIÊN (CTV):</b>\n\n"
            f"👉 <b>Cách 1 (Nhập Telegram ID):</b>\n"
            f"<code>/addctv [Telegram_ID] [Số_ngày]</code>\n"
            f"<i>Ví dụ: <code>/addctv 6685744035 29</code></i>\n\n"
            f"👉 <b>Cách 2 (Trả lời tin nhắn của khách):</b>\n"
            f"<i>Reply tin nhắn khách bằng lệnh: <code>/addctv 29</code></i>"
        )
        await update.message.reply_text(help_msg, parse_mode=ParseMode.HTML)
        return
        
    try:
        exp_ts = db.add_ctv(target_uid, days)
        ctv_info = db.get_ctv_info(target_uid)
        
        reply_txt = (
            f"✅ <b>ĐÃ THÊM CỘNG TÁC VIÊN (CTV) THÀNH CÔNG!</b>\n\n"
            f"👤 <b>Telegram ID:</b> <code>{target_uid}</code>\n"
            f"⏳ <b>Thời hạn gói CTV:</b> <b>{days} Ngày</b>\n"
            f"⏰ <b>Hạn dùng:</b> <b>{ctv_info.get('countdown_str', '')}</b>\n"
            f"🛡️ <b>Lưu trữ:</b> Đã đồng bộ đa tầng (An toàn 100% khi Render chạy lại)."
        )
        await update.message.reply_text(reply_txt, parse_mode=ParseMode.HTML)
        
        # Notify CTV user directly!
        try:
            user_noti = (
                f"🎉 <b>CHÚC MỪNG! BẠN ĐÃ ĐƯỢC KÍCH HOẠT GÓI CỘNG TÁC VIÊN (CTV)!</b>\n\n"
                f"⭐ <b>Trạng Thái:</b> CỘNG TÁC VIÊN (NÂNG GOLD KHÔNG GIỚI HẠN)\n"
                f"⏳ <b>Thời Gian Còn Lại:</b> <b>{ctv_info.get('countdown_str', '')}</b>\n\n"
                f"🚀 Bạn có quyền kích hoạt Locket Gold tự động 24/7 không giới hạn số lượng trong tháng!"
            )
            await context.bot.send_message(chat_id=target_uid, text=user_noti, parse_mode=ParseMode.HTML)
        except Exception as e_notify:
            print(f"Failed to notify CTV user {target_uid}: {e_notify}")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

async def delctv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin_user = is_admin(user_id)
    if not is_admin_user:
        return
        
    target_uid = None
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_uid = update.message.reply_to_message.from_user.id
    elif context.args and context.args[0].isdigit():
        target_uid = int(context.args[0])

    if not target_uid:
        await update.message.reply_text(
            f"❌ <b>CÚ PHÁP XÓA CỘNG TÁC VIÊN (CTV):</b>\n\n"
            f"• <b>Nhập ID:</b> <code>/delctv [Telegram_ID]</code>\n"
            f"• <b>Reply tin nhắn:</b> <code>/delctv</code>",
            parse_mode=ParseMode.HTML
        )
        return
        
    try:
        db.remove_ctv(target_uid)
        await update.message.reply_text(f"✅ Đã xoá Telegram ID <code>{target_uid}</code> khỏi danh sách CTV!", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

async def ctv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin_user = is_admin(user_id)
    if not is_admin_user:
        return
        
    ctvs = db.get_all_ctvs()
    if not ctvs:
        await update.message.reply_text("📋 <b>Hiện tại chưa có Cộng Tác Viên (CTV) nào.</b>\n👉 Dùng lệnh <code>/addctv [id] [ngày]</code> để thêm.", parse_mode=ParseMode.HTML)
        return
        
    txt_lines = ["⭐ <b>DANH SÁCH CỘNG TÁC VIÊN (CTV) ĐANG HOẠT ĐỘNG:</b>\n"]
    for idx, c in enumerate(ctvs, 1):
        txt_lines.append(f"{idx}. 👤 <code>{c['user_id']}</code> — ⏳ Còn: <b>{c['remaining_str']}</b>")
        
    txt_lines.append(f"\n📊 <b>Tổng số CTV:</b> <code>{len(ctvs)}</code> người")
    await update.message.reply_text("\n".join(txt_lines), parse_mode=ParseMode.HTML)

def build_admin_stats_msg():
    stats = db.get_detailed_stats()
    ctvs = db.get_all_ctvs()
    
    total_req = stats['total_requests'] or 1
    success_rate = round((stats['success_requests'] / total_req) * 100) if stats['total_requests'] else 100
    
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://locket-gold-bot-ptp6.onrender.com").rstrip('/')
    
    user_ids_list = [str(uid) for uid in stats['user_ids']]
    show_ids = user_ids_list[-20:] if len(user_ids_list) > 20 else user_ids_list
    ids_str = ", ".join(show_ids) if show_ids else "Chưa có người dùng"
    if len(user_ids_list) > 20:
        ids_str += f"\n<i>(...và {len(user_ids_list) - 20} ID khác)</i>"

    p_month = int(db.get_config("price_month", 15000))
    p_year = int(db.get_config("price_year", 69000))

    from datetime import datetime, timedelta, timezone
    vn_now = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")

    msg = (
        f"👑 <b>BÁO CÁO THỐNG KÊ CHI TIẾT BOT (REALTIME)</b> 👑\n"
        f"⏰ <i>Cập nhật: {vn_now} (Múi giờ Việt Nam UTC+7)</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"📊 <b>1. QUẢN LÝ NGƯỜI DÙNG & CTV:</b>\n"
        f"• 👤 <b>Tổng người dùng Bot:</b> <code>{stats['total_users']}</code> Users\n"
        f"• 👑 <b>VIP Member Active:</b> <code>{stats['active_vips']}</code> thành viên\n"
        f"• ⭐ <b>Cộng Tác Viên (CTV):</b> <code>{len(ctvs)}</code> CTV (Nâng không giới hạn)\n\n"

        f"⚡ <b>2. THỐNG KÊ NÂNG CẤP LOCKET GOLD:</b>\n"
        f"• 🎯 <b>Tổng số yêu cầu:</b> <code>{stats['total_requests']}</code> lượt\n"
        f"• ✅ <b>Nâng thành công:</b> <code>{stats['success_requests']}</code> lượt (<b>{success_rate}% Tỷ lệ</b>)\n"
        f"• ❌ <b>Nâng thất bại:</b> <code>{stats['fail_requests']}</code> lượt\n\n"

        f"💰 <b>3. THỐNG KÊ DOANH THU PAYOS / BANK:</b>\n"
        f"• 🔑 <b>Gói 1 Tháng ({p_month//1000}k):</b> <code>{stats['single_orders_count']}</code> đơn (<b>{stats['single_revenue']:,}đ</b>)\n"
        f"• 👑 <b>Gói 1 Năm ({p_year//1000}k):</b> <code>{stats['vip_orders_count']}</code> đơn (<b>{stats['vip_revenue']:,}đ</b>)\n"
        f"• 💵 <b>TỔNG DOANH THU BẢN QUYỀN:</b> <b>{stats['total_revenue']:,} VNĐ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"⚙️ <b>4. THÔNG SỐ SERVER & ENGINE:</b>\n"
        f"• 🤖 <b>Active Workers:</b> <code>{NUM_WORKERS}</code> Threads\n"
        f"• 🔑 <b>Token Sets Exploit:</b> <code>{len(TOKEN_SETS)}</code> Sets\n"
        f"• ⏳ <b>Hàng chờ hiện tại:</b> <code>{request_queue.qsize()}</code> lượt\n"
        f"• 🟢 <b>Server Status:</b> <code>Online 24/7 (Render Cloud)</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"🆔 <b>5. TELEGRAM USER ID MỚI NHẤT ({len(show_ids)} ID gần đây):</b>\n"
        f"<code>{ids_str}</code>"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Mở Web Admin Dashboard", url=f"{render_url}/quantridev")],
        [
            InlineKeyboardButton("⭐ Xem Danh Sách CTV", callback_data="admin_view_ctv"),
            InlineKeyboardButton("🔄 Làm Mới (Refresh)", callback_data="admin_refresh_stats")
        ]
    ])
    return msg, keyboard

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    msg, keyboard = build_admin_stats_msg()
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)

# --- Admin Commands ---
async def broadcast_worker(bot, users, content_payload, chat_id, message_id):
    """
    Broadcasts message or media to all users who have interacted with the bot.
    content_payload can be:
    - dict with type="copy" and from_chat_id, reply_msg_id
    - string text message
    """
    success = 0
    fail = 0
    total = len(users)

    for i, uid in enumerate(users):
        try:
            if isinstance(content_payload, dict) and content_payload.get("type") == "copy":
                await bot.copy_message(
                    chat_id=uid,
                    from_chat_id=content_payload["from_chat_id"],
                    message_id=content_payload["reply_msg_id"]
                )
            else:
                text_content = str(content_payload)
                full_text = f"📢 <b>THÔNG BÁO TỪ ADMIN</b> 📢\n━━━━━━━━━━━━━━━━━━━\n\n{text_content}"
                await bot.send_message(chat_id=uid, text=full_text, parse_mode=ParseMode.HTML)
            success += 1
        except Exception:
            fail += 1

        # Update progress log every 5 users or at end
        if (i + 1) % 5 == 0 or (i + 1) == total:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=(
                        f"📢 <b>ĐANG GỬI THÔNG BÁO TỚI TẤT CẢ KHÁCH HÀNG...</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"🔄 <b>Tiến độ:</b> {i+1}/{total} người\n"
                        f"✅ <b>Thành công:</b> {success}\n"
                        f"❌ <b>Thất bại (Block bot):</b> {fail}"
                    ),
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass

        await asyncio.sleep(0.04)  # Rate limit protection

    # Final summary card
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=(
                f"🎉 <b>ĐÃ GỬI THÔNG BÁO HOÀN TẤT 100%!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👥 <b>Tổng số khách nhận:</b> {total} người\n"
                f"✅ <b>Đã nhận thành công:</b> {success} người\n"
                f"❌ <b>Thất bại / Đã chặn Bot:</b> {fail} người"
            ),
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass


async def noti_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    db.register_user(user_id, update.effective_user.username, update.effective_user.first_name)

    content_payload = None

    # Option 1: Reply to a message (Text, Image, Video, Card, Sticker)
    if update.message and update.message.reply_to_message:
        content_payload = {
            "type": "copy",
            "from_chat_id": update.message.chat_id,
            "reply_msg_id": update.message.reply_to_message.message_id
        }
    # Option 2: Text after /noti
    elif context.args and len(context.args) > 0:
        content_payload = " ".join(context.args)

    if not content_payload:
        help_txt = (
            f"📢 <b>HƯỚNG DẪN GỬI THÔNG BÁO HÀNG LOẠT CHO TẤT CẢ KHÁCH HÀNG:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👉 <b>Cách 1 (Gửi chữ):</b>\n"
            f"<code>/noti Nội dung thông báo tại đây...</code>\n\n"
            f"👉 <b>Cách 2 (Gửi Hình ảnh / Video / Sticker / Nút bấm):</b>\n"
            f"<i>Soạn tin nhắn/hình ảnh bất kỳ ➔ Reply (trả lời) tin nhắn đó và gõ: <code>/noti</code></i>"
        )
        await update.message.reply_text(help_txt, parse_mode=ParseMode.HTML)
        return

    users = db.get_all_users()
    if not users:
        await update.message.reply_text("❌ Chưa có người dùng nào trong CSDL.")
        return

    status_msg = await update.message.reply_text(
        f"⏳ <b>Đang chuẩn bị gửi thông báo tới {len(users)} người dùng đã dùng Bot...</b>",
        parse_mode=ParseMode.HTML
    )

    asyncio.create_task(broadcast_worker(context.bot, users, content_payload, status_msg.chat_id, status_msg.message_id))

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = db.get_lang(user_id) or DEFAULT_LANG
    
    if not is_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text("Usage: /rs {user_id}")
        return
        
    try:
        target_id = int(context.args[0])
        db.reset_usage(target_id)
        await update.message.reply_text(T("admin_reset", lang).format(target_id))
    except ValueError:
        await update.message.reply_text("Invalid User ID")

async def set_donate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    photo = None
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        photo = update.message.reply_to_message.photo[-1]
    elif update.message.photo:
        photo = update.message.photo[-1]
        
    if photo:
        file_id = photo.file_id
        db.set_config("donate_photo", file_id)
        await update.message.reply_text(f"✅ Updated Donate Photo ID:\n<code>{file_id}</code>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("❌ Please reply to a photo with /setdonate to set it.")

async def show_language_select(update: Update):
    keyboard = [
        [InlineKeyboardButton("Tiếng Việt 🇻🇳", callback_data="setlang_VI")],
        [InlineKeyboardButton("English 🇺🇸", callback_data="setlang_EN")]
    ]
    text = T("lang_select", "EN")
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def addvip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin_user = is_admin(user_id)
    if not is_admin_user:
        return
        
    args = context.args
    if not args:
        await update.message.reply_text("❌ Cú pháp: <code>/addvip [user_id] [số_ngày (mặc định 365)]</code>", parse_mode=ParseMode.HTML)
        return
        
    try:
        target_user_id = int(args[0])
        days = int(args[1]) if len(args) > 1 else 365
        db.add_vip(target_user_id, days)
        exp_str = db.get_vip_expiry(target_user_id)
        await update.message.reply_text(f"✅ Đã thêm VIP 1 Năm ({days} ngày) cho User <code>{target_user_id}</code>!\n📅 Hạn dùng: <b>{exp_str}</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

async def setprice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin_user = is_admin(user_id)
    if not is_admin_user:
        return
        
    args = context.args
    p_month = int(db.get_config("price_month", 15000))
    p_year = int(db.get_config("price_year", 69000))
    
    if len(args) < 2:
        await update.message.reply_text(
            f"⚙️ <b>CẤU HÌNH BẢNG GIÁ HIỆN TẠI:</b>\n"
            f"• 🔑 Gói 1 Tháng: <b>{p_month:,} VNĐ</b>\n"
            f"• 👑 Gói 1 Năm: <b>{p_year:,} VNĐ</b>\n\n"
            f"👉 <b>Cú pháp đổi giá:</b>\n"
            f"<code>/setprice [giá_1_tháng] [giá_1_năm]</code>\n"
            f"<i>Ví dụ: <code>/setprice 15000 69000</code></i>",
            parse_mode=ParseMode.HTML
        )
        return
        
    try:
        new_month = int(args[0])
        new_year = int(args[1])
        db.set_config("price_month", str(new_month))
        db.set_config("price_year", str(new_year))
        db.set_config("price_single", str(new_month))
        db.set_config("price_vip", str(new_year))
        await update.message.reply_text(
            f"✅ <b>ĐÃ CẬP NHẬT GIÁ MỚI THÀNH CÔNG!</b>\n\n"
            f"• 🔑 Gói 1 Tháng: <b>{new_month:,} VNĐ</b>\n"
            f"• 👑 Gói 1 Năm: <b>{new_year:,} VNĐ</b>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.effective_chat.type != "private":
        return

    user_id = update.effective_user.id
    text = update.message.text.strip() if update.message.text else ""
    lang = db.get_lang(user_id) or DEFAULT_LANG
    is_admin = is_admin(user_id)

    db.register_user(user_id, update.effective_user.username, update.effective_user.first_name)

    if not text or text.startswith("/"):
        return

    # Handle inline keyboard button text clicks
    if text in ["🔑 Kích Hoạt 1 Tháng (15k/lượt)", "🔑 Đăng Ký VIP 1 Tháng (29k)", "btn_month"]:
        await send_vip_payment_card(update, context, pkg_type="month")
        return
    if text in ["👑 Đăng Ký VIP 1 Năm (79k)", "👑 Đăng Ký VIP 1 Năm (69k)", "btn_input", "btn_year"]:
        await send_vip_payment_card(update, context, pkg_type="year")
        return
    if text in ["🌟 Đăng Ký VIP Vĩnh Viễn (109k)", "btn_lifetime"]:
        await send_vip_payment_card(update, context, pkg_type="lifetime")
        return
    if text in ["🌐 Đổi Ngôn Ngữ", "btn_lang"]:
        await show_language_select(update)
        return
    if text in ["🆘 Hỗ Trợ", "btn_help"]:
        await update.message.reply_text(T("help_msg", lang), parse_mode=ParseMode.HTML)
        return

    # Extract username from text
    if "locket.cam/" in text:
        username = text.split("locket.cam/")[-1].split("?")[0].split("/")[0].strip()
    elif len(text) < 50 and " " not in text:
        username = text.strip().lstrip("@")
    else:
        return

    if not username or len(username) < 2:
        return

    # Step 1: Send "Resolving..." message
    msg = await update.message.reply_text(T("resolving", lang), parse_mode=ParseMode.HTML)

    # Step 2: Resolve UID (with timeout)
    uid = None
    try:
        uid = await asyncio.wait_for(locket.resolve_uid(username), timeout=5.0)
    except Exception:
        pass

    if not uid:
        await msg.edit_text(T("not_found", lang), parse_mode=ParseMode.HTML)
        return

    # Admin/CTV bypass daily trial limit check
    is_unlimited_user = is_admin or db.is_ctv(user_id)
    if not is_unlimited_user and not db.check_can_request(user_id):
        await msg.edit_text(T("limit_reached", lang), parse_mode=ParseMode.HTML)
        return

    # Step 3: Check status (with timeout)
    await msg.edit_text(T("checking_status", lang), parse_mode=ParseMode.HTML)
    
    status = None
    try:
        status = await asyncio.wait_for(locket.check_status(uid), timeout=4.0)
    except Exception:
        pass
    
    status_text = T("free_status", lang)
    if status and status.get("active"):
        status_text = T("gold_active", lang).format(status.get('expires', 'N/A'))
    
    # Step 4: Show User Info card with Upgrade button
    safe_username = username[:30]
    keyboard = [[InlineKeyboardButton(T("btn_upgrade", lang), callback_data=f"upg|{uid}|{safe_username}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    vip_tag = ""
    if is_admin:
        vip_tag = "\n👑 <b>Tài khoản Admin</b>: Không giới hạn"
    elif db.is_vip(user_id):
        vip_tag = "\n🎉 <b>VIP Member</b>: Đã kích hoạt"
    
    await msg.edit_text(
        f"{T('user_info_title', lang)}\n"
        f"{E_ID}: <code>{uid}</code>\n"
        f"{E_TAG}: <code>{username}</code>\n"
        f"{E_STAT} <b>Status</b>: {status_text}"
        f"{vip_tag}\n\n"
        f"👇",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def auto_poll_payment(app, order_id, order_code, user_id, chat_id, days, pkg_name, message_id=None):
    """Silent background poller checking PayOS API every 3s for 10 minutes until paid"""
    poll_count = 0
    max_polls = 200 # 200 * 3s = 10 minutes
    
    while poll_count < max_polls:
        await asyncio.sleep(3)
        poll_count += 1
        
        payment = db.get_pending_payment(order_id)
        if not payment or payment['status'] == 'APPROVED':
            return
            
        if payment['status'] in ['CANCELLED', 'FAILED', 'DECLINED']:
            return

        try:
            payos_info = await payos_service.get_payment_link_information(order_code)
            if payos_info and payos_info.get("status") == "PAID":
                db.update_payment_status(order_id, "APPROVED")
                
                from datetime import datetime
                now_str = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
                
                if days >= 3000:
                    db.add_vip(user_id, days=3650)
                elif days >= 365:
                    db.add_vip(user_id, days=365)
                else:
                    db.add_vip(user_id, days=30)
                exp_str = db.get_vip_expiry(user_id) or "N/A"
                
                price_val_str = f"{int(db.get_config('price_month', 15000)):,}đ" if order_id.startswith("M") else f"{int(db.get_config('price_year', 69000)):,}đ"
                
                if message_id:
                    try:
                        await app.bot.delete_message(chat_id=chat_id, message_id=message_id)
                    except Exception:
                        pass
                
                auto_success_text = (
                    f"🎉 <b>CHÚC MỪNG! HỆ THỐNG ĐÃ TỰ ĐỘNG XÁC NHẬN THANH TOÁN THÀNH CÔNG!</b>\n\n"
                    f"Thanh toán gói <b>{pkg_name.upper()}</b> ({price_val_str}) qua PayOS thành công!\n"
                    f"📅 Hạn dùng VIP của bạn: <b>{exp_str}</b>\n\n"
                    f"👉 <b>VUI LÒNG NHẬP USERNAME HOẶC LINK LOCKET CỦA BẠN VÀO TIN NHẮN BÊN DƯỚI ĐỂ TIẾN HÀNH NÂNG GOLD NGAY:</b>"
                )
                try:
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=auto_success_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=ForceReply(selective=True, input_field_placeholder="Username hoặc Link Locket...")
                    )
                except Exception as e_send:
                    print(f"Auto poll send user error: {e_send}")

                admin_noti = (
                    f"💰 <b>[THÔNG BÁO DOANH THU THỰC NHẬN PAYOS]</b> 💰\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"💵 <b>Số Tiền Nhận:</b> <b>+{price_val_str}</b>\n"
                    f"🔑 <b>Gói Dịch Vụ:</b> {pkg_name}\n"
                    f"👤 <b>Khách Hàng Telegram:</b> <code>{user_id}</code>\n"
                    f"🧾 <b>Mã Đơn PayOS:</b> <code>{order_id}</code>\n"
                    f"⏰ <b>Thời Gian:</b> <code>{now_str}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"⚡ <i>Hệ thống đã nhận tiền tự động 100% qua PayOS Gateway 24/24.</i>"
                )
                await send_noti_bot_message(admin_noti)
                return
        except Exception as e_poll:
            pass

async def send_vip_payment_card(update: Update, context: ContextTypes.DEFAULT_TYPE, pkg_type: str = "year"):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    lang = db.get_lang(user_id) or DEFAULT_LANG
    
    import time
    order_code = int(time.time() * 1000) % 9007199254740991
    
    if pkg_type == "month":
        prefix = "M"
        pkg_name = "Gói 1 Tháng"
        price_val = int(db.get_config("price_month", 15000))
        duration_str = "1 Tháng (30 Ngày)"
        icon = "🔑"
        days = 30
    elif pkg_type == "lifetime":
        prefix = "L"
        pkg_name = "Gói Vĩnh Viễn"
        price_val = int(db.get_config("price_lifetime", 89000))
        duration_str = "Vĩnh Viễn (Trọn Đời)"
        icon = "🌟"
        days = 3650
    else:
        prefix = "Y"
        pkg_name = "Gói 1 Năm"
        price_val = int(db.get_config("price_year", 79000))
        duration_str = "1 Năm (365 Ngày)"
        icon = "👑"
        days = 365
        
    order_id = f"{prefix}{order_code}"
    
    msg_id = update.callback_query.message.message_id if update.callback_query else (update.message.message_id if update.message else None)
    db.add_pending_payment(order_id, user_id, "VIP", pkg_name, chat_id, msg_id or 0)
    
    payos_link = None
    if PAYOS_CLIENT_ID and PAYOS_API_KEY and PAYOS_CHECKSUM_KEY:
        try:
            bot_info = await context.bot.get_me()
            bot_url = f"https://t.me/{bot_info.username}"
            payos_data = await payos_service.create_payment_link(
                order_code=order_code,
                amount=price_val,
                description=f"{pkg_name[:15]}",
                return_url=bot_url,
                cancel_url=bot_url
            )
            if payos_data:
                payos_link = payos_data.get("checkoutUrl")
        except Exception as e:
            print(f"Error generating PayOS link for VIP: {e}")

    btn_admin_label = f"⚡ Admin Duyệt Nhanh {pkg_name} (Miễn phí)"
    admin_upg_callback = f"admin_vip_upg|{user_id}|{days}"
    is_admin_user = is_admin(user_id)

    if payos_link:
        text = (
            f"{icon} <b>ĐĂNG KÝ GÓI {pkg_name.upper()} ({price_val:,}đ / {duration_str.upper()})</b>\n"
            f"🎖️ <b>CAM KẾT CÓ HUY HIỆU VÀNG GOLD (BADGE) NỔI BẬT!</b>\n\n"
            f"🔥 <b>Quyền lợi VIP:</b> Nâng cấp Locket Gold <b>{duration_str}</b>!\n\n"
            f"🔗 Vui lòng bấm vào nút bên dưới để chuyển sang trang thanh toán PayOS tự động:\n"
            f"👉 <a href='{payos_link}'><b>[BẤM VÀO ĐÂY ĐỂ THANH TOÁN {price_val:,}Đ]</b></a>\n\n"
            f"<i>⚡ Hệ thống tự động nhận tiền từ PayOS và kích hoạt {pkg_name} ngay lập tức 24/24 (Không cần duyệt tay).</i>"
        )
        keyboard = [
            [InlineKeyboardButton("💳 Mở trang thanh toán PayOS (Tự động 100%)", url=payos_link)],
            [InlineKeyboardButton("🔄 Kiểm tra thanh toán", callback_data=f"check_pay|{order_id}")]
        ]
        if is_admin_user:
            keyboard.append([InlineKeyboardButton(btn_admin_label, callback_data=admin_upg_callback)])
        keyboard.append([InlineKeyboardButton("❌ Hủy giao dịch", callback_data=f"cancel_pay|{order_id}")])
        
        sent_msg = None
        if update.callback_query:
            try:
                sent_msg = await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception:
                sent_msg = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            sent_msg = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

        # Start silent real-time background poller so customer payment checks 100% automatically!
        poll_msg_id = sent_msg.message_id if sent_msg else None
        asyncio.create_task(auto_poll_payment(context.application, order_id, order_code, user_id, chat_id, days, pkg_name, message_id=poll_msg_id))
        return
    else:
        bank_id = BANK_ID or "vietcombank"
        bank_acc = BANK_ACCOUNT or "1032591781"
        bank_name = BANK_NAME or "NGUYEN XUAN HAU"
        
        text = (
            f"{icon} <b>ĐĂNG KÝ GÓI {pkg_name.upper()} ({price_val:,}đ / {duration_str.upper()})</b>\n\n"
            f"🔥 <b>Quyền lợi VIP:</b> Nâng cấp Locket Gold <b>{duration_str}</b>!\n\n"
            f"📌 <b>Thông tin chuyển khoản:</b>\n"
            f"- Ngân hàng: <code>{bank_id}</code>\n"
            f"- Số tài khoản: <code>{bank_acc}</code>\n"
            f"- Chủ tài khoản: <code>{bank_name}</code>\n"
            f"- Số tiền: <code>{price_val:,}đ</code>\n"
            f"- Nội dung chuyển khoản: <code>{order_id}</code>\n\n"
            f"<i>Vui lòng chuyển khoản đúng nội dung và số tiền trên!</i>"
        )
        keyboard = []
        if is_admin_user:
            keyboard.append([InlineKeyboardButton(btn_admin_label, callback_data=admin_upg_callback)])
        keyboard.append([InlineKeyboardButton("❌ Hủy giao dịch", callback_data=f"cancel_pay|{order_id}")])
        
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception:
                await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    data = query.data
    user_id = query.from_user.id
    lang = db.get_lang(user_id) or DEFAULT_LANG

    # Answer callback for non-upg handlers (upg handles its own answer)
    if not data.startswith("upg|") and not data.startswith("admin_upg|"):
        try:
            await query.answer()
        except Exception:
            pass

    if data == "admin_refresh_stats":
        if not is_admin(user_id):
            return
        msg, keyboard = build_admin_stats_msg()
        try:
            await query.message.edit_text(msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            await query.answer("⚡ Đã cập nhật thống kê mới nhất!", show_alert=False)
        except Exception:
            await query.answer("ℹ️ Thống kê đã là mới nhất!", show_alert=False)
        return

    if data == "admin_view_ctv":
        if not is_admin(user_id):
            return
        ctvs = db.get_all_ctvs()
        if not ctvs:
            await query.answer("📋 Chưa có CTV nào hoạt động.", show_alert=True)
            return
        txt_lines = ["⭐ <b>DANH SÁCH CỘNG TÁC VIÊN (CTV) ĐANG HOẠT ĐỘNG:</b>\n"]
        for idx, c in enumerate(ctvs, 1):
            txt_lines.append(f"{idx}. 👤 <code>{c['user_id']}</code> — ⏳ Còn: <b>{c['remaining_str']}</b>")
        txt_lines.append(f"\n📊 <b>Tổng số CTV:</b> <code>{len(ctvs)}</code> người")
        await query.message.reply_text("\n".join(txt_lines), parse_mode=ParseMode.HTML)
        return

    if data.startswith("setlang_"):
        new_lang = data.split("_")[1]
        db.set_lang(user_id, new_lang)
        lang = new_lang
        await query.answer(f"Language: {new_lang}")
        await query.message.edit_text(
            T("menu_msg", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard(lang)
        )
        return

    if data == "menu_input":
        await query.message.reply_text(
            T("prompt_input", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True)
        )
        return

    if data == "menu_lang":
        await show_language_select(update)
        return
        
    if data == "menu_help":
        help_text = T("help_msg", lang)
        if is_admin(user_id):
            help_text += (
                f"\n\n<b>👑 Admin Control:</b>\n"
                f"/noti [msg] - Broadcast message\n"
                f"/rs [id] - Reset usage limit\n"
                f"/setdonate - Set success photo\n"
                f"/stats - View detailed statistics"
            )
            
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu_back")]])
        )
        return

    if data == "menu_back":
        await query.message.edit_text(
            T("menu_msg", lang),
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard(lang)
        )
        return

    if data == "menu_referral":
        bot_info = await context.bot.get_me()
        ref_url = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        stats = db.get_referral_stats(user_id)
        total_invited = stats["total_invited"]
        credits = stats["credits"]
        progress_in_step = total_invited % 5
        
        ref_msg = (
            f"🎁 <b>CHƯƠNG TRÌNH RỦ BẠN BÈ - NHẬN GOLD MIỄN PHÍ</b> 🚀\n\n"
            f"Khi bạn gửi link giới thiệu cho bạn bè tham gia Bot:\n"
            f"• 👥 Cứ rủ <b>5 người bạn</b> tham gia = <b>Tặng +1 Lượt Nâng Gold Miễn Phí!</b>\n\n"
            f"📊 <b>THỐNG KÊ CỦA BẠN:</b>\n"
            f"• 👥 Tổng bạn bè đã mời: <b>{total_invited} người bạn</b>\n"
            f"• 🎯 Tiến độ nhận lượt tiếp theo: <b>{progress_in_step}/5 người</b>\n"
            f"• 🎁 Lượt nâng Gold miễn phí hiện có: <b>{credits} lượt</b>\n\n"
            f"🔗 <b>LINK GIỚI THIỆU CỦA BẠN:</b>\n"
            f"<code>{ref_url}</code>\n\n"
            f"👇 <i>Hãy bấm nút bên dưới để chia sẻ link cho bạn bè hoặc đăng lên TikTok/Threads ngay!</i>"
        )
        
        import urllib.parse
        share_text = urllib.parse.quote(f"⚡ Nâng Locket Gold CÓ HUY HIỆU VÀNG (BADGE GOLD 🎖️) giá học sinh sinh viên cực rẻ 17k - Tự động 100%! Nhấn vào đây để trải nghiệm ngay: {ref_url}")
        share_button_url = f"https://t.me/share/url?url={ref_url}&text={share_text}"
        
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Chia Sẻ Link Ngay Qua Telegram", url=share_button_url)],
            [InlineKeyboardButton("🔙 Quay Lại Menu", callback_data="menu_back")]
        ])
        
        await query.message.edit_text(ref_msg, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    if data in ["buy_vip", "buy_vip_month", "buy_vip_year", "buy_vip_lifetime"]:
        if data == "buy_vip_lifetime":
            pkg_type = "lifetime"
        elif data == "buy_vip_month":
            pkg_type = "month"
        else:
            pkg_type = "year"
        await send_vip_payment_card(update, context, pkg_type=pkg_type)
        return

    if data.startswith("admin_vip_upg|"):
        parts = data.split("|")
        target_uid = int(parts[1])
        days = int(parts[2]) if len(parts) > 2 else 365
        db.add_vip(target_uid, days)
        exp_str = db.get_vip_expiry(target_uid)
        
        try:
            await query.answer(f"⚡ Đã duyệt VIP ({'Vĩnh Viễn' if days >= 3000 else '1 Năm'})!", show_alert=True)
        except Exception:
            pass
            
        pkg_title = "VĨNH VIỄN (TRỌN ĐỜI)" if days >= 3000 else "1 NĂM (365 NGÀY)"
        vip_msg = (
            f"⚡ <b>ADMIN DUYỆT NHANH (MIỄN PHÍ) - GÓI VIP MEMBER {pkg_title}</b>\n\n"
            f"🎉 Gói VIP Member {pkg_title} đã được kích hoạt thành công!\n"
            f"📅 Hạn dùng VIP: <b>{exp_str}</b>\n\n"
            f"👉 <b>VUI LÒNG GỬI USERNAME HOẶC LINK LOCKET CỦA BẠN VÀO TIN NHẮN BÊN DƯỚI ĐỂ BẮT ĐẦU NÂNG GOLD NGAY:</b>"
        )
        
        try:
            await query.message.edit_text(vip_msg, parse_mode=ParseMode.HTML)
        except Exception:
            await context.bot.send_message(chat_id=query.message.chat_id, text=vip_msg, parse_mode=ParseMode.HTML)
        return

    if data.startswith("upg|") or data.startswith("admin_upg|"):
        try:
            is_admin_bypass = data.startswith("admin_upg|")
            parts = data.split("|")
            uid = parts[1]
            username = parts[2] if len(parts) > 2 else uid
            
            is_admin_user = is_admin(user_id)
            is_ctv_active = db.is_ctv(user_id)
            is_vip_active = db.is_vip(user_id)
            approved_order = db.get_unused_approved_order(user_id)

            if not (is_admin_bypass or is_admin_user or is_ctv_active or is_vip_active or approved_order):
                try:
                    await query.answer("🛒 Vui lòng đăng ký Gói 1 Năm (79k) để nâng Gold!", show_alert=True)
                except Exception:
                    pass
                await send_vip_payment_card(update, context, pkg_type="year")
                return

            active_order_id = None
            if not (is_admin_bypass or is_admin_user or is_ctv_active or is_vip_active):
                if approved_order:
                    active_order_id = approved_order['order_id']
                    db.mark_order_used(active_order_id)

            # User is authorized — process upgrade
            try:
                await query.answer("🚀 Đang xử lý...")
            except Exception:
                pass

            chat_id = query.message.chat_id
            
            # Plain text queue message (no custom emoji to avoid parse errors)
            queue_text = (
                f"✅ <b>Đã thêm vào hàng chờ kích hoạt Gold</b>\n\n"
                f"🎯 Target: <code>{username}</code>\n"
                f"⏳ Đang xử lý..."
            )
            
            # Try edit existing message, fallback to new message
            msg_id = query.message.message_id
            try:
                await query.message.edit_text(queue_text, parse_mode=ParseMode.HTML)
            except Exception as e1:
                print(f"Edit failed: {e1}")
                try:
                    new_msg = await context.bot.send_message(
                        chat_id=chat_id, text=queue_text, parse_mode=ParseMode.HTML
                    )
                    msg_id = new_msg.message_id
                except Exception as e2:
                    print(f"Send failed: {e2}")
            
            item = {
                'user_id': user_id,
                'uid': uid,
                'username': username,
                'chat_id': chat_id,
                'message_id': msg_id,
                'order_id': active_order_id,
                'lang': lang
            }
            
            async with get_lock():
                pending_items.append(item)
            
            await get_queue().put(item)
            print(f"[UPG] Queued: uid={uid} user={username} chat={chat_id} msg={msg_id}")
            return
            
        except Exception as e:
            print(f"[UPG ERROR] {e}")
            try:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"❌ Lỗi xử lý: {e}\nVui lòng thử lại.",
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass
            return

    if data.startswith("paid|"):
        order_id = data.split("|")[1]
        payment = db.get_pending_payment(order_id)
        if not payment:
            await query.answer("❌ Không tìm thấy thông tin giao dịch.", show_alert=True)
            return
            
        if payment['status'] == 'APPROVED':
            await query.answer("✅ Giao dịch đã được duyệt trước đó!", show_alert=True)
            return

        is_vip_order = order_id.startswith("V")
        order_type_str = "Đăng ký VIP Member 1 Năm (79k)" if is_vip_order else "Nâng cấp Lượt lẻ 1 Tháng (15k)"
            
        admin_text = (
            f"🔔 <b>Yêu cầu thanh toán mới ({order_type_str}):</b>\n\n"
            f"- Người mua: @{query.from_user.username or 'NoUsername'} (ID: <code>{user_id}</code>)\n"
            f"- Loại gói: <b>{order_type_str}</b>\n"
            f"- Tài khoản: <code>{payment['username']}</code>\n"
            f"- Nội dung CK: <code>{order_id}</code>\n\n"
            f"Admin hãy kiểm tra tài khoản ngân hàng xem đã nhận tiền chưa, sau đó bấm nút duyệt bên dưới!"
        )
        keyboard = [
            [InlineKeyboardButton("✅ Duyệt kích hoạt", callback_data=f"apv|{order_id}")],
            [InlineKeyboardButton("❌ Từ chối", callback_data=f"ref|{order_id}")]
        ]
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        success_msg = (
            f"📩 <b>Yêu cầu đã được gửi đến Admin!</b>\n\n"
            f"Bot sẽ tự động thực hiện kích hoạt ngay sau khi Admin xác nhận giao dịch chuyển khoản thành công. Vui lòng giữ tin nhắn này và đợi trong giây lát!"
        )
        if query.message.caption:
            await query.message.edit_caption(caption=success_msg, parse_mode=ParseMode.HTML)
        else:
            await query.message.edit_text(text=success_msg, parse_mode=ParseMode.HTML)
        return

    if data.startswith("apv|"):
        order_id = data.split("|")[1]
        payment = db.get_pending_payment(order_id)
        if not payment:
            await query.answer("❌ Không tìm thấy thông tin giao dịch.", show_alert=True)
            return
            
        if payment['status'] != 'PENDING':
            await query.answer(f"ℹ️ Giao dịch này đã được xử lý (Trạng thái: {payment['status']})", show_alert=True)
            return
            
        db.update_payment_status(order_id, "APPROVED")
        
        if order_id.startswith("Y") or order_id.startswith("V") or order_id.startswith("L"):
            is_lifetime = order_id.startswith("L")
            days = 3650 if is_lifetime else 365
            db.add_vip(payment['user_id'], days)
            exp_str = db.get_vip_expiry(payment['user_id'])
            pkg_name_str = "VIP Vĩnh Viễn" if is_lifetime else "VIP Member 1 Năm"
            
            await query.message.edit_text(
                f"✅ <b>Đã duyệt thành công Gói {pkg_name_str} cho User {payment['user_id']}!</b>\n"
                f"Hạn dùng VIP: <b>{exp_str}</b>",
                parse_mode=ParseMode.HTML
            )
            
            try:
                await context.bot.send_message(
                    chat_id=payment['chat_id'],
                    text=(
                        f"🎉 <b>CHÚC MỪNG! BẠN ĐÃ ĐƯỢC DUYỆT GÓI {pkg_name_str.upper()}!</b>\n\n"
                        f"Gói {pkg_name_str} đã được kích hoạt thành công!\n"
                        f"📅 Hạn dùng VIP: <b>{exp_str}</b>\n\n"
                        f"👉 <b>VUI LÒNG NHẬP USERNAME HOẶC LINK LOCKET CỦA BẠN VÀO TIN NHẮN BÊN DƯỚI ĐỂ TIẾN HÀNH NÂNG GOLD NGAY:</b>"
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=ForceReply(selective=True, input_field_placeholder="Username hoặc Link Locket...")
                )
            except Exception as e:
                print(f"Failed to notify user on VIP approve: {e}")
            return
        else:
            item = {
                'user_id': payment['user_id'],
                'uid': payment['uid'],
                'username': payment['username'],
                'chat_id': payment['chat_id'],
                'message_id': payment['message_id'],
                'lang': lang
            }
            
            async with get_lock():
                pending_items.append(item)
                position = len(pending_items)
                ahead = position - 1
                
            await query.message.edit_text(
                f"✅ <b>Đã duyệt giao dịch {order_id}!</b>\n"
                f"Tài khoản <code>{payment['username']}</code> đã được đưa vào hàng chờ nâng cấp.",
                parse_mode=ParseMode.HTML
            )
            
            sent_msg = None
            try:
                sent_msg = await context.bot.send_message(
                    chat_id=payment['chat_id'],
                    text=f"✅ <b>Giao dịch của bạn đã được Admin phê duyệt!</b>\n\n" + T("queued", lang).format(payment['username'], position, ahead),
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                print(f"Failed to notify user on approve: {e}")
                
            if sent_msg:
                item['message_id'] = sent_msg.message_id
                
            await get_queue().put(item)
            return

    if data.startswith("ref|"):
        order_id = data.split("|")[1]
        payment = db.get_pending_payment(order_id)
        if not payment:
            await query.answer("❌ Không tìm thấy thông tin giao dịch.", show_alert=True)
            return
            
        if payment['status'] != 'PENDING':
            await query.answer(f"ℹ️ Giao dịch này đã được xử lý (Trạng thái: {payment['status']})", show_alert=True)
            return
            
        db.update_payment_status(order_id, "DECLINED")
        
        await query.message.edit_text(
            f"❌ <b>Đã từ chối giao dịch {order_id}!</b>",
            parse_mode=ParseMode.HTML
        )
        
        try:
            await context.bot.send_message(
                chat_id=payment['chat_id'],
                text=f"❌ <b>Giao dịch của bạn đã bị từ chối!</b>\n\nNếu bạn đã chuyển khoản mà bị từ chối, vui lòng liên hệ Admin để giải quyết.",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"Failed to notify user on decline: {e}")
        return

    if data.startswith("check_pay|"):
        order_id = data.split("|")[1]
        try:
            order_code = int(order_id[1:])
        except Exception as e:
            await query.answer("❌ Mã đơn hàng không hợp lệ.", show_alert=True)
            return

        payment = db.get_pending_payment(order_id)
        if not payment:
            await query.answer("❌ Không tìm thấy thông tin giao dịch.", show_alert=True)
            return

        if payment['status'] == 'APPROVED':
            await query.answer("✅ Giao dịch này đã được duyệt và kích hoạt trước đó!", show_alert=True)
            return

        # Query PayOS API directly!
        payos_info = await payos_service.get_payment_link_information(order_code)
        if payos_info and payos_info.get("status") == "PAID":
            # Approved successfully!
            db.update_payment_status(order_id, "APPROVED")
            
            from datetime import datetime
            now_str = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
            
            if order_id.startswith("M") or order_id.startswith("Y") or order_id.startswith("V") or order_id.startswith("L"):
                if order_id.startswith("M"):
                    days = 30
                    pkg_name_str = "VIP Member 1 Tháng"
                    price_val_str = f"{int(db.get_config('price_month', 15000)):,}đ"
                    db.add_vip(payment['user_id'], 30)
                elif order_id.startswith("L"):
                    days = 3650
                    pkg_name_str = "VIP Vĩnh Viễn"
                    price_val_str = f"{int(db.get_config('price_lifetime', 89000)):,}đ"
                    db.add_vip(payment['user_id'], 3650)
                else:
                    days = 365
                    pkg_name_str = "VIP Member 1 Năm"
                    price_val_str = f"{int(db.get_config('price_year', 69000)):,}đ"
                    db.add_vip(payment['user_id'], 365)

                exp_str = db.get_vip_expiry(payment['user_id']) or "N/A"
                
                try:
                    await query.message.delete()
                except Exception:
                    pass
                
                await context.bot.send_message(
                    chat_id=payment['chat_id'],
                    text=(
                        f"🎉 <b>CHÚC MỪNG! BẠN ĐÃ ĐĂNG KÝ GÓI {pkg_name_str.upper()}!</b>\n\n"
                        f"Thanh toán qua PayOS thành công! Gói {pkg_name_str} đã tự động kích hoạt!\n"
                        f"📅 Hạn dùng VIP: <b>{exp_str}</b>\n\n"
                        f"👉 <b>VUI LÒNG NHẬP USERNAME HOẶC LINK LOCKET CỦA BẠN VÀO TIN NHẮN BÊN DƯỚI ĐỂ TIẾN HÀNH NÂNG GOLD NGAY:</b>"
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=ForceReply(selective=True, input_field_placeholder="Username hoặc Link Locket...")
                )
                
                # Revenue Notification to Admin
                admin_noti = (
                    f"💰 <b>[THÔNG BÁO DOANH THU THỰC NHẬN PAYOS]</b> 💰\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"💵 <b>Số Tiền Nhận:</b> <b>+{price_val_str}</b>\n"
                    f"🔑 <b>Gói Dịch Vụ:</b> {pkg_name_str}\n"
                    f"👤 <b>Khách Hàng Telegram:</b> ID <code>{payment['user_id']}</code> (@{payment['username']})\n"
                    f"🧾 <b>Mã Đơn PayOS:</b> <code>{order_id}</code>\n"
                    f"⏰ <b>Thời Gian:</b> <code>{now_str}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"⚡ <i>Hệ thống đã nhận tiền tự động 100% qua PayOS Gateway 24/24.</i>"
                )
                await send_noti_bot_message(admin_noti)
                await query.answer("✅ Xác nhận thanh toán thành công!", show_alert=True)
            else:
                item = {
                    'user_id': payment['user_id'],
                    'uid': payment['uid'],
                    'username': payment['username'],
                    'chat_id': payment['chat_id'],
                    'message_id': payment['message_id'],
                    'lang': lang
                }
                
                async with get_lock():
                    pending_items.append(item)
                    position = len(pending_items)
                    ahead = position - 1
                
                try:
                    await query.message.delete()
                except Exception:
                    pass
                
                sent_msg = None
                try:
                    sent_msg = await context.bot.send_message(
                        chat_id=payment['chat_id'],
                        text=f"⚡ <b>Admin Duyệt Nhanh (Miễn phí)</b>\n\n" + T("queued", item['lang']).format(payment['username'], position, ahead),
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    print(f"Failed to send queue message in check_pay: {e}")
                    
                if sent_msg:
                    item['message_id'] = sent_msg.message_id
                
                # Revenue Notification to Admin
                admin_noti = (
                    f"💰 <b>[DOANH THU PAYOS MỚI] +15.000đ</b>\n\n"
                    f"🔑 <b>Gói dịch vụ:</b> Locket Gold 1 Tháng\n"
                    f"👤 <b>Người mua ID:</b> <code>{payment['user_id']}</code>\n"
                    f"🎯 <b>Acc Locket:</b> <code>{payment['username']}</code>\n"
                    f"🧾 <b>Mã đơn PayOS:</b> <code>{order_id}</code>\n"
                    f"⏰ <b>Thời gian:</b> <code>{now_str}</code>"
                )
                await send_noti_bot_message(admin_noti)
                
                await get_queue().put(item)
                
            await query.answer("✅ Xác nhận thanh toán thành công!", show_alert=True)
        else:
            await query.answer("⚠️ Giao dịch chưa hoàn tất thanh toán trên PayOS. Vui lòng thử lại sau khi thanh toán thành công!", show_alert=True)
        return

    if data.startswith("cancel_pay|"):
        order_id = data.split("|")[1]
        db.update_payment_status(order_id, "CANCELLED")
        
        try:
            await query.message.edit_text(
                T("menu_msg", lang),
                parse_mode=ParseMode.HTML,
                reply_markup=get_main_menu_keyboard(lang)
            )
        except Exception:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=T("menu_msg", lang),
                parse_mode=ParseMode.HTML,
                reply_markup=get_main_menu_keyboard(lang)
            )
        return

async def queue_worker(app, worker_id):
    # Select token based on worker ID (round-robin)
    token_idx = (worker_id - 1) % len(TOKEN_SETS)
    token_config = TOKEN_SETS[token_idx]
    token_name = f"Token-{token_idx+1}"
    
    print(f"Worker #{worker_id} started using {token_name}...")
    
    while True:
        try:
            item = await get_queue().get()
            
            user_id = item['user_id']
            uid = item['uid']
            username = item['username']
            chat_id = item['chat_id']
            message_id = item['message_id']
            lang = item['lang']
            
            async with get_lock():
                if item in pending_items:
                    pending_items.remove(item)
                await update_pending_positions(app)

            print(f"{Clr.BLUE}[Worker #{worker_id}][{token_name}] Processing:{Clr.ENDC} UID={uid} | UserID={user_id}")

            async def edit(text):
                try:
                    await app.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    if "Message is not modified" not in str(e) and "Message to edit not found" not in str(e):
                        logger.error(f"Edit msg error: {e}")

            # Double check limit before processing (unless admin/CTV)
            is_unlimited = is_admin(user_id) or db.is_ctv(user_id)
            if not is_unlimited and not db.check_can_request(user_id):
                await edit(T("limit_reached", lang))
                get_queue().task_done()
                continue

            logs = [
                f"[SYSTEM] Worker #{worker_id} Engine Active",
                f"[TARGET] User: {username} | UID: {uid}",
                f"[SECURITY] Initializing RevenueCat Exploit Payload..."
            ]
            log_updated = [True]
            finished = [False]
            
            def safe_log_callback(msg):
                clean_msg = msg.replace(Clr.BLUE, "").replace(Clr.GREEN, "").replace(Clr.WARNING, "").replace(Clr.FAIL, "").replace(Clr.ENDC, "").replace(Clr.BOLD, "")
                logs.append(clean_msg)
                log_updated[0] = True

            async def ui_refresher():
                while not finished[0]:
                    if log_updated[0]:
                        log_updated[0] = False
                        display_logs = "\n".join(logs[-12:])
                        text = (
                            f"⚡ <b>SYSTEM LOG (WORKER #{worker_id})</b>\n\n"
                            f"<pre>{display_logs}</pre>"
                        )
                        try:
                            await app.bot.edit_message_text(
                                chat_id=chat_id,
                                message_id=message_id,
                                text=text,
                                parse_mode=ParseMode.HTML,
                                disable_web_page_preview=True
                            )
                        except:
                            pass
                    await asyncio.sleep(0.5)

            # Edit message immediately to start Terminal UI
            await edit(
                f"⚡ <b>SYSTEM LOG (WORKER #{worker_id})</b>\n\n"
                f"<pre>" + "\n".join(logs) + "</pre>"
            )

            refresher_task = asyncio.create_task(ui_refresher())
            
            success = False
            msg_result = "Unknown error"
            pid, link = None, None

            try:
                # 1. Inject Gold
                success, msg_result = await locket.inject_gold(uid, token_config, safe_log_callback)
                
                # 2. Prepare DNS profiles for iOS (P12.VN) and Android (NextDNS DoT)
                if success:
                    if not is_admin(user_id):
                        db.increment_usage(user_id)
                    render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://locket-gold-bot-ptp6.onrender.com").rstrip('/')
                    link = f"{render_url}/locket-gold-vip.mobileconfig"
                    pid, _ = await nextdns.create_profile(NEXTDNS_KEYS, safe_log_callback)
                    if not pid:
                        pid = "bbaae884"
                    safe_log_callback(f"[+] Loaded P12.VN Locket VIP Profile for iOS.")
                    safe_log_callback(f"[+] Created NextDNS DoT Node: {pid}.dns.nextdns.io for Android.")
                    safe_log_callback(f"[SUCCESS] DNS Anti-Revoke Active.")
            except Exception as ex:
                logger.error(f"Worker processing error: {ex}")
                msg_result = str(ex)
            finally:
                finished[0] = True
                refresher_task.cancel()
            
            # Log request to DB
            db.log_request(user_id, uid, "SUCCESS" if success else "FAIL")
            
            if success:
                render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://locket-gold-bot-ptp6.onrender.com").rstrip('/')
                link = f"{render_url}/locket-gold-vip.mobileconfig"
                pid_code = f"<code>{pid}.dns.nextdns.io</code>" if pid else "<code>c52224.dns.nextdns.io</code>"

                order_id = item.get('order_id')
                if order_id:
                    db.mark_order_used(order_id)
                else:
                    import time
                    order_code = int(time.time() * 1000) % 9007199254740991
                    order_id = f"UPG{order_code}"
                
                from datetime import datetime, timedelta
                
                # Check package type from order_id or DB
                import sqlite3
                is_lifetime = False
                if str(order_id).startswith("L"):
                    is_lifetime = True
                else:
                    try:
                        conn = sqlite3.connect(db.DB_NAME)
                        c = conn.cursor()
                        c.execute("SELECT expires_at FROM vip_users WHERE user_id = ?", (user_id,))
                        row = c.fetchone()
                        conn.close()
                        import time
                        if row and row[0] > int(time.time() + 365 * 24 * 3600 * 2): # more than 2 years -> lifetime
                            is_lifetime = True
                    except Exception:
                        pass
                
                if is_lifetime:
                    expiry_date = "Vĩnh Viễn (Trọn Đời)"
                    pkg_label = "Gold VIP (Vĩnh Viễn)"
                else:
                    expiry_date = (datetime.now() + timedelta(days=365)).strftime("%H:%M:%S %d/%m/%Y")
                    pkg_label = "Gold VIP (1 Năm)"

                final_msg = (
                    f"✅ <b>KÍCH HOẠT HUY HIỆU VÀNG GOLD THÀNH CÔNG 🎖️</b>\n\n"
                    f"🧾 Mã Đơn Hàng: <code>{order_id}</code>\n"
                    f"🏷️: {username}\n"
                    f"🆔: {uid}\n"
                    f"📅 Gói Dịch Vụ: <b>{pkg_label} (Có Huy Hiệu 🎖️)</b>\n"
                    f"⏰ Hạn Sử Dụng Đến: <b>{expiry_date}</b>\n\n"
                    f"📜 <b>CHÍNH SÁCH BẢO HÀNH XUÂN HẬU MEDIA:</b>\n"
                    f"• 🔰 <b>Bảo hành 1 đổi 1:</b> Hỗ trợ kích hoạt lại 100% miễn phí trọn thời gian sử dụng.\n"
                    f"• 🛡️ <b>An toàn tuyệt đối:</b> Bảo mật thông tin, giữ nguyên 100% ảnh Locket.\n"
                    f"• 👑 <b>Admin hỗ trợ 24/7:</b> @hemtainguyen\n\n"
                    f"🛡️ <b>HƯỚNG DẪN CÀI DNS CHỐNG THU HỒI GOLD (PHIÊN BẢN PRO MAX):</b>\n"
                    f"1️⃣ Vào App Locket kiểm tra đã có <b>Huy Hiệu Gold</b> chưa.\n"
                    f"2️⃣ Nếu đã có, tiến hành <b>CÀI DNS CHỐNG THU HỒI NGAY</b> (trong 45s):\n\n"
                    f"🍏 <b>Dành cho iPhone / iPad (iOS):</b>\n"
                    f"👉 <a href='{link}'><b>[BẤM VÀO ĐÂY ĐỂ TẢI HỒ SƠ XUÂN HẬU GOLD]</b></a>\n"
                    f"<i>(Mở bằng Safari ➔ Cho phép ➔ Vào Cài đặt iPhone ➔ Hồ sơ đã tải về ➔ Bấm Cài đặt)</i>\n\n"
                    f"🤖 <b>Dành cho điện thoại Android (Samsung, Xiaomi, OPPO...):</b>\n"
                    f"👉 Vào Cài đặt ➔ Mạng & Internet (Kết nối) ➔ DNS riêng tư (Private DNS) ➔ Chọn 'Tên máy chủ DNS riêng tư' và điền:\n"
                    f"<code>c52224.dns.nextdns.io</code>\n"
                    f"<i>(Hoặc điền máy chủ dự phòng: <code>dns.p12.vn</code>)</i>\n\n"
                    f"💡 <b>Lưu ý:</b> <i>Cài file DNS này 1 lần duy nhất để ĐÓNG BĂNG GOLD vĩnh viễn không bao giờ lo bị rớt trên mọi thiết bị.</i>"
                )
                
                # Directly edit the progress message to final success card!
                await edit(final_msg)
                
                # Send order notification to admin bot!
                try:
                    vn_time_str = db.format_vn_time(int(time.time()))
                    admin_noti = (
                        f"👑 <b>[BÁO CÁO NÂNG CẤP LOCKET GOLD THÀNH CÔNG]</b> 👑\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🧾 <b>Mã Đơn Hàng:</b> <code>{order_id}</code>\n"
                        f"🎖️ <b>Huy Hiệu Gold:</b> <b>ĐÃ CÓ HUY HIỆU VÀNG GOLD 🎖️ (BADGE ACTIVE)</b>\n"
                        f"👤 <b>Tài Khoản Yêu Cầu:</b> @{username} <i>(ID: <code>{user_id}</code>)</i>\n"
                        f"🆔 <b>UID Locket Target:</b> <code>{uid}</code>\n"
                        f"🔑 <b>Gói Dịch Vụ:</b> <b>{pkg_label}</b>\n"
                        f"⏰ <b>Thời Gian Hoàn Tất:</b> <code>{vn_time_str}</code>\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"⚡ <i>Payload Exploit RevenueCat đã kích hoạt bản quyền Gold 24/7 thành công vĩnh viễn trên Server Locket Cloud!</i>"
                    )
                    await send_noti_bot_message(admin_noti)
                except Exception as e_noti:
                    print(f"Failed to send admin notification: {e_noti}")

                current_photo = db.get_config("donate_photo", DONATE_PHOTO)
                if current_photo:
                    try:
                        await app.bot.send_photo(
                            chat_id=chat_id,
                            photo=current_photo,
                            caption=final_msg,
                            parse_mode=ParseMode.HTML
                        )
                    except Exception as e:
                        print(f"Optional photo error: {e}")

                # Cooldown 45s per worker
                await asyncio.sleep(45)
            else:
                final_msg = f"{T('fail_title', lang)}\nInfo:\n<code>{msg_result}</code>"
                await edit(final_msg)
                
            get_queue().task_done()
            
        except Exception as e:
            logger.error(f"Worker #{worker_id} Exception: {e}")
            get_queue().task_done()

def run_bot():
    logging.basicConfig(
        format='%(message)s',
        level=logging.INFO
    )
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("telegram").setLevel(logging.ERROR)
    logging.getLogger("aiohttp").setLevel(logging.ERROR)

    async def post_init(application):
        print("🚀 [SYSTEM] Initializing Queue Workers...")
        for i in range(1, NUM_WORKERS + 1):
            asyncio.create_task(queue_worker(application, i))

        async def periodic_db_backup():
            while True:
                await asyncio.sleep(60)
                try:
                    db.backup_db_to_json()
                except Exception:
                    pass

        asyncio.create_task(periodic_db_backup())

        # Always start a lightweight HTTP server for Render/Koyeb port binding & health checks
        try:
            from aiohttp import web
            port = int(os.environ.get("PORT", "10000"))

            async def health_check(request):
                return web.Response(text="Bot is running healthy!")

            async def payos_webhook(request):
                try:
                    payload = await request.json()
                    if payos_service.verify_webhook_data(payload):
                        data = payload["data"]
                        order_code = data["orderCode"]
                        
                        order_id_m = f"M{order_code}"
                        order_id_y = f"Y{order_code}"
                        order_id_l = f"L{order_code}"
                        order_id_g = f"G{order_code}"
                        order_id_v = f"V{order_code}"
                        
                        payment = (db.get_pending_payment(order_id_m) or 
                                   db.get_pending_payment(order_id_y) or 
                                   db.get_pending_payment(order_id_l) or 
                                   db.get_pending_payment(order_id_g) or 
                                   db.get_pending_payment(order_id_v))
                        if payment and payment['status'] == 'PENDING':
                            actual_order_id = payment.get('order_id', order_id_g)
                            db.update_payment_status(actual_order_id, "APPROVED")
                            
                            from datetime import datetime
                            now_str = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
                            
                            if str(actual_order_id).startswith("V"):
                                db.add_vip(payment['user_id'], 365)
                                exp_str = db.get_vip_expiry(payment['user_id'])
                                try:
                                    await application.bot.send_message(
                                        chat_id=payment['chat_id'],
                                        text=f"🎉 <b>CHÚC MỪNG! BẠN ĐÃ ĐĂNG KÝ GÓI VIP MEMBER 1 NĂM!</b>\n\nThanh toán qua PayOS thành công! Gói VIP Member 1 Năm đã tự động kích hoạt!\n📅 Hạn dùng VIP: <b>{exp_str}</b>\n\n🚀 Bạn đã sở hữu bản quyền Locket Gold 1 Năm (365 Ngày) cho tài khoản <code>{payment['username']}</code>!",
                                        parse_mode=ParseMode.HTML
                                    )
                                except Exception as e:
                                    print(f"PayOS Webhook notify user error: {e}")

                                # Revenue Notification to Admin via Dedicated Notification Bot!
                                admin_noti = (
                                    f"💰 <b>[DOANH THU PAYOS MỚI] +79.000đ</b>\n\n"
                                    f"👑 <b>Gói dịch vụ:</b> VIP Member 1 Năm (79k)\n"
                                    f"👤 <b>Khách hàng:</b> ID <code>{payment['user_id']}</code> (@{payment['username']})\n"
                                    f"🧾 <b>Mã đơn PayOS:</b> <code>{actual_order_id}</code>\n"
                                    f"⏰ <b>Thời gian:</b> <code>{now_str}</code>"
                                )
                                await send_noti_bot_message(admin_noti)
                            else:
                                item = {
                                    'user_id': payment['user_id'],
                                    'uid': payment['uid'],
                                    'username': payment['username'],
                                    'chat_id': payment['chat_id'],
                                    'message_id': payment['message_id'],
                                    'lang': db.get_lang(payment['user_id']) or DEFAULT_LANG
                                }
                                
                                async with get_lock():
                                    pending_items.append(item)
                                    position = len(pending_items)
                                    ahead = position - 1
                                
                                sent_msg = None
                                try:
                                    sent_msg = await application.bot.send_message(
                                        chat_id=payment['chat_id'],
                                        text=f"⚡ <b>Admin Duyệt Nhanh (Miễn phí)</b>\n\n" + T("queued", item['lang']).format(payment['username'], position, ahead),
                                        parse_mode=ParseMode.HTML
                                    )
                                except Exception as e:
                                    print(f"PayOS Webhook notify user error: {e}")
                                    
                                if sent_msg:
                                    item['message_id'] = sent_msg.message_id
                                    
                                # Revenue Notification to Admin via Dedicated Notification Bot!
                                admin_noti = (
                                    f"💰 <b>[DOANH THU PAYOS MỚI] +15.000đ</b>\n\n"
                                    f"🔑 <b>Gói dịch vụ:</b> Locket Gold 1 Tháng\n"
                                    f"👤 <b>Người mua ID:</b> <code>{payment['user_id']}</code>\n"
                                    f"🎯 <b>Acc Locket:</b> <code>{payment['username']}</code>\n"
                                    f"🧾 <b>Mã đơn PayOS:</b> <code>{actual_order_id}</code>\n"
                                    f"⏰ <b>Thời gian:</b> <code>{now_str}</code>"
                                )
                                await send_noti_bot_message(admin_noti)
                                    
                                await get_queue().put(item)
                            
                    return web.json_response({"success": True})
                except Exception as e:
                    print(f"Webhook error: {e}")
                    return web.json_response({"success": False}, status=400)

            async def serve_mobileconfig(request):
                config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locket-gold-vip.mobileconfig")
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    return web.Response(
                        text=content,
                        content_type="application/x-apple-aspen-config",
                        headers={
                            "Content-Disposition": 'attachment; filename="locket-gold-vip.mobileconfig"'
                        }
                    )
                except Exception as e:
                    return web.Response(text=f"Error serving mobileconfig: {e}", status=500)

            async def serve_dashboard(request):
                dash_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
                try:
                    with open(dash_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    return web.Response(text=content, content_type="text/html")
                except Exception as e:
                    return web.Response(text=f"Dashboard Error: {e}", status=500)

            async def api_stats_json(request):
                try:
                    stats = db.get_detailed_stats()
                    txs = db.get_recent_transactions()
                    users = db.get_users_table_data()
                    ctvs = db.get_all_ctvs()
                    top_users = db.get_top_users(10)
                    p_year = int(db.get_config("price_year", 79000))
                    return web.json_response({
                        "success": True,
                        "stats": stats,
                        "transactions": txs,
                        "users": users,
                        "ctvs": ctvs,
                        "top_users": top_users,
                        "price_single": p_year,
                        "price_vip": p_year
                    })
                except Exception as e:
                    return web.json_response({"success": False, "error": str(e)}, status=500)

            async def api_add_ctv(request):
                try:
                    data = await request.json()
                    target_user_id = int(data.get("user_id"))
                    days = int(data.get("days", 29))
                    exp_ts = db.add_ctv(target_user_id, days)
                    ctv_info = db.get_ctv_info(target_user_id)
                    return web.json_response({
                        "success": True,
                        "user_id": target_user_id,
                        "remaining_str": ctv_info.get("countdown_str", "")
                    })
                except Exception as e:
                    return web.json_response({"success": False, "error": str(e)}, status=400)

            async def api_remove_ctv(request):
                try:
                    data = await request.json()
                    target_user_id = int(data.get("user_id"))
                    db.remove_ctv(target_user_id)
                    return web.json_response({"success": True, "user_id": target_user_id})
                except Exception as e:
                    return web.json_response({"success": False, "error": str(e)}, status=400)

            async def api_add_vip(request):
                try:
                    data = await request.json()
                    target_user_id = int(data.get("user_id"))
                    days = int(data.get("days", 365))
                    db.add_vip(target_user_id, days)
                    exp_str = db.get_vip_expiry(target_user_id)
                    return web.json_response({
                        "success": True,
                        "user_id": target_user_id,
                        "expires_at": exp_str
                    })
                except Exception as e:
                    return web.json_response({"success": False, "error": str(e)}, status=400)

            async def api_revoke_vip(request):
                try:
                    data = await request.json()
                    target_user_id = int(data.get("user_id"))
                    db.remove_vip(target_user_id)
                    return web.json_response({"success": True, "user_id": target_user_id})
                except Exception as e:
                    return web.json_response({"success": False, "error": str(e)}, status=400)

            async def api_setprice(request):
                try:
                    data = await request.json()
                    new_single = int(data.get("price_single", 15000))
                    new_vip = int(data.get("price_vip", 69000))
                    db.set_config("price_single", str(new_single))
                    db.set_config("price_vip", str(new_vip))
                    return web.json_response({
                        "success": True,
                        "price_single": new_single,
                        "price_vip": new_vip
                    })
                except Exception as e:
                    return web.json_response({"success": False, "error": str(e)}, status=400)

            async def api_debug(request):
                try:
                    bot_token_masked = BOT_TOKEN[:6] + "..." + BOT_TOKEN[-4:] if len(BOT_TOKEN) > 10 else "Too short"
                    bot_me = None
                    try:
                        me = await app.bot.get_me()
                        bot_me = {
                            "username": me.username,
                            "id": me.id,
                            "first_name": me.first_name
                        }
                    except Exception as e_me:
                        bot_me = f"Error: {e_me}"
                    return web.json_response({
                        "success": True,
                        "bot_token_masked": bot_token_masked,
                        "admin_id": ADMIN_ID,
                        "telegram_bot_info": bot_me,
                        "db_exists": os.path.exists(db.DB_NAME),
                        "env_bot_token": bool(os.environ.get("BOT_TOKEN")),
                        "pending_items_count": len(pending_items)
                    })
                except Exception as e:
                    return web.json_response({"success": False, "error": str(e)}, status=500)

            async def api_login(request):
                try:
                    data = await request.json()
                    password = data.get("password", "")
                    if password == "xuanhauvn@2024":
                        return web.json_response({"success": True, "token": "admin_session_xuanhau_2024"})
                    else:
                        return web.json_response({"success": False, "error": "Mật khẩu không chính xác!"}, status=401)
                except Exception as e:
                    return web.json_response({"success": False, "error": str(e)}, status=400)

            async def api_broadcast(request):
                try:
                    data = await request.json()
                    message_text = data.get("message", "").strip()
                    if not message_text:
                        return web.json_response({"success": False, "error": "Nội dung tin nhắn không được để trống!"}, status=400)
                    
                    users = db.get_all_users()
                    if not users:
                        return web.json_response({"success": False, "error": "Chưa có người dùng nào trong CSDL!"}, status=400)

                    status_msg = await app.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"📢 <b>[WEB BROADCAST INITIATED]</b>\nĐang gửi tới {len(users)} khách hàng...",
                        parse_mode=ParseMode.HTML
                    )

                    asyncio.create_task(broadcast_worker(app.bot, users, message_text, status_msg.chat_id, status_msg.message_id))
                    return web.json_response({"success": True, "total_users": len(users)})
                except Exception as e:
                    return web.json_response({"success": False, "error": str(e)}, status=500)

            web_app = web.Application()
            web_app.router.add_get('/', health_check)
            web_app.router.add_get('/quantridev', serve_dashboard)
            web_app.router.add_get('/quantri', serve_dashboard)
            web_app.router.add_get('/health', health_check)
            web_app.router.add_get('/api/stats', api_stats_json)
            web_app.router.add_get('/api/debug', api_debug)
            web_app.router.add_post('/api/login', api_login)
            web_app.router.add_post('/api/broadcast', api_broadcast)
            web_app.router.add_post('/api/addvip', api_add_vip)
            web_app.router.add_post('/api/revokevip', api_revoke_vip)
            web_app.router.add_post('/api/addctv', api_add_ctv)
            web_app.router.add_post('/api/removectv', api_remove_ctv)
            web_app.router.add_post('/api/setprice', api_setprice)
            web_app.router.add_post('/payos-webhook', payos_webhook)
            web_app.router.add_get('/locket-gold-vip.mobileconfig', serve_mobileconfig)
            web_app.router.add_get('/dns.mobileconfig', serve_mobileconfig)
            web_app.router.add_get('/dns', serve_mobileconfig)

            runner = web.AppRunner(web_app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', port)
            await site.start()
            print(f"HTTP Health Check Server running on port {port}...")

            # Self-ping background task every 5 minutes to prevent Render Free Tier from sleeping!
            async def keep_render_alive():
                render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://locket-gold-bot-ptp6.onrender.com").rstrip('/')
                health_url = f"{render_url}/health"
                while True:
                    await asyncio.sleep(300) # 5 minutes
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(health_url, timeout=10) as resp:
                                pass
                    except Exception as e:
                        pass

            asyncio.create_task(keep_render_alive())
        except Exception as e:
            print(f"Error starting health check server: {e}")

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setlang", setlang_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("noti", noti_command))
    app.add_handler(CommandHandler("rs", reset_command))
    app.add_handler(CommandHandler("setdonate", set_donate_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("addvip", addvip_command))
    app.add_handler(CommandHandler("addctv", addctv_command))
    app.add_handler(CommandHandler("delctv", delctv_command))
    app.add_handler(CommandHandler("ctv", ctv_command))
    app.add_handler(CommandHandler("setprice", setprice_command))
    app.add_handler(CommandHandler("setbank", setbank_command))
    
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print(f"Bot is running... ({NUM_WORKERS} workers)")
    app.run_polling()
