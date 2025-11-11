
# Демонстрация работы системы распознавания розыгрышей
import re
import json

# Ключевые слова для распознавания розыгрышей
GIVEAWAY_KEYWORDS = [
    'розыгрыш', 'розыграш', 'конкурс', 'раздача', 'приз', 'выиграть',
    'giveaway', 'contest', 'раздаем', 'дарим', 'бесплатно', 'выигрыш',
    'лотерея', 'разыгрываем', 'участвуй', 'побеждай', 'получи приз',
    'скидка', 'промокод', 'акция'
]

# Паттерны для извлечения информации
DATE_PATTERNS = [
    r'\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\b',  # ДД.ММ.ГГГГ
    r'\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2})\b',   # ДД.ММ.ГГ
]

CHANNEL_PATTERNS = [
    r'@[a-zA-Z_][a-zA-Z0-9_]{4,}',  # @channel_name
    r't\.me/[a-zA-Z_][a-zA-Z0-9_]+', # t.me/channel
]

PRIZE_PATTERNS = [
    r'(iPhone|iPad|MacBook|Samsung|Xiaomi|Huawei|OnePlus)[^\n]*',
    r'(\d+\s*(?:руб|рублей|долларов|евро|₽|$|€))',
    r'(сертификат|подарочный\s+сертификат)[^\n]*',
    r'(приз|подарок)[^\n]*',
]

def extract_dates_from_text(text):
    dates = []
    for pattern in DATE_PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches:
            if len(match) == 3:
                try:
                    date_str = f"{match[0]}.{match[1]}.{match[2]}"
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

    # Подсчитываем ключевые слова
    keyword_count = sum(1 for keyword in GIVEAWAY_KEYWORDS if keyword in text_lower)
    keyword_score = min(keyword_count / 3.0, 1.0)

    # Проверяем наличие элементов
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

# Демонстрационные сообщения
test_messages = [
    {
        "title": "✅ Отличный розыгрыш (высокая уверенность)",
        "text": '''🎉 МЕГА РОЗЫГРЫШ IPHONE 15 PRO MAX!

🎁 Разыгрываем iPhone 15 Pro Max 256GB Space Black
📅 Дата розыгрыша: 25.12.2024 в 20:00

📋 Условия участия:
• Подписаться на @tech_news_channel
• Подписаться на @giveaway_central  
• Подписаться на @apple_fans_ru
• Поставить лайк под этим постом
• Репостнуть к себе на стену

🏆 Победитель будет выбран рандомно!
Удачи всем участникам! 🍀'''
    },
    {
        "title": "⚠️ Средний розыгрыш (средняя уверенность)", 
        "text": '''Друзья! Скоро новогодний конкурс 🎄

Будем дарить классные подарки!
Дата проведения: 31.12.2024

Следите за обновлениями в @our_channel
Подробности позже!'''
    },
    {
        "title": "❌ Не розыгрыш (низкая уверенность)",
        "text": '''Привет! Как дела? 

Сегодня отличная погода на улице.
Встретимся завтра в 15:00 в кафе?
Не забудь захватить документы.

До свидания!'''
    },
    {
        "title": "🤖 Технический пример (средняя-высокая уверенность)",
        "text": '''💰 Раздача денежных призов!

Общий призовой фонд: 50000 рублей
Разыгрываем между подписчиками

Условия:
- Подписка на t.me/money_channel
- Подписка на t.me/crypto_news
- Репост этого сообщения

Итоги подведем 15.01.2025 в 21:00'''
    }
]

print("=" * 60)
print("🤖 ДЕМОНСТРАЦИЯ АВТОМАТИЧЕСКОГО РАСПОЗНАВАНИЯ РОЗЫГРЫШЕЙ")
print("=" * 60)
print()

for i, msg in enumerate(test_messages, 1):
    print(f"📝 ПРИМЕР {i}: {msg['title']}")
    print("-" * 50)
    print("📄 Исходное сообщение:")
    print(msg['text'])
    print()

    result = analyze_message_for_giveaway(msg['text'])

    if result:
        print("🔍 РЕЗУЛЬТАТ АНАЛИЗА:")
        print(f"📊 Уверенность: {result['confidence']:.1%}")
        print(f"📝 Название: {result['title']}")
        print(f"🎁 Приз: {result['suggested_prize']}")
        print(f"📅 Дата: {result['suggested_date']}")
        print(f"📢 Каналы: {result['suggested_channels'] if result['suggested_channels'] else 'Не найдены'}")
        print()
        print("📋 Детали:")
        print(f"   • Найдено дат: {len(result['dates'])}")
        print(f"   • Найдено каналов: {len(result['channels'])}")  
        print(f"   • Найдено призов: {len(result['prizes'])}")

        # Определяем действие бота
        if result['confidence'] >= 0.6:
            action = "✅ БОТ ПРЕДЛОЖИТ ДОБАВИТЬ РОЗЫГРЫШ"
        elif result['confidence'] >= 0.4:
            action = "⚠️ БОТ МОЖЕТ ПРЕДЛОЖИТЬ (зависит от настроек)"
        else:
            action = "❌ БОТ НЕ БУДЕТ ПРЕДЛАГАТЬ"

        print(f"   • Действие бота: {action}")
    else:
        print("🔍 РЕЗУЛЬТАТ АНАЛИЗА:")
        print("❌ Розыгрыш не распознан (уверенность < 30%)")
        print("   • Действие бота: НЕ ПРЕДЛАГАТЬ ДОБАВЛЕНИЕ")

    print()
    print("=" * 60)
    print()

# Создаем статистику по анализу
print("📊 СТАТИСТИКА АНАЛИЗА:")
print("-" * 30)

results = []
for msg in test_messages:
    result = analyze_message_for_giveaway(msg['text'])
    if result:
        results.append(result['confidence'])
    else:
        results.append(0.0)

print(f"Всего сообщений проанализировано: {len(test_messages)}")
print(f"Распознано как розыгрыши: {len([r for r in results if r >= 0.3])}")
print(f"Средняя уверенность: {sum(results)/len(results):.1%}")
print(f"Максимальная уверенность: {max(results):.1%}")
print(f"Минимальная уверенность: {min(results):.1%}")

print()
print("🎯 РЕКОМЕНДАЦИИ ПО НАСТРОЙКЕ:")
print("• Для высокой точности: минимум 70%")
print("• Для баланса точность/полнота: минимум 50%") 
print("• Для максимального охвата: минимум 30%")
