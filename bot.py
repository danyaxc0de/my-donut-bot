import telebot
from telebot import types
import sqlite3, threading, time, os
from flask import Flask

TOKEN = "8529552239:AAHQObpHylRkir7Xr4uIjiiIpV6zu2bZ4es"
ADMIN_ID = 8192413936
CHANNEL_USERNAME = "@bubmagnat"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is running"
def run_web(): app.run(host='0.0.0.0', port=8080)
threading.Thread(target=run_web, daemon=True).start()

db_lock = threading.Lock()
conn = sqlite3.connect("ai_bot.db", check_same_thread=False)
cursor = conn.cursor()

with db_lock:
    cursor.execute('''CREATE TABLE IF NOT EXISTS profiles (user_id INTEGER PRIMARY KEY, name TEXT COLLATE NOCASE UNIQUE, is_banned INTEGER DEFAULT 0, is_registered INTEGER DEFAULT 0, love_status INTEGER DEFAULT 0, partner_uid INTEGER DEFAULT NULL, gems INTEGER DEFAULT 0, referrer_id INTEGER DEFAULT NULL, subscribed INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS chats (user_id INTEGER PRIMARY KEY, partner_id INTEGER, status TEXT DEFAULT 'idle')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS queue (user_id INTEGER PRIMARY KEY, join_time INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, partner_id INTEGER, message_text TEXT, timestamp INTEGER)''')
    conn.commit()

def get_profile(uid):
    with db_lock:
        cursor.execute("SELECT name, is_banned, is_registered, love_status, partner_uid, gems, referrer_id, subscribed FROM profiles WHERE user_id = ?", (uid,))
        return cursor.fetchone()

def register_user(uid, name, ref_id=None):
    with db_lock:
        cursor.execute("INSERT OR REPLACE INTO profiles (user_id, name, is_registered, referrer_id) VALUES (?, ?, 1, ?)", (uid, name, ref_id))
        conn.commit()

def add_gems(uid, amount):
    with db_lock:
        cursor.execute("UPDATE profiles SET gems = gems + ? WHERE user_id = ?", (amount, uid))
        conn.commit()

def remove_gems(uid, amount):
    with db_lock:
        cursor.execute("UPDATE profiles SET gems = gems - ? WHERE user_id = ?", (amount, uid))
        conn.commit()

def set_subscribed(uid):
    with db_lock:
        cursor.execute("UPDATE profiles SET subscribed = 1 WHERE user_id = ?", (uid,))
        conn.commit()

def set_love_status(uid, level):
    with db_lock:
        cursor.execute("UPDATE profiles SET love_status = ? WHERE user_id = ?", (level, uid))
        conn.commit()

def set_partner(uid1, uid2):
    with db_lock:
        cursor.execute("UPDATE profiles SET partner_uid = ? WHERE user_id = ?", (uid2, uid1))
        cursor.execute("UPDATE profiles SET partner_uid = ? WHERE user_id = ?", (uid1, uid2))
        conn.commit()

def is_name_taken(name):
    with db_lock:
        cursor.execute("SELECT user_id FROM profiles WHERE name = ? COLLATE NOCASE", (name,))
        return cursor.fetchone() is not None

def is_banned(uid):
    with db_lock:
        cursor.execute("SELECT is_banned FROM profiles WHERE user_id = ?", (uid,))
        res = cursor.fetchone()
        return res and res[0] == 1

def ban_user(uid):
    with db_lock:
        cursor.execute("UPDATE profiles SET is_banned = 1 WHERE user_id = ?", (uid,))
        conn.commit()

def unban_user(uid):
    with db_lock:
        cursor.execute("UPDATE profiles SET is_banned = 0 WHERE user_id = ?", (uid,))
        conn.commit()

def get_partner_chat(uid):
    with db_lock:
        cursor.execute("SELECT partner_id, status FROM chats WHERE user_id = ?", (uid,))
        return cursor.fetchone()

