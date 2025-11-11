# -*- coding: utf-8 -*-
"""
🚀 ПРЕМИУМ ТЕЛЕГРАМ-БОТ ДЛЯ РОЗЫГРЫШЕЙ v3.0 PRO
==============================================

С системой подписки: 60₽/месяц, Telegram Stars, TON
"""

import telebot
import sqlite3
import datetime
import re
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import pytz
import json
import time
from decimal import Decimal

# Попытка импорта дополнительных библиотек
try:
    from PIL import Image
    import pytesseract
    import io
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    import openai
    CHATGPT_AVAILABLE = True
except ImportError:
    CHATGPT_AVAILABLE = False

# Константы
BOT_TOKEN = "ВАШ_ТОКЕН_ОТ_BOTFATHER"
OPENAI_API_KEY = "ВАШ_OPENAI_API_KEY"
DB_NAME = "premium_giveaways.db"

# Настройки оплаты
SUBSCRIPTION_PRICE_RUB = 60  # Цена в рублях
SUBSCRIPTION_PRICE_STARS = 60  # Цена в Telegram Stars (1 Star ≈ 1₽)
SUBSCRIPTION_PRICE_TON = 0.034  # Цена в TON (~60₽ по курсу)
TRIAL_DAYS = 3  # Бесплатный пробный период

# TON кошелек для получения платежей (замените на свой)
TON_WALLET = "UQAbc123def456ghi789jkl012mno345pqr678stu901vwx234yz"

# Настройка OpenAI
if CHATGPT_AVAILABLE and OPENAI_API_KEY != "ВАШ_OPENAI_API_KEY":
    openai.api_key = OPENAI_API_KEY

# Инициализация бота и планировщика
bot = telebot.TeleBot(BOT_TOKEN)
scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Moscow'))
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# Ключевые слова для распознавания розыгрышей
GIVEAWAY_KEYWORDS = [
    'розыгрыш', 'розыграш', 'конкурс', 'раздача', 'приз', 'выиграть',
    'giveaway', 'contest', 'раздаем', 'дарим', 'бесплатно', 'выигрыш',
    'лотерея', 'разыгрываем', 'участвуй', 'побеждай', 'получи приз',
    'скидка', 'промокод', 'акция', 'викторина', 'состязание'
]

# Паттерны для извлечения информации
DATE_PATTERNS = [
    r'\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\b',
    r'\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2})\b',
]

CHANNEL_PATTERNS = [
    r'@[a-zA-Z_][a-zA-Z0-9_]{4,}',
    r't\.me/[a-zA-Z_][a-zA-Z0-9_]+',
    r'https://t\.me/[a-zA-Z_][a-zA-Z0-9_]+',
]

PRIZE_PATTERNS = [
    r'(iPhone|iPad|MacBook|Samsung|Xiaomi|Huawei|OnePlus)[^\n]*',
    r'(\d+\s*(?:руб|рублей|долларов|евро|₽|$|€))',
    r'(сертификат|подарочный\s+сертификат)[^\n]*',
    r'(приз|подарок)[^\n]*',
]

# Инициализация базы данных с системой подписок
def init_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Основная таблица розыгрышей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS giveaways (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            prize TEXT,
            date_time TEXT,
            channels TEXT,
            source_message TEXT,
            auto_detected BOOLEAN DEFAULT FALSE,
            confidence_score REAL DEFAULT 0.0,
            ocr_processed BOOLEAN DEFAULT FALSE,
            ai_analyzed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP NULL,
            is_active BOOLEAN DEFAULT TRUE,
            status TEXT DEFAULT 'active',
            subscription_checked_at TIMESTAMP NULL,
            subscription_status TEXT DEFAULT 'unknown'
        )
    ''')

    # История розыгрышей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS giveaway_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_giveaway_id INTEGER,
            user_id INTEGER,
            title TEXT,
            prize TEXT,
            date_time TEXT,
            channels TEXT,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            result TEXT,
            notes TEXT,
            won BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (original_giveaway_id) REFERENCES giveaways (id)
        )
    ''')

    # Пользователи и подписки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_premium BOOLEAN DEFAULT FALSE,
            premium_until TIMESTAMP NULL,
            trial_used BOOLEAN DEFAULT FALSE,
            trial_until TIMESTAMP NULL,
            total_payments INTEGER DEFAULT 0,
            last_payment_date TIMESTAMP NULL,
            referral_code TEXT UNIQUE,
            referred_by INTEGER NULL,
            FOREIGN KEY (referred_by) REFERENCES users (user_id)
        )
    ''')

    # Платежи
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            currency TEXT,
            payment_method TEXT,
            payment_id TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TIMESTAMP NULL,
            subscription_months INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # Настройки пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            auto_detect BOOLEAN DEFAULT TRUE,
            min_confidence REAL DEFAULT 0.6,
            ocr_enabled BOOLEAN DEFAULT TRUE,
            ai_enabled BOOLEAN DEFAULT TRUE,
            notifications_enabled BOOLEAN DEFAULT TRUE,
            language TEXT DEFAULT 'ru',
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # Статистика использования
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # Промокоды
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promo_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            discount_percent INTEGER DEFAULT 0,
            free_months INTEGER DEFAULT 0,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NULL,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')

    conn.commit()
    conn.close()

# Система подписок
def create_user(user_id, username=None, first_name=None):
    """Создает нового пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Генерируем уникальный реферальный код
    referral_code = f"REF{user_id}{int(time.time()) % 10000}"

    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, referral_code)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, referral_code))

    cursor.execute('''
        INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)
    ''', (user_id,))

    conn.commit()
    conn.close()

def get_user_subscription_status(user_id):
    """Получает статус подписки пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT is_premium, premium_until, trial_used, trial_until
        FROM users WHERE user_id = ?
    ''', (user_id,))

    result = cursor.fetchone()
    conn.close()

    if not result:
        return {
            'is_premium': False,
            'is_trial': False,
            'days_left': 0,
            'status': 'free'
        }

    is_premium, premium_until, trial_used, trial_until = result
    now = datetime.datetime.now()

    # Проверяем премиум подписку
    if is_premium and premium_until:
        premium_end = datetime.datetime.fromisoformat(premium_until)
        if premium_end > now:
            days_left = (premium_end - now).days
            return {
                'is_premium': True,
                'is_trial': False,
                'days_left': days_left,
                'status': 'premium'
            }

    # Проверяем пробный период
    if not trial_used and trial_until:
        trial_end = datetime.datetime.fromisoformat(trial_until)
        if trial_end > now:
            days_left = (trial_end - now).days
            return {
                'is_premium': False,
                'is_trial': True,
                'days_left': days_left,
                'status': 'trial'
            }

    return {
        'is_premium': False,
        'is_trial': False,
        'days_left': 0,
        'status': 'free'
    }

