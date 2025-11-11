#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Примеры использования функций бота для розыгрышей
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.bots.giveaway_recognition_demo import (
    analyze_message_for_giveaway,
    calculate_giveaway_confidence,
    extract_dates_from_text,
    extract_channels_from_text,
    extract_prizes_from_text
)

def example_text_analysis():
    """Пример анализа текста на предмет розыгрыша"""
    print("🔍 Пример анализа текста")
    print("=" * 40)
    
    # Тестовые сообщения
    test_messages = [
        "🎉 РОЗЫГРЫШ IPHONE 15 PRO MAX! Дата: 25.12.2024 в 20:00. Подпишитесь на @tech_channel",
        "Привет! Как дела? Встретимся завтра?",
        "💰 Раздача 50000 рублей! Условия: подписка на @money_channel и @crypto_news"
    ]
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n📝 Сообщение {i}: {message}")
        
        # Анализируем сообщение
        result = analyze_message_for_giveaway(message)
        
        if result:
            print(f"✅ Розыгрыш обнаружен!")
            print(f"📊 Уверенность: {result['confidence']:.1%}")
            print(f"📝 Название: {result['title']}")
            print(f"🎁 Приз: {result['suggested_prize']}")
            print(f"📅 Дата: {result['suggested_date']}")
            print(f"📢 Каналы: {result['suggested_channels']}")
        else:
            print("❌ Розыгрыш не обнаружен")

def example_component_analysis():
    """Пример анализа отдельных компонентов"""
    print("\n\n🔧 Пример анализа компонентов")
    print("=" * 40)
    
    text = "🎁 Розыгрыш iPhone 15! Дата: 25.12.2024 в 20:00. Подпишитесь на @apple_fans и @tech_news"
    
    print(f"📝 Текст: {text}")
    print()
    
    # Извлекаем даты
    dates = extract_dates_from_text(text)
    print(f"📅 Найденные даты: {dates}")
    
    # Извлекаем каналы
    channels = extract_channels_from_text(text)
    print(f"📢 Найденные каналы: {channels}")
    
    # Извлекаем призы
    prizes = extract_prizes_from_text(text)
    print(f"🎁 Найденные призы: {prizes}")
    
    # Вычисляем уверенность
    confidence = calculate_giveaway_confidence(text)
    print(f"📊 Общая уверенность: {confidence:.1%}")

def example_confidence_thresholds():
    """Пример работы с порогами уверенности"""
    print("\n\n🎯 Пример порогов уверенности")
    print("=" * 40)
    
    messages = [
        ("🎉 МЕГА РОЗЫГРЫШ! iPhone 15 Pro Max! Дата: 25.12.2024", 0.9),
        ("Конкурс на подарок", 0.6),
        ("Розыгрыш приза", 0.4),
        ("Привет, как дела?", 0.1)
    ]
    
    thresholds = [0.3, 0.5, 0.7, 0.9]
    
    for message, expected_confidence in messages:
        result = analyze_message_for_giveaway(message)
        confidence = result['confidence'] if result else 0.0
        
        print(f"\n📝 Сообщение: {message}")
        print(f"📊 Уверенность: {confidence:.1%}")
        
        for threshold in thresholds:
            action = "✅ ПРЕДЛОЖИТЬ" if confidence >= threshold else "❌ ОТКЛОНИТЬ"
            print(f"   Порог {threshold:.0%}: {action}")

if __name__ == "__main__":
    print("🤖 Примеры использования функций бота для розыгрышей")
    print("=" * 60)
    
    # Запускаем примеры
    example_text_analysis()
    example_component_analysis()
    example_confidence_thresholds()
    
    print("\n\n🎉 Все примеры выполнены!")
    print("📖 Для запуска бота используйте файлы в папке src/bots/")

