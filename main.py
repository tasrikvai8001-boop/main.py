import importlib.util
import subprocess
import sys

# Flask অটো-ইনস্টল চেক
if importlib.util.find_spec("flask") is None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask"])

from flask import Flask
import threading
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import json
import os
import time
import random
import string

# ============================================
# --- WEB SERVER FOR RENDER (FREE HOSTING) ---
# ============================================
app = Flask('')

@app.route('/')
def home():
    return "Fast Pay Bot is running 24/7!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()

# ============================================
# --- CONFIGURATION ---
# ============================================
TOKEN = "8979865542:AAH7VUTHGERuV2y_7lDcjNRskzMind3D6h0"  # আপনার বট টোকেন
ADMIN_ID = 7833766898          # আপনার টেলিগ্রাম ID
BOT_NAME = "Fast Pay Bot"
DATA_FILE = "fast_pay_bot_data.json"

bot = telebot.TeleBot(TOKEN, num_threads=50)
data_lock = threading.RLock()

# ============================================
# --- STYLE PATCH FOR TELEBOT BUTTONS ---
# ============================================
_old_inline_dict = InlineKeyboardButton.to_dict
def _new_inline_dict(self):
    d = _old_inline_dict(self)
    if hasattr(self, 'style'): d['style'] = self.style
    return d
InlineKeyboardButton.to_dict = _new_inline_dict

_old_kb_dict = KeyboardButton.to_dict
def _new_kb_dict(self):
    d = _old_kb_dict(self)
    if hasattr(self, 'style'): d['style'] = self.style
    return d
KeyboardButton.to_dict = _new_kb_dict

def ibtn(text, callback_data=None, url=None, style=None):
    kwargs = {'text': text}
    if callback_data: kwargs['callback_data'] = callback_data
    if url: kwargs['url'] = url
    b = InlineKeyboardButton(**kwargs)
    if style: b.style = style
    return b

def rbtn(text, style=None):
    b = KeyboardButton(text=text)
    if style: b.style = style
    return b

# ============================================
# --- DATABASE MANAGEMENT ---
# ============================================
def load_data():
    with data_lock:
        default_data = {
            "users": {},
            "banned_users": [],
            "force_channels": [],
            "daily_bonus_amount": 5.0,
            "ref_bonus": 2.0,
            "leaderboard": {
                "last_reset": time.time(),
                "daily_refs": {}  # user_id: count
            },
            "tasks": {
                "telegram": [],  
                "app": [],       
                "gmail": []      
            },
            "withdraw_methods": {
                "bKash": {"enabled": True, "min": 50.0},
                "Nagad": {"enabled": True, "min": 50.0},
                "USDT BEP20": {"enabled": True, "min": 100.0}
            },
            "ref_box_levels": {
                "30": {"req_ref": 5, "reward": 30},
                "60": {"req_ref": 10, "reward": 60},
                "90": {"req_ref": 15, "reward": 90},
                "120": {"req_ref": 20, "reward": 120},
                "150": {"req_ref": 25, "reward": 150},
                "200": {"req_ref": 30, "reward": 200},
                "300": {"req_ref": 40, "reward": 300},
                "500": {"req_ref": 60, "reward": 500},
                "1000": {"req_ref": 100, "reward": 1000},
                "5000": {"req_ref": 500, "reward": 5000}
            },
            "pending_proofs": {},
            "pending_withdraws": {},
            "pending_gmail_verifications": {}
        }
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, "w", encoding='utf-8') as f:
                json.dump(default_data, f, indent=4)
            return default_data
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
                for key, val in default_data.items():
                    if key not in data:
                        data[key] = val
                return data
        except:
            return default_data

def save_data(data):
    with data_lock:
        try:
            with open(DATA_FILE, "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print("Database Save Error:", e)

def get_user(user_id):
    data = load_data()
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "balance": 0.0,
            "total_income": 0.0,
            "total_withdraw": 0.0,
            "referrals": 0,
            "referred_by": None,
            "ref_rewarded": False,
            "last_bonus": 0,
            "claimed_ref_boxes": [],
            "claimed_lb_tiers": [],
            "approved_tasks": 0,
            "rejected_tasks": 0,
            "pending_tasks": 0,
            "completed_tasks": [], 
            "state": None,
            "temp_withdraw": {},
            "active_gmail_task": None
        }
        save_data(data)
    return data["users"][uid]

def update_user(user_id, key, value):
    data = load_data()
    uid = str(user_id)
    if uid in data["users"]:
        data["users"][uid][key] = value
        save_data(data)

# ============================================
# --- LEADERBOARD LOGIC & AUTOMATIC RESET ---
# ============================================
def check_and_reset_leaderboard(data):
    now = time.time()
    lb = data.get("leaderboard", {"last_reset": now, "daily_refs": {}})
    if now - lb.get("last_reset", now) >= 86400:
        lb["last_reset"] = now
        lb["daily_refs"] = {}
        data["leaderboard"] = lb
        for u in data["users"]:
            data["users"][u]["claimed_lb_tiers"] = []
        save_data(data)

# ============================================
# --- GMAIL NAME/USERNAME GENERATOR ---
# ============================================
FIRST_NAMES = ["Tanvir", "Rahim", "Kareem", "Sabbir", "Arif", "Mahmud", "Shakib", "Naim", "Fahim", "Hasan"]
LAST_NAMES = ["Hossain", "Islam", "Ahmed", "Chowdhury", "Khan", "Uddin", "Rahman", "Mia", "Ali", "Sarker"]

def generate_random_gmail_credentials():
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    rand_num = random.randint(1000, 99999)
    email = f"{first.lower()}{last.lower()}{rand_num}@gmail.com"
    return first, last, email

# ============================================
# --- FORCE JOIN CHECKER ---
# ============================================
def check_force_join(user_id):
    data = load_data()
    channels = data.get("force_channels", [])
    if not channels:
        return True
    
    for ch in channels:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            return False
    return True

def get_force_join_markup():
    data = load_data()
    markup = InlineKeyboardMarkup(row_width=1)
    for ch in data.get("force_channels", []):
        ch_clean = ch.replace("@", "")
        markup.add(ibtn("📢 Join Now", url=f"https://t.me/{ch_clean}", style="primary"))
    markup.add(ibtn("✅ Verify Now", callback_data="check_join", style="success"))
    return markup