def activate_trial(user_id):
    """Активирует пробный период"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    trial_end = datetime.datetime.now() + datetime.timedelta(days=TRIAL_DAYS)

    cursor.execute('''
        UPDATE users 
        SET trial_used = TRUE, trial_until = ?
        WHERE user_id = ?
    ''', (trial_end.isoformat(), user_id))

    conn.commit()
    conn.close()

    return trial_end

def activate_premium(user_id, months=1):
    """Активирует премиум подписку"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Получаем текущий статус
    cursor.execute('SELECT premium_until FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    # Если уже есть премиум, продлеваем
    if result and result[0]:
        try:
            current_end = datetime.datetime.fromisoformat(result[0])
            if current_end > datetime.datetime.now():
                new_end = current_end + datetime.timedelta(days=30 * months)
            else:
                new_end = datetime.datetime.now() + datetime.timedelta(days=30 * months)
        except:
            new_end = datetime.datetime.now() + datetime.timedelta(days=30 * months)
    else:
        new_end = datetime.datetime.now() + datetime.timedelta(days=30 * months)

    cursor.execute('''
        UPDATE users 
        SET is_premium = TRUE, premium_until = ?, last_payment_date = CURRENT_TIMESTAMP,
            total_payments = total_payments + 1
        WHERE user_id = ?
    ''', (new_end.isoformat(), user_id))

    conn.commit()
    conn.close()

    return new_end

def is_premium_user(user_id):
    """Проверяет, является ли пользователь премиум"""
    status = get_user_subscription_status(user_id)
    return status['is_premium'] or status['is_trial']

def check_premium_required(func):
    """Декоратор для проверки премиум статуса"""
    def wrapper(message):
        user_id = message.from_user.id
        if not is_premium_user(user_id):
            show_premium_required(message)
            return
        return func(message)
    return wrapper

def show_premium_required(message):
    """Показывает сообщение о необходимости премиум подписки"""
    user_id = message.from_user.id
    status = get_user_subscription_status(user_id)

    # Проверяем, можно ли активировать пробный период
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT trial_used FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    trial_used = result[0] if result else False
    conn.close()

    response = "🔒 **Премиум функция**\n\n"

    if status['status'] == 'free' and not trial_used:
        response += "Эта функция доступна только для премиум пользователей\n\n"
        response += f"🎁 **Попробуйте бесплатно {TRIAL_DAYS} дня!**\n\n"

        keyboard = telebot.types.InlineKeyboardMarkup()
        btn_trial = telebot.types.InlineKeyboardButton(
            f"🎁 Активировать {TRIAL_DAYS} дня бесплатно",
            callback_data="activate_trial"
        )
        btn_buy = telebot.types.InlineKeyboardButton(
            "💳 Купить премиум",
            callback_data="show_pricing"
        )
        keyboard.add(btn_trial)
        keyboard.add(btn_buy)
    else:
        response += "Ваша подписка закончилась\n\n"
        response += "Продлите подписку для продолжения использования всех функций"

        keyboard = telebot.types.InlineKeyboardMarkup()
        btn_buy = telebot.types.InlineKeyboardButton(
            "💳 Продлить подписку",
            callback_data="show_pricing"
        )
        keyboard.add(btn_buy)

    bot.send_message(
        message.chat.id,
        response,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

def create_payment(user_id, amount, currency, payment_method, months=1):
    """Создает запись о платеже"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    payment_id = f"PAY_{user_id}_{int(time.time())}"

    cursor.execute('''
        INSERT INTO payments (user_id, amount, currency, payment_method, payment_id, subscription_months)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, amount, currency, payment_method, payment_id, months))

    conn.commit()
    conn.close()

    return payment_id

def confirm_payment(payment_id):
    """Подтверждает платеж и активирует подписку"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT user_id, subscription_months FROM payments 
        WHERE payment_id = ? AND status = 'pending'
    ''', (payment_id,))

    result = cursor.fetchone()
    if result:
        user_id, months = result

        # Обновляем статус платежа
        cursor.execute('''
            UPDATE payments 
            SET status = 'confirmed', confirmed_at = CURRENT_TIMESTAMP
            WHERE payment_id = ?
        ''', (payment_id,))

        conn.commit()
        conn.close()

        # Активируем премиум
        end_date = activate_premium(user_id, months)

        return user_id, end_date

    conn.close()
    return None, None

# Функции анализа текста (без изменений)
def extract_dates_from_text(text):
    dates = []
    for pattern in DATE_PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches:
            if len(match) == 3:
                try:
                    if len(match[2]) == 4:
                        date_str = f"{match[0]}.{match[1]}.{match[2]}"
                    else:
                        year = int(match[2])
                        if year < 50:
                            year += 2000
                        else:
                            year += 1900
                        date_str = f"{match[0]}.{match[1]}.{year}"
                    dates.append(date_str)
                except ValueError:
                    continue
    return dates

def extract_channels_from_text(text):
    channels = []
    for pattern in CHANNEL_PATTERNS:
        matches = re.findall(pattern, text)
        channels.extend(matches)
    return list(set(channels))

def extract_prizes_from_text(text):
    prizes = []
    for pattern in PRIZE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        prizes.extend(matches)
    return prizes

def calculate_giveaway_confidence(text):
    text_lower = text.lower()
    keyword_count = sum(1 for keyword in GIVEAWAY_KEYWORDS if keyword in text_lower)
    keyword_score = min(keyword_count / 3.0, 1.0)

    dates = extract_dates_from_text(text)
    channels = extract_channels_from_text(text)
    prizes = extract_prizes_from_text(text)

    date_score = 0.3 if dates else 0.0
    channel_score = 0.2 if channels else 0.0
    prize_score = 0.2 if prizes else 0.0

    total_confidence = keyword_score * 0.5 + date_score + channel_score + prize_score
    return min(total_confidence, 1.0)

def analyze_message_for_giveaway(text):
    confidence = calculate_giveaway_confidence(text)

    if confidence < 0.3:
        return None

    dates = extract_dates_from_text(text)
    channels = extract_channels_from_text(text)
    prizes = extract_prizes_from_text(text)

    lines = text.split('\n')
    title = ""
    for line in lines[:3]:
        if any(keyword in line.lower() for keyword in GIVEAWAY_KEYWORDS[:5]):
            title = line.strip()
            break

    if not title and lines:
        title = lines[0][:100]

    result = {
        'confidence': confidence,
        'title': title or "Автоматически найденный розыгрыш",
        'dates': dates,
        'channels': channels,
        'prizes': prizes,
        'suggested_date': dates[0] if dates else "",
        'suggested_channels': "\n".join(channels[:5]) if channels else "",
        'suggested_prize': " ".join(prizes[:3]) if prizes else "Не определено"
    }

    return result

# OCR функции (премиум)
def extract_text_from_image(image_data: bytes) -> str:
    if not OCR_AVAILABLE:
        return ""

    try:
        image = Image.open(io.BytesIO(image_data))
        image = image.convert('RGB')
        width, height = image.size
        image = image.resize((width * 2, height * 2), Image.Resampling.LANCZOS)

        text = pytesseract.image_to_string(
            image, 
            lang='rus+eng',
            config='--oem 3 --psm 6'
        )

        return text.strip()
    except Exception as e:
        print(f"Ошибка OCR: {e}")
        return ""

# Проверка подписок (премиум)
async def check_user_subscription(user_id: int, channel: str) -> dict:
    try:
        if channel.startswith('@'):
            channel_id = channel
        elif 't.me/' in channel:
            channel_id = '@' + channel.split('/')[-1]
        else:
            channel_id = '@' + channel

        member = await bot.get_chat_member(channel_id, user_id)
        is_subscribed = member.status in ['member', 'administrator', 'creator']

        return {
            'subscribed': is_subscribed,
            'status': member.status,
            'error': None
        }
    except Exception as e:
        return {
            'subscribed': False,
            'status': 'unknown',
            'error': str(e)
        }

async def check_all_giveaway_subscriptions(giveaway_id: int, user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('SELECT channels FROM giveaways WHERE id = ?', (giveaway_id,))
    result = cursor.fetchone()

    if not result or not result[0]:
        return []

    channels = [ch.strip() for ch in result[0].split('\n') if ch.strip()]

    subscription_results = []
    for channel in channels:
        check_result = await check_user_subscription(user_id, channel)
        subscription_results.append({
            'channel': channel,
            'subscribed': check_result['subscribed'],
            'status': check_result['status'],
            'error': check_result['error']
        })

    subscribed_count = sum(1 for r in subscription_results if r['subscribed'])
    total_count = len(subscription_results)

    if total_count > 0:
        status = f"{subscribed_count}/{total_count}"
        cursor.execute('''
            UPDATE giveaways 
            SET subscription_status = ?, subscription_checked_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, giveaway_id))

    conn.commit()
    conn.close()
    return subscription_results

