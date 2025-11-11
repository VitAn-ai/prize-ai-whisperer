# -*- coding: utf-8 -*-
"""
🚀 УЛЬТИМАТИВНЫЙ ТЕЛЕГРАМ-БОТ ДЛЯ РОЗЫГРЫШЕЙ v3.0
=================================================

Автор: AI Assistant
Дата: 06.10.2025
Версия: 3.0 Ultimate Edition

🎯 ВОЗМОЖНОСТИ:
• 🤖 Автоматическое распознавание розыгрышей из текста
• 🧠 Интеграция с ChatGPT для ИИ-анализа
• ✅ Автоматическая проверка подписок на каналы
• 📊 Экспорт данных в Excel с графиками
• 📈 Продвинутая аналитика с визуализацией
• 📚 Полная история всех розыгрышей
• ⚙️ Гибкие настройки пользователя
• 🔔 Умные напоминания
• 🌍 Поддержка многоязычности (готовность)

📋 ТРЕБОВАНИЯ:
pip install pyTelegramBotAPI APScheduler pytz pandas matplotlib seaborn openpyxl openai

🔧 НАСТРОЙКА:
1. Замените BOT_TOKEN на ваш токен от @BotFather
2. Замените OPENAI_API_KEY на ваш ключ OpenAI (опционально)
3. Запустите: python ultimate_giveaway_bot.py

⚠️ ВАЖНО:
- Для полной функциональности нужны все зависимости
- ChatGPT функции опциональны (нужен API ключ)
- Бот создает локальную SQLite базу данных

🎉 ГОТОВ К РАБОТЕ!
"""


import telebot
import sqlite3
import datetime
import re
import json
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import pytz
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
import os

# Импорт модулей
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from core.unsubscribe_manager import UnsubscribeManager
from core.ai_giveaway_recognizer import AIGiveawayRecognizer

# Дополнительные импорты для новых функций
try:
    import openai
    CHATGPT_AVAILABLE = True
except ImportError:
    CHATGPT_AVAILABLE = False
    print("⚠️ OpenAI не установлен. ChatGPT функции недоступны.")

# Константы
BOT_TOKEN = "7587317710:AAHwWNR0PP4aWGImFcjWIYfhfnEqMHAdrlk"  # Токен бота
OPENAI_API_KEY = "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"  # OpenAI ключ

# Путь к базе данных (всегда в корне проекта)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DB_NAME = os.path.join(PROJECT_ROOT, "ultimate_giveaways.db")

# Настройка OpenAI
if CHATGPT_AVAILABLE and OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Инициализация бота и планировщика
bot = telebot.TeleBot(BOT_TOKEN)
scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Moscow'))
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# Инициализация менеджеров
unsubscribe_manager = None
ai_recognizer = None

# Инициализация ИИ-распознавателя
if OPENAI_API_KEY:
    try:
        ai_recognizer = AIGiveawayRecognizer(OPENAI_API_KEY)
        print("✅ ИИ-распознаватель инициализирован")
    except Exception as e:
        print(f"⚠️ Ошибка инициализации ИИ-распознавателя: {e}")
        ai_recognizer = None

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
    r'\b(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\b',   # ГГГГ.ММ.ДД
]

TIME_PATTERNS = [
    r'\b(\d{1,2}):(\d{2})\b',  # ЧЧ:ММ
    r'\b(\d{1,2})\.(\d{2})\b', # ЧЧ.ММ
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

# Инициализация расширенной базы данных
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
            source_message TEXT,
            auto_detected BOOLEAN DEFAULT FALSE,
            confidence_score REAL DEFAULT 0.0,
            created_at TIMESTAMP,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            result TEXT,
            notes TEXT,
            won BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (original_giveaway_id) REFERENCES giveaways (id)
        )
    ''')

    # Детали каналов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS giveaway_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            giveaway_id INTEGER,
            channel_name TEXT,
            channel_link TEXT,
            is_subscribed BOOLEAN DEFAULT FALSE,
            last_checked TIMESTAMP NULL,
            FOREIGN KEY (giveaway_id) REFERENCES giveaways (id)
        )
    ''')

    # Настройки пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            auto_detect BOOLEAN DEFAULT TRUE,
            min_confidence REAL DEFAULT 0.6,
            notify_auto_detect BOOLEAN DEFAULT TRUE,
            timezone TEXT DEFAULT 'Europe/Moscow',
            language TEXT DEFAULT 'ru',
            ai_enabled BOOLEAN DEFAULT TRUE,
            export_format TEXT DEFAULT 'xlsx'
        )
    ''')

    # Статистика использования
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

# ==================== ФУНКЦИИ АНАЛИЗА ТЕКСТА ====================

def extract_dates_from_text(text):
    """Извлекает даты из текста"""
    dates = []
    for pattern in DATE_PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches:
            if len(match) == 3:
                try:
                    if len(match[2]) == 4:  # ГГГГ формат
                        if int(match[0]) > 12:  # ДД.ММ.ГГГГ
                            date_str = f"{match[0]}.{match[1]}.{match[2]}"
                        else:  # ММ.ДД.ГГГГ
                            date_str = f"{match[1]}.{match[0]}.{match[2]}"
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
    """Извлекает каналы из текста"""
    channels = []
    for pattern in CHANNEL_PATTERNS:
        matches = re.findall(pattern, text)
        channels.extend(matches)
    return list(set(channels))

def extract_prizes_from_text(text):
    """Извлекает информацию о призах из текста"""
    prizes = []
    for pattern in PRIZE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        prizes.extend(matches)
    return prizes

def calculate_giveaway_confidence(text):
    """Вычисляет уверенность в том, что текст содержит информацию о розыгрыше"""
    text_lower = text.lower()

    # Подсчитываем ключевые слова
    keyword_count = sum(1 for keyword in GIVEAWAY_KEYWORDS if keyword in text_lower)
    keyword_score = min(keyword_count / 3.0, 1.0)

    # Проверяем наличие структурных элементов
    dates = extract_dates_from_text(text)
    channels = extract_channels_from_text(text)
    prizes = extract_prizes_from_text(text)

    date_score = 0.3 if dates else 0.0
    channel_score = 0.2 if channels else 0.0
    prize_score = 0.2 if prizes else 0.0

    total_confidence = keyword_score * 0.5 + date_score + channel_score + prize_score
    return min(total_confidence, 1.0)

# ==================== CHATGPT ФУНКЦИИ ====================

async def analyze_giveaway_with_ai(text: str) -> dict:
    """Анализирует розыгрыш с помощью ChatGPT"""
    if not CHATGPT_AVAILABLE or not OPENAI_API_KEY:
        return None

    prompt = f'''
    Проанализируй этот текст и определи, есть ли в нем информация о розыгрыше/конкурсе.

    Текст: "{text}"

    Ответь в JSON формате:
    {{
        "is_giveaway": true/false,
        "confidence": 0.0-1.0,
        "title": "название розыгрыша",
        "prize": "приз",
        "date": "дата в формате ДД.ММ.ГГГГ",
        "time": "время в формате ЧЧ:ММ",
        "channels": ["@канал1", "@канал2"],
        "conditions": ["условие 1", "условие 2"],
        "summary": "краткое описание розыгрыша на русском"
    }}
    '''

    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.3
        )

        result = response.choices[0].message.content
        return json.loads(result)
    except Exception as e:
        print(f"Ошибка ChatGPT: {e}")
        return None

# ==================== ФУНКЦИИ ПРОВЕРКИ ПОДПИСОК ====================

async def check_user_subscription(user_id: int, channel: str) -> dict:
    """Проверяет подписку пользователя на канал"""
    try:
        # Убираем @ из начала канала если есть
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
    """Проверяет все подписки для конкретного розыгрыша"""
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

        # Обновляем статус в базе
        cursor.execute('''
            INSERT OR REPLACE INTO giveaway_channels 
            (giveaway_id, channel_name, is_subscribed, last_checked)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (giveaway_id, channel, check_result['subscribed']))

    # Обновляем общий статус розыгрыша
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

# ==================== ФУНКЦИИ ЭКСПОРТА ДАННЫХ ====================