# ============================================
# --- KEYBOARDS & UI ---
# ============================================
def get_main_menu(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(rbtn("💰 Balance", "primary"), rbtn("👥 Invite Friends", "primary"))
    markup.add(rbtn("📝 Daily Task", "primary"), rbtn("🎁 Daily Bonus", "primary"))
    markup.add(rbtn("📥 Withdraw", "primary"), rbtn("🎁 Referral Box", "primary"))
    markup.add(rbtn("🏆 Leaderboard", "primary"))
    
    if int(user_id) == ADMIN_ID:
        markup.add(rbtn("⚙️ Admin Panel", "danger"))
    return markup

def get_admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(rbtn("📢 Force Join Settings", "primary"), rbtn("➕ Add Task", "success"))
    markup.add(rbtn("💳 Withdraw Settings", "primary"), rbtn("🎁 Ref Box Settings", "primary"))
    markup.add(rbtn("🔎 Pending Approvals", "primary"), rbtn("📥 Pending Withdraws", "primary"))
    markup.add(rbtn("📢 Broadcast", "primary"), rbtn("📊 Bot Statistics", "primary"))
    markup.add(rbtn("🗑️ Task Delete/Edit", "danger"), rbtn("⛔ Ban/Unban User", "danger"))
    markup.add(rbtn("⚙️ Set Ref Bonus", "primary"), rbtn("🎁 Set Daily Bonus", "primary"))
    markup.add(rbtn("➕ Add Balance", "success"), rbtn("🏆 Leaderboard", "primary"))
    markup.add(rbtn("🔙 Main Menu", "danger"))
    return markup

# ============================================
# --- REFERRAL REWARD LOGIC ---
# ============================================
def process_referral_reward(user_id):
    data = load_data()
    check_and_reset_leaderboard(data)
    
    uid = str(user_id)
    user = data["users"].get(uid)
    if user and user.get("referred_by") and not user.get("ref_rewarded"):
        ref_id = str(user["referred_by"])
        if ref_id in data["users"]:
            bonus = data.get("ref_bonus", 2.0)
            data["users"][ref_id]["balance"] += bonus
            data["users"][ref_id]["total_income"] += bonus
            data["users"][ref_id]["referrals"] += 1
            data["users"][uid]["ref_rewarded"] = True
            
            lb_refs = data["leaderboard"]["daily_refs"].get(ref_id, 0)
            data["leaderboard"]["daily_refs"][ref_id] = lb_refs + 1
            
            save_data(data)
            try:
                bot.send_message(ref_id, f"🎉 <b>New Referral Joined!</b>\nআপনি <b>${bonus:.2f}</b> রেফার বোনাস পেয়েছেন!", parse_mode="HTML")
            except:
                pass

# ============================================
# --- BOT HANDLERS ---
# ============================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    data = load_data()
    check_and_reset_leaderboard(data)

    if str(user_id) in data.get("banned_users", []):
        bot.send_message(message.chat.id, "⛔ আপনি এই বটে ব্লকড আছেন।")
        return

    user = get_user(user_id)
    
    args = message.text.split()
    if len(args) > 1 and user.get("referred_by") is None:
        ref_id = args[1]
        if ref_id != str(user_id) and ref_id in data["users"]:
            update_user(user_id, "referred_by", ref_id)

    if not check_force_join(user_id):
        msg = f"<b>👋 Welcome to {BOT_NAME}!</b>\n\nবটটি ব্যবহার করতে নিচের চ্যানেলগুলোতে জয়েন করুন এবং 'Verify Now' এ ক্লিক করুন:"
        bot.send_message(message.chat.id, msg, parse_mode="HTML", reply_markup=get_force_join_markup())
        return

    process_referral_reward(user_id)

    welcome_text = f"<b>Welcome to {BOT_NAME}!</b>\nনিচের মেনু থেকে আপনার কাঙ্খিত অপশনটি বেছে নিন:"
    bot.send_message(message.chat.id, welcome_text, parse_mode="HTML", reply_markup=get_main_menu(user_id))

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo'])
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""
    data = load_data()
    check_and_reset_leaderboard(data)

    if str(user_id) in data.get("banned_users", []):
        bot.send_message(message.chat.id, "⛔ আপনি এই বটে ব্লকড আছেন।")
        return

    user = get_user(user_id)
    state = user.get("state")

    if not check_force_join(user_id):
        bot.send_message(message.chat.id, "⚠️ আপনি চ্যানেল থেকে লিভ নিয়েছেন বা জয়েন করেননি! দয়া করে জয়েন করুন:", reply_markup=get_force_join_markup())
        return

    if message.photo and state and state.startswith("submit_proof_"):
        task_type, task_id = state.replace("submit_proof_", "").split("_")
        photo_id = message.photo[-1].file_id
        
        proof_key = f"{user_id}_{int(time.time())}"
        data["pending_proofs"][proof_key] = {
            "user_id": user_id,
            "task_type": task_type,
            "task_id": int(task_id),
            "photo_id": photo_id
        }
        
        uid = str(user_id)
        data["users"][uid]["pending_tasks"] += 1
        data["users"][uid]["state"] = None
        data["users"][uid]["completed_tasks"].append(f"{task_type}_{task_id}")
        save_data(data)

        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            ibtn("✅ Approve", callback_data=f"appr_{proof_key}", style="success"),
            ibtn("❌ Reject", callback_data=f"rej_{proof_key}", style="danger")
        )
        bot.send_photo(
            ADMIN_ID, 
            photo_id, 
            caption=f"📩 <b>New Proof Submission!</b>\nUser: <code>{user_id}</code>\nTask Type: {task_type}\nTask ID: {task_id}", 
            parse_mode="HTML",
            reply_markup=markup
        )
        bot.send_message(message.chat.id, "✅ আপনার স্ক্রিনশট জমা হয়েছে! এডমিন যাচাই করে ব্যালেন্স যোগ করে দেবে।", reply_markup=get_main_menu(user_id))
        return

    if state == "with_enter_address":
        method = user["temp_withdraw"].get("method")
        user["temp_withdraw"]["address"] = text
        user["state"] = "with_enter_amount"
        data["users"][str(user_id)] = user
        save_data(data)
        min_limit = data["withdraw_methods"][method]["min"]
        bot.send_message(message.chat.id, f"💵 আপনার উইথড্র পরিমাণ লিখুন (মেথড: {method}, মিনিমাম: ${min_limit:.2f}):")
        return

    elif state == "with_enter_amount":
        try:
            amt = float(text)
            method = user["temp_withdraw"].get("method")
            address = user["temp_withdraw"].get("address")
            min_limit = data["withdraw_methods"][method]["min"]

            if amt < min_limit:
                bot.send_message(message.chat.id, f"❌ মিনিমাম উইথড্র পরিমাণ ${min_limit:.2f}!")
                return
            if amt > user["balance"]:
                bot.send_message(message.chat.id, f"❌ আপনার পর্যাপ্ত ব্যালেন্স নেই! বর্তমান ব্যালেন্স: ${user['balance']:.2f}")
                return

            uid = str(user_id)
            data["users"][uid]["balance"] -= amt
            data["users"][uid]["state"] = None
            w_id = f"w_{user_id}_{int(time.time())}"
            data["pending_withdraws"][w_id] = {
                "user_id": user_id,
                "method": method,
                "address": address,
                "amount": amt
            }
            save_data(data)

            bot.send_message(message.chat.id, f"✅ আপনার ${amt:.2f} ({method}) উইথড্র রিকোয়েস্ট জমা হয়েছে!", reply_markup=get_main_menu(user_id))
            
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                ibtn("✅ Approve", callback_data=f"wappr_{w_id}", style="success"),
                ibtn("❌ Reject", callback_data=f"wrej_{w_id}", style="danger")
            )
            bot.send_message(ADMIN_ID, f"📥 <b>New Withdrawal Request!</b>\nUser: <code>{user_id}</code>\nMethod: {method}\nAddress: <code>{address}</code>\nAmount: ${amt:.2f}", parse_mode="HTML", reply_markup=markup)
            return
        except ValueError:
            bot.send_message(message.chat.id, "❌ অনুগ্রহ করে সঠিক সংখ্যা লিখুন:")
            return

    if int(user_id) == ADMIN_ID and state:
        if state == "add_force_channel":
            if text.startswith("@"):
                data["force_channels"].append(text)
                save_data(data)
                bot.send_message(message.chat.id, f"✅ চ্যানেল যুক্ত হয়েছে: {text}")
            else:
                bot.send_message(message.chat.id, "❌ ইউজারনেম `@` দিয়ে শুরু হতে হবে।")
            update_user(user_id, "state", None)
            return

        elif state == "add_tg_task":
            try:
                link, limit, rate = text.split("|")
                task = {
                    "id": len(data["tasks"]["telegram"]) + 1,
                    "link": link.strip(),
                    "rate": float(rate.strip()),
                    "limit": int(limit.strip()),
                    "completed": 0
                }
                data["tasks"]["telegram"].append(task)
                save_data(data)
                bot.send_message(message.chat.id, "✅ টেলিগ্রাম চ্যানেল টাস্ক যুক্ত হয়েছে!")
            except:
                bot.send_message(message.chat.id, "❌ সঠিক ফরম্যাটে লিখুন:\n`Link | Limit | Rate`", parse_mode="Markdown")
            update_user(user_id, "state", None)
            return

        elif state == "add_app_task":
            try:
                link, desc, rate, limit = text.split("|")
                task = {
                    "id": len(data["tasks"]["app"]) + 1,
                    "link": link.strip(),
                    "desc": desc.strip(),
                    "rate": float(rate.strip()),
                    "limit": int(limit.strip()),
                    "completed": 0
                }
                data["tasks"]["app"].append(task)
                save_data(data)
                bot.send_message(message.chat.id, "✅ অ্যাপ ডাউনলোড টাস্ক যুক্ত হয়েছে!")
            except:
                bot.send_message(message.chat.id, "❌ সঠিক ফরম্যাটে লিখুন:\n`Link | Description | Rate | Limit`", parse_mode="Markdown")
            update_user(user_id, "state", None)
            return

        elif state == "add_gmail_task":
            try:
                password, rate, limit = text.split("|")
                task = {
                    "id": len(data["tasks"]["gmail"]) + 1,
                    "password": password.strip(),
                    "rate": float(rate.strip()),
                    "limit": int(limit.strip()),
                    "completed": 0
                }
                data["tasks"]["gmail"].append(task)
                save_data(data)
                bot.send_message(message.chat.id, "✅ জিমেইল টাস্ক যুক্ত হয়েছে! (ইউজারনেম এবং নেম অটো জেনারেট হবে)")
            except:
                bot.send_message(message.chat.id, "❌ সঠিক ফরম্যাটে লিখুন:\n`Password | Rate | Limit`", parse_mode="Markdown")
            update_user(user_id, "state", None)
            return

        elif state.startswith("set_min_withdraw_"):
            method = state.replace("set_min_withdraw_", "")
            try:
                min_amt = float(text)
                if method in data["withdraw_methods"]:
                    data["withdraw_methods"][method]["min"] = min_amt
                    save_data(data)
                    bot.send_message(message.chat.id, f"✅ {method} এর জন্য মিনিমাম উইথড্র লিমিট ${min_amt:.2f} করা হয়েছে!")
            except:
                bot.send_message(message.chat.id, "❌ সঠিক সংখ্যা লিখুন।")
            update_user(user_id, "state", None)
            return

        elif state == "admin_broadcast":
            count = 0
            for u in data["users"]:
                try:
                    bot.send_message(u, f"📢 <b>Broadcast Message:</b>\n\n{text}", parse_mode="HTML")
                    count += 1
                except:
                    pass
            bot.send_message(message.chat.id, f"✅ সফলভাবে {count} জন ইউজারের কাছে মেসেজ পাঠানো হয়েছে!")
            update_user(user_id, "state", None)
            return

        elif state == "admin_ban_unban":
            target = text.strip()
            if target in data["banned_users"]:
                data["banned_users"].remove(target)
                bot.send_message(message.chat.id, f"✅ User {target} Unbanned!")
            else:
                data["banned_users"].append(target)
                bot.send_message(message.chat.id, f"⛔ User {target} Banned!")
            save_data(data)
            update_user(user_id, "state", None)
            return

        elif state == "admin_set_ref_bonus":
            try:
                val = float(text)
                data["ref_bonus"] = val
                save_data(data)
                bot.send_message(message.chat.id, f"✅ রেফার বোনাস ${val} সেট করা হয়েছে!")
            except:
                bot.send_message(message.chat.id, "❌ সঠিক সংখ্যা লিখুন।")
            update_user(user_id, "state", None)
            return

        elif state == "admin_set_daily_bonus":
            try:
                val = float(text)
                data["daily_bonus_amount"] = val
                save_data(data)
                bot.send_message(message.chat.id, f"✅ ডেলি বোনাস ${val} সেট করা হয়েছে!")
            except:
                bot.send_message(message.chat.id, "❌ সঠিক সংখ্যা লিখুন।")
            update_user(user_id, "state", None)
            return

        elif state == "set_ref_box":
            try:
                tier, req, reward = text.split("|")
                tier = tier.strip()
                data["ref_box_levels"][tier] = {"req_ref": int(req.strip()), "reward": float(reward.strip())}
                save_data(data)
                bot.send_message(message.chat.id, f"✅ রেফারেল বক্স {tier} আপডেট হয়েছে!")
            except:
                bot.send_message(message.chat.id, "❌ সঠিক ফরম্যাটে লিখুন:\n`Tier | Required_Ref | Reward`", parse_mode="Markdown")
            update_user(user_id, "state", None)
            return

        elif state == "add_balance_admin":
            try:
                t_id, amt = text.split()
                amt = float(amt)
                t_id = str(t_id)
                if t_id in data["users"]:
                    data["users"][t_id]["balance"] += amt
                    data["users"][t_id]["total_income"] += amt
                    save_data(data)
                    bot.send_message(message.chat.id, f"✅ Added ${amt} to {t_id}")
                    try: bot.send_message(t_id, f"🎉 Admin added ${amt} to your balance!")
                    except: pass
                else:
                    bot.send_message(message.chat.id, "❌ ইউজার পাওয়া যায়নি।")
            except:
                bot.send_message(message.chat.id, "❌ ফরম্যাট: `USER_ID AMOUNT`", parse_mode="Markdown")
            update_user(user_id, "state", None)
            return

    if text == "💰 Balance":
        user = get_user(user_id)
        msg = (f"👤 <b>Account Details</b>\n\n"
               f"💰 Current Balance: <b>${user.get('balance', 0.0):.2f}</b>\n"
               f"💵 Total Income: <b>${user.get('total_income', 0.0):.2f}</b>\n"
               f"📤 Total Withdraw: <b>${user.get('total_withdraw', 0.0):.2f}</b>\n\n"
               f"✅ Approved Tasks: <b>{user.get('approved_tasks', 0)}</b>\n"
               f"❌ Rejected Tasks: <b>{user.get('rejected_tasks', 0)}</b>\n"
               f"⏳ Pending Tasks: <b>{user.get('pending_tasks', 0)}</b>")
        bot.send_message(message.chat.id, msg, parse_mode="HTML")

    elif text == "👥 Invite Friends":
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        msg = (f"👥 <b>Invite Friends & Earn!</b>\n\n"
               f"🔗 Referral Link:\n<code>{ref_link}</code>\n\n"
               f"📊 Total Referrals: <b>{user.get('referrals', 0)}</b>\n"
               f"🎁 Earn ${data.get('ref_bonus', 2.0)} per verified referral!")
        bot.send_message(message.chat.id, msg, parse_mode="HTML")

    elif text == "🎁 Daily Bonus":
        uid = str(user_id)
        now = time.time()
        last = user.get("last_bonus", 0)
        
        if now - last >= 86400:
            bonus = float(data.get("daily_bonus_amount", 5.0))
            data["users"][uid]["balance"] += bonus
            data["users"][uid]["total_income"] += bonus
            data["users"][uid]["last_bonus"] = now
            save_data(data)
            bot.send_message(message.chat.id, f"🎉 আপনি দৈনিক বোনাস <b>${bonus:.2f}</b> পেয়েছেন!", parse_mode="HTML")
        else:
            rem = int((86400 - (now - last)) / 3600)
            if rem < 1:
                rem_mins = int((86400 - (now - last)) / 60)
                bot.send_message(message.chat.id, f"⏳ আপনি আজ বোনাস নিয়েছেন। আর {rem_mins} মিনিট পর আবার নিতে পারবেন।")
            else:
                bot.send_message(message.chat.id, f"⏳ আপনি আজ বোনাস নিয়েছেন। আর {rem} ঘণ্টা পর আবার নিতে পারবেন।")

    elif text == "🏆 Leaderboard":
        lb_refs = data["leaderboard"].get("daily_refs", {})
        sorted_lb = sorted(lb_refs.items(), key=lambda x: x[1], reverse=True)[:10]
        
        msg = "🏆 <b>24-Hour Top Referral Leaderboard</b> 🏆\n\n"
        if not sorted_lb:
            msg += "এখনো ২৪ ঘন্টায় কোনো ইউজার রেফার শুরু করেনি।\n\n"
        else:
            for idx, (u_id, count) in enumerate(sorted_lb, 1):
                msg += f"<b>{idx}. User:</b> <code>{u_id}</code> ➔ <b>{count} Referrals</b>\n"
        
        user_daily_refs = lb_refs.get(str(user_id), 0)
        msg += f"\n📊 <b>Your 24h Referrals:</b> {user_daily_refs}\n\n"
        msg += "🎁 <b>Leaderboard Bonuses:</b>\n"
        msg += "• 10 Referrals = <b>$3.00 Bonus</b>\n"
        msg += "• 20 Referrals = <b>$7.00 Bonus</b>\n"
        msg += "• 30 Referrals = <b>$12.00 Bonus</b>\n\n"
        
        markup = InlineKeyboardMarkup()
        markup.add(ibtn("🎁 Claim Leaderboard Reward", callback_data="claim_lb_bonus", style="success"))
        bot.send_message(message.chat.id, msg, parse_mode="HTML", reply_markup=markup)

    elif text == "🎁 Referral Box":
        markup = InlineKeyboardMarkup(row_width=3)
        buttons = []
        user_refs = user.get("referrals", 0)
        claimed = user.get("claimed_ref_boxes", [])

        for tier, conf in data.get("ref_box_levels", {}).items():
            req = conf["req_ref"]
            if tier in claimed:
                btn_text = f"✅ {tier} (Claimed)"
                btn_style = "danger"
            elif user_refs >= req:
                btn_text = f"🔓 {tier} (${conf['reward']})"
                btn_style = "success"
            else:
                btn_text = f"🔒 {tier} ({user_refs}/{req})"
                btn_style = "primary"
            
            buttons.append(ibtn(btn_text, callback_data=f"claim_refbox_{tier}", style=btn_style))
        
        markup.add(*buttons)
        bot.send_message(message.chat.id, "🎁 <b>Referral Box Unlocks:</b>\nনির্দিষ্ট রেফার কমপ্লিট হলে আনলক এ চাপ দিয়ে রিওয়ার্ড নিন!", parse_mode="HTML", reply_markup=markup)

    elif text == "📝 Daily Task":
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            ibtn("📲 Telegram Join Tasks", callback_data="show_tg_tasks", style="primary"),
            ibtn("📥 App Download Tasks", callback_data="show_app_tasks", style="primary"),
            ibtn("📧 Gmail Sell Tasks", callback_data="show_gmail_tasks", style="primary")
        )
        bot.send_message(message.chat.id, "📝 <b>Available Task Categories:</b>", parse_mode="HTML", reply_markup=markup)

    elif text == "📥 Withdraw":
        markup = InlineKeyboardMarkup(row_width=1)
        for method, settings in data.get("withdraw_methods", {}).items():
            if settings["enabled"]:
                markup.add(ibtn(f"💳 {method} (Min: ${settings['min']:.2f})", callback_data=f"with_select_{method}", style="primary"))
        bot.send_message(message.chat.id, "📥 <b>Select Withdrawal Method:</b>", parse_mode="HTML", reply_markup=markup)

    elif text == "⚙️ Admin Panel" and int(user_id) == ADMIN_ID:
        bot.send_message(message.chat.id, "⚙️ <b>Fast Pay Bot Admin Controls:</b>", parse_mode="HTML", reply_markup=get_admin_menu())

    elif text == "🔎 Pending Approvals" and int(user_id) == ADMIN_ID:
        proofs = data.get("pending_proofs", {})
        gmail_proofs = data.get("pending_gmail_verifications", {})
        
        if not proofs and not gmail_proofs:
            bot.send_message(message.chat.id, "✅ কোনো পেন্ডিং টাস্ক নেই।")
        else:
            bot.send_message(message.chat.id, f"🔎 মোট পেন্ডিং স্ক্রিনশট: {len(proofs)} টি | পেন্ডিং জিমেইল: {len(gmail_proofs)} টি")
            
            for key, p in list(proofs.items()):
                markup = InlineKeyboardMarkup(row_width=2)
                markup.add(
                    ibtn("✅ Approve", callback_data=f"appr_{key}", style="success"),
                    ibtn("❌ Reject", callback_data=f"rej_{key}", style="danger")
                )
                try:
                    bot.send_photo(message.chat.id, p["photo_id"], caption=f"User: <code>{p['user_id']}</code>\nTask: {p['task_type']} #{p['task_id']}", parse_mode="HTML", reply_markup=markup)
                except:
                    pass

            for g_key, g in list(gmail_proofs.items()):
                markup = InlineKeyboardMarkup(row_width=2)
                markup.add(
                    ibtn("✅ Approve Gmail", callback_data=f"gappr_{g_key}", style="success"),
                    ibtn("❌ Reject Gmail", callback_data=f"grej_{g_key}", style="danger")
                )
                caption = (f"📧 <b>Gmail Task Verification</b>\n"
                           f"User: <code>{g['user_id']}</code>\n"
                           f"Name: {g['first_name']} {g['last_name']}\n"
                           f"Email: <code>{g['email']}</code>\n"
                           f"Password: <code>{g['password']}</code>\n"
                           f"Rate: ${g['rate']}")
                bot.send_message(message.chat.id, caption, parse_mode="HTML", reply_markup=markup)

    elif text == "📥 Pending Withdraws" and int(user_id) == ADMIN_ID:
        withdraws = data.get("pending_withdraws", {})
        if not withdraws:
            bot.send_message(message.chat.id, "✅ কোনো পেন্ডিং উইথড্র রিকোয়েস্ট নেই।")
        else:
            bot.send_message(message.chat.id, f"📥 মোট পেন্ডিং উইথড্র: {len(withdraws)} টি।")
            for w_id, w in list(withdraws.items()):
                markup = InlineKeyboardMarkup(row_width=2)
                markup.add(
                    ibtn("✅ Approve", callback_data=f"wappr_{w_id}", style="success"),
                    ibtn("❌ Reject", callback_data=f"wrej_{w_id}", style="danger")
                )
                bot.send_message(message.chat.id, f"User: <code>{w['user_id']}</code>\nMethod: {w['method']}\nAddress: <code>{w['address']}</code>\nAmount: ${w['amount']:.2f}", parse_mode="HTML", reply_markup=markup)

    elif text == "📢 Force Join Settings" and int(user_id) == ADMIN_ID:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(ibtn("➕ Add Force Channel", callback_data="admin_add_fch", style="success"))
        channels = "\n".join(data.get("force_channels", []))
        bot.send_message(message.chat.id, f"📢 <b>Current Force Channels:</b>\n{channels}", parse_mode="HTML", reply_markup=markup)

    elif text == "➕ Add Task" and int(user_id) == ADMIN_ID:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            ibtn("➕ Add Telegram Join Task", callback_data="admin_add_tg", style="primary"),
            ibtn("➕ Add App Download Task", callback_data="admin_add_app", style="primary"),
            ibtn("➕ Add Gmail Task", callback_data="admin_add_gmail", style="primary")
        )
        bot.send_message(message.chat.id, "➕ <b>Select Task Category to Add:</b>", parse_mode="HTML", reply_markup=markup)

    elif text == "📢 Broadcast" and int(user_id) == ADMIN_ID:
        update_user(user_id, "state", "admin_broadcast")
        bot.send_message(message.chat.id, "📢 সকল ইউজারের কাছে পাঠানোর জন্য মেসেজটি লিখুন:")

    elif text == "📊 Bot Statistics" and int(user_id) == ADMIN_ID:
        total_u = len(data["users"])
        total_bal = sum(u.get("balance", 0) for u in data["users"].values())
        total_wd = sum(u.get("total_withdraw", 0) for u in data["users"].values())
        msg = (f"📊 <b>Bot Statistics</b>\n\n"
               f"👥 Total Users: <b>{total_u}</b>\n"
               f"💰 Total User Balance: <b>${total_bal:.2f}</b>\n"
               f"📤 Total Withdraw Paid: <b>${total_wd:.2f}</b>\n"
               f"⏳ Pending Proofs: <b>{len(data['pending_proofs'])}</b>\n"
               f"📧 Pending Gmails: <b>{len(data['pending_gmail_verifications'])}</b>\n"
               f"📥 Pending Withdraws: <b>{len(data['pending_withdraws'])}</b>")
        bot.send_message(message.chat.id, msg, parse_mode="HTML")

    elif text == "🗑️ Task Delete/Edit" and int(user_id) == ADMIN_ID:
        markup = InlineKeyboardMarkup(row_width=1)
        for category in ["telegram", "app", "gmail"]:
            for task in data["tasks"][category]:
                markup.add(ibtn(f"❌ Delete {category.upper()} #{task['id']}", callback_data=f"del_task_{category}_{task['id']}", style="danger"))
        bot.send_message(message.chat.id, "🗑️ <b>Select Task to Delete:</b>", parse_mode="HTML", reply_markup=markup)

    elif text == "⛔ Ban/Unban User" and int(user_id) == ADMIN_ID:
        update_user(user_id, "state", "admin_ban_unban")
        bot.send_message(message.chat.id, "SEND USER_ID TO BAN/UNBAN:")

    elif text == "⚙️ Set Ref Bonus" and int(user_id) == ADMIN_ID:
        update_user(user_id, "state", "admin_set_ref_bonus")
        bot.send_message(message.chat.id, f"Current Ref Bonus: ${data.get('ref_bonus', 2.0)}\nনতুন রেফার বোনাস অ্যামাউন্ট দিন:")

    elif text == "🎁 Set Daily Bonus" and int(user_id) == ADMIN_ID:
        update_user(user_id, "state", "admin_set_daily_bonus")
        bot.send_message(message.chat.id, f"Current Daily Bonus: ${data.get('daily_bonus_amount', 5.0)}\nনতুন ডেলি বোনাস অ্যামাউন্ট দিন:")

    elif text == "🎁 Ref Box Settings" and int(user_id) == ADMIN_ID:
        update_user(user_id, "state", "set_ref_box")
        msg = "<b>Set Referral Box Tier:</b>\nSend format: `Tier | Required_Ref | Reward`"
        bot.send_message(message.chat.id, msg, parse_mode="Markdown")

    elif text == "💳 Withdraw Settings" and int(user_id) == ADMIN_ID:
        markup = InlineKeyboardMarkup(row_width=1)
        for m, val in data["withdraw_methods"].items():
            status = "🟢 ON" if val["enabled"] else "🔴 OFF"
            markup.add(
                ibtn(f"{m}: {status} (Min: ${val['min']:.2f})", callback_data=f"toggle_with_{m}", style="primary"),
                ibtn(f"✏️ Set Min Limit for {m}", callback_data=f"edit_min_with_{m}", style="success")
            )
        bot.send_message(message.chat.id, "💳 <b>Withdrawal Method Controls & Limits:</b>", parse_mode="HTML", reply_markup=markup)

    elif text == "➕ Add Balance" and int(user_id) == ADMIN_ID:
        update_user(user_id, "state", "add_balance_admin")
        bot.send_message(message.chat.id, "SEND USER_ID AND AMOUNT (E.G. `123456789 50`):", parse_mode="Markdown")

    elif text == "🔙 Main Menu":
        update_user(user_id, "state", None)
        bot.send_message(message.chat.id, "Main Menu", reply_markup=get_main_menu(user_id))

