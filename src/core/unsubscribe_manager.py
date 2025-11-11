# -*- coding: utf-8 -*-
"""
Модуль для управления отписками от каналов после завершения розыгрышей
"""

import sqlite3
import datetime
import asyncio
import telebot
from typing import List, Dict, Optional

class UnsubscribeManager:
    """Менеджер для отслеживания и управления отписками от каналов"""
    
    def __init__(self, bot, db_name: str):
        self.bot = bot
        self.db_name = db_name
        self.init_unsubscribe_tables()
    
    def init_unsubscribe_tables(self):
        """Инициализация таблиц для отслеживания отписок"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Таблица отслеживания отписок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unsubscribe_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                giveaway_id INTEGER,
                user_id INTEGER,
                channel_name TEXT,
                channel_link TEXT,
                subscribed_before_giveaway BOOLEAN DEFAULT TRUE,
                unsubscribe_reminder_sent BOOLEAN DEFAULT FALSE,
                unsubscribe_reminder_date TIMESTAMP NULL,
                actually_unsubscribed BOOLEAN DEFAULT FALSE,
                unsubscribe_date TIMESTAMP NULL,
                reminder_count INTEGER DEFAULT 0,
                unsubscribed_at DATETIME,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (giveaway_id) REFERENCES giveaways (id)
            )
        ''')
        
        # Таблица настроек отписок пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_unsubscribe_settings (
                user_id INTEGER PRIMARY KEY,
                auto_unsubscribe_reminder BOOLEAN DEFAULT TRUE,
                reminder_delay_hours INTEGER DEFAULT 24,
                max_reminders INTEGER DEFAULT 3,
                unsubscribe_after_days INTEGER DEFAULT 7,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Добавляем поля для отписок в существующие таблицы
        try:
            cursor.execute('ALTER TABLE giveaways ADD COLUMN unsubscribe_tracking_enabled BOOLEAN DEFAULT TRUE')
        except sqlite3.OperationalError:
            pass  # Поле уже существует
        
        try:
            cursor.execute('ALTER TABLE giveaway_history ADD COLUMN unsubscribe_completed BOOLEAN DEFAULT FALSE')
        except sqlite3.OperationalError:
            pass  # Поле уже существует
        
        conn.commit()
        conn.close()
    
    def track_giveaway_channels(self, giveaway_id: int, user_id: int, channels: str):
        """Начинает отслеживание каналов для розыгрыша"""
        if not channels or not channels.strip():
            return
        
        channel_list = [ch.strip() for ch in channels.split('\n') if ch.strip()]
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Проверяем текущие подписки (синхронно для простоты)
        for channel in channel_list:
            # Для упрощения считаем, что пользователь подписан на каналы, которые он добавил
            is_subscribed = True
            
            cursor.execute('''
                INSERT INTO unsubscribe_tracking 
                (giveaway_id, user_id, channel_name, channel_link, subscribed_before_giveaway)
                VALUES (?, ?, ?, ?, ?)
            ''', (giveaway_id, user_id, channel, channel, is_subscribed))
        
        conn.commit()
        conn.close()
    
    async def _check_subscription_status(self, user_id: int, channel: str) -> bool:
        """Проверяет статус подписки пользователя на канал"""
        try:
            if channel.startswith('@'):
                channel_id = channel
            elif 't.me/' in channel:
                channel_id = '@' + channel.split('/')[-1]
            else:
                channel_id = '@' + channel
            
            member = await self.bot.get_chat_member(channel_id, user_id)
            return member.status in ['member', 'administrator', 'creator']
        except Exception:
            return False
    
    def schedule_unsubscribe_reminders(self, giveaway_id: int, user_id: int):
        """Планирует напоминания об отписке от каналов"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Получаем настройки пользователя
        cursor.execute('''
            SELECT auto_unsubscribe_reminder, reminder_delay_hours, max_reminders
            FROM user_unsubscribe_settings WHERE user_id = ?
        ''', (user_id,))
        
        settings = cursor.fetchone()
        if not settings:
            # Создаем настройки по умолчанию
            cursor.execute('''
                INSERT INTO user_unsubscribe_settings (user_id) VALUES (?)
            ''', (user_id,))
            auto_reminder, delay_hours, max_reminders = True, 24, 3
        else:
            auto_reminder, delay_hours, max_reminders = settings
        
        if not auto_reminder:
            conn.close()
            return
        
        # Получаем каналы для отслеживания
        cursor.execute('''
            SELECT id, channel_name FROM unsubscribe_tracking 
            WHERE giveaway_id = ? AND user_id = ? AND subscribed_before_giveaway = TRUE
        ''', (giveaway_id, user_id))
        
        channels = cursor.fetchall()
        
        if channels:
            # Планируем первое напоминание
            reminder_time = datetime.datetime.now() + datetime.timedelta(hours=delay_hours)
            
            cursor.execute('''
                UPDATE unsubscribe_tracking 
                SET unsubscribe_reminder_date = ?, reminder_count = 1
                WHERE giveaway_id = ? AND user_id = ?
            ''', (reminder_time.isoformat(), giveaway_id, user_id))
        
        conn.commit()
        conn.close()
        
        # Планируем отправку напоминания
        if channels:
            self._schedule_reminder(user_id, giveaway_id, reminder_time)
    
    def _schedule_reminder(self, user_id: int, giveaway_id: int, reminder_time: datetime.datetime):
        """Планирует отправку напоминания об отписке"""
        # Здесь должна быть интеграция с планировщиком задач
        # Для примера используем простое логирование
        print(f"Запланировано напоминание об отписке для пользователя {user_id}, розыгрыш {giveaway_id} на {reminder_time}")
    
    def get_unsubscribe_status(self, user_id: int) -> Dict:
        """Получает статус отслеживания отписок пользователя"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Активные отслеживания
        cursor.execute('''
            SELECT COUNT(*) FROM unsubscribe_tracking ut
            JOIN giveaways g ON ut.giveaway_id = g.id
            WHERE ut.user_id = ? AND g.is_active = TRUE AND ut.subscribed_before_giveaway = TRUE
        ''', (user_id,))
        active_tracking = cursor.fetchone()[0]
        
        # Завершенные отписки
        cursor.execute('''
            SELECT COUNT(*) FROM unsubscribe_tracking 
            WHERE user_id = ? AND actually_unsubscribed = TRUE
        ''', (user_id,))
        completed_unsubscribes = cursor.fetchone()[0]
        
        # Ожидающие напоминания
        cursor.execute('''
            SELECT COUNT(*) FROM unsubscribe_tracking 
            WHERE user_id = ? AND unsubscribe_reminder_sent = FALSE AND subscribed_before_giveaway = TRUE
        ''', (user_id,))
        pending_reminders = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'active_tracking': active_tracking,
            'completed_unsubscribes': completed_unsubscribes,
            'pending_reminders': pending_reminders
        }
    
    def mark_channel_unsubscribed(self, user_id: int, giveaway_id: int, channel_name: str):
        """Отмечает канал как отписанный пользователем"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE unsubscribe_tracking 
            SET actually_unsubscribed = TRUE, unsubscribe_date = CURRENT_TIMESTAMP
            WHERE user_id = ? AND giveaway_id = ? AND channel_name = ?
        ''', (user_id, giveaway_id, channel_name))
        
        conn.commit()
        conn.close()
    
    def get_channels_to_unsubscribe(self, user_id: int, giveaway_id: int = None) -> List[Dict]:
        """Получает список каналов для отписки"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        if giveaway_id:
            query = '''
                SELECT ut.channel_name, ut.channel_link, g.title as giveaway_title, g.date_time
                FROM unsubscribe_tracking ut
                JOIN giveaways g ON ut.giveaway_id = g.id
                WHERE ut.user_id = ? AND ut.giveaway_id = ? 
                AND ut.subscribed_before_giveaway = TRUE 
                AND ut.actually_unsubscribed = FALSE
            '''
            params = (user_id, giveaway_id)
        else:
            query = '''
                SELECT ut.channel_name, ut.channel_link, g.title as giveaway_title, g.date_time
                FROM unsubscribe_tracking ut
                JOIN giveaways g ON ut.giveaway_id = g.id
                WHERE ut.user_id = ? AND ut.subscribed_before_giveaway = TRUE 
                AND ut.actually_unsubscribed = FALSE
                ORDER BY g.date_time DESC
            '''
            params = (user_id,)
        
        cursor.execute(query, params)
        channels = []
        
        for row in cursor.fetchall():
            channels.append({
                'channel_name': row[0],
                'channel_link': row[1],
                'giveaway_title': row[2],
                'giveaway_date': row[3]
            })
        
        conn.close()
        return channels
    
    def send_unsubscribe_reminder(self, user_id: int, giveaway_id: int):
        """Отправляет напоминание об отписке от каналов"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Получаем информацию о розыгрыше
        cursor.execute('''
            SELECT title, date_time FROM giveaways WHERE id = ?
        ''', (giveaway_id,))
        giveaway_info = cursor.fetchone()
        
        if not giveaway_info:
            conn.close()
            return
        
        title, date_time = giveaway_info
        
        # Получаем каналы для отписки
        channels = self.get_channels_to_unsubscribe(user_id, giveaway_id)
        
        if not channels:
            conn.close()
            return
        
        # Формируем сообщение
        message = f"🧹 **Время почистить подписки!**\n\n"
        message += f"📝 **Розыгрыш:** {title}\n"
        message += f"📅 **Дата:** {date_time}\n\n"
        message += f"📢 **Каналы для отписки ({len(channels)}):**\n"
        
        for i, channel in enumerate(channels[:10], 1):  # Ограничиваем до 10
            message += f"{i}. {channel['channel_name']}\n"
        
        if len(channels) > 10:
            message += f"... и еще {len(channels) - 10} каналов\n"
        
        message += f"\n💡 **Совет:** Отпишитесь от каналов, чтобы не захламлять ленту"
        
        # Создаем клавиатуру
        keyboard = self._create_unsubscribe_keyboard(user_id, giveaway_id, channels)
        
        # Отправляем сообщение
        self.bot.send_message(
            user_id,
            message,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        
        # Отмечаем напоминание как отправленное
        cursor.execute('''
            UPDATE unsubscribe_tracking 
            SET unsubscribe_reminder_sent = TRUE
            WHERE user_id = ? AND giveaway_id = ?
        ''', (user_id, giveaway_id))
        
        conn.commit()
        conn.close()
    
    def _create_unsubscribe_keyboard(self, user_id: int, giveaway_id: int, channels: List[Dict]):
        """Создает клавиатуру для управления отписками"""
        keyboard = telebot.types.InlineKeyboardMarkup()
        
        # Кнопка "Отписаться от всех"
        btn_unsubscribe_all = telebot.types.InlineKeyboardButton(
            "🧹 Отписаться от всех",
            callback_data=f"unsubscribe_all_{giveaway_id}"
        )
        keyboard.add(btn_unsubscribe_all)
        
        # Кнопка "Выбрать каналы"
        btn_select_channels = telebot.types.InlineKeyboardButton(
            "📋 Выбрать каналы",
            callback_data=f"unsubscribe_select_{giveaway_id}"
        )
        keyboard.add(btn_select_channels)
        
        # Кнопка "Пропустить"
        btn_skip = telebot.types.InlineKeyboardButton(
            "⏭️ Пропустить",
            callback_data=f"unsubscribe_skip_{giveaway_id}"
        )
        keyboard.add(btn_skip)
        
        return keyboard
    
    def update_user_unsubscribe_settings(self, user_id: int, **settings):
        """Обновляет настройки отписок пользователя"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Поддерживаемые настройки
        allowed_settings = {
            'auto_unsubscribe_reminder': bool,
            'reminder_delay_hours': int,
            'max_reminders': int,
            'unsubscribe_after_days': int
        }
        
        for key, value in settings.items():
            if key in allowed_settings and isinstance(value, allowed_settings[key]):
                cursor.execute(f'''
                    INSERT OR REPLACE INTO user_unsubscribe_settings 
                    (user_id, {key}) VALUES (?, ?)
                ''', (user_id, value))
        
        conn.commit()
        conn.close()
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Получает статистику отписок для пользователя"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute('''
            SELECT 
                COUNT(*) as total_tracked,
                SUM(CASE WHEN unsubscribed_at IS NOT NULL THEN 1 ELSE 0 END) as total_unsubscribed
            FROM unsubscribe_tracking 
            WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        total_tracked = result[0] if result else 0
        total_unsubscribed = result[1] if result and result[1] else 0
        
        # Последняя отписка
        cursor.execute('''
            SELECT MAX(unsubscribed_at) 
            FROM unsubscribe_tracking 
            WHERE user_id = ? AND unsubscribed_at IS NOT NULL
        ''', (user_id,))
        
        last_unsubscribe = cursor.fetchone()
        last_unsubscribe_date = last_unsubscribe[0] if last_unsubscribe and last_unsubscribe[0] else None
        
        conn.close()
        
        return {
            'total_channels_tracked': total_tracked,
            'total_unsubscribed': total_unsubscribed,
            'last_unsubscribe_date': last_unsubscribe_date,
            'unsubscribe_rate': (total_unsubscribed / total_tracked * 100) if total_tracked > 0 else 0
        }