def set_status(uid, status, partner_id=None):
    with db_lock:
        cursor.execute("INSERT OR REPLACE INTO chats (user_id, partner_id, status) VALUES (?, ?, ?)", (uid, partner_id, status))
        conn.commit()

def add_to_queue(uid):
    with db_lock:
        cursor.execute("INSERT OR IGNORE INTO queue (user_id, join_time) VALUES (?, ?)", (uid, int(time.time())))
        conn.commit()

def remove_from_queue(uid):
    with db_lock:
        cursor.execute("DELETE FROM queue WHERE user_id = ?", (uid,))
        conn.commit()

def find_partner(uid):
    with db_lock:
        cursor.execute("SELECT user_id FROM queue WHERE user_id != ? ORDER BY join_time ASC LIMIT 1", (uid,))
        res = cursor.fetchone()
        if res:
            partner_id = res[0]
            cursor.execute("DELETE FROM queue WHERE user_id IN (?, ?)", (uid, partner_id))
            conn.commit()
            return partner_id
    return None

def save_message(uid, partner_id, text):
    with db_lock:
        cursor.execute("INSERT INTO messages (user_id, partner_id, message_text, timestamp) VALUES (?, ?, ?, ?)", (uid, partner_id, text, int(time.time())))
        conn.commit()

def get_chat_history(uid1, uid2):
    with db_lock:
        cursor.execute("SELECT user_id, message_text FROM messages WHERE (user_id = ? AND partner_id = ?) OR (user_id = ? AND partner_id = ?) ORDER BY timestamp ASC LIMIT 30", (uid1, uid2, uid2, uid1))
        return cursor.fetchall()

def check_sub(uid):
    try:
        status = bot.get_chat_member(CHANNEL_USERNAME, uid).status
        return status in ['member', 'administrator', 'creator']
    except: return False

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔍 Искать собеседника"), types.KeyboardButton("👤 Моя анкета"))
    markup.add(types.KeyboardButton("💎 Гемы / Магазин"), types.KeyboardButton("💌 Валентинки"))
    markup.add(types.KeyboardButton("💖 Донат / Любовь"))
    return markup

def in_chat_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🛑 Стоп / Сменить"), types.KeyboardButton("⚠️ Пожаловаться"))
    return markup

@bot.message_handler(commands=['help'])
def cmd_help(message):
    text = "📖 **Помощь**\n\n🔍 **Искать собеседника** — начать анонимный чат.\n👤 **Моя анкета** — посмотреть свой профиль.\n💎 **Гемы / Магазин** — заработать или купить гемы.\n💌 **Валентинки** — отправить анонимную открытку.\n💖 **Донат / Любовь** — купить любовные статусы.\n\n⚠️ *Запрещено:* 18+, наркотики, личные данные, оскорбления. За это бан."
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['balance'])
def cmd_balance(message):
    uid = message.from_user.id
    profile = get_profile(uid)
    if profile: bot.send_message(uid, f"💎 Твой баланс: **{profile[5]} гемов**", parse_mode="Markdown")
    else: bot.send_message(uid, "❌ Ты еще не зарегистрирован. Напиши /start")

@bot.message_handler(commands=['admin'])
def cmd_admin(message):
    if message.from_user.id != ADMIN_ID: return 
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📊 Статистика", callback_data="adm_stats"), types.InlineKeyboardButton("🗣 Активные чаты", callback_data="adm_chats"))
    bot.send_message(ADMIN_ID, "👑 **Админ-панель**\n\nВыбери действие:", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "adm_stats")
def cb_adm_stats(call):
    if call.from_user.id != ADMIN_ID: return bot.answer_callback_query(call.id, "Нет доступа", show_alert=True)
    with db_lock:
        cursor.execute("SELECT COUNT(*) FROM profiles WHERE is_registered = 1")
        users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM profiles WHERE is_banned = 1")
        banned = cursor.fetchone()[0]
        cursor.execute("SELECT SUM(gems) FROM profiles")
        gems = cursor.fetchone()[0] or 0
    bot.edit_message_text(f"📊 **Статистика**\n\nПользователей: {users}\nЗабанено: {banned}\nГемов в системе: {gems}", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "adm_chats")
