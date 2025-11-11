# -*- coding: utf-8 -*-
"""
🚀 ТЕЛЕГРАМ-БОТ ДЛЯ РОЗЫГРЫШЕЙ v3.0 (Упрощенная версия)
=====================================================

Без экспорта данных для более простой установки и запуска
"""

import telebot
import sqlite3
import datetime
import re
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import pytz

# Попытка импорта дополнительных библиотек
try:
    from PIL import Image
    import pytesseract
    import io
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("⚠️ OCR функции недоступны. Установите: pip install pillow pytesseract")

try:
    import openai
    CHATGPT_AVAILABLE = True
except ImportError:
    CHATGPT_AVAILABLE = False
    print("⚠️ ChatGPT функции недоступны. Установите: pip install openai")

# Константы
BOT_TOKEN = "ВАШ_ТОКЕН_ОТ_BOTFATHER"  # Замените на ваш токен
OPENAI_API_KEY = "ВАШ_OPENAI_API_KEY"  # Замените на ваш OpenAI ключ (опционально)
DB_NAME = "ultimate_giveaways.db"

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
    r'\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\b',  # ДД.ММ.ГГГГ
    r'\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2})\b',   # ДД.ММ.ГГ
]

CHANNEL_PATTERNS = [
    r'@[a-zA-Z_][a-zA-Z0-9_]{4,}',  # @channel_name
    r't\.me/[a-zA-Z_][a-zA-Z0-9_]+', # t.me/channel
    r'https://t\.me/[a-zA-Z_][a-zA-Z0-9_]+',  # https://t.me/channel
]

PRIZE_PATTERNS = [
    r'(iPhone|iPad|MacBook|Samsung|Xiaomi|Huawei|OnePlus)[^\n]*',
    r'(\d+\s*(?:руб|рублей|долларов|евро|₽|$|€))',
    r'(сертификат|подарочный\s+сертификат)[^\n]*',
    r'(приз|подарок)[^\n]*',
]