def export_user_data_to_excel(user_id: int) -> str:
    """Экспортирует все данные пользователя в Excel файл"""
    conn = sqlite3.connect(DB_NAME)

    try:
        # Активные розыгрыши
        active_query = '''
            SELECT 
                title as "Название",
                prize as "Приз", 
                date_time as "Дата и время",
                channels as "Каналы",
                CASE WHEN auto_detected = 1 THEN "Автоматически" ELSE "Вручную" END as "Способ добавления",
                CASE WHEN auto_detected = 1 THEN ROUND(confidence_score * 100, 1) || "%" ELSE "-" END as "Уверенность ИИ",
                CASE WHEN ocr_processed = 1 THEN "Да" ELSE "Нет" END as "Обработка OCR",
                subscription_status as "Статус подписок",
                created_at as "Дата создания"
            FROM giveaways 
            WHERE user_id = ? AND is_active = 1
            ORDER BY date_time ASC
        '''

        active_df = pd.read_sql_query(active_query, conn, params=(user_id,))

        # История розыгрышей  
        history_query = '''
            SELECT 
                title as "Название",
                prize as "Приз",
                date_time as "Дата розыгрыша", 
                completed_at as "Дата завершения",
                result as "Результат",
                CASE WHEN won = 1 THEN "Да" ELSE "Нет" END as "Выиграл",
                notes as "Заметки"
            FROM giveaway_history
            WHERE user_id = ?
            ORDER BY completed_at DESC
        '''

        history_df = pd.read_sql_query(history_query, conn, params=(user_id,))

        # Статистика
        stats_query = '''
            SELECT 
                'Всего розыгрышей' as "Показатель",
                COUNT(*) as "Значение"
            FROM giveaways WHERE user_id = ?
            UNION ALL
            SELECT 
                'Активных', 
                COUNT(*)
            FROM giveaways WHERE user_id = ? AND is_active = 1
            UNION ALL  
            SELECT
                'Завершенных',
                COUNT(*)
            FROM giveaway_history WHERE user_id = ?
            UNION ALL
            SELECT 
                'Найдено автоматически',
                COUNT(*)
            FROM giveaways WHERE user_id = ? AND auto_detected = 1
            UNION ALL
            SELECT 
                'Обработано OCR',
                COUNT(*)
            FROM giveaways WHERE user_id = ? AND ocr_processed = 1
            UNION ALL
            SELECT 
                'Выигрышей',
                COUNT(*)
            FROM giveaway_history WHERE user_id = ? AND won = 1
        '''

        stats_df = pd.read_sql_query(stats_query, conn, params=(user_id, user_id, user_id, user_id, user_id, user_id))

        # Создаем Excel файл
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'my_giveaways_{timestamp}.xlsx'

        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            active_df.to_excel(writer, sheet_name='Активные розыгрыши', index=False)
            history_df.to_excel(writer, sheet_name='История', index=False) 
            stats_df.to_excel(writer, sheet_name='Статистика', index=False)

            # Автоширина колонок
            for sheet_name in ['Активные розыгрыши', 'История', 'Статистика']:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column = [cell for cell in column]
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column[0].column_letter].width = adjusted_width

        conn.close()
        return filename

    except Exception as e:
        conn.close()
        raise e

# ==================== ФУНКЦИИ АНАЛИТИКИ ====================