def cb_adm_chats(call):
    if call.from_user.id != ADMIN_ID: return bot.answer_callback_query(call.id, "Нет доступа", show_alert=True)
    with db_lock:
        cursor.execute("SELECT user_id, partner_id FROM chats WHERE status = 'chatting'")
        chats = cursor.fetchall()
    if not chats: return bot.edit_message_text("Сейчас нет активных чатов.", call.message.chat.id, call.message.message_id)
    text = "🗣 **Активные чаты:**\n\n"
    for c in chats[:10]: text += f"• `{c[0]}` ↔ `{c[1]}`\n👉 /read_{c[0]}_{c[1]}\n\n"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text.startswith("/read_"))
def cmd_read_chat(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split("_")
        uid1, uid2 = int(parts[1]), int(parts[2])
        history = get_chat_history(uid1, uid2)
        if not history: return bot.send_message(ADMIN_ID, "Нет сообщений.")
        text = f"📝 **Переписка {uid1} и {uid2}:**\n\n"
        for msg in history: text += f"`{msg[0]}`: {msg[1]}\n"
        bot.send_message(ADMIN_ID, text, parse_mode="Markdown")
    except: bot.send_message(ADMIN_ID, "❌ Ошибка формата.")

@bot.message_handler(commands=['unban'])
def cmd_unban(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        uid = int(message.text.split()[1])
        unban_user(uid)
        bot.send_message(ADMIN_ID, f"✅ {uid} разбанен.")
    except: bot.send_message(ADMIN_ID, "❌ Формат: /unban ID")

@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = message.from_user.id
    if is_banned(uid): return bot.send_message(uid, "⛔ Вы забанены.")
    remove_from_queue(uid); set_status(uid, 'idle')
    args = message.text.split()
    ref_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try: ref_id = int(args[1].replace("ref_", ""))
        except: pass
    profile = get_profile(uid)
    if not profile or profile[2] == 0:
        msg = bot.send_message(uid, "👋 Привет! Давай зарегистрируемся.\n\nПридумай себе ник (от 4 до 16 символов, только буквы и цифры):")
        bot.register_next_step_handler(msg, reg_name, ref_id)
    else: show_main_menu(uid)

def reg_name(message, ref_id=None):
    uid = message.from_user.id
    name = message.text.strip()
    if len(name) < 4 or len(name) > 16:
        msg = bot.send_message(uid, "❌ Ошибка! Ник должен быть от 4 до 16 символов.\nПопробуй снова:"); bot.register_next_step_handler(msg, reg_name, ref_id); return
    if not name.isalnum():
        msg = bot.send_message(uid, "❌ Ошибка! Ник должен состоять только из букв и цифр.\nПопробуй снова:"); bot.register_next_step_handler(msg, reg_name, ref_id); return
    bad_words = ["хуй", "пизд", "бля", "ебан", "дроч", "секс", "порн"]
    if any(word in name.lower() for word in bad_words):
        msg = bot.send_message(uid, "❌ Ошибка! Этот ник запрещен.\nПопробуй другой:"); bot.register_next_step_handler(msg, reg_name, ref_id); return
    if is_name_taken(name):
        msg = bot.send_message(uid, "❌ Ошибка! Этот ник уже занят кем-то другим.\nПридумай другой:"); bot.register_next_step_handler(msg, reg_name, ref_id); return
    register_user(uid, name, ref_id)
    if ref_id:
        add_gems(ref_id, 5)
        try: bot.send_message(ref_id, f"🎉 По твоей ссылке зашел новый пользователь! +5 гемов.")
        except: pass
        bot.send_message(uid, "✅ Ты зарегистрирован по реф. ссылке!")
    bot.send_message(uid, f"✅ Отлично, {name}! Твоя анкета создана.")
    show_main_menu(uid)

def show_main_menu(uid):
    profile = get_profile(uid)
    gems = profile[5] if profile else 0
    text = (f"🏠 Главное меню:\n💎 Твои гемы: {gems}\n\n⚠️ **ВНИМАНИЕ:** Администрация бота **не несет ответственности** за действия пользователей. Если вам предлагают наркотики, порно или мошенничество — сразу жалуйтесь.")
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == "👤 Моя анкета")
def show_profile(message):
    uid = message.from_user.id
    profile = get_profile(uid)
    if profile:
        name, love, p_uid, gems = profile[0], profile[3], profile[4], profile[5]
        status_text = "Обычный"
        if love == 1: status_text = "💖 Влюбленный"
        elif love == 2: status_text = "💍 Вторые половинки"
        elif love == 3: status_text = "👑 Романтик"
        partner_text = f"\nПартнер: `{p_uid}`" if p_uid else ""
        bot.send_message(uid, f"👤 **Твоя анкета:**\nИмя: {name}\nСтатус: {status_text}\nГемы: {gems}{partner_text}", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "💎 Гемы / Магазин")
def gems_menu(message):
    uid = message.from_user.id
    profile = get_profile(uid)
    gems = profile[5] if profile else 0
    ref_link = f"https://t.me/{bot.get_me().username}?start=ref_{uid}"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("📢 Подписаться на канал (+10 💎)", callback_data="check_sub"), types.InlineKeyboardButton("💎 Купить 10 гемов (10 ⭐)", callback_data="buy_gems_10"), types.InlineKeyboardButton("💎 Купить 50 гемов (50 ⭐)", callback_data="buy_gems_50"), types.InlineKeyboardButton("💎 Купить 100 гемов (100 ⭐)", callback_data="buy_gems_100"))
    text = (f"💎 **Гемы**\nУ тебя: {gems} 💎\n\n🔗 **Твоя реф. ссылка (5 💎 за друга):**\n`{ref_link}`\n\nВыполняй задания и покупай гемы за звезды!")
    bot.send_message(uid, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_subscription(call):
    uid = call.from_user.id
    profile = get_profile(uid)
    if profile[7] == 1: return bot.answer_callback_query(call.id, "Ты уже получил награду за подписку!", show_alert=True)
    if check_sub(uid):
        add_gems(uid, 10); set_subscribed(uid)
        bot.answer_callback_query(call.id, "✅ Спасибо за подписку! +10 гемов.", show_alert=True)
        bot.edit_message_text("✅ Ты получил 10 гемов за подписку!", call.message.chat.id, call.message.message_id)
    else: bot.answer_callback_query(call.id, "❌ Ты не подписан на канал!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_gems_"))