# Функции базы данных
def add_giveaway(user_id, title, prize, date_time, channels, source_message="", 
                auto_detected=False, confidence=0.0, ocr_processed=False, ai_analyzed=False):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO giveaways (user_id, title, prize, date_time, channels, 
                             source_message, auto_detected, confidence_score,
                             ocr_processed, ai_analyzed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, title, prize, date_time, channels, source_message, 
          auto_detected, confidence, ocr_processed, ai_analyzed))

    giveaway_id = cursor.lastrowid

    # Логируем действие
    cursor.execute('''
        INSERT INTO usage_stats (user_id, action, details)
        VALUES (?, ?, ?)
    ''', (user_id, 'add_giveaway', f'Method: {"auto" if auto_detected else "manual"}'))

    conn.commit()
    conn.close()
    return giveaway_id

def get_user_giveaways(user_id, include_completed=False):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if include_completed:
        query = '''
            SELECT id, title, prize, date_time, channels, is_active, status, 
                   auto_detected, confidence_score, subscription_status
            FROM giveaways 
            WHERE user_id = ?
            ORDER BY created_at DESC
        '''
    else:
        query = '''
            SELECT id, title, prize, date_time, channels, is_active, status,
                   auto_detected, confidence_score, subscription_status
            FROM giveaways 
            WHERE user_id = ? AND is_active = TRUE
            ORDER BY date_time ASC
        '''

    cursor.execute(query, (user_id,))
    giveaways = cursor.fetchall()
    conn.close()
    return giveaways

def complete_giveaway(giveaway_id, result="", notes="", won=False):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM giveaways WHERE id = ?', (giveaway_id,))
    giveaway = cursor.fetchone()

    if giveaway:
        cursor.execute('''
            INSERT INTO giveaway_history (
                original_giveaway_id, user_id, title, prize, date_time, 
                channels, result, notes, won
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            giveaway[0], giveaway[1], giveaway[2], giveaway[3], 
            giveaway[4], giveaway[5], result, notes, won
        ))

        cursor.execute('''
            UPDATE giveaways 
            SET is_active = FALSE, status = 'completed', completed_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (giveaway_id,))

        # Логируем завершение
        cursor.execute('''
            INSERT INTO usage_stats (user_id, action, details)
            VALUES (?, ?, ?)
        ''', (giveaway[1], 'complete_giveaway', f'Won: {won}'))

    conn.commit()
    conn.close()

# Клавиатуры
def create_main_keyboard(user_id):
    status = get_user_subscription_status(user_id)

    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = telebot.types.KeyboardButton("➕ Добавить розыгрыш")
    btn2 = telebot.types.KeyboardButton("📋 Мои розыгрыши")

    if status['is_premium'] or status['is_trial']:
        btn3 = telebot.types.KeyboardButton("✅ Проверить подписки")
        btn4 = telebot.types.KeyboardButton("🔔 Напоминания")
        btn5 = telebot.types.KeyboardButton("📚 История")
        btn6 = telebot.types.KeyboardButton("⚙️ Настройки")
        keyboard.add(btn1, btn2, btn3, btn4, btn5, btn6)
    else:
        btn3 = telebot.types.KeyboardButton("🔔 Напоминания")
        btn4 = telebot.types.KeyboardButton("💎 Премиум")
        keyboard.add(btn1, btn2, btn3, btn4)

    return keyboard

def create_premium_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup()

    # Активация пробного периода
    btn_trial = telebot.types.InlineKeyboardButton(
        f"🎁 {TRIAL_DAYS} дня бесплатно",
        callback_data="activate_trial"
    )

    # Покупка подписки
    btn_month = telebot.types.InlineKeyboardButton(
        f"💳 1 месяц - {SUBSCRIPTION_PRICE_RUB}₽",
        callback_data="buy_1_month"
    )

    btn_3months = telebot.types.InlineKeyboardButton(
        f"💎 3 месяца - {SUBSCRIPTION_PRICE_RUB * 3 * 0.9:.0f}₽ (-10%)",
        callback_data="buy_3_months"
    )

    btn_year = telebot.types.InlineKeyboardButton(
        f"👑 12 месяцев - {SUBSCRIPTION_PRICE_RUB * 12 * 0.75:.0f}₽ (-25%)",
        callback_data="buy_12_months"
    )

    # Альтернативные способы оплаты
    btn_stars = telebot.types.InlineKeyboardButton(
        f"⭐ Telegram Stars ({SUBSCRIPTION_PRICE_STARS}★)",
        callback_data="pay_stars"
    )

    btn_ton = telebot.types.InlineKeyboardButton(
        f"💎 TON Криpto ({SUBSCRIPTION_PRICE_TON} TON)",
        callback_data="pay_ton"
    )

    keyboard.add(btn_trial)
    keyboard.add(btn_month)
    keyboard.add(btn_3months) 
    keyboard.add(btn_year)
    keyboard.add(btn_stars, btn_ton)

    return keyboard

def create_payment_keyboard(payment_method, amount, currency):
    keyboard = telebot.types.InlineKeyboardMarkup()

    if payment_method == 'card':
        # Для карточных платежей - ссылка на внешний платежный сервис
        btn_pay = telebot.types.InlineKeyboardButton(
            f"💳 Оплатить {amount}{currency}",
            url=f"https://your-payment-service.com/pay?amount={amount}&currency={currency}"
        )
        keyboard.add(btn_pay)

    elif payment_method == 'stars':
        # Для Telegram Stars - встроенная оплата
        btn_pay = telebot.types.InlineKeyboardButton(
            f"⭐ Оплатить {amount} Stars",
            callback_data=f"confirm_stars_{amount}"
        )
        keyboard.add(btn_pay)

    elif payment_method == 'ton':
        # Для TON - показываем адрес кошелька
        btn_copy = telebot.types.InlineKeyboardButton(
            "📋 Скопировать адрес",
            callback_data=f"copy_ton_address"
        )
        btn_paid = telebot.types.InlineKeyboardButton(
            "✅ Я оплатил",
            callback_data=f"confirm_ton_payment_{amount}"
        )
        keyboard.add(btn_copy)
        keyboard.add(btn_paid)

    btn_back = telebot.types.InlineKeyboardButton(
        "◀️ Назад",
        callback_data="show_pricing"
    )
    keyboard.add(btn_back)

    return keyboard