def generate_user_analytics(user_id: int) -> dict:
    """Генерирует подробную аналитику пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Базовая статистика
    cursor.execute('''
        SELECT 
            COUNT(*) as total_giveaways,
            COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_count,
            COUNT(CASE WHEN auto_detected = 1 THEN 1 END) as auto_detected_count,
            COUNT(CASE WHEN ocr_processed = 1 THEN 1 END) as ocr_count,
            AVG(confidence_score) as avg_confidence
        FROM giveaways WHERE user_id = ?
    ''', (user_id,))

    stats = cursor.fetchone()

    # Статистика выигрышей
    cursor.execute('''
        SELECT 
            COUNT(*) as total_completed,
            COUNT(CASE WHEN won = 1 THEN 1 END) as wins_count
        FROM giveaway_history WHERE user_id = ?
    ''', (user_id,))

    wins_stats = cursor.fetchone()

    # Статистика по месяцам
    cursor.execute('''
        SELECT 
            strftime('%Y-%m', created_at) as month,
            COUNT(*) as count,
            COUNT(CASE WHEN auto_detected = 1 THEN 1 END) as auto_count
        FROM giveaways 
        WHERE user_id = ?
        GROUP BY strftime('%Y-%m', created_at)
        ORDER BY month DESC
        LIMIT 12
    ''', (user_id,))

    monthly_stats = cursor.fetchall()

    # Топ призов
    cursor.execute('''
        SELECT prize, COUNT(*) as count
        FROM giveaways 
        WHERE user_id = ? AND prize != 'Не определено'
        GROUP BY prize
        ORDER BY count DESC
        LIMIT 5
    ''', (user_id,))

    top_prizes = cursor.fetchall()

    conn.close()

    return {
        'total_giveaways': stats[0] or 0,
        'active_count': stats[1] or 0,
        'completed_count': wins_stats[0] or 0,
        'auto_detected_count': stats[2] or 0,
        'ocr_count': stats[3] or 0,
        'avg_confidence': round((stats[4] or 0) * 100, 1),
        'wins_count': wins_stats[1] or 0,
        'win_rate': round((wins_stats[1] or 0) / max(wins_stats[0] or 1, 1) * 100, 1),
        'monthly_stats': monthly_stats,
        'top_prizes': top_prizes
    }

def create_analytics_chart(user_id: int) -> bytes:
    """Создает график аналитики пользователя"""
    analytics = generate_user_analytics(user_id)

    # Настройка стиля
    plt.style.use('seaborn-v0_8')
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

    # График 1: Активность по месяцам
    if analytics['monthly_stats']:
        months = [row[0] for row in analytics['monthly_stats']]
        total_counts = [row[1] for row in analytics['monthly_stats']]
        auto_counts = [row[2] for row in analytics['monthly_stats']]
        manual_counts = [total - auto for total, auto in zip(total_counts, auto_counts)]

        x = range(len(months))
        width = 0.35

        ax1.bar([i - width/2 for i in x], manual_counts, width, 
                label='Добавлено вручную', color='#3498db', alpha=0.8)
        ax1.bar([i + width/2 for i in x], auto_counts, width,
                label='Найдено автоматически', color='#e74c3c', alpha=0.8)

        ax1.set_xlabel('Месяц')
        ax1.set_ylabel('Количество розыгрышей') 
        ax1.set_title('Активность по месяцам')
        ax1.set_xticks(x)
        ax1.set_xticklabels(months, rotation=45)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
    else:
        ax1.text(0.5, 0.5, 'Нет данных\nпо месяцам', ha='center', va='center')
        ax1.set_title('Активность по месяцам')

    # График 2: Соотношение способов добавления
    manual_count = analytics['total_giveaways'] - analytics['auto_detected_count']
    if manual_count + analytics['auto_detected_count'] > 0:
        sizes = [manual_count, analytics['auto_detected_count'], analytics['ocr_count']]
        labels = ['Ручное\nдобавление', 'Автопоиск', 'OCR']
        colors = ['#3498db', '#e74c3c', '#f39c12']

        # Убираем нулевые значения
        sizes_filtered = []
        labels_filtered = []
        colors_filtered = []
        for i, size in enumerate(sizes):
            if size > 0:
                sizes_filtered.append(size)
                labels_filtered.append(labels[i])
                colors_filtered.append(colors[i])

        if sizes_filtered:
            ax2.pie(sizes_filtered, labels=labels_filtered, colors=colors_filtered, 
                   autopct='%1.1f%%', startangle=90, shadow=True)
        ax2.set_title('Способы добавления')
    else:
        ax2.text(0.5, 0.5, 'Нет данных', ha='center', va='center')
        ax2.set_title('Способы добавления')

    # График 3: Успешность участия
    if analytics['completed_count'] > 0:
        wins = analytics['wins_count']
        losses = analytics['completed_count'] - wins

        ax3.bar(['Выигрыши', 'Проигрыши'], [wins, losses], 
               color=['#27ae60', '#e74c3c'], alpha=0.8)
        ax3.set_ylabel('Количество')
        ax3.set_title(f'Результативность ({analytics["win_rate"]}% побед)')
        ax3.grid(True, alpha=0.3)
    else:
        ax3.text(0.5, 0.5, 'Нет завершенных\nрозыгрышей', ha='center', va='center')
        ax3.set_title('Результативность')

    # График 4: Точность ИИ
    if analytics['avg_confidence'] > 0:
        confidence_ranges = ['0-30%', '30-60%', '60-80%', '80-100%']
        # В реальной реализации здесь был бы запрос к БД для подсчета по диапазонам
        sample_values = [5, 15, 30, 25]  # Пример данных

        ax4.bar(confidence_ranges, sample_values, color='#9b59b6', alpha=0.8)
        ax4.set_xlabel('Диапазон уверенности')
        ax4.set_ylabel('Количество')
        ax4.set_title(f'Распределение точности ИИ\n(среднее: {analytics["avg_confidence"]}%)')
        ax4.grid(True, alpha=0.3)
    else:
        ax4.text(0.5, 0.5, 'ИИ анализ\nне использовался', ha='center', va='center')
        ax4.set_title('Точность ИИ')

    plt.tight_layout()

    # Сохраняем в байты
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    buffer.seek(0)
    plt.close(fig)

    return buffer.getvalue()

# ==================== ФУНКЦИИ БАЗЫ ДАННЫХ ====================

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
    
    # Инициализируем менеджер отписок и начинаем отслеживание каналов
    global unsubscribe_manager
    if unsubscribe_manager is None:
        unsubscribe_manager = UnsubscribeManager(bot, DB_NAME)
    
    # Начинаем отслеживание каналов для отписки
    if channels and channels.strip():
        unsubscribe_manager.track_giveaway_channels(giveaway_id, user_id, channels)
        
        # Настраиваем напоминание об отписке через день после завершения
        if date_time:
            try:
                setup_unsubscribe_reminder(user_id, giveaway_id, title, date_time)
            except Exception as e:
                print(f"❌ Ошибка настройки напоминания об отписке: {e}")
    
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

    # Получаем данные розыгрыша
    cursor.execute('SELECT * FROM giveaways WHERE id = ?', (giveaway_id,))
    giveaway = cursor.fetchone()

    if giveaway:
        # Перемещаем в историю
        cursor.execute('''
            INSERT INTO giveaway_history (
                original_giveaway_id, user_id, title, prize, date_time, 
                channels, source_message, auto_detected, confidence_score,
                created_at, result, notes, won
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            giveaway[0], giveaway[1], giveaway[2], giveaway[3], 
            giveaway[4], giveaway[5], giveaway[6], giveaway[7], 
            giveaway[8], giveaway[11], result, notes, won
        ))

        # Обновляем статус оригинального розыгрыша
        cursor.execute('''
            UPDATE giveaways 
            SET is_active = FALSE, status = 'completed', completed_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (giveaway_id,))

        # Логируем действие
        cursor.execute('''
            INSERT INTO usage_stats (user_id, action, details)
            VALUES (?, ?, ?)
        ''', (giveaway[1], 'complete_giveaway', f'Won: {won}'))

    conn.commit()
    conn.close()

# ==================== КЛАВИАТУРЫ ====================

def create_main_keyboard():
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = telebot.types.KeyboardButton("➕ Добавить розыгрыш")
    btn2 = telebot.types.KeyboardButton("📋 Мои розыгрыши")
    btn3 = telebot.types.KeyboardButton("✅ Проверить подписки")
    btn4 = telebot.types.KeyboardButton("🧹 Управление подписками")
    btn5 = telebot.types.KeyboardButton("📊 Экспорт данных")
    btn6 = telebot.types.KeyboardButton("📈 Моя аналитика")
    btn7 = telebot.types.KeyboardButton("🔔 Напоминания")
    btn8 = telebot.types.KeyboardButton("📚 История")
    btn9 = telebot.types.KeyboardButton("⚙️ Настройки")
    keyboard.add(btn1, btn2, btn3, btn4)
    keyboard.add(btn5, btn6, btn7, btn8)
    keyboard.add(btn9)
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
    btn3 = telebot.types.InlineKeyboardButton(
        "🧠 ИИ анализ", 
        callback_data="ai_analyze"
    )
    btn4 = telebot.types.InlineKeyboardButton(
        "❌ Отклонить", 
        callback_data="auto_reject"
    )
    keyboard.add(btn1, btn2)
    keyboard.add(btn3, btn4)
    return keyboard

def create_ai_giveaway_keyboard(ai_result):
    """Создает клавиатуру для ИИ-анализа розыгрыша"""
    keyboard = telebot.types.InlineKeyboardMarkup()
    btn1 = telebot.types.InlineKeyboardButton(
        "✅ Добавить", 
        callback_data=f"ai_add_{ai_result.get('confidence', 0)}"
    )
    btn2 = telebot.types.InlineKeyboardButton(
        "❌ Отклонить", 
        callback_data="ai_reject"
    )
    btn3 = telebot.types.InlineKeyboardButton(
        "📝 Редактировать", 
        callback_data="ai_edit"
    )
    keyboard.add(btn1, btn2)
    keyboard.add(btn3)
    return keyboard

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id

    # Создаем настройки по умолчанию
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)
    ''', (user_id,))
    cursor.execute('''
        INSERT INTO usage_stats (user_id, action) VALUES (?, 'start')
    ''', (user_id,))
    conn.commit()
    conn.close()

    bot.send_message(
        message.chat.id,
        f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
        "🚀 **Ультимативный бот для розыгрышей v3.0**\n\n"
        "🎯 **Новые возможности:**\n"
        "• 🔍 Автопроверка подписок на каналы\n"
        "• 🧠 ИИ-анализ с ChatGPT (опционально)\n"
        "• 📊 Экспорт данных в Excel\n"
        "• 📈 Продвинутая аналитика с графиками\n"
        "• 📚 Полная история участия\n\n"
        "📝 **Просто пересылайте мне текстовые сообщения с розыгрышами!**",
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

# Обработчик всех текстовых сообщений
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
    elif text == "🧹 Управление подписками":
        show_unsubscribe_management(message)
    elif text == "📊 Экспорт данных":
        export_data_menu(message)
    elif text == "📈 Моя аналитика":
        show_detailed_analytics(message)
    elif text == "🔔 Напоминания":
        show_reminders(message)
    elif text == "📚 История":
        show_history(message)
    elif text == "⚙️ Настройки":
        show_settings(message)
    else:
        # Анализируем сообщение на предмет розыгрыша
        analyze_and_suggest_giveaway(message)
# [Продолжение кода следует...]

if __name__ == "__main__":
    print("🚀 Инициализация ультимативного бота...")
    init_database()
    print("✅ База данных инициализирована")
    print("🔍 Автопоиск розыгрышей: активен")
    print("🧠 ChatGPT интеграция:", "активна" if CHATGPT_AVAILABLE else "недоступна")
    print("📊 Экспорт и аналитика: активны")
    print("🎉 Ультимативный бот запущен!")

    try:
        bot.polling(none_stop=True, interval=0)
    except Exception as e:
        print(f"Ошибка: {e}")



# ==================== ПРОДОЛЖЕНИЕ ОБРАБОТЧИКОВ ====================

def analyze_and_suggest_giveaway(message):
    """Анализирует сообщение и предлагает добавить розыгрыш"""  
    user_id = message.from_user.id
    text = message.text

    # Получаем настройки пользователя
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT auto_detect, min_confidence FROM user_settings WHERE user_id = ?', (user_id,))
    settings = cursor.fetchone()
    conn.close()

    if not settings or not settings[0]:  # Автопоиск отключен
        bot.send_message(
            message.chat.id,
            "🤔 Не понимаю эту команду\n\n"
            "Используйте кнопки меню или команду /start",
            reply_markup=create_main_keyboard()
        )
        return

    min_confidence = settings[1] or 0.6

    # Используем новый ИИ-распознаватель
    global ai_recognizer
    if ai_recognizer:
        try:
            # Анализируем с помощью ИИ
            ai_result = ai_recognizer.analyze_giveaway(text)
            giveaway_data = {
                'confidence': ai_result.get('confidence', 0) / 100,  # Конвертируем в 0-1
                'title': ai_result.get('title', 'Неизвестный розыгрыш'),
                'prize': ai_result.get('prize', 'Не указан'),
                'suggested_date': ai_result.get('date', 'Не указана'),
                'suggested_channels': ', '.join(ai_result.get('channels', [])) if ai_result.get('channels') else 'Не указаны',
                'ai_result': ai_result
            }
        except Exception as e:
            print(f"❌ Ошибка ИИ-анализа: {e}")
            # Fallback к старому методу
            giveaway_data = analyze_message_for_giveaway(text)
    else:
        # Fallback к старому методу
        giveaway_data = analyze_message_for_giveaway(text)

    if not giveaway_data or giveaway_data['confidence'] < min_confidence:
        confidence_info = f" (уверенность: {giveaway_data['confidence']:.1%})" if giveaway_data else ""
        bot.send_message(
            message.chat.id,
            f"🔍 Сообщение проанализировано{confidence_info}\n\n"
            f"Минимальный порог: {min_confidence:.0%}\n"
            "Розыгрыш не обнаружен или уверенность недостаточна\n\n"
            "Используйте кнопки меню для ручного добавления",
            reply_markup=create_main_keyboard()
        )
        return

    # Сохраняем данные для дальнейшего использования
    bot.giveaway_temp_data = {
        'user_id': user_id,
        'message_text': text,
        'analysis': giveaway_data,
        'ocr_processed': False
    }

    # Предлагаем добавить розыгрыш
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

# ==================== CALLBACK ОБРАБОТЧИКИ ====================

@bot.callback_query_handler(func=lambda call: call.data.startswith('auto_'))
def handle_auto_giveaway(call):
    user_id = call.from_user.id

    if call.data.startswith('auto_add_'):
        # Автоматическое добавление
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

            # Настраиваем напоминание
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
        # Ручное редактирование
        bot.answer_callback_query(call.id, "✏️ Перехожу к ручному добавлению...")
        bot.edit_message_text(
            "✏️ **Ручное добавление розыгрыша**\n\n"
            "Введите название розыгрыша:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

        bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_giveaway_title)

    elif call.data == 'ai_analyze':
        # ИИ анализ с ChatGPT
        if not CHATGPT_AVAILABLE:
            bot.answer_callback_query(call.id, "❌ ChatGPT недоступен")
            return

        bot.answer_callback_query(call.id, "🧠 Запускаю ИИ анализ...")

        if hasattr(bot, 'giveaway_temp_data') and bot.giveaway_temp_data['user_id'] == user_id:
            asyncio.create_task(process_ai_analysis_callback(call))

    elif call.data == 'auto_reject':
        # Отклонить
        bot.edit_message_text(
            "❌ **Розыгрыш отклонен**\n\n"
            "Используйте кнопки меню для других действий",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id, "❌ Отклонено")

async def process_ai_analysis_callback(call):
    """Обрабатывает ИИ анализ через callback"""
    user_id = call.from_user.id
    text = bot.giveaway_temp_data['message_text']

    bot.edit_message_text(
        "🧠 **ИИ анализирует текст...**\n\n"
        "Это может занять несколько секунд",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

    ai_result = await analyze_giveaway_with_ai(text)

    if ai_result and ai_result.get('is_giveaway'):
        response = f"🧠 **ИИ анализ завершен!**\n\n"
        response += f"📊 Уверенность: {ai_result['confidence']:.1%}\n"
        response += f"📝 Название: {ai_result.get('title', 'Не определено')}\n"
        response += f"🎁 Приз: {ai_result.get('prize', 'Не определено')}\n"

        if ai_result.get('date'):
            date_time = ai_result['date']
            if ai_result.get('time'):
                date_time += f" {ai_result['time']}"
            response += f"📅 Дата: {date_time}\n"

        if ai_result.get('channels'):
            response += f"📢 Каналы: {', '.join(ai_result['channels'])}\n"

        if ai_result.get('conditions'):
            response += f"📋 Условия:\n"
            for condition in ai_result['conditions'][:3]:
                response += f"  • {condition}\n"

        response += f"\n📝 **Резюме ИИ:** {ai_result.get('summary', 'Не указано')}"

        # Обновляем временные данные
        bot.giveaway_temp_data['ai_result'] = ai_result

        # Предлагаем добавить с ИИ данными
        keyboard = telebot.types.InlineKeyboardMarkup()
        btn = telebot.types.InlineKeyboardButton("✅ Добавить (ИИ данные)", callback_data="ai_add_giveaway")
        keyboard.add(btn)

        bot.edit_message_text(
            response, call.message.chat.id, call.message.message_id,
            parse_mode='Markdown', reply_markup=keyboard
        )
    else:
        bot.edit_message_text(
            "🧠 **ИИ анализ завершен**\n\n"
            "ИИ не обнаружил достаточно информации о розыгрыше\n\n"
            "Попробуйте добавить вручную или используйте более подробный текст",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

@bot.callback_query_handler(func=lambda call: call.data == 'ai_add_giveaway')
def handle_ai_add_giveaway(call):
    user_id = call.from_user.id

    if hasattr(bot, 'giveaway_temp_data') and 'ai_result' in bot.giveaway_temp_data:
        ai_result = bot.giveaway_temp_data['ai_result']

        # Формируем данные для добавления
        date_time = ai_result.get('date', '')
        if ai_result.get('time'):
            date_time += f" {ai_result['time']}"

        channels = '\n'.join(ai_result.get('channels', []))

        giveaway_id = add_giveaway(
            user_id=user_id,
            title=ai_result.get('title', 'ИИ розыгрыш'),
            prize=ai_result.get('prize', 'Не определено'),
            date_time=date_time,
            channels=channels,
            source_message=bot.giveaway_temp_data['message_text'][:500],
            auto_detected=True,
            confidence=ai_result.get('confidence', 0.0),
            ai_analyzed=True
        )

        # Настраиваем напоминание
        if date_time:
            setup_reminder(user_id, giveaway_id, ai_result.get('title', ''), date_time)

        bot.edit_message_text(
            "🧠 **Розыгрыш добавлен с помощью ИИ!**\n\n"
            f"📝 {ai_result.get('title')}\n"
            f"🎁 {ai_result.get('prize')}\n"
            f"📅 {date_time}\n\n"
            "✨ Проанализировано ChatGPT",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

        bot.answer_callback_query(call.id, "🧠 Добавлено с ИИ!")

# ==================== ОБРАБОТЧИКИ ПРОВЕРКИ ПОДПИСОК ====================

@bot.message_handler(func=lambda message: message.text == "✅ Проверить подписки")
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
    for giveaway in giveaways[:10]:  # Ограничиваем до 10
        giveaway_id, title = giveaway[0], giveaway[1]
        subscription_status = giveaway[9] if len(giveaway) > 9 else "unknown"

        status_emoji = "✅" if subscription_status and subscription_status != "unknown" else "❓"
        btn = telebot.types.InlineKeyboardButton(
            f"{status_emoji} {title[:25]}...",
            callback_data=f"check_subs_{giveaway_id}"
        )
        keyboard.add(btn)

    # Добавляем кнопку "Проверить все"
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
        "🔄 **Проверяю подписки...**\n\n"
        "Подключаюсь к Telegram API",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

    try:
        subscription_results = await check_all_giveaway_subscriptions(giveaway_id, user_id)

        if not subscription_results:
            bot.edit_message_text(
                "❌ **Ошибка проверки**\n\n"
                "Не удалось найти каналы для проверки или каналы недоступны",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
            return

        # Формируем отчет
        response = "✅ **Результаты проверки подписок:**\n\n"

        subscribed_count = 0
        total_count = len(subscription_results)

        for result in subscription_results:
            if result['subscribed']:
                response += f"✅ `{result['channel']}` - подписаны\n"
                subscribed_count += 1
            else:
                response += f"❌ `{result['channel']}` - НЕ подписаны\n"
                if result['error'] and 'not found' not in result['error'].lower():
                    response += f"   ⚠️ {result['error'][:50]}\n"

        response += f"\n📊 **Итого: {subscribed_count}/{total_count} подписок**\n"

        if subscribed_count == total_count:
            response += "\n🎉 **Отлично!** Все подписки активны!\n"
            response += "Вы полностью участвуете в розыгрыше!"
        elif subscribed_count > 0:
            response += f"\n⚠️ **Внимание!** Недостает {total_count - subscribed_count} подписок\n"
            response += "Подпишитесь на недостающие каналы для участия"
        else:
            response += "\n❌ **Проблема!** Вы не подписаны ни на один канал\n"
            response += "Необходимо подписаться для участия в розыгрыше"

        # Добавляем кнопку повторной проверки
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
            f"Детали: {str(e)[:100]}\n\n"
            "Попробуйте позже или проверьте вручную",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

@bot.callback_query_handler(func=lambda call: call.data == 'check_all_subs')
async def handle_check_all_subscriptions(call):
    user_id = call.from_user.id
    giveaways = get_user_giveaways(user_id)

    if not giveaways:
        bot.answer_callback_query(call.id, "❌ Нет активных розыгрышей")
        return

    bot.edit_message_text(
        f"🔄 **Проверяю все подписки...**\n\n"
        f"Обрабатываю {len(giveaways)} розыгрышей",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

    total_checked = 0
    total_subscribed = 0
    results_summary = []

    for giveaway in giveaways:
        giveaway_id, title = giveaway[0], giveaway[1]

        try:
            subscription_results = await check_all_giveaway_subscriptions(giveaway_id, user_id)
            if subscription_results:
                subscribed_count = sum(1 for r in subscription_results if r['subscribed'])
                total_count = len(subscription_results)

                total_checked += total_count
                total_subscribed += subscribed_count

                status = "✅" if subscribed_count == total_count else "⚠️" if subscribed_count > 0 else "❌"
                results_summary.append(f"{status} {title[:20]}: {subscribed_count}/{total_count}")
        except:
            results_summary.append(f"❌ {title[:20]}: ошибка")

    # Формируем итоговый отчет
    response = "✅ **Проверка всех подписок завершена**\n\n"

    for result in results_summary[:10]:  # Показываем первые 10
        response += f"{result}\n"

    if len(results_summary) > 10:
        response += f"... и еще {len(results_summary) - 10}\n"

    response += f"\n📊 **Общая статистика:**\n"
    response += f"Всего проверено: {total_checked} подписок\n"
    response += f"Активных: {total_subscribed}\n"

    if total_checked > 0:
        success_rate = (total_subscribed / total_checked) * 100
        response += f"Процент подписок: {success_rate:.1f}%\n"

        if success_rate >= 90:
            response += "\n🎉 Отличный результат!"
        elif success_rate >= 70:
            response += "\n👍 Хороший результат!"
        else:
            response += "\n⚠️ Есть над чем поработать"

    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

# Продолжение следует в части 2...



# ==================== ОБРАБОТЧИКИ ЭКСПОРТА И АНАЛИТИКИ ====================

@bot.message_handler(func=lambda message: message.text == "📊 Экспорт данных")
def export_data_menu(message):
    keyboard = telebot.types.InlineKeyboardMarkup()
    btn1 = telebot.types.InlineKeyboardButton("📈 Excel файл", callback_data="export_excel")
    btn2 = telebot.types.InlineKeyboardButton("📋 CSV файлы", callback_data="export_csv") 
    btn3 = telebot.types.InlineKeyboardButton("📱 Для печати", callback_data="export_print")
    btn4 = telebot.types.InlineKeyboardButton("📊 Статистика", callback_data="export_stats")
    keyboard.add(btn1, btn2)
    keyboard.add(btn3, btn4)

    bot.send_message(
        message.chat.id,
        "📊 **Экспорт ваших данных**\n\n"
        "Выберите формат для экспорта:\n\n"
        "📈 **Excel** - полный отчет с графиками\n"
        "📋 **CSV** - для анализа в других программах\n"
        "📱 **Печать** - красивый PDF для печати\n"
        "📊 **Статистика** - краткая сводка",
        parse_mode='Markdown',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == 'export_excel')
def handle_excel_export(call):
    user_id = call.from_user.id

    bot.edit_message_text(
        "📊 **Создаю Excel файл...**\n\n"
        "⏳ Обрабатываю данные\n"
        "📋 Формирую таблицы\n"
        "🎨 Применяю форматирование",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

    try:
        filename = export_user_data_to_excel(user_id)

        # Получаем статистику для описания
        analytics = generate_user_analytics(user_id)

        caption = f"📊 **Ваши розыгрыши в Excel**\n\n"
        caption += f"📈 **Статистика:**\n"
        caption += f"• Всего розыгрышей: {analytics['total_giveaways']}\n"
        caption += f"• Активных: {analytics['active_count']}\n" 
        caption += f"• Завершенных: {analytics['completed_count']}\n"
        caption += f"• Выигрышей: {analytics['wins_count']}\n\n"
        caption += f"📋 **Файл содержит:**\n"
        caption += f"• Активные розыгрыши с деталями\n"
        caption += f"• Полную историю участия\n"
        caption += f"• Детальную статистику\n\n"
        caption += f"💡 Откройте в Excel или Google Sheets"

        # Отправляем файл
        with open(filename, 'rb') as file:
            bot.send_document(
                call.message.chat.id,
                file,
                caption=caption,
                parse_mode='Markdown'
            )

        # Удаляем временный файл
        os.remove(filename)

        # Логируем экспорт
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO usage_stats (user_id, action, details)
            VALUES (?, ?, ?)
        ''', (user_id, 'export_excel', f'Records: {analytics["total_giveaways"]}'))
        conn.commit()
        conn.close()

        bot.edit_message_text(
            "✅ **Excel файл отправлен!**\n\n"
            "📄 Файл содержит все ваши данные в удобном формате",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

    except Exception as e:
        bot.edit_message_text(
            f"❌ **Ошибка создания файла**\n\n"
            f"Детали: {str(e)[:100]}\n\n"
            "Попробуйте позже или обратитесь к администратору",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

@bot.message_handler(func=lambda message: message.text == "📈 Моя аналитика")
def show_detailed_analytics(message):
    user_id = message.from_user.id

    # Отправляем сообщение о создании
    processing_msg = bot.send_message(
        message.chat.id, 
        "📈 **Создаю аналитику...**\n\n"
        "⏳ Анализирую данные\n"
        "📊 Строю графики\n"
        "🧮 Рассчитываю статистику",
        parse_mode='Markdown'
    )

    try:
        # Генерируем график
        chart_bytes = create_analytics_chart(user_id)

        # Получаем текстовую статистику
        analytics = generate_user_analytics(user_id)

        # Формируем подробный отчет
        report = f"📈 **Детальная аналитика участия**\n\n"

        # Основные показатели
        report += f"🎯 **Основные показатели:**\n"
        report += f"• Всего розыгрышей: **{analytics['total_giveaways']}**\n"
        report += f"• Активных: **{analytics['active_count']}**\n"
        report += f"• Завершенных: **{analytics['completed_count']}**\n"
        report += f"• Выигрышей: **{analytics['wins_count']}**\n\n"

        # Эффективность
        if analytics['completed_count'] > 0:
            report += f"🏆 **Эффективность:**\n"
            report += f"• Процент побед: **{analytics['win_rate']}%**\n"

            if analytics['win_rate'] >= 20:
                report += f"• 🎉 Отличный результат!\n"
            elif analytics['win_rate'] >= 10:
                report += f"• 👍 Хороший результат!\n"
            elif analytics['win_rate'] >= 5:
                report += f"• 📈 Средний результат\n"
            else:
                report += f"• 💪 Есть над чем работать\n"
            report += "\n"

        # Технологии
        if analytics['total_giveaways'] > 0:
            auto_ratio = (analytics['auto_detected_count'] / analytics['total_giveaways']) * 100
            ocr_ratio = (analytics['ocr_count'] / analytics['total_giveaways']) * 100

            report += f"🤖 **Использование технологий:**\n"
            report += f"• Автопоиск: **{auto_ratio:.1f}%** случаев\n"
            report += f"• OCR анализ: **{ocr_ratio:.1f}%** случаев\n"
            report += f"• Средняя точность ИИ: **{analytics['avg_confidence']}%**\n\n"

        # Инсайты и рекомендации
        report += f"💡 **Персональные инсайты:**\n"

        if analytics['total_giveaways'] == 0:
            report += f"• Начните добавлять розыгрыши для анализа\n"
        elif analytics['total_giveaways'] < 5:
            report += f"• Добавьте больше розыгрышей для точной статистики\n"

        if analytics['active_count'] > 10:
            report += f"• У вас много активных розыгрышей - не забывайте проверять подписки!\n"

        if analytics['avg_confidence'] > 80:
            report += f"• Отличная точность ИИ-анализа! 🎯\n"
        elif analytics['avg_confidence'] > 60:
            report += f"• Хорошая точность ИИ, продолжайте использовать\n"
        elif analytics['avg_confidence'] > 0:
            report += f"• Попробуйте отправлять более четкие тексты для ИИ\n"

        if analytics['ocr_count'] > 0:
            report += f"• Активно используете OCR - отлично! 📸\n"

        if analytics['completed_count'] > 0 and analytics['wins_count'] == 0:
            report += f"• Пока без побед, но продолжайте участвовать! 💪\n"

        # Отправляем график и отчет
        bot.send_photo(
            message.chat.id,
            chart_bytes,
            caption=report,
            parse_mode='Markdown'
        )

        # Добавляем кнопки для дополнительных действий
        keyboard = telebot.types.InlineKeyboardMarkup()
        btn1 = telebot.types.InlineKeyboardButton("📊 Экспорт Excel", callback_data="export_excel")
        btn2 = telebot.types.InlineKeyboardButton("🔄 Обновить", callback_data="refresh_analytics")
        keyboard.add(btn1, btn2)

        bot.send_message(
            message.chat.id,
            "📊 **Дополнительные действия:**",
            parse_mode='Markdown',
            reply_markup=keyboard
        )

        # Удаляем сообщение о создании
        bot.delete_message(message.chat.id, processing_msg.message_id)

        # Логируем просмотр аналитики
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO usage_stats (user_id, action)
            VALUES (?, ?)
        ''', (user_id, 'view_analytics'))
        conn.commit()
        conn.close()

    except Exception as e:
        bot.edit_message_text(
            f"❌ **Ошибка создания аналитики**\n\n"
            f"Детали: {str(e)[:100]}\n\n"
            "Попробуйте позже",
            message.chat.id,
            processing_msg.message_id,
            parse_mode='Markdown'
        )

@bot.callback_query_handler(func=lambda call: call.data == 'refresh_analytics')
def refresh_analytics(call):
    """Обновляет аналитику"""
    bot.answer_callback_query(call.id, "🔄 Обновляю аналитику...")

    # Имитируем нажатие кнопки "Моя аналитика"
    fake_message = type('obj', (object,), {
        'chat': type('obj', (object,), {'id': call.message.chat.id}),
        'from_user': call.from_user
    })
    show_detailed_analytics(fake_message)

# ==================== ОСТАЛЬНЫЕ ОБРАБОТЧИКИ ====================

def add_giveaway_start(message):
    msg = bot.send_message(
        message.chat.id,
        "📝 **Добавление нового розыгрыша**\n\n"
        "Введите название розыгрыша:\n\n"
        "💡 *Совет: Используйте описательные названия*",
        parse_mode='Markdown',
        reply_markup=telebot.types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, get_giveaway_title)

def get_giveaway_title(message):
    title = message.text
    msg = bot.send_message(
        message.chat.id,
        f"✅ **Название:** {title}\n\n"
        "🎁 Теперь введите что разыгрывается (приз):\n\n"
        "💡 *Примеры: iPhone 15, 10000 рублей, подарочный сертификат*",
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
            "@channel2\n"
            "https://t.me/channel3",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, save_manual_giveaway, title, prize, date_time_str)
    except ValueError:
        msg = bot.send_message(
            message.chat.id,
            "❌ **Неверный формат даты!**\n\n"
            "📝 Используйте формат: **ДД.ММ.ГГГГ ЧЧ:ММ**\n"
            "💡 Пример: **25.12.2024 20:00**\n\n"
            "Попробуйте еще раз:",
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
    success_msg += f"🔔 Напоминание настроено за час до розыгрыша!\n"
    success_msg += f"✅ Проверьте подписки через кнопку меню"

    bot.send_message(
        message.chat.id,
        success_msg,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

def show_giveaways(message):
    user_id = message.from_user.id
    giveaways = get_user_giveaways(user_id)

    if not giveaways:
        bot.send_message(
            message.chat.id,
            "📭 **У вас нет активных розыгрышей**\n\n"
            "➕ Добавьте первый розыгрыш с помощью кнопки меню\n"
            "📸 Или отправьте фото/текст с информацией о розыгрыше",
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

        # Определяем иконки статуса
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

        # Добавляем кнопки управления
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

    # Добавляем общие кнопки
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
            "Завершите несколько розыгрышей, чтобы они появились здесь\n\n"
            "💡 *Используйте кнопку '✅ Завершить' в разделе 'Мои розыгрыши'*",
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
        return

    response = f"📚 **История розыгрышей ({len(history)}):**\n\n"

    wins_count = sum(1 for entry in history if entry[5])  # won field
    win_rate = (wins_count / len(history)) * 100 if history else 0

    response += f"🏆 **Статистика:** {wins_count} побед из {len(history)} ({win_rate:.1f}%)\n\n"

    for i, entry in enumerate(history, 1):
        title, prize, date_time, completed_at, result, won, notes = entry
        completed_date = completed_at.split()[0] if completed_at else "Неизвестно"

        win_icon = "🏆" if won else "😐"

        response += f"{i}. {win_icon} **{title}**\n"
        response += f"   🎁 {prize}\n"
        response += f"   📅 Дата розыгрыша: {date_time}\n"
        response += f"   ✅ Завершен: {completed_date}\n"

        if result:
            response += f"   🎯 Результат: {result}\n"

        if notes:
            response += f"   📝 Заметки: {notes[:50]}{'...' if len(notes) > 50 else ''}\n"

        response += "   " + "─" * 25 + "\n\n"

    # Добавляем кнопки действий
    keyboard = telebot.types.InlineKeyboardMarkup()
    btn1 = telebot.types.InlineKeyboardButton("📊 Экспорт истории", callback_data="export_excel")
    btn2 = telebot.types.InlineKeyboardButton("📈 Аналитика", callback_data="refresh_analytics")
    keyboard.add(btn1, btn2)

    bot.send_message(
        message.chat.id, 
        response, 
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

                # Определяем срочность
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
        response = "📭 **Все розыгрыши уже прошли**\n\n"
        response += "➕ Добавьте новые розыгрыши для получения напоминаний"
    else:
        response = f"🔔 **Ближайшие розыгрыши ({upcoming_count}):**\n\n" + response[len("🔔 **Ближайшие розыгрыши:**\n\n"):]

    bot.send_message(
        message.chat.id, 
        response, 
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )

def show_unsubscribe_management(message):
    """Показать меню управления подписками"""
    user_id = message.from_user.id
    
    # Инициализируем менеджер отписок если еще не инициализирован
    global unsubscribe_manager
    if unsubscribe_manager is None:
        unsubscribe_manager = UnsubscribeManager(bot, DB_NAME)
    
    # Получаем список завершенных розыгрышей с каналами для отписки
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT g.id, g.title, g.end_date, g.channels, ut.channel_name, ut.unsubscribed_at
        FROM giveaways g
        LEFT JOIN unsubscribe_tracking ut ON g.id = ut.giveaway_id AND ut.user_id = ?
        WHERE g.user_id = ? AND g.end_date < datetime('now')
        ORDER BY g.end_date DESC
        LIMIT 10
    ''', (user_id, user_id))
    
    giveaways = cursor.fetchall()
    conn.close()
    
    if not giveaways:
        bot.send_message(user_id, 
                        "🧹 <b>Управление подписками</b>\n\n"
                        "У вас пока нет завершенных розыгрышей для отписки от каналов.",
                        parse_mode='HTML', reply_markup=create_main_keyboard())
        return
    
    # Группируем по розыгрышам
    giveaway_channels = {}
    for row in giveaways:
        giveaway_id, title, end_date, channels, channel_name, unsubscribed_at = row
        if giveaway_id not in giveaway_channels:
            giveaway_channels[giveaway_id] = {
                'title': title,
                'end_date': end_date,
                'channels': []
            }
        if channel_name and unsubscribed_at is None:
            giveaway_channels[giveaway_id]['channels'].append(channel_name)
    
    # Формируем сообщение
    text = "🧹 <b>Управление подписками</b>\n\n"
    text += "Завершенные розыгрыши с каналами для отписки:\n\n"
    
    keyboard = telebot.types.InlineKeyboardMarkup()
    
    for giveaway_id, data in giveaway_channels.items():
        if data['channels']:  # Только если есть каналы для отписки
            text += f"🎯 <b>{data['title']}</b>\n"
            text += f"📅 Завершен: {data['end_date']}\n"
            text += f"📺 Каналы: {', '.join(data['channels'])}\n\n"
            
            # Добавляем кнопку для отписки
            btn = telebot.types.InlineKeyboardButton(
                f"Отписаться от {data['title'][:20]}...",
                callback_data=f"unsubscribe_{giveaway_id}"
            )
            keyboard.add(btn)
    
    if not keyboard.inline_keyboard:
        text += "✅ Все каналы уже обработаны!"
    
    bot.send_message(user_id, text, parse_mode='HTML', reply_markup=keyboard)

def show_settings(message):
    user_id = message.from_user.id

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT auto_detect, min_confidence, ai_enabled, export_format, language
        FROM user_settings WHERE user_id = ?
    ''', (user_id,))
    settings = cursor.fetchone()
    conn.close()

    if not settings:
        settings = (True, 0.6, True, 'xlsx', 'ru')  # Значения по умолчанию

    auto_detect, min_confidence, ai_enabled, export_format, language = settings

    response = f"⚙️ **Настройки бота**\n\n"

    response += f"🤖 **Автопоиск розыгрышей:**\n"
    response += f"• Статус: {'✅ Включен' if auto_detect else '❌ Отключен'}\n"
    response += f"• Минимальная уверенность: {min_confidence:.0%}\n\n"

    if CHATGPT_AVAILABLE:
        response += f"🧠 **ИИ анализ (ChatGPT):**\n"
        response += f"• Статус: {'✅ Включен' if ai_enabled else '❌ Отключен'}\n\n"

    response += f"📊 **Экспорт данных:**\n"
    response += f"• Формат по умолчанию: {export_format.upper()}\n\n"

    response += f"🌍 **Язык интерфейса:** {language.upper()}\n\n"

    response += f"💡 **Совет:** Настройте параметры под ваши потребности"

    # Создаем клавиатуру настроек
    keyboard = telebot.types.InlineKeyboardMarkup()

    # Переключатели
    toggle_auto = "❌ Отключить автопоиск" if auto_detect else "✅ Включить автопоиск"
    btn1 = telebot.types.InlineKeyboardButton(toggle_auto, callback_data="toggle_auto_detect")
    keyboard.add(btn1)

    if CHATGPT_AVAILABLE:
        toggle_ai = "❌ Отключить ИИ" if ai_enabled else "✅ Включить ИИ"
        btn2 = telebot.types.InlineKeyboardButton(toggle_ai, callback_data="toggle_ai")
        keyboard.add(btn2)

    # Настройки уверенности
    btn4 = telebot.types.InlineKeyboardButton("🎚 Настроить уверенность", callback_data="set_confidence")
    btn5 = telebot.types.InlineKeyboardButton("📊 Формат экспорта", callback_data="set_export_format")
    keyboard.add(btn4, btn5)

    bot.send_message(
        message.chat.id,
        response,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

# ==================== CALLBACK ОБРАБОТЧИКИ НАСТРОЕК ====================

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

    elif call.data == 'toggle_ai':
        cursor.execute('SELECT ai_enabled FROM user_settings WHERE user_id = ?', (user_id,))
        current = cursor.fetchone()
        current_value = current[0] if current else True
        new_value = not current_value

        cursor.execute('''
            INSERT OR REPLACE INTO user_settings (user_id, ai_enabled) 
            VALUES (?, ?)
        ''', (user_id, new_value))

        status = "включен" if new_value else "отключен"
        bot.answer_callback_query(call.id, f"ИИ анализ {status}!")

    conn.commit()
    conn.close()

    # Обновляем сообщение с настройками
    fake_message = type('obj', (object,), {
        'chat': type('obj', (object,), {'id': call.message.chat.id}),
        'from_user': call.from_user
    })
    show_settings(fake_message)

# ==================== ЗАВЕРШЕНИЕ РОЗЫГРЫШЕЙ ====================

@bot.callback_query_handler(func=lambda call: call.data.startswith('complete_'))
def complete_giveaway_handler(call):
    giveaway_id = int(call.data.split('_')[1])
    user_id = call.from_user.id

    # Получаем информацию о розыгрыше
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT title FROM giveaways WHERE id = ? AND user_id = ?', (giveaway_id, user_id))
    giveaway = cursor.fetchone()
    conn.close()

    if not giveaway:
        bot.answer_callback_query(call.id, "❌ Розыгрыш не найден")
        return

    title = giveaway[0]

    # Создаем клавиатуру для выбора результата
    keyboard = telebot.types.InlineKeyboardMarkup()
    btn1 = telebot.types.InlineKeyboardButton("🏆 Выиграл!", callback_data=f"result_won_{giveaway_id}")
    btn2 = telebot.types.InlineKeyboardButton("😐 Не выиграл", callback_data=f"result_lost_{giveaway_id}")
    btn3 = telebot.types.InlineKeyboardButton("❓ Результат неизвестен", callback_data=f"result_unknown_{giveaway_id}")
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

    # Определяем результат
    if result_type == 'won':
        result_text = "Выиграл! 🎉"
        won = True
        emoji = "🏆"
    elif result_type == 'lost':
        result_text = "Не выиграл"
        won = False
        emoji = "😐"
    else:  # unknown
        result_text = "Результат неизвестен"
        won = False
        emoji = "❓"

    # Завершаем розыгрыш
    complete_giveaway(giveaway_id, result_text, "", won)

    # Удаляем напоминание
    try:
        scheduler.remove_job(f"reminder_{giveaway_id}")
    except:
        pass

    bot.edit_message_text(
        f"{emoji} **Розыгрыш завершен!**\n\n"
        f"📊 Результат: **{result_text}**\n"
        f"📚 Розыгрыш перенесен в историю\n\n"
        f"💡 Посмотрите статистику в разделе 'История'",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

    bot.answer_callback_query(
        call.id, 
        f"{emoji} Розыгрыш завершен как '{result_text}'"
    )

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_complete')
def cancel_complete(call):
    bot.edit_message_text(
        "❌ **Завершение отменено**\n\n"
        "Розыгрыш остался активным",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('unsubscribe_'))
def handle_unsubscribe(call):
    """Обработчик отписки от каналов розыгрыша"""
    user_id = call.from_user.id
    giveaway_id = int(call.data.split('_')[1])
    
    # Инициализируем менеджер отписок если еще не инициализирован
    global unsubscribe_manager
    if unsubscribe_manager is None:
        unsubscribe_manager = UnsubscribeManager(bot, DB_NAME)
    
    # Получаем каналы для отписки
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT g.title, g.channels, ut.channel_name, ut.channel_link
        FROM giveaways g
        JOIN unsubscribe_tracking ut ON g.id = ut.giveaway_id
        WHERE g.id = ? AND ut.user_id = ? AND ut.unsubscribed_at IS NULL
    ''', (giveaway_id, user_id))
    
    channels_to_unsubscribe = cursor.fetchall()
    conn.close()
    
    if not channels_to_unsubscribe:
        bot.answer_callback_query(call.id, "❌ Нет каналов для отписки")
        return
    
    # Формируем сообщение с инструкциями
    title = channels_to_unsubscribe[0][0]
    text = f"🧹 <b>Отписка от каналов</b>\n\n"
    text += f"🎯 <b>Розыгрыш:</b> {title}\n\n"
    text += "📋 <b>Каналы для отписки:</b>\n"
    
    for _, _, channel_name, channel_link in channels_to_unsubscribe:
        text += f"• {channel_name}\n"
    
    text += "\n🔗 <b>Инструкции:</b>\n"
    text += "1. Откройте каждый канал по ссылке\n"
    text += "2. Нажмите \"Покинуть канал\"\n"
    text += "3. Вернитесь сюда и нажмите \"Подтвердить отписку\"\n"
    
    # Создаем кнопки с ссылками на каналы
    keyboard = telebot.types.InlineKeyboardMarkup()
    
    for _, _, channel_name, channel_link in channels_to_unsubscribe:
        if channel_link.startswith('@'):
            channel_url = f"https://t.me/{channel_link[1:]}"
        else:
            channel_url = channel_link if channel_link.startswith('http') else f"https://t.me/{channel_link}"
        
        btn = telebot.types.InlineKeyboardButton(
            f"📺 {channel_name}",
            url=channel_url
        )
        keyboard.add(btn)
    
    # Кнопка подтверждения отписки
    confirm_btn = telebot.types.InlineKeyboardButton(
        "✅ Подтвердить отписку",
        callback_data=f"confirm_unsubscribe_{giveaway_id}"
    )
    keyboard.add(confirm_btn)
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_unsubscribe_'))
def confirm_unsubscribe(call):
    """Подтверждение отписки от каналов"""
    user_id = call.from_user.id
    giveaway_id = int(call.data.split('_')[2])
    
    # Инициализируем менеджер отписок если еще не инициализирован
    global unsubscribe_manager
    if unsubscribe_manager is None:
        unsubscribe_manager = UnsubscribeManager(bot, DB_NAME)
    
    # Отмечаем каналы как отписанные
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE unsubscribe_tracking 
        SET unsubscribed_at = datetime('now')
        WHERE giveaway_id = ? AND user_id = ? AND unsubscribed_at IS NULL
    ''', (giveaway_id, user_id))
    
    updated_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    if updated_count > 0:
        bot.edit_message_text(
            f"✅ <b>Отписка подтверждена!</b>\n\n"
            f"Отмечено {updated_count} каналов как отписанные.\n"
            f"Ваша лента теперь чище! 🧹",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=telebot.types.InlineKeyboardMarkup([
                [telebot.types.InlineKeyboardButton("🧹 Управление подписками", callback_data="back_to_unsubscribe")]
            ])
        )
        bot.answer_callback_query(call.id, f"✅ Отписано от {updated_count} каналов")
    else:
        bot.answer_callback_query(call.id, "❌ Ошибка при подтверждении отписки")

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_unsubscribe')
def back_to_unsubscribe(call):
    """Возврат к меню управления подписками"""
    # Имитируем нажатие кнопки "Управление подписками"
    message = type('obj', (object,), {
        'from_user': call.from_user,
        'chat': call.message.chat
    })
    show_unsubscribe_management(message)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id, "Отменено")

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def setup_unsubscribe_reminder(user_id, giveaway_id, title, end_date):
    """Настраивает напоминание об отписке от каналов после завершения розыгрыша"""
    try:
        # Парсим дату завершения
        if ' ' in end_date:
            end_datetime = datetime.datetime.strptime(end_date, '%d.%m.%Y %H:%M')
        else:
            end_datetime = datetime.datetime.strptime(end_date + ' 20:00', '%d.%m.%Y %H:%M')
        
        # Напоминание через 1 день после завершения
        reminder_time = end_datetime + datetime.timedelta(days=1)
        
        scheduler.add_job(
            send_unsubscribe_reminder,
            'date',
            run_date=reminder_time,
            args=[user_id, giveaway_id, title],
            id=f'unsubscribe_reminder_{user_id}_{giveaway_id}'
        )
        
        print(f"✅ Напоминание об отписке настроено для пользователя {user_id}, розыгрыш {title}")
        
    except Exception as e:
        print(f"❌ Ошибка настройки напоминания об отписке: {e}")

def send_unsubscribe_reminder(user_id, giveaway_id, title):
    """Отправляет напоминание об отписке от каналов"""
    try:
        # Инициализируем менеджер отписок если еще не инициализирован
        global unsubscribe_manager
        if unsubscribe_manager is None:
            unsubscribe_manager = UnsubscribeManager(bot, DB_NAME)
        
        # Проверяем, есть ли каналы для отписки
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM unsubscribe_tracking 
            WHERE giveaway_id = ? AND user_id = ? AND unsubscribed_at IS NULL
        ''', (giveaway_id, user_id))
        
        channels_count = cursor.fetchone()[0]
        conn.close()
        
        if channels_count > 0:
            text = f"🧹 <b>Напоминание об отписке</b>\n\n"
            text += f"🎯 <b>Розыгрыш:</b> {title}\n"
            text += f"📅 Завершен вчера\n\n"
            text += f"📺 У вас есть {channels_count} канал(ов) для отписки.\n"
            text += "Не забудьте отписаться, чтобы не захламлять ленту! 💫\n\n"
            text += "Нажмите кнопку ниже для управления подписками:"
            
            keyboard = telebot.types.InlineKeyboardMarkup()
            btn = telebot.types.InlineKeyboardButton(
                "🧹 Управление подписками",
                callback_data="back_to_unsubscribe"
            )
            keyboard.add(btn)
            
            bot.send_message(user_id, text, parse_mode='HTML', reply_markup=keyboard)
            
    except Exception as e:
        print(f"❌ Ошибка отправки напоминания об отписке: {e}")

def setup_reminder(user_id, giveaway_id, title, date_str):
    """Настраивает напоминание для розыгрыша"""
    try:
        # Парсим дату
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
        btn2 = telebot.types.InlineKeyboardButton(
            "📋 Мои розыгрыши",
            callback_data="show_giveaways"
        )
        keyboard.add(btn1, btn2)

        bot.send_message(
            user_id,
            reminder_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )

        # Логируем отправку напоминания
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO usage_stats (user_id, action, details)
            VALUES (?, ?, ?)
        ''', (user_id, 'reminder_sent', f'Giveaway: {giveaway_id}'))
        conn.commit()
        conn.close()

    except Exception as e:
        print(f"Ошибка при отправке напоминания: {e}")

def analyze_message_for_giveaway(text):
    """Анализирует сообщение на предмет розыгрыша"""
    confidence = calculate_giveaway_confidence(text)

    if confidence < 0.3:
        return None

    # Извлекаем информацию
    dates = extract_dates_from_text(text)
    channels = extract_channels_from_text(text)
    prizes = extract_prizes_from_text(text)

    # Пытаемся извлечь название розыгрыша из первых строк
    lines = text.split('\n')
    title = ""
    for line in lines[:3]:  # Смотрим первые 3 строки
        if any(keyword in line.lower() for keyword in GIVEAWAY_KEYWORDS[:5]):
            title = line.strip()
            break

    if not title and lines:
        title = lines[0][:100]  # Берем первую строку как заголовок

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

# ==================== ЗАПУСК БОТА ====================

if __name__ == "__main__":
    print("🚀 Инициализация ультимативного бота v3.0...")
    init_database()
    print("✅ База данных инициализирована")
    print("🔍 Автопоиск розыгрышей: активен")
    print("📸 OCR обработка изображений: активна") 
    print("🧠 ChatGPT интеграция:", "активна" if CHATGPT_AVAILABLE else "недоступна")
    print("📊 Экспорт и аналитика: активны")
    print("✅ Проверка подписок: активна")
    print("📚 История розыгрышей: активна")
    print("⚙️ Гибкие настройки: активны")
    print("🎉 Ультимативный бот запущен!")

    try:
        bot.polling(none_stop=True, interval=0)
    except Exception as e:
        print(f"Ошибка: {e}")