def buy_gems(call):
    amount = int(call.data.split("_")[2]); price = amount
    bot.send_invoice(chat_id=call.message.chat.id, title=f"{amount} гемов", description=f"Покупка {amount} гемов", invoice_payload=f"gems_{amount}", provider_token="", currency="XTR", prices=[types.LabeledPrice(label=f"{amount} гемов", amount=price)])

@bot.message_handler(func=lambda message: message.text == "💖 Донат / Любовь")
def donate_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💖 Влюбленный (50 💎)", callback_data="buy_love_1_gems"), types.InlineKeyboardButton("💍 Вторые половинки (150 💎)", callback_data="buy_love_2_gems"), types.InlineKeyboardButton("👑 Романтик (500 💎)", callback_data="buy_love_3_gems"), types.InlineKeyboardButton("💳 Купить за Звезды", callback_data="donate_stars"))
    bot.send_message(message.chat.id, "💖 **Прокачай свою любовь!**\n\nПокупай статусы за гемы или напрямую за звезды.", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_love_") or call.data == "donate_stars")
def process_donate(call):
    if call.data == "donate_stars":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("💖 Влюбленный (50 ⭐)", callback_data="buy_love_stars_1"), types.InlineKeyboardButton("💍 Вторые половинки (150 ⭐)", callback_data="buy_love_stars_2"), types.InlineKeyboardButton("👑 Романтик (500 ⭐)", callback_data="buy_love_stars_3"))
        return bot.edit_message_text("Выбери статус за звезды:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    if "gems" in call.data:
        level = int(call.data.split("_")[2]); prices = {1: 50, 2: 150, 3: 500}
        uid = call.from_user.id; profile = get_profile(uid); gems = profile[5] if profile else 0
        if gems < prices[level]: return bot.answer_callback_query(call.id, "❌ Недостаточно гемов!", show_alert=True)
        remove_gems(uid, prices[level]); set_love_status(uid, level)
        bot.edit_message_text(f"✅ Статус куплен за гемы!", call.message.chat.id, call.message.message_id)
        if level == 2:
            bot.send_message(uid, "💍 Теперь напиши **ID** человека, с которым хочешь создать пару:"); bot.register_next_step_handler_by_chat_id(uid, set_couple)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_love_stars_"))
def process_donate_stars(call):
    level = int(call.data.split("_")[3]); prices = {1: 50, 2: 150, 3: 500}; names = {1: "💖 Влюбленный", 2: "💍 Вторые половинки", 3: "👑 Романтик"}
    bot.send_invoice(chat_id=call.message.chat.id, title=f"Статус {names[level]}", description=f"Покупка статуса {names[level]}", invoice_payload=f"donate_love_{level}", provider_token="", currency="XTR", prices=[types.LabeledPrice(label=f"Статус {names[level]}", amount=prices[level])])

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query): bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    payload = message.successful_payment.invoice_payload; uid = message.from_user.id
    if payload.startswith("gems_"):
        amount = int(payload.split("_")[1]); add_gems(uid, amount); bot.send_message(uid, f"✅ Ты купил {amount} гемов!")
    elif payload.startswith("donate_love_"):
        level = int(payload.split("_")[2]); set_love_status(uid, level)
        if level == 2:
            bot.send_message(uid, "💍 Теперь напиши **ID** человека, с которым хочешь создать пару:"); bot.register_next_step_handler_by_chat_id(uid, set_couple)
        else: bot.send_message(uid, f"🎉 Статус активирован!")