# Инициализация базы данных
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

    # Настройки пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            auto_detect BOOLEAN DEFAULT TRUE,
            min_confidence REAL DEFAULT 0.6,
            ocr_enabled BOOLEAN DEFAULT TRUE,
            ai_enabled BOOLEAN DEFAULT TRUE
        )
    ''')

    conn.commit()
    conn.close()

# Функции анализа текста
def extract_dates_from_text(text):
    dates = []
    for pattern in DATE_PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches:
            if len(match) == 3:
                try:
                    if len(match[2]) == 4:  # ГГГГ формат
                        date_str = f"{match[0]}.{match[1]}.{match[2]}"
                    else:  # ГГ формат
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

# OCR функции (если доступны)
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

# Проверка подписок
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

    # Обновляем общий статус
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

    conn.commit()
    conn.close()

# Клавиатуры
def create_main_keyboard():
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = telebot.types.KeyboardButton("➕ Добавить розыгрыш")
    btn2 = telebot.types.KeyboardButton("📋 Мои розыгрыши")
    btn3 = telebot.types.KeyboardButton("✅ Проверить подписки")
    btn4 = telebot.types.KeyboardButton("🔔 Напоминания")
    btn5 = telebot.types.KeyboardButton("📚 История")
    btn6 = telebot.types.KeyboardButton("⚙️ Настройки")
    keyboard.add(btn1, btn2, btn3, btn4, btn5, btn6)
    return keyboard

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
    if CHATGPT_AVAILABLE and OPENAI_API_KEY != "ВАШ_OPENAI_API_KEY":
        btn3 = telebot.types.InlineKeyboardButton(
            "🧠 ИИ анализ", 
            callback_data="ai_analyze"
        )
        keyboard.add(btn1, btn2, btn3)
    else:
        keyboard.add(btn1, btn2)

    btn4 = telebot.types.InlineKeyboardButton(
        "❌ Отклонить", 
        callback_data="auto_reject"
    )
    keyboard.add(btn4)
    return keyboard

# Основные обработчики
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

    features_text = "🎯 **Возможности:**\n"
    features_text += "• 🤖 Автопоиск розыгрышей в сообщениях\n"
    if OCR_AVAILABLE:
        features_text += "• 📸 Анализ изображений с OCR\n"
    if CHATGPT_AVAILABLE and OPENAI_API_KEY != "ВАШ_OPENAI_API_KEY":
        features_text += "• 🧠 ИИ-анализ с ChatGPT\n"
    features_text += "• ✅ Проверка подписок на каналы\n"
    features_text += "• 📚 История всех розыгрышей\n"
    features_text += "• 🔔 Умные напоминания"

    bot.send_message(
        message.chat.id,
        f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
        "🚀 **Телеграм-бот для розыгрышей v3.0**\n\n"
        f"{features_text}\n\n"
        "📝 **Просто пересылайте мне сообщения с розыгрышами!**",
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
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
    else:
        analyze_and_suggest_giveaway(message)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if not OCR_AVAILABLE:
        bot.send_message(
            message.chat.id,
            "📸 Получено изображение, но OCR функции недоступны\n\n"
            "Для анализа изображений установите:\n"
            "`pip install pillow pytesseract`\n\n"
            "А также Tesseract OCR на вашу систему",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        return

    user_id = message.from_user.id
    processing_msg = bot.send_message(message.chat.id, "📸 Обрабатываю изображение...")

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        bot.edit_message_text("🔍 Распознаю текст...", message.chat.id, processing_msg.message_id)
        text = extract_text_from_image(downloaded_file)

        if not text:
            bot.edit_message_text(
                "❌ Не удалось распознать текст на изображении\n\n"
                "Попробуйте с более четким изображением",
                message.chat.id, processing_msg.message_id,
                reply_markup=create_main_keyboard()
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
                channels_preview = giveaway_data['suggested_channels'][:200]
                response += f"📢 Каналы:\n{channels_preview}\n"

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
            confidence_text = f" (уверенность: {giveaway_data['confidence']:.1%})" if giveaway_data else ""

            bot.edit_message_text(
                f"📸 **OCR завершен**\n\n"
                f"📝 Распознанный текст:\n{text[:300]}{'...' if len(text) > 300 else ''}\n\n"
                f"🔍 Розыгрыш не обнаружен{confidence_text}",
                message.chat.id, processing_msg.message_id,
                parse_mode='Markdown', reply_markup=create_main_keyboard()
            )

    except Exception as e:
        bot.edit_message_text(
            f"❌ Ошибка обработки изображения: {str(e)[:100]}",
            message.chat.id, processing_msg.message_id,
            reply_markup=create_main_keyboard()
        )

def analyze_and_suggest_giveaway(message):
    user_id = message.from_user.id
    text = message.text

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT auto_detect, min_confidence FROM user_settings WHERE user_id = ?', (user_id,))
    settings = cursor.fetchone()
    conn.close()

    if not settings or not settings[0]:
        bot.send_message(
            message.chat.id,
            "🤔 Не понимаю эту команду\n\n"
            "Используйте кнопки меню или команду /start",
            reply_markup=create_main_keyboard()
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
            reply_markup=create_main_keyboard()
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

# Callback обработчики
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
            "💡 **Пример:**\n"
            "@channel1\n"
            "@channel2",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, save_manual_giveaway, title, prize, date_time_str)
    except ValueError:
        msg = bot.send_message(
            message.chat.id,
            "❌ **Неверный формат даты!**\n\n"
            "📝 Используйте формат: **ДД.ММ.ГГГГ ЧЧ:ММ**\n"
            "💡 Пример: **25.12.2024 20:00**",
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
        reply_markup=create_main_keyboard()
    )

# Просмотр розыгрышей
def show_giveaways(message):
    user_id = message.from_user.id
    giveaways = get_user_giveaways(user_id)

    if not giveaways:
        bot.send_message(
            message.chat.id,
            "📭 **У вас нет активных розыгрышей**\n\n"
            "➕ Добавьте первый розыгрыш с помощью кнопки меню",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
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
        subscription_icon = "✅" if subscription_status != "unknown" and "/" in str(subscription_status) else "❓"

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
        btn_check = telebot.types.InlineKeyboardButton(
            f"🔍 Проверить подписки",
            callback_data=f"check_subs_{giveaway_id}"
        )
        keyboard.add(btn_complete)
        keyboard.add(btn_check)

    if len(giveaways) > 1:
        btn_check_all = telebot.types.InlineKeyboardButton(
            "🔄 Проверить все подписки",
            callback_data="check_all_subs"
        )
        keyboard.add(btn_check_all)

    bot.send_message(
        message.chat.id, 
        response, 
        parse_mode='Markdown',
        reply_markup=keyboard
    )

# Проверка подписок
def check_subscriptions_menu(message):
    user_id = message.from_user.id
    giveaways = get_user_giveaways(user_id)

    if not giveaways:
        bot.send_message(
            message.chat.id,
            "📭 У вас нет активных розыгрышей для проверки подписок",
            reply_markup=create_main_keyboard()
        )
        return

    keyboard = telebot.types.InlineKeyboardMarkup()
    for giveaway in giveaways[:10]:
        giveaway_id, title = giveaway[0], giveaway[1]
        subscription_status = giveaway[9] if len(giveaway) > 9 else "unknown"

        status_emoji = "✅" if subscription_status and subscription_status != "unknown" else "❓"
        btn = telebot.types.InlineKeyboardButton(
            f"{status_emoji} {title[:25]}...",
            callback_data=f"check_subs_{giveaway_id}"
        )
        keyboard.add(btn)

    if len(giveaways) > 1:
        btn_all = telebot.types.InlineKeyboardButton(
            "🔄 Проверить все подписки",
            callback_data="check_all_subs"
        )
        keyboard.add(btn_all)

    bot.send_message(
        message.chat.id,
        "✅ **Проверка подписок**\n\n"
        "Выберите розыгрыш для проверки подписок на каналы:",
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_subs_'))
async def handle_subscription_check(call):
    user_id = call.from_user.id
    giveaway_id = int(call.data.split('_')[2])

    bot.edit_message_text(
        "🔄 **Проверяю подписки...**",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

    try:
        subscription_results = await check_all_giveaway_subscriptions(giveaway_id, user_id)

        if not subscription_results:
            bot.edit_message_text(
                "❌ **Ошибка проверки**\n\n"
                "Не удалось найти каналы для проверки",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
            return

        response = "✅ **Результаты проверки подписок:**\n\n"

        subscribed_count = 0
        total_count = len(subscription_results)

        for result in subscription_results:
            if result['subscribed']:
                response += f"✅ `{result['channel']}` - подписаны\n"
                subscribed_count += 1
            else:
                response += f"❌ `{result['channel']}` - НЕ подписаны\n"

        response += f"\n📊 **Итого: {subscribed_count}/{total_count} подписок**\n"

        if subscribed_count == total_count:
            response += "\n🎉 **Отлично!** Все подписки активны!"
        elif subscribed_count > 0:
            response += f"\n⚠️ **Внимание!** Недостает {total_count - subscribed_count} подписок"
        else:
            response += "\n❌ **Проблема!** Вы не подписаны ни на один канал"

        keyboard = telebot.types.InlineKeyboardMarkup()
        btn_recheck = telebot.types.InlineKeyboardButton(
            "🔄 Проверить снова", 
            callback_data=f"check_subs_{giveaway_id}"
        )
        keyboard.add(btn_recheck)

        bot.edit_message_text(
            response,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=keyboard
        )

    except Exception as e:
        bot.edit_message_text(
            f"❌ **Ошибка проверки подписок**\n\n"
            f"Детали: {str(e)[:100]}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

# История розыгрышей
def show_history(message):
    user_id = message.from_user.id

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, prize, date_time, completed_at, result, won, notes
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
            "📭 **История розыгрышей пуста**\n\n"
            "Завершите несколько розыгрышей, чтобы они появились здесь",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        return

    response = f"📚 **История розыгрышей ({len(history)}):**\n\n"

    wins_count = sum(1 for entry in history if entry[5])
    win_rate = (wins_count / len(history)) * 100 if history else 0

    response += f"🏆 **Статистика:** {wins_count} побед из {len(history)} ({win_rate:.1f}%)\n\n"

    for i, entry in enumerate(history, 1):
        title, prize, date_time, completed_at, result, won, notes = entry
        completed_date = completed_at.split()[0] if completed_at else "Неизвестно"

        win_icon = "🏆" if won else "😐"

        response += f"{i}. {win_icon} **{title}**\n"
        response += f"   🎁 {prize}\n"
        response += f"   📅 Розыгрыш: {date_time}\n"
        response += f"   ✅ Завершен: {completed_date}\n"

        if result:
            response += f"   🎯 Результат: {result}\n"

        response += "   " + "─" * 25 + "\n\n"

    bot.send_message(
        message.chat.id, 
        response, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

# Напоминания
def show_reminders(message):
    user_id = message.from_user.id
    giveaways = get_user_giveaways(user_id)

    if not giveaways:
        bot.send_message(
            message.chat.id,
            "📭 У вас нет запланированных напоминаний",
            reply_markup=create_main_keyboard()
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
                response += f"{urgency} "

                if days > 0:
                    response += f"({days} дн. {hours} ч. {minutes} мин.)\n"
                else:
                    response += f"({hours} ч. {minutes} мин.)\n"

                response += "─" * 30 + "\n\n"
        except:
            continue

    if upcoming_count == 0:
        response = "📭 **Все розыгрыши уже прошли**"
    else:
        response = f"🔔 **Ближайшие розыгрыши ({upcoming_count}):**\n\n" + response[len("🔔 **Ближайшие розыгрыши:**\n\n"):]

    bot.send_message(
        message.chat.id, 
        response, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

# Настройки
def show_settings(message):
    user_id = message.from_user.id

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT auto_detect, min_confidence, ocr_enabled, ai_enabled
        FROM user_settings WHERE user_id = ?
    ''', (user_id,))
    settings = cursor.fetchone()
    conn.close()

    if not settings:
        settings = (True, 0.6, True, True)

    auto_detect, min_confidence, ocr_enabled, ai_enabled = settings

    response = f"⚙️ **Настройки бота**\n\n"
    response += f"🤖 **Автопоиск:** {'✅ Включен' if auto_detect else '❌ Отключен'}\n"
    response += f"📊 **Минимальная уверенность:** {min_confidence:.0%}\n\n"

    if OCR_AVAILABLE:
        response += f"📸 **OCR:** {'✅ Включен' if ocr_enabled else '❌ Отключен'}\n\n"

    if CHATGPT_AVAILABLE:
        response += f"🧠 **ИИ анализ:** {'✅ Включен' if ai_enabled else '❌ Отключен'}\n\n"

    response += f"💡 **Совет:** Настройте параметры под ваши потребности"

    keyboard = telebot.types.InlineKeyboardMarkup()

    toggle_auto = "❌ Отключить автопоиск" if auto_detect else "✅ Включить автопоиск"
    btn1 = telebot.types.InlineKeyboardButton(toggle_auto, callback_data="toggle_auto_detect")
    keyboard.add(btn1)

    if OCR_AVAILABLE:
        toggle_ocr = "❌ Отключить OCR" if ocr_enabled else "✅ Включить OCR"
        btn2 = telebot.types.InlineKeyboardButton(toggle_ocr, callback_data="toggle_ocr")
        keyboard.add(btn2)

    bot.send_message(
        message.chat.id,
        response,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_'))
def handle_settings_toggle(call):
    user_id = call.from_user.id

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if call.data == 'toggle_auto_detect':
        cursor.execute('SELECT auto_detect FROM user_settings WHERE user_id = ?', (user_id,))
        current = cursor.fetchone()
        current_value = current[0] if current else True
        new_value = not current_value

        cursor.execute('''
            INSERT OR REPLACE INTO user_settings (user_id, auto_detect) 
            VALUES (?, ?)
        ''', (user_id, new_value))

        status = "включен" if new_value else "отключен"
        bot.answer_callback_query(call.id, f"Автопоиск {status}!")

    elif call.data == 'toggle_ocr':
        cursor.execute('SELECT ocr_enabled FROM user_settings WHERE user_id = ?', (user_id,))
        current = cursor.fetchone()
        current_value = current[0] if current else True
        new_value = not current_value

        cursor.execute('''
            INSERT OR REPLACE INTO user_settings (user_id, ocr_enabled) 
            VALUES (?, ?)
        ''', (user_id, new_value))

        status = "включен" if new_value else "отключен"
        bot.answer_callback_query(call.id, f"OCR {status}!")

    conn.commit()
    conn.close()

    fake_message = type('obj', (object,), {
        'chat': type('obj', (object,), {'id': call.message.chat.id}),
        'from_user': call.from_user
    })
    show_settings(fake_message)

# Завершение розыгрышей
@bot.callback_query_handler(func=lambda call: call.data.startswith('complete_'))
def complete_giveaway_handler(call):
    giveaway_id = int(call.data.split('_')[1])
    user_id = call.from_user.id

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT title FROM giveaways WHERE id = ? AND user_id = ?', (giveaway_id, user_id))
    giveaway = cursor.fetchone()
    conn.close()

    if not giveaway:
        bot.answer_callback_query(call.id, "❌ Розыгрыш не найден")
        return

    title = giveaway[0]

    keyboard = telebot.types.InlineKeyboardMarkup()
    btn1 = telebot.types.InlineKeyboardButton("🏆 Выиграл!", callback_data=f"result_won_{giveaway_id}")
    btn2 = telebot.types.InlineKeyboardButton("😐 Не выиграл", callback_data=f"result_lost_{giveaway_id}")
    btn3 = telebot.types.InlineKeyboardButton("❓ Неизвестно", callback_data=f"result_unknown_{giveaway_id}")
    btn4 = telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_complete")

    keyboard.add(btn1, btn2)
    keyboard.add(btn3, btn4)

    bot.edit_message_text(
        f"🎯 **Завершение розыгрыша**\n\n"
        f"📝 **{title}**\n\n"
        f"Какой результат?",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('result_'))
def handle_giveaway_result(call):
    parts = call.data.split('_')
    result_type = parts[1]
    giveaway_id = int(parts[2])

    if result_type == 'won':
        result_text = "Выиграл! 🎉"
        won = True
        emoji = "🏆"
    elif result_type == 'lost':
        result_text = "Не выиграл"
        won = False
        emoji = "😐"
    else:
        result_text = "Результат неизвестен"
        won = False
        emoji = "❓"

    complete_giveaway(giveaway_id, result_text, "", won)

    try:
        scheduler.remove_job(f"reminder_{giveaway_id}")
    except:
        pass

    bot.edit_message_text(
        f"{emoji} **Розыгрыш завершен!**\n\n"
        f"📊 Результат: **{result_text}**\n"
        f"📚 Розыгрыш перенесен в историю",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

    bot.answer_callback_query(call.id, f"{emoji} Розыгрыш завершен!")

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_complete')
def cancel_complete(call):
    bot.edit_message_text(
        "❌ **Завершение отменено**",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )
    bot.answer_callback_query(call.id, "Отменено")

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
        reminder_text += "⏰ Розыгрыш начнется через час!\n"
        reminder_text += "✅ Не забудьте проверить подписки на каналы"

        keyboard = telebot.types.InlineKeyboardMarkup()
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

# Запуск бота
if __name__ == "__main__":
    print("🚀 Инициализация телеграм-бота v3.0...")
    init_database()
    print("✅ База данных инициализирована")
    print("🔍 Автопоиск розыгрышей: активен")

    if OCR_AVAILABLE:
        print("📸 OCR обработка изображений: активна") 
    else:
        print("📸 OCR обработка: недоступна (установите pillow и pytesseract)")

    if CHATGPT_AVAILABLE:
        print("🧠 ChatGPT интеграция:", "активна" if OPENAI_API_KEY != "ВАШ_OPENAI_API_KEY" else "настройте API ключ")
    else:
        print("🧠 ChatGPT интеграция: недоступна (установите openai)")

    print("✅ Проверка подписок: активна")
    print("📚 История розыгрышей: активна")
    print("⚙️ Настройки: активны")
    print("🎉 Бот запущен!")

    try:
        bot.polling(none_stop=True, interval=0)
    except Exception as e:
        print(f"Ошибка: {e}")