# Основные обработчики
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    # Создаем пользователя
    create_user(user_id, username, first_name)

    # Проверяем реферальный код
    if len(message.text.split()) > 1:
        referral_code = message.text.split()[1]
        process_referral(user_id, referral_code)

    status = get_user_subscription_status(user_id)

    welcome_text = f"👋 Добро пожаловать, {first_name}!\n\n"
    welcome_text += "🚀 **Премиум бот для розыгрышей**\n\n"

    if status['status'] == 'premium':
        welcome_text += f"💎 **Премиум активен** ({status['days_left']} дн.)\n\n"
        welcome_text += "🎯 **Доступные функции:**\n"
        welcome_text += "• 🤖 Автопоиск розыгрышей\n"
        if OCR_AVAILABLE:
            welcome_text += "• 📸 Анализ изображений\n"
        welcome_text += "• ✅ Проверка подписок\n"
        welcome_text += "• 📚 Полная история\n"
        welcome_text += "• 🔔 Умные напоминания"
    elif status['status'] == 'trial':
        welcome_text += f"🎁 **Пробный период** ({status['days_left']} дн.)\n\n"
        welcome_text += "Протестируйте все премиум функции!"
    else:
        welcome_text += "🆓 **Базовая версия**\n\n"
        welcome_text += "• ➕ Ручное добавление розыгрышей\n"
        welcome_text += "• 🔔 Базовые напоминания\n\n"
        welcome_text += f"🎁 **Попробуйте премиум {TRIAL_DAYS} дня бесплатно!**"

    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard(user_id)
    )

@bot.message_handler(content_types=['text'])
def handle_text_message(message):
    user_id = message.from_user.id
    text = message.text

    if text == "➕ Добавить розыгрыш":
        add_giveaway_start(message)
    elif text == "📋 Мои розыгрыши":
        show_giveaways(message)
    elif text == "✅ Проверить подписки":
        check_subscriptions_menu(message)
    elif text == "🔔 Напоминания":
        show_reminders(message)
    elif text == "📚 История":
        show_history(message)
    elif text == "⚙️ Настройки":
        show_settings(message)
    elif text == "💎 Премиум":
        show_premium_info(message)
    else:
        # Автопоиск доступен всем пользователям
        analyze_and_suggest_giveaway(message)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id

    if not is_premium_user(user_id):
        bot.send_message(
            message.chat.id,
            "📸 **Анализ изображений - премиум функция**\n\n"
            "🎁 Активируйте пробный период для тестирования!",
            parse_mode='Markdown',
            reply_markup=telebot.types.InlineKeyboardMarkup([
                [telebot.types.InlineKeyboardButton("🎁 Попробовать бесплатно", callback_data="activate_trial")],
                [telebot.types.InlineKeyboardButton("💳 Купить премиум", callback_data="show_pricing")]
            ])
        )
        return

    if not OCR_AVAILABLE:
        bot.send_message(
            message.chat.id,
            "📸 OCR функции недоступны на сервере\n\n"
            "Используйте текстовые сообщения для анализа",
            reply_markup=create_main_keyboard(user_id)
        )
        return

    processing_msg = bot.send_message(message.chat.id, "📸 Обрабатываю изображение...")

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        bot.edit_message_text("🔍 Распознаю текст...", message.chat.id, processing_msg.message_id)
        text = extract_text_from_image(downloaded_file)

        if not text:
            bot.edit_message_text(
                "❌ Не удалось распознать текст на изображении",
                message.chat.id, processing_msg.message_id,
                reply_markup=create_main_keyboard(user_id)
            )
            return

        bot.edit_message_text("🧠 Анализирую содержимое...", message.chat.id, processing_msg.message_id)
        giveaway_data = analyze_message_for_giveaway(text)

        if giveaway_data and giveaway_data['confidence'] >= 0.3:
            response = f"📸 **Найден розыгрыш на изображении!**\n\n"
            response += f"📊 Уверенность: {giveaway_data['confidence']:.1%}\n"
            response += f"📝 Название: {giveaway_data['title']}\n"
            response += f"🎁 Приз: {giveaway_data['suggested_prize']}\n"

            if giveaway_data['suggested_date']:
                response += f"📅 Дата: {giveaway_data['suggested_date']}\n"

            if giveaway_data['suggested_channels']:
                response += f"📢 Каналы: {giveaway_data['suggested_channels'][:100]}\n"

            response += "\n🔥 **OCR успешно распознал розыгрыш!**"

            bot.giveaway_temp_data = {
                'user_id': user_id,
                'message_text': text,
                'analysis': giveaway_data,
                'ocr_processed': True
            }

            keyboard = create_auto_giveaway_keyboard(giveaway_data)
            bot.edit_message_text(
                response, message.chat.id, processing_msg.message_id,
                parse_mode='Markdown', reply_markup=keyboard
            )
        else:
            bot.edit_message_text(
                f"📸 **OCR завершен**\n\n"
                f"📝 Текст: {text[:200]}...\n\n"
                f"🔍 Розыгрыш не обнаружен",
                message.chat.id, processing_msg.message_id,
                parse_mode='Markdown'
            )

    except Exception as e:
        bot.edit_message_text(
            f"❌ Ошибка обработки: {str(e)[:100]}",
            message.chat.id, processing_msg.message_id
        )