def set_couple(message):
    uid = message.from_user.id; partner_input = message.text.strip().replace("@", "")
    try:
        if partner_input.isdigit(): partner_id = int(partner_input); set_partner(uid, partner_id); bot.send_message(uid, "💍 Вы теперь официально пара!")
        else: bot.send_message(uid, "❌ Пожалуйста, отправь ID цифрами.")
    except: bot.send_message(uid, "❌ Ошибка.")

@bot.message_handler(func=lambda message: message.text == "💌 Валентинки")
def valentine_menu(message):
    uid = message.from_user.id; profile = get_profile(uid)
    if not profile or profile[3] == 0: return bot.send_message(uid, "❌ Эта функция доступна только тем, кто купил любой любовный статус в донате!")
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💌 Создать Валентинку (5 💎)", callback_data="create_valentine"), types.InlineKeyboardButton("⭐ Купить Валентинку (5 ⭐)", callback_data="buy_valentine_star"))
    bot.send_message(uid, "💌 **Валентинки**\nТы можешь создать анонимную открытку за 5 гемов или 5 звезд.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["create_valentine", "buy_valentine_star"])
def ask_valentine_text(call):
    uid = call.from_user.id
    if call.data == "create_valentine":
        profile = get_profile(uid)
        if profile[5] < 5: return bot.answer_callback_query(call.id, "❌ Нужно 5 гемов!", show_alert=True)
        remove_gems(uid, 5); bot.edit_message_text("Напиши текст для валентинки:", call.message.chat.id, call.message.message_id)
        msg = bot.send_message(call.message.chat.id, "Жду текст..."); bot.register_next_step_handler(msg, ask_valentine_target)
    else:
        bot.send_invoice(chat_id=call.message.chat.id, title="Анонимная валентинка", description="Покупка валентинки", invoice_payload="valentine_star", provider_token="", currency="XTR", prices=[types.LabeledPrice(label="Валентинка", amount=5)])

@bot.callback_query_handler(func=lambda call: call.data == "ask_valentine_target_after_pay")
def ask_valentine_text_after_pay(call):
    bot.edit_message_text("Напиши текст для валентинки:", call.message.chat.id, call.message.message_id)
    msg = bot.send_message(call.message.chat.id, "Жду текст..."); bot.register_next_step_handler(msg, ask_valentine_target)

def ask_valentine_target(message):
    uid = message.from_user.id; text = message.text
    msg = bot.send_message(uid, "Кому отправить? Напиши ID получателя (цифры):"); bot.register_next_step_handler(msg, send_valentine, text)

def send_valentine(message, text):
    uid = message.from_user.id
    try:
        target_id = int(message.text.strip()); bot.send_message(target_id, f"💌 **Анонимная Валентинка!**\n\n{text}\n\n(Отправитель скрыт)"); bot.send_message(uid, "✅ Валентинка отправлена!")
    except: bot.send_message(uid, "❌ Ошибка. Убедись, что ID правильный.")

BLOCKED_WORDS = ["порно", "секс", "дроч", "закладк", "наркот", "мефедрон", "соль", "спайс", "героин", "кокаин", "минет", "интим", "18+"]

@bot.message_handler(content_types=['text', 'photo', 'video', 'sticker', 'voice', 'video_note', 'document'])
def relay_message(message):
    uid = message.from_user.id
    if message.text in ["🔍 Искать собеседника", "🛑 Стоп / Сменить", "⚠️ Пожаловаться", "👤 Моя анкета", "/start", "💎 Гемы / Магазин", "💖 Донат / Любовь", "💌 Валентинки"]: return
    if message.text and message.text.startswith("/"): return
    if is_banned(uid): return
    status = get_partner_chat(uid)
    if status and status[1] == 'chatting' and status[0]:
        partner_id = status[0]; profile = get_profile(uid)
        name = profile[0] if profile else "Неизвестный"; love = profile[3] if profile else 0
        if love == 1: name_text = f"💖 {name}"
        elif love == 2: name_text = f"💍 {name}"
        elif love == 3: name_text = f"👑 {name}"
        else: name_text = name
        if message.text:
            msg_lower = message.text.lower()
            if any(word in msg_lower for word in BLOCKED_WORDS):
                save_message(uid, partner_id, message.text); send_auto_report(uid, partner_id, message.text); set_status(uid, 'idle'); set_status(partner_id, 'idle'); bot.send_message(uid, "⛔ Твое сообщение нарушает правила.")
                try: bot.send_message(partner_id, "❌ Собеседник нарушил правила.", reply_markup=main_menu())
                except: pass
                return
            save_message(uid, partner_id, f"{name_text}: {message.text}")
        else: save_message(uid, partner_id, f"[МЕДИА] от {name_text}")
        try: 
            bot.copy_message(partner_id, message.chat.id, message.message_id)
            if message.text: bot.send_message(partner_id, f"👤 {name_text}")
        except: bot.send_message(uid, "❌ Ошибка отправки."); set_status(uid, 'idle'); set_status(partner_id, 'idle')
    elif status and status[1] == 'searching': bot.send_message(uid, "⏳ Бот все еще ищет тебе собеседника.")
    else: bot.send_message(uid, "❌ Ты не в чате.", reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == "🔍 Искать собеседника")
def search_partner(message):
    uid = message.from_user.id
    if is_banned(uid): return
    status = get_partner_chat(uid)
    if status and status[1] == 'chatting': return bot.send_message(uid, "❌ Ты уже в чате!", reply_markup=in_chat_menu())
    partner_id = find_partner(uid)
    if partner_id:
        set_status(uid, 'chatting', partner_id); set_status(partner_id, 'chatting', uid); bot.send_message(uid, "✅ Собеседник найден!", reply_markup=in_chat_menu()); bot.send_message(partner_id, "✅ Собеседник найден!", reply_markup=in_chat_menu())
    else: add_to_queue(uid); set_status(uid, 'searching'); bot.send_message(uid, "⏳ Ищем...")

@bot.message_handler(func=lambda message: message.text == "🛑 Стоп / Сменить")
def stop_chat(message):
    uid = message.from_user.id; status = get_partner_chat(uid); remove_from_queue(uid)
    if status and status[1] == 'chatting' and status[0]:
        set_status(status[0], 'idle')
        try: bot.send_message(status[0], "❌ Собеседник вышел.", reply_markup=main_menu())
        except: pass
    set_status(uid, 'idle'); bot.send_message(uid, "Ты вышел из чата.", reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == "⚠️ Пожаловаться")
def complain_menu(message):
    uid = message.from_user.id; status = get_partner_chat(uid)
    if not status or status[1] != 'chatting': return bot.send_message(uid, "❌ Ты не в чате.")
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🔞 Интим", callback_data="rep_sex"), types.InlineKeyboardButton("📞 Личные данные", callback_data="rep_dox"), types.InlineKeyboardButton("🤬 Оскорбления", callback_data="rep_abuse"), types.InlineKeyboardButton("🚫 Отмена", callback_data="rep_cancel"))
    bot.send_message(uid, "Выбери причину жалобы:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("rep_"))
def process_report(call):
    if call.data == "rep_cancel": return bot.edit_message_text("Отмена.", call.message.chat.id, call.message.message_id)
    uid = call.from_user.id; status = get_partner_chat(uid)
    if not status or status[1] != 'chatting': return bot.edit_message_text("❌ Чат закрыт.", call.message.chat.id, call.message.message_id)
    partner_id = status[0]; history = get_chat_history(uid, partner_id); reasons = {"rep_sex": "🔞 Интим", "rep_dox": "📞 Личные данные", "rep_abuse": "🤬 Оскорбления"}; reason_text = reasons.get(call.data, "Другое")
    text = f"🚨 **ЖАЛОБА!**\n❗ {reason_text}\n\n👤 На кого: `{partner_id}`\n\n"
    for msg in history: text += f"[{'Нарушитель' if partner_id in msg[1] else 'Жалобщик'}]: {msg[1]}\n"
    markup = types.InlineKeyboardMarkup(row_width=2); markup.add(types.InlineKeyboardButton("🚫 Забанить", callback_data=f"ban_{partner_id}"), types.InlineKeyboardButton("✅ Игнор", callback_data="ignore_report"))
    bot.send_message(ADMIN_ID, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("ban_") or call.data == "ignore_report")
def admin_action(call):
    if call.from_user.id != ADMIN_ID: return
    if call.data.startswith("ban_"):
        uid = int(call.data.split("_")[1]); ban_user(uid); bot.edit_message_text(f"✅ {uid} забанен.", call.message.chat.id, call.message.message_id)
        status = get_partner_chat(uid)
        if status and status[1] == 'chatting' and status[0]:
            partner = status[0]; set_status(uid, 'idle'); set_status(partner, 'idle')
            try: bot.send_message(partner, "❌ Собеседник забанен.", reply_markup=main_menu())
            except: pass
    else: bot.edit_message_text("✅ Игнор.", call.message.chat.id, call.message.message_id)

if __name__ == "__main__":
    print("Бот готов.")
    while True:
        try: bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e: time.sleep(5)