# ============================================
# --- CALLBACK HANDLERS ---
# ============================================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = load_data()
    check_and_reset_leaderboard(data)

    if str(user_id) in data.get("banned_users", []):
        bot.answer_callback_query(call.id, "⛔ আপনি ব্লকড আছেন!", show_alert=True)
        return

    user = get_user(user_id)

    if call.data == "check_join":
        if check_force_join(user_id):
            process_referral_reward(user_id)
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except: pass
            bot.send_message(call.message.chat.id, "✅ Verification Successful!", reply_markup=get_main_menu(user_id))
        else:
            bot.answer_callback_query(call.id, "❌ আপনি এখনো সবগুলো চ্যানেলে জয়েন করেননি!", show_alert=True)

    elif not check_force_join(user_id):
        bot.answer_callback_query(call.id, "⚠️ আগে সবগুলো চ্যানেলে জয়েন করুন!", show_alert=True)
        return

    elif call.data == "claim_lb_bonus":
        daily_refs = data["leaderboard"].get("daily_refs", {}).get(str(user_id), 0)
        claimed = user.get("claimed_lb_tiers", [])
        uid = str(user_id)
        
        bonus_awarded = 0.0
        tier_claimed = ""
        
        if daily_refs >= 30 and "30" not in claimed:
            bonus_awarded = 12.0
            tier_claimed = "30"
        elif daily_refs >= 20 and "20" not in claimed:
            bonus_awarded = 7.0
            tier_claimed = "20"
        elif daily_refs >= 10 and "10" not in claimed:
            bonus_awarded = 3.0
            tier_claimed = "10"
            
        if bonus_awarded > 0:
            data["users"][uid]["balance"] += bonus_awarded
            data["users"][uid]["total_income"] += bonus_awarded
            data["users"][uid]["claimed_lb_tiers"].append(tier_claimed)
            save_data(data)
            bot.answer_callback_query(call.id, f"🎉 Leaderboard Reward: ${bonus_awarded:.2f} Claimed!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ আপনার ক্লেইম করার মতো পর্যাপ্ত ২৪ ঘণ্টার রেফার নেই অথবা ইতিমধ্যে ক্লেইম করেছেন!", show_alert=True)

    elif call.data.startswith("with_select_"):
        method = call.data.replace("with_select_", "")
        uid = str(user_id)
        data["users"][uid]["temp_withdraw"] = {"method": method}
        data["users"][uid]["state"] = "with_enter_address"
        save_data(data)
        prompt = "📱 আপনার অ্যাকাউন্ট / ফোন নম্বর দিন:" if method != "USDT BEP20" else "🔗 আপনার USDT BEP20 ওয়ালেট এড্রেস দিন:"
        bot.send_message(call.message.chat.id, prompt)

    elif call.data.startswith("claim_refbox_"):
        tier = call.data.replace("claim_refbox_", "")
        conf = data["ref_box_levels"].get(tier)
        claimed = user.get("claimed_ref_boxes", [])
        uid = str(user_id)

        if tier in claimed:
            bot.answer_callback_query(call.id, "⚠️ আপনি ইতিমধ্যেই এই রিওয়ার্ড ক্লেইম করেছেন!", show_alert=True)
        elif user.get("referrals", 0) >= conf["req_ref"]:
            data["users"][uid]["balance"] += conf["reward"]
            data["users"][uid]["total_income"] += conf["reward"]
            data["users"][uid]["claimed_ref_boxes"].append(tier)
            save_data(data)
            bot.answer_callback_query(call.id, f"🎉 ${conf['reward']} আপনার ব্যালেন্সে যোগ হয়েছে!", show_alert=True)
            bot.edit_message_text("✅ Reward Claimed!", call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, f"❌ আপনার পর্যাপ্ত রেফারেল নেই! প্রয়োজনীয়: {conf['req_ref']}", show_alert=True)

    elif call.data == "show_tg_tasks":
        tasks = [t for t in data["tasks"].get("telegram", []) if t["completed"] < t["limit"] and f"telegram_{t['id']}" not in user.get("completed_tasks", [])]
        if not tasks:
            bot.answer_callback_query(call.id, "বর্তমানে কোনো টেলিগ্রাম টাস্ক খালি নেই।")
            return
        for t in tasks:
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(
                ibtn("📢 Join Channel", url=t["link"], style="primary"),
                ibtn("📤 Submit Screenshot Proof", callback_data=f"sub_proof_telegram_{t['id']}", style="success")
            )
            msg = f"📲 <b>Telegram Join Task #{t['id']}</b>\n\n💰 Reward: ${t['rate']}"
            bot.send_message(call.message.chat.id, msg, parse_mode="HTML", reply_markup=markup)

    elif call.data == "show_app_tasks":
        tasks = [t for t in data["tasks"].get("app", []) if t["completed"] < t["limit"] and f"app_{t['id']}" not in user.get("completed_tasks", [])]
        if not tasks:
            bot.answer_callback_query(call.id, "বর্তমানে কোনো অ্যাপ টাস্ক খালি নেই।")
            return
        for t in tasks:
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(
                ibtn("🌐 Open Link", url=t["link"], style="primary"),
                ibtn("📤 Submit Screenshot Proof", callback_data=f"sub_proof_app_{t['id']}", style="success")
            )
            msg = f"📱 <b>App Download Task #{t['id']}</b>\n\n{t['desc']}\n\n💰 Reward: ${t['rate']}"
            bot.send_message(call.message.chat.id, msg, parse_mode="HTML", reply_markup=markup)

    elif call.data == "show_gmail_tasks":
        tasks = [t for t in data["tasks"].get("gmail", []) if t["completed"] < t["limit"] and f"gmail_{t['id']}" not in user.get("completed_tasks", [])]
        if not tasks:
            bot.answer_callback_query(call.id, "বর্তমানে কোনো জিমেইল সেল টাস্ক খালি নেই।")
            return
        
        t = tasks[0]
        fname, lname, g_email = generate_random_gmail_credentials()
        uid = str(user_id)
        
        data["users"][uid]["active_gmail_task"] = {
            "task_id": t["id"],
            "first_name": fname,
            "last_name": lname,
            "email": g_email,
            "password": t["password"],
            "rate": t["rate"],
            "start_time": time.time()
        }
        save_data(data)

        msg = (f"📧 <b>Gmail Creation Task #{t['id']}</b>\n\n"
               f"👤 First Name: <code>{fname}</code>\n"
               f"👤 Last Name: <code>{lname}</code>\n"
               f"✉️ Gmail Email: <code>{g_email}</code>\n"
               f"🔑 Password: <code>{t['password']}</code>\n"
               f"💰 Rate: <b>${t['rate']:.2f}</b>\n\n"
               f"ℹ️ <i>টেক্সটগুলোতে চাপ দিয়ে কপি করুন। জিমেইল অ্যাকাউন্ট তৈরি শেষ হলে নিচের বাটনে চাপ দিন।</i>")
        
        markup = InlineKeyboardMarkup()
        markup.add(ibtn("✅ একাউন্ট খোলা শেষ", callback_data=f"finish_gmail_{t['id']}", style="success"))
        bot.send_message(call.message.chat.id, msg, parse_mode="HTML", reply_markup=markup)

    elif call.data.startswith("finish_gmail_"):
        t_id = int(call.data.replace("finish_gmail_", ""))
        uid = str(user_id)
        active_task = user.get("active_gmail_task")
        
        if not active_task or active_task.get("task_id") != t_id:
            bot.answer_callback_query(call.id, "❌ এই টাস্কটি সক্রিয় নেই!", show_alert=True)
            return

        elapsed = time.time() - active_task.get("start_time", 0)
        
        if elapsed < 120:
            bot.answer_callback_query(call.id, "⚠️ আপনি কোনো একাউন্ট খুলেননি! জিমেইল তৈরি করতে অন্তত ২ মিনিট সময় লাগে।", show_alert=True)
            return

        g_key = f"g_{user_id}_{int(time.time())}"
        data["pending_gmail_verifications"][g_key] = {
            "user_id": user_id,
            "task_id": t_id,
            "first_name": active_task["first_name"],
            "last_name": active_task["last_name"],
            "email": active_task["email"],
            "password": active_task["password"],
            "rate": active_task["rate"]
        }
        
        data["users"][uid]["active_gmail_task"] = None
        data["users"][uid]["pending_tasks"] += 1
        data["users"][uid]["completed_tasks"].append(f"gmail_{t_id}")
        save_data(data)

        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass

        bot.send_message(call.message.chat.id, "✅ তথ্য জমা দেওয়া হয়েছে! আপনার কাজ ৬-৭২ ঘন্টার মধ্যে এপ্রুভ হবে।")

    elif call.data.startswith("sub_proof_"):
        parts = call.data.replace("sub_proof_", "")
        update_user(user_id, "state", f"submit_proof_{parts}")
        bot.send_message(call.message.chat.id, "📸 দয়া করে কাজটি সম্পন্ন করে একটি পরিষ্কার স্কিনশট (Photo) পাঠান:")

    elif call.data.startswith("appr_") and int(user_id) == ADMIN_ID:
        key = call.data.replace("appr_", "")
        item = data["pending_proofs"].get(key)
        if item:
            u_id = str(item["user_id"])
            t_type = item["task_type"]
            t_id = item["task_id"]
            
            rate = 0.0
            for t in data["tasks"].get(t_type, []):
                if t["id"] == t_id:
                    rate = t["rate"]
                    t["completed"] += 1
                    break

            if u_id in data["users"]:
                data["users"][u_id]["balance"] += rate
                data["users"][u_id]["total_income"] += rate
                data["users"][u_id]["approved_tasks"] += 1
                if data["users"][u_id]["pending_tasks"] > 0:
                    data["users"][u_id]["pending_tasks"] -= 1

            del data["pending_proofs"][key]
            save_data(data)

            bot.edit_message_caption(f"✅ Approved! ${rate} added to {u_id}", call.message.chat.id, call.message.message_id)
            try: bot.send_message(u_id, f"🎉 আপনার জমা দেওয়া টাস্ক অনুমোদিত হয়েছে! ${rate:.2f} ব্যালেন্সে যোগ হয়েছে।")
            except: pass

    elif call.data.startswith("rej_") and int(user_id) == ADMIN_ID:
        key = call.data.replace("rej_", "")
        item = data["pending_proofs"].get(key)
        if item:
            u_id = str(item["user_id"])
            if u_id in data["users"]:
                data["users"][u_id]["rejected_tasks"] += 1
                if data["users"][u_id]["pending_tasks"] > 0:
                    data["users"][u_id]["pending_tasks"] -= 1
            
            del data["pending_proofs"][key]
            save_data(data)

            bot.edit_message_caption(f"❌ Proof Rejected for user {u_id}", call.message.chat.id, call.message.message_id)
            try: bot.send_message(u_id, "❌ আপনার জমা দেওয়া টাস্কের স্কিনশটটি বাতিল করা হয়েছে।")
            except: pass

    elif call.data.startswith("gappr_") and int(user_id) == ADMIN_ID:
        g_key = call.data.replace("gappr_", "")
        item = data["pending_gmail_verifications"].get(g_key)
        if item:
            u_id = str(item["user_id"])
            rate = item["rate"]
            t_id = item["task_id"]

            for t in data["tasks"].get("gmail", []):
                if t["id"] == t_id:
                    t["completed"] += 1
                    break

            if u_id in data["users"]:
                data["users"][u_id]["balance"] += rate
                data["users"][u_id]["total_income"] += rate
                data["users"][u_id]["approved_tasks"] += 1
                if data["users"][u_id]["pending_tasks"] > 0:
                    data["users"][u_id]["pending_tasks"] -= 1

            del data["pending_gmail_verifications"][g_key]
            save_data(data)

            bot.edit_message_text(f"✅ Gmail Approved! ${rate} added to {u_id}", call.message.chat.id, call.message.message_id)
            try: bot.send_message(u_id, f"🎉 আপনার জিমেইল টাস্ক এপ্রুভ হয়েছে! ${rate:.2f} ব্যালেন্সে যোগ হয়েছে।")
            except: pass

    elif call.data.startswith("grej_") and int(user_id) == ADMIN_ID:
        g_key = call.data.replace("grej_", "")
        item = data["pending_gmail_verifications"].get(g_key)
        if item:
            u_id = str(item["user_id"])
            if u_id in data["users"]:
                data["users"][u_id]["rejected_tasks"] += 1
                if data["users"][u_id]["pending_tasks"] > 0:
                    data["users"][u_id]["pending_tasks"] -= 1

            del data["pending_gmail_verifications"][g_key]
            save_data(data)

            bot.edit_message_text(f"❌ Gmail Rejected for user {u_id}", call.message.chat.id, call.message.message_id)
            try: bot.send_message(u_id, "❌ আপনার জমা দেওয়া জিমেইল অ্যাকাউন্টটি বাতিল করা হয়েছে।")
            except: pass

    elif call.data.startswith("wappr_") and int(user_id) == ADMIN_ID:
        w_id = call.data.replace("wappr_", "")
        item = data["pending_withdraws"].get(w_id)
        if item:
            u_id = str(item["user_id"])
            amt = item["amount"]
            if u_id in data["users"]:
                data["users"][u_id]["total_withdraw"] += amt
            del data["pending_withdraws"][w_id]
            save_data(data)
            bot.edit_message_text(f"✅ Withdrawal Approved (${amt:.2f}) for user {u_id}", call.message.chat.id, call.message.message_id)
            try: bot.send_message(u_id, f"🎉 আপনার ${amt:.2f} উইথড্র সফলভাবে সম্পন্ন হয়েছে!")
            except: pass

    elif call.data.startswith("wrej_") and int(user_id) == ADMIN_ID:
        w_id = call.data.replace("wrej_", "")
        item = data["pending_withdraws"].get(w_id)
        if item:
            u_id = str(item["user_id"])
            amt = item["amount"]
            if u_id in data["users"]:
                data["users"][u_id]["balance"] += amt
            del data["pending_withdraws"][w_id]
            save_data(data)
            bot.edit_message_text(f"❌ Withdrawal Rejected (${amt:.2f}) for user {u_id}", call.message.chat.id, call.message.message_id)
            try: bot.send_message(u_id, f"❌ আপনার ${amt:.2f} উইথড্র রিকোয়েস্ট বাতিল করা হয়েছে এবং ব্যালেন্স ফেরত দেওয়া হয়েছে।")
            except: pass

    elif call.data.startswith("del_task_") and int(user_id) == ADMIN_ID:
        _, _, category, task_id = call.data.split("_")
        task_id = int(task_id)
        data["tasks"][category] = [t for t in data["tasks"][category] if t["id"] != task_id]
        save_data(data)
        bot.answer_callback_query(call.id, "✅ টাস্ক ডিলিট হয়েছে!")
        bot.edit_message_text("🗑️ Task Deleted successfully.", call.message.chat.id, call.message.message_id)

    elif call.data.startswith("admin_add_fch"):
        update_user(user_id, "state", "add_force_channel")
        bot.send_message(call.message.chat.id, "Send Channel Username (e.g. `@MyChannel`):")

    elif call.data == "admin_add_tg":
        update_user(user_id, "state", "add_tg_task")
        bot.send_message(call.message.chat.id, "Format: `Link | Limit | Rate`", parse_mode="Markdown")

    elif call.data == "admin_add_app":
        update_user(user_id, "state", "add_app_task")
        bot.send_message(call.message.chat.id, "Format: `Link | Description | Rate | Limit`", parse_mode="Markdown")

    elif call.data == "admin_add_gmail":
        update_user(user_id, "state", "add_gmail_task")
        bot.send_message(call.message.chat.id, "Format: `Password | Rate | Limit`", parse_mode="Markdown")

    elif call.data.startswith("toggle_with_"):
        m = call.data.replace("toggle_with_", "")
        if m in data["withdraw_methods"]:
            data["withdraw_methods"][m]["enabled"] = not data["withdraw_methods"][m]["enabled"]
            save_data(data)
            bot.answer_callback_query(call.id, "Updated!")
            bot.edit_message_text("💳 Settings updated.", call.message.chat.id, call.message.message_id)

    elif call.data.startswith("edit_min_with_"):
        m = call.data.replace("edit_min_with_", "")
        update_user(user_id, "state", f"set_min_withdraw_{m}")
        bot.send_message(call.message.chat.id, f"Enter new minimum withdrawal amount for {m}:")

# ============================================
# --- BOT START ---
# ============================================
if __name__ == "__main__":
    keep_alive()  # Web server for Render Keep-Alive
    print(f"🚀 {BOT_NAME} is Running with Leaderboard, Gmail Anti-Cheat, & Limit Controls...")
    bot.infinity_polling()