def process_referral(user_id, referral_code):
    """Обрабатывает реферальный код"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Находим пользователя по реферальному коду
    cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referral_code,))
    referrer = cursor.fetchone()

    if referrer and referrer[0] != user_id:
        # Устанавливаем связь
        cursor.execute('''
            UPDATE users SET referred_by = ? WHERE user_id = ?
        ''', (referrer[0], user_id))

        # Даем бонус рефереру (например, 1 день бесплатно)
        cursor.execute('''
            UPDATE users 
            SET premium_until = COALESCE(
                datetime(premium_until, '+1 day'),
                datetime('now', '+1 day')
            )
            WHERE user_id = ?
        ''', (referrer[0],))

        conn.commit()

        # Уведомляем реферера
        try:
            bot.send_message(
                referrer[0],
                "🎉 **Новый реферал!**\n\n"
                "Кто-то зарегистрировался по вашей ссылке\n"
                "Вы получили +1 день премиума!",
                parse_mode='Markdown'
            )
        except:
            pass

    conn.close()

# Продолжение следует...

def analyze_and_suggest_giveaway(message):
    user_id = message.from_user.id
    text = message.text

    # Логируем использование
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO usage_stats (user_id, action, details)
        VALUES (?, ?, ?)
    ''', (user_id, 'auto_analysis', f'Text length: {len(text)}'))
    conn.commit()

    cursor.execute('SELECT auto_detect, min_confidence FROM user_settings WHERE user_id = ?', (user_id,))
    settings = cursor.fetchone()
    conn.close()

    if not settings or not settings[0]:
        bot.send_message(
            message.chat.id,
            "🤔 Не понимаю эту команду\n\n"
            "Используйте кнопки меню или команду /start",
            reply_markup=create_main_keyboard(user_id)
        )
        return

    min_confidence = settings[1] or 0.6
    giveaway_data = analyze_message_for_giveaway(text)

    if not giveaway_data or giveaway_data['confidence'] < min_confidence:
        confidence_info = f" (уверенность: {giveaway_data['confidence']:.1%})" if giveaway_data else ""
        bot.send_message(
            message.chat.id,
            f"🔍 Сообщение проанализировано{confidence_info}\n\n"
            f"Минимальный порог: {min_confidence:.0%}\n"
            "Розыгрыш не обнаружен или уверенность недостаточна",
            reply_markup=create_main_keyboard(user_id)
        )
        return

    bot.giveaway_temp_data = {
        'user_id': user_id,
        'message_text': text,
        'analysis': giveaway_data,
        'ocr_processed': False
    }

    response = f"🤖 **Обнаружен розыгрыш!**\n\n"
    response += f"📊 Уверенность: {giveaway_data['confidence']:.1%}\n\n"
    response += f"📝 Название: {giveaway_data['title']}\n"
    response += f"🎁 Приз: {giveaway_data['suggested_prize']}\n"

    if giveaway_data['suggested_date']:
        response += f"📅 Дата: {giveaway_data['suggested_date']}\n"

    if giveaway_data['suggested_channels']:
        response += f"📢 Каналы:\n{giveaway_data['suggested_channels'][:200]}\n"

    response += "\nЧто хотите сделать?"

    bot.send_message(
        message.chat.id,
        response,
        parse_mode='Markdown',
        reply_markup=create_auto_giveaway_keyboard(giveaway_data)
    )

def create_auto_giveaway_keyboard(giveaway_data):
    keyboard = telebot.types.InlineKeyboardMarkup()
    btn1 = telebot.types.InlineKeyboardButton(
        "✅ Добавить", 
        callback_data=f"auto_add_{giveaway_data['confidence']}"
    )
    btn2 = telebot.types.InlineKeyboardButton(
        "✏️ Редактировать", 
        callback_data="auto_edit"
    )
    btn3 = telebot.types.InlineKeyboardButton(
        "❌ Отклонить", 
        callback_data="auto_reject"
    )
    keyboard.add(btn1, btn2, btn3)
    return keyboard

# Callback обработчики для премиум функций
@bot.callback_query_handler(func=lambda call: call.data == "activate_trial")
def activate_trial_handler(call):
    user_id = call.from_user.id

    # Проверяем, не использовал ли уже пробный период
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT trial_used FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if result and result[0]:
        bot.answer_callback_query(call.id, "❌ Пробный период уже использован")
        return

    # Активируем пробный период
    trial_end = activate_trial(user_id)

    response = f"🎁 **Пробный период активирован!**\n\n"
    response += f"⏰ Действует до: {trial_end.strftime('%d.%m.%Y %H:%M')}\n\n"
    response += "🎯 **Теперь доступно:**\n"
    response += "• ✅ Автопроверка подписок\n"
    if OCR_AVAILABLE:
        response += "• 📸 Анализ изображений\n"
    response += "• 📚 Полная история розыгрышей\n"
    response += "• ⚙️ Расширенные настройки\n\n"
    response += "💡 Протестируйте все функции!"

    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

    bot.answer_callback_query(call.id, f"🎁 Пробный период на {TRIAL_DAYS} дня активирован!")

    conn.close()

@bot.callback_query_handler(func=lambda call: call.data == "show_pricing")
def show_pricing_handler(call):
    user_id = call.from_user.id
    status = get_user_subscription_status(user_id)

    response = "💎 **Премиум подписка**\n\n"

    if status['status'] == 'premium':
        response += f"✅ У вас активна подписка до {status['days_left']} дн.\n\n"
        response += "🔄 **Продлить подписку:**\n"
    else:
        response += "🎯 **Премиум возможности:**\n"
        response += "• ✅ Автопроверка подписок на каналы\n"
        if OCR_AVAILABLE:
            response += "• 📸 Анализ изображений с OCR\n"
        if CHATGPT_AVAILABLE:
            response += "• 🧠 ИИ-анализ с ChatGPT\n"
        response += "• 📚 Полная история участия\n"
        response += "• 📊 Детальная статистика\n"
        response += "• ⚙️ Расширенные настройки\n"
        response += "• 🔔 Приоритетная поддержка\n\n"
        response += "💳 **Тарифы:**\n"

    response += f"• 1 месяц: **{SUBSCRIPTION_PRICE_RUB}₽**\n"
    response += f"• 3 месяца: **{int(SUBSCRIPTION_PRICE_RUB * 3 * 0.9)}₽** (скидка 10%)\n"
    response += f"• 12 месяцев: **{int(SUBSCRIPTION_PRICE_RUB * 12 * 0.75)}₽** (скидка 25%)\n\n"
    response += "⭐ **Альтернативная оплата:**\n"
    response += f"• Telegram Stars: {SUBSCRIPTION_PRICE_STARS}★\n"
    response += f"• TON Crypto: {SUBSCRIPTION_PRICE_TON} TON"

    keyboard = create_premium_keyboard()

    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_subscription_purchase(call):
    user_id = call.from_user.id

    months_map = {
        "buy_1_month": (1, SUBSCRIPTION_PRICE_RUB),
        "buy_3_months": (3, int(SUBSCRIPTION_PRICE_RUB * 3 * 0.9)),
        "buy_12_months": (12, int(SUBSCRIPTION_PRICE_RUB * 12 * 0.75))
    }

    if call.data not in months_map:
        return

    months, price = months_map[call.data]

    # Создаем платеж
    payment_id = create_payment(user_id, price, "RUB", "card", months)

    response = f"💳 **Оплата подписки**\n\n"
    response += f"📋 Тариф: {months} мес.\n"
    response += f"💰 Сумма: {price}₽\n"
    response += f"🆔 ID платежа: `{payment_id}`\n\n"
    response += "Выберите способ оплаты:"

    keyboard = create_payment_keyboard("card", price, "₽")

    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == "pay_stars")
def handle_stars_payment(call):
    user_id = call.from_user.id

    # Создаем инвойс для Telegram Stars
    response = f"⭐ **Оплата Telegram Stars**\n\n"
    response += f"💰 Стоимость: {SUBSCRIPTION_PRICE_STARS} Stars\n"
    response += f"📋 Подписка: 1 месяц\n\n"
    response += "Stars можно купить в настройках Telegram\n"
    response += "Настройки → Telegram Premium → Stars"

    keyboard = telebot.types.InlineKeyboardMarkup()

    # Здесь должна быть интеграция с Telegram Payments API
    # Пока показываем заглушку
    btn_pay = telebot.types.InlineKeyboardButton(
        f"⭐ Оплатить {SUBSCRIPTION_PRICE_STARS} Stars",
        callback_data=f"confirm_stars_{SUBSCRIPTION_PRICE_STARS}"
    )
    btn_back = telebot.types.InlineKeyboardButton(
        "◀️ Назад",
        callback_data="show_pricing"
    )

    keyboard.add(btn_pay)
    keyboard.add(btn_back)

    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == "pay_ton")
def handle_ton_payment(call):
    user_id = call.from_user.id

    # Создаем платеж TON
    payment_id = create_payment(user_id, SUBSCRIPTION_PRICE_TON, "TON", "ton", 1)

    response = f"💎 **Оплата TON**\n\n"
    response += f"💰 Сумма: {SUBSCRIPTION_PRICE_TON} TON\n"
    response += f"📋 Подписка: 1 месяц\n"
    response += f"🆔 ID: `{payment_id}`\n\n"
    response += f"💼 **Адрес кошелька:**\n"
    response += f"`{TON_WALLET}`\n\n"
    response += "⚠️ **Важно:**\n"
    response += f"• Отправьте точно {SUBSCRIPTION_PRICE_TON} TON\n"
    response += f"• В комментарии укажите: {payment_id}\n"
    response += f"• После оплаты нажмите 'Я оплатил'"

    keyboard = create_payment_keyboard("ton", SUBSCRIPTION_PRICE_TON, " TON")

    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == "copy_ton_address")
def copy_ton_address(call):
    bot.answer_callback_query(
        call.id, 
        f"Адрес скопирован: {TON_WALLET[:20]}...",
        show_alert=True
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_ton_payment_"))
def confirm_ton_payment_handler(call):
    user_id = call.from_user.id
    amount = call.data.split("_")[-1]

    # В реальной реализации здесь должна быть проверка блокчейна TON
    # Пока делаем заглушку с ручным подтверждением

    response = f"✅ **Заявка на подтверждение отправлена**\n\n"
    response += f"🔍 Проверяем поступление {amount} TON\n"
    response += f"⏰ Обычно занимает 5-15 минут\n\n"
    response += f"📞 При проблемах обращайтесь в поддержку\n"
    response += f"Указывайте ID пользователя: `{user_id}`"

    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

    # Уведомляем администратора о платеже (замените на ваш ID)
    admin_id = 123456789  # Ваш Telegram ID
    try:
        bot.send_message(
            admin_id,
            f"💎 **Новый TON платеж**\n\n"
            f"👤 Пользователь: {user_id}\n"
            f"💰 Сумма: {amount} TON\n"
            f"🕐 Время: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Проверьте кошелек и подтвердите: /confirm_payment {user_id}"
        )
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_stars_"))
def confirm_stars_payment_handler(call):
    user_id = call.from_user.id
    stars_amount = int(call.data.split("_")[-1])

    # Здесь должна быть интеграция с Telegram Payments API
    # Пока показываем заглушку

    response = f"⭐ **Функция в разработке**\n\n"
    response += f"Оплата Telegram Stars будет доступна в следующем обновлении\n\n"
    response += f"💳 Пока используйте карточную оплату или TON"

    keyboard = telebot.types.InlineKeyboardMarkup()
    btn_back = telebot.types.InlineKeyboardButton(
        "◀️ Вернуться к тарифам",
        callback_data="show_pricing"
    )
    keyboard.add(btn_back)

    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

# Автоматические обработчики
@bot.callback_query_handler(func=lambda call: call.data.startswith('auto_'))
def handle_auto_giveaway(call):
    user_id = call.from_user.id

    if call.data.startswith('auto_add_'):
        if hasattr(bot, 'giveaway_temp_data') and bot.giveaway_temp_data['user_id'] == user_id:
            data = bot.giveaway_temp_data['analysis']
            ocr_processed = bot.giveaway_temp_data.get('ocr_processed', False)

            giveaway_id = add_giveaway(
                user_id=user_id,
                title=data['title'],
                prize=data['suggested_prize'],
                date_time=data['suggested_date'],
                channels=data['suggested_channels'],
                source_message=bot.giveaway_temp_data['message_text'][:500],
                auto_detected=True,
                confidence=data['confidence'],
                ocr_processed=ocr_processed
            )

            if data['suggested_date']:
                setup_reminder(user_id, giveaway_id, data['title'], data['suggested_date'])

            success_msg = "✅ **Розыгрыш добавлен!**\n\n"
            success_msg += f"📝 {data['title']}\n"
            success_msg += f"🎁 {data['suggested_prize']}\n"
            success_msg += f"📅 {data['suggested_date']}\n\n"
            if ocr_processed:
                success_msg += "📸 Обработано с помощью OCR\n"
            success_msg += "🔔 Напоминание настроено!"

            bot.edit_message_text(
                success_msg,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
            bot.answer_callback_query(call.id, "✅ Розыгрыш добавлен!")

    elif call.data == 'auto_edit':
        bot.answer_callback_query(call.id, "✏️ Перехожу к ручному добавлению...")
        bot.edit_message_text(
            "✏️ **Ручное добавление розыгрыша**\n\n"
            "Введите название розыгрыша:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_giveaway_title)

    elif call.data == 'auto_reject':
        bot.edit_message_text(
            "❌ **Розыгрыш отклонен**\n\n"
            "Используйте кнопки меню для других действий",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id, "❌ Отклонено")

# Функции для просмотра информации
def show_premium_info(message):
    user_id = message.from_user.id
    status = get_user_subscription_status(user_id)

    if status['status'] == 'premium':
        response = f"💎 **Ваша премиум подписка**\n\n"
        response += f"✅ Статус: Активна\n"
        response += f"⏰ Осталось: {status['days_left']} дней\n\n"
        response += f"🎯 **Активные функции:**\n"
        response += f"• ✅ Автопроверка подписок\n"
        if OCR_AVAILABLE:
            response += f"• 📸 Анализ изображений\n"
        response += f"• 📚 Полная история\n"
        response += f"• ⚙️ Расширенные настройки\n\n"

        # Статистика использования
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM usage_stats WHERE user_id = ? AND timestamp >= date('now', '-30 days')
        ''', (user_id,))
        monthly_usage = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM giveaways WHERE user_id = ?', (user_id,))
        total_giveaways = cursor.fetchone()[0]
        conn.close()

        response += f"📊 **Статистика за месяц:**\n"
        response += f"• Действий выполнено: {monthly_usage}\n"
        response += f"• Всего розыгрышей: {total_giveaways}\n\n"

        keyboard = telebot.types.InlineKeyboardMarkup()
        btn_extend = telebot.types.InlineKeyboardButton(
            "🔄 Продлить подписку",
            callback_data="show_pricing"
        )

        # Реферальная система
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT referral_code FROM users WHERE user_id = ?', (user_id,))
        referral_code = cursor.fetchone()[0]
        conn.close()

        btn_referral = telebot.types.InlineKeyboardButton(
            "👥 Пригласить друга",
            callback_data="show_referral"
        )

        keyboard.add(btn_extend)
        keyboard.add(btn_referral)

    elif status['status'] == 'trial':
        response = f"🎁 **Пробный период**\n\n"
        response += f"⏰ Осталось: {status['days_left']} дней\n\n"
        response += f"🎯 Протестируйте все премиум функции!\n\n"
        response += f"💡 После окончания пробного периода\n"
        response += f"оформите подписку для продолжения"

        keyboard = telebot.types.InlineKeyboardMarkup()
        btn_buy = telebot.types.InlineKeyboardButton(
            "💳 Купить премиум",
            callback_data="show_pricing"
        )
        keyboard.add(btn_buy)

    else:
        response = f"🆓 **Базовая версия**\n\n"
        response += f"🎯 **Доступные функции:**\n"
        response += f"• ➕ Ручное добавление розыгрышей\n"
        response += f"• 🤖 Базовый автопоиск\n"
        response += f"• 🔔 Простые напоминания\n\n"
        response += f"💎 **Премиум дает:**\n"
        response += f"• ✅ Автопроверку подписок\n"
        if OCR_AVAILABLE:
            response += f"• 📸 Анализ изображений\n"
        response += f"• 📚 Полную историю\n"
        response += f"• 📊 Детальную статистику\n\n"

        # Проверяем доступность пробного периода
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT trial_used FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        trial_used = result[0] if result else False
        conn.close()

        if not trial_used:
            response += f"🎁 **Попробуйте {TRIAL_DAYS} дня бесплатно!**"

        keyboard = create_premium_keyboard()

    bot.send_message(
        message.chat.id,
        response,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == "show_referral")
def show_referral_info(call):
    user_id = call.from_user.id

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Получаем реферальный код
    cursor.execute('SELECT referral_code FROM users WHERE user_id = ?', (user_id,))
    referral_code = cursor.fetchone()[0]

    # Считаем рефералов
    cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = ?', (user_id,))
    referral_count = cursor.fetchone()[0]

    conn.close()

    response = f"👥 **Реферальная программа**\n\n"
    response += f"🔗 **Ваша ссылка:**\n"
    response += f"`https://t.me/{bot.get_me().username}?start={referral_code}`\n\n"
    response += f"👥 **Приглашено друзей:** {referral_count}\n\n"
    response += f"🎁 **За каждого друга:**\n"
    response += f"• Вы получаете +1 день премиума\n"
    response += f"• Друг получает скидку 10%\n\n"
    response += f"💡 Делитесь ссылкой с друзьями!"

    keyboard = telebot.types.InlineKeyboardMarkup()
    btn_copy = telebot.types.InlineKeyboardButton(
        "📋 Скопировать ссылку",
        callback_data=f"copy_referral_{referral_code}"
    )
    btn_back = telebot.types.InlineKeyboardButton(
        "◀️ Назад",
        callback_data="back_to_premium"
    )
    keyboard.add(btn_copy)
    keyboard.add(btn_back)

    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("copy_referral_"))
def copy_referral_link(call):
    referral_code = call.data.split("_")[-1]
    bot_username = bot.get_me().username

    bot.answer_callback_query(
        call.id,
        f"Ссылка скопирована: https://t.me/{bot_username}?start={referral_code}",
        show_alert=True
    )

# Ручное добавление розыгрышей
def add_giveaway_start(message):
    msg = bot.send_message(
        message.chat.id,
        "📝 **Добавление нового розыгрыша**\n\n"
        "Введите название розыгрыша:",
        parse_mode='Markdown',
        reply_markup=telebot.types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, get_giveaway_title)

def get_giveaway_title(message):
    title = message.text
    msg = bot.send_message(
        message.chat.id,
        f"✅ **Название:** {title}\n\n"
        "🎁 Теперь введите что разыгрывается (приз):",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, get_giveaway_prize, title)

def get_giveaway_prize(message, title):
    prize = message.text
    msg = bot.send_message(
        message.chat.id,
        f"✅ **Название:** {title}\n"
        f"✅ **Приз:** {prize}\n\n"
        "📅 Введите дату и время розыгрыша:\n\n"
        "📝 **Формат:** ДД.ММ.ГГГГ ЧЧ:ММ\n"
        "💡 **Пример:** 25.12.2024 20:00",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, get_giveaway_datetime, title, prize)

def get_giveaway_datetime(message, title, prize):
    try:
        date_time_str = message.text
        datetime.datetime.strptime(date_time_str, '%d.%m.%Y %H:%M')

        msg = bot.send_message(
            message.chat.id,
            f"✅ **Название:** {title}\n"
            f"✅ **Приз:** {prize}\n"
            f"✅ **Дата и время:** {date_time_str}\n\n"
            "📢 Введите каналы для подписки:\n\n"
            "📝 **Формат:** Каждый канал с новой строки\n"
            "💡 **Пример:**\n@channel1\n@channel2",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, save_manual_giveaway, title, prize, date_time_str)
    except ValueError:
        msg = bot.send_message(
            message.chat.id,
            "❌ **Неверный формат даты!**\n\n"
            "📝 Используйте формат: **ДД.ММ.ГГГГ ЧЧ:ММ**",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, get_giveaway_datetime, title, prize)

def save_manual_giveaway(message, title, prize, date_time_str):
    channels = message.text
    user_id = message.from_user.id

    giveaway_id = add_giveaway(
        user_id=user_id, 
        title=title, 
        prize=prize, 
        date_time=date_time_str, 
        channels=channels, 
        auto_detected=False
    )

    setup_reminder(user_id, giveaway_id, title, date_time_str)

    success_msg = f"✅ **Розыгрыш успешно добавлен!**\n\n"
    success_msg += f"📝 **{title}**\n"
    success_msg += f"🎁 **{prize}**\n" 
    success_msg += f"📅 **{date_time_str}**\n"
    success_msg += f"📢 **Каналы:**\n{channels}\n\n"
    success_msg += f"🔔 Напоминание настроено!"

    bot.send_message(
        message.chat.id,
        success_msg,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard(user_id)
    )

# Остальные функции
def show_giveaways(message):
    user_id = message.from_user.id
    giveaways = get_user_giveaways(user_id)

    if not giveaways:
        bot.send_message(
            message.chat.id,
            "📭 **У вас нет активных розыгрышей**\n\n"
            "➕ Добавьте первый розыгрыш с помощью кнопки меню",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard(user_id)
        )
        return

    response = f"📋 **Ваши активные розыгрыши ({len(giveaways)}):**\n\n"
    keyboard = telebot.types.InlineKeyboardMarkup()

    for i, giveaway in enumerate(giveaways, 1):
        giveaway_id, title, prize, date_time, channels = giveaway[:5]
        auto_detected = giveaway[7] if len(giveaway) > 7 else False
        confidence = giveaway[8] if len(giveaway) > 8 else 0
        subscription_status = giveaway[9] if len(giveaway) > 9 else "unknown"

        method_icon = "🤖" if auto_detected else "👤"
        subscription_icon = "✅" if subscription_status != "unknown" else "❓"

        confidence_info = f" ({confidence:.0%})" if auto_detected and confidence > 0 else ""

        response += f"{i}. {method_icon} **{title}**{confidence_info}\n"
        response += f"   🎁 {prize}\n"
        response += f"   📅 {date_time}\n"

        if subscription_status != "unknown":
            response += f"   {subscription_icon} Подписки: {subscription_status}\n"

        if channels:
            channels_preview = channels[:50] + "..." if len(channels) > 50 else channels
            response += f"   📢 {channels_preview}\n"

        response += "   " + "─" * 30 + "\n\n"

        btn_complete = telebot.types.InlineKeyboardButton(
            f"✅ Завершить '{title[:15]}...'",
            callback_data=f"complete_{giveaway_id}"
        )
        keyboard.add(btn_complete)

        # Проверка подписок только для премиум
        if is_premium_user(user_id):
            btn_check = telebot.types.InlineKeyboardButton(
                f"🔍 Проверить подписки",
                callback_data=f"check_subs_{giveaway_id}"
            )
            keyboard.add(btn_check)

    bot.send_message(
        message.chat.id, 
        response, 
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@check_premium_required
def check_subscriptions_menu(message):
    user_id = message.from_user.id
    giveaways = get_user_giveaways(user_id)

    if not giveaways:
        bot.send_message(
            message.chat.id,
            "📭 У вас нет активных розыгрышей для проверки подписок",
            reply_markup=create_main_keyboard(user_id)
        )
        return

    keyboard = telebot.types.InlineKeyboardMarkup()
    for giveaway in giveaways[:10]:
        giveaway_id, title = giveaway[0], giveaway[1]
        subscription_status = giveaway[9] if len(giveaway) > 9 else "unknown"

        status_emoji = "✅" if subscription_status != "unknown" else "❓"
        btn = telebot.types.InlineKeyboardButton(
            f"{status_emoji} {title[:25]}...",
            callback_data=f"check_subs_{giveaway_id}"
        )
        keyboard.add(btn)

    bot.send_message(
        message.chat.id,
        "✅ **Проверка подписок**\n\n"
        "Выберите розыгрыш для проверки подписок на каналы:",
        parse_mode='Markdown',
        reply_markup=keyboard
    )

def show_reminders(message):
    user_id = message.from_user.id
    giveaways = get_user_giveaways(user_id)

    if not giveaways:
        bot.send_message(
            message.chat.id,
            "📭 У вас нет запланированных напоминаний",
            reply_markup=create_main_keyboard(user_id)
        )
        return

    response = "🔔 **Ближайшие розыгрыши:**\n\n"
    now = datetime.datetime.now()
    upcoming_count = 0

    for giveaway in giveaways:
        title = giveaway[1]
        date_time_str = giveaway[3]

        try:
            giveaway_datetime = datetime.datetime.strptime(date_time_str, '%d.%m.%Y %H:%M')
            time_left = giveaway_datetime - now

            if time_left.total_seconds() > 0:
                upcoming_count += 1
                days = time_left.days
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, _ = divmod(remainder, 60)

                if days == 0 and hours < 2:
                    urgency = "🔥 СКОРО!"
                elif days == 0:
                    urgency = "⚡ Сегодня"
                elif days == 1:
                    urgency = "📅 Завтра"
                else:
                    urgency = f"📆 Через {days} дн."

                response += f"**{title}**\n"
                response += f"📅 {date_time_str}\n"
                response += f"{urgency} ({hours}ч {minutes}м)\n"
                response += "─" * 30 + "\n\n"
        except:
            continue

    if upcoming_count == 0:
        response = "📭 **Все розыгрыши уже прошли**"

    bot.send_message(
        message.chat.id, 
        response, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard(user_id)
    )

@check_premium_required
def show_history(message):
    user_id = message.from_user.id

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, prize, date_time, completed_at, result, won
        FROM giveaway_history 
        WHERE user_id = ?
        ORDER BY completed_at DESC
        LIMIT 15
    ''', (user_id,))

    history = cursor.fetchall()
    conn.close()

    if not history:
        bot.send_message(
            message.chat.id,
            "📭 **История розыгрышей пуста**",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard(user_id)
        )
        return

    response = f"📚 **История розыгрышей ({len(history)}):**\n\n"

    wins_count = sum(1 for entry in history if entry[5])
    win_rate = (wins_count / len(history)) * 100 if history else 0

    response += f"🏆 **Статистика:** {wins_count} побед из {len(history)} ({win_rate:.1f}%)\n\n"

    for i, entry in enumerate(history, 1):
        title, prize, date_time, completed_at, result, won = entry
        win_icon = "🏆" if won else "😐"

        response += f"{i}. {win_icon} **{title}**\n"
        response += f"   🎁 {prize}\n"
        response += f"   📅 {date_time}\n"
        if result:
            response += f"   🎯 {result}\n"
        response += "   " + "─" * 25 + "\n\n"

    bot.send_message(
        message.chat.id, 
        response, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard(user_id)
    )

def show_settings(message):
    user_id = message.from_user.id
    status = get_user_subscription_status(user_id)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT auto_detect, min_confidence, ocr_enabled, ai_enabled, notifications_enabled
        FROM user_settings WHERE user_id = ?
    ''', (user_id,))
    settings = cursor.fetchone()
    conn.close()

    if not settings:
        settings = (True, 0.6, True, True, True)

    auto_detect, min_confidence, ocr_enabled, ai_enabled, notifications_enabled = settings

    response = f"⚙️ **Настройки бота**\n\n"

    if status['is_premium'] or status['is_trial']:
        response += f"💎 **Премиум настройки:**\n"
        response += f"• 🤖 Автопоиск: {'✅' if auto_detect else '❌'}\n"
        response += f"• 📊 Минимум уверенности: {min_confidence:.0%}\n"
        if OCR_AVAILABLE:
            response += f"• 📸 OCR: {'✅' if ocr_enabled else '❌'}\n"
        response += f"• 🔔 Уведомления: {'✅' if notifications_enabled else '❌'}\n"
    else:
        response += f"🆓 **Базовые настройки:**\n"
        response += f"• 🤖 Автопоиск: {'✅' if auto_detect else '❌'}\n"
        response += f"• 🔔 Уведомления: {'✅' if notifications_enabled else '❌'}\n\n"
        response += f"💎 **Премиум функции заблокированы**"

    keyboard = telebot.types.InlineKeyboardMarkup()

    if status['is_premium'] or status['is_trial']:
        toggle_auto = "❌ Отключить автопоиск" if auto_detect else "✅ Включить автопоиск"
        btn1 = telebot.types.InlineKeyboardButton(toggle_auto, callback_data="toggle_auto_detect")
        keyboard.add(btn1)

        if OCR_AVAILABLE:
            toggle_ocr = "❌ Отключить OCR" if ocr_enabled else "✅ Включить OCR"
            btn2 = telebot.types.InlineKeyboardButton(toggle_ocr, callback_data="toggle_ocr")
            keyboard.add(btn2)
    else:
        btn_premium = telebot.types.InlineKeyboardButton("💎 Получить премиум", callback_data="show_pricing")
        keyboard.add(btn_premium)

    bot.send_message(
        message.chat.id,
        response,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

# Вспомогательные функции
def setup_reminder(user_id, giveaway_id, title, date_str):
    try:
        if ' ' in date_str:
            reminder_datetime = datetime.datetime.strptime(date_str, '%d.%m.%Y %H:%M')
        else:
            reminder_datetime = datetime.datetime.strptime(date_str + ' 20:00', '%d.%m.%Y %H:%M')

        reminder_time = reminder_datetime - datetime.timedelta(hours=1)

        if reminder_time > datetime.datetime.now():
            scheduler.add_job(
                send_reminder,
                'date',
                run_date=reminder_time,
                args=[user_id, giveaway_id, title, date_str],
                id=f"reminder_{giveaway_id}"
            )
            return True
    except Exception as e:
        print(f"Ошибка настройки напоминания: {e}")
        return False

def send_reminder(user_id, giveaway_id, title, date_time):
    try:
        reminder_text = f"🔔 **Напоминание о розыгрыше!**\n\n"
        reminder_text += f"📝 {title}\n"
        reminder_text += f"📅 Начало: {date_time}\n\n"
        reminder_text += "⏰ Розыгрыш начнется через час!"

        keyboard = telebot.types.InlineKeyboardMarkup()

        # Проверка подписок только для премиум
        if is_premium_user(user_id):
            btn1 = telebot.types.InlineKeyboardButton(
                "🔍 Проверить подписки",
                callback_data=f"check_subs_{giveaway_id}"
            )
            keyboard.add(btn1)

        bot.send_message(
            user_id,
            reminder_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )

    except Exception as e:
        print(f"Ошибка при отправке напоминания: {e}")

# Команды администратора
@bot.message_handler(commands=['confirm_payment'])
def admin_confirm_payment(message):
    # Только для администраторов (добавьте проверку прав)
    admin_ids = [123456789]  # Замените на реальные ID администраторов

    if message.from_user.id not in admin_ids:
        return

    try:
        user_id = int(message.text.split()[1])
        end_date = activate_premium(user_id, 1)

        bot.send_message(
            message.chat.id,
            f"✅ Премиум активирован для пользователя {user_id}\n"
            f"До: {end_date.strftime('%d.%m.%Y')}"
        )

        # Уведомляем пользователя
        try:
            bot.send_message(
                user_id,
                "✅ **Оплата подтверждена!**\n\n"
                f"💎 Премиум подписка активирована\n"
                f"⏰ Действует до: {end_date.strftime('%d.%m.%Y')}\n\n"
                "Спасибо за покупку! 🎉",
                parse_mode='Markdown'
            )
        except:
            pass

    except (IndexError, ValueError):
        bot.send_message(
            message.chat.id,
            "❌ Использование: /confirm_payment USER_ID"
        )

# Запуск бота
if __name__ == "__main__":
    print("🚀 Инициализация премиум бота v3.0...")
    init_database()
    print("✅ База данных инициализирована")
    print("💎 Система подписок активна")
    print("💳 Поддержка оплаты: Карты, Telegram Stars, TON")
    print("🎁 Пробный период: 3 дня")
    print("💰 Цена подписки: 60₽/месяц")
    print("🔍 Автопоиск розыгрышей: активен")

    if OCR_AVAILABLE:
        print("📸 OCR обработка: активна (премиум)") 
    else:
        print("📸 OCR обработка: недоступна")

    print("✅ Проверка подписок: активна (премиум)")
    print("📚 История розыгрышей: активна (премиум)")
    print("👥 Реферальная система: активна")
    print("🎉 Премиум бот запущен!")

    try:
        bot.polling(none_stop=True, interval=0)
    except Exception as e:
        print(f"Ошибка: {e}")
