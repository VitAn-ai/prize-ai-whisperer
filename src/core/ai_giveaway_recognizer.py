# -*- coding: utf-8 -*-
"""
Модуль для распознавания розыгрышей с помощью OpenAI
"""

import openai
import json
import re
from typing import Dict, List, Optional

class AIGiveawayRecognizer:
    """Класс для распознавания розыгрышей с помощью ИИ"""
    
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = "gpt-3.5-turbo"
    
    def analyze_giveaway(self, text: str) -> Dict:
        """
        Анализирует текст на предмет розыгрыша с помощью OpenAI
        
        Args:
            text: Текст для анализа
            
        Returns:
            Dict с результатами анализа
        """
        try:
            prompt = self._create_giveaway_prompt(text)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты эксперт по анализу розыгрышей и конкурсов в социальных сетях. Твоя задача - определить, содержит ли текст информацию о розыгрыше, и извлечь ключевую информацию."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            ai_response = response.choices[0].message.content
            return self._parse_ai_response(ai_response, text)
            
        except Exception as e:
            print(f"❌ Ошибка ИИ-анализа: {e}")
            return self._fallback_analysis(text)
    
    def _create_giveaway_prompt(self, text: str) -> str:
        """Создает промпт для анализа розыгрыша"""
        return f"""
Проанализируй этот текст и определи, есть ли в нем информация о розыгрыше, конкурсе или раздаче призов.

Текст для анализа:
"{text}"

Ответь в формате JSON со следующими полями:
{{
    "is_giveaway": true/false,
    "confidence": число от 0 до 100,
    "title": "название розыгрыша или null",
    "prize": "приз или описание приза или null",
    "date": "дата проведения в формате ДД.ММ.ГГГГ или null",
    "time": "время проведения или null",
    "channels": ["список каналов для подписки"],
    "conditions": ["условия участия"],
    "description": "краткое описание розыгрыша"
}}

Критерии определения розыгрыша:
1. Упоминание слов: розыгрыш, конкурс, раздача, приз, выиграть, дарим, бесплатно
2. Условия участия: подписка, лайк, репост, комментарий
3. Указание приза или награды
4. Указание срока проведения
5. Призыв к участию

Если это НЕ розыгрыш, верни is_giveaway: false и confidence: 0.

Отвечай ТОЛЬКО JSON без дополнительного текста.
"""
    
    def _parse_ai_response(self, ai_response: str, original_text: str) -> Dict:
        """Парсит ответ от ИИ"""
        try:
            # Очищаем ответ от возможных артефактов
            ai_response = ai_response.strip()
            if ai_response.startswith('```json'):
                ai_response = ai_response[7:]
            if ai_response.endswith('```'):
                ai_response = ai_response[:-3]
            
            # Парсим JSON
            result = json.loads(ai_response)
            
            # Дополняем результат извлеченными данными
            if result.get('is_giveaway', False):
                # Извлекаем дополнительные данные из текста
                extracted_data = self._extract_additional_data(original_text)
                result.update(extracted_data)
            
            return result
            
        except json.JSONDecodeError:
            print(f"⚠️ Не удалось распарсить ответ ИИ: {ai_response}")
            return self._fallback_analysis(original_text)
        except Exception as e:
            print(f"❌ Ошибка парсинга ответа ИИ: {e}")
            return self._fallback_analysis(original_text)
    
    def _extract_additional_data(self, text: str) -> Dict:
        """Извлекает дополнительные данные из текста"""
        data = {
            'channels': [],
            'dates': [],
            'prizes': []
        }
        
        # Извлекаем каналы
        channel_pattern = r'@[\w_]+|t\.me/[\w_]+'
        channels = re.findall(channel_pattern, text, re.IGNORECASE)
        data['channels'] = list(set(channels))
        
        # Извлекаем даты
        date_pattern = r'\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b'
        dates = re.findall(date_pattern, text)
        data['dates'] = dates
        
        # Извлекаем призы
        prize_keywords = ['iPhone', 'MacBook', 'денег', 'рублей', 'долларов', 'приз', 'подарок']
        for keyword in prize_keywords:
            if keyword.lower() in text.lower():
                data['prizes'].append(keyword)
        
        return data
    
    def _fallback_analysis(self, text: str) -> Dict:
        """Улучшенный резервный анализ без ИИ"""
        text_lower = text.lower()
        
        # Ключевые слова для розыгрышей с весами
        giveaway_keywords = {
            'розыгрыш': 30, 'конкурс': 30, 'раздача': 25, 'giveaway': 30, 'contest': 25,
            'приз': 20, 'выиграть': 25, 'дарим': 20, 'бесплатно': 15,
            'победитель': 15, 'участник': 10, 'участие': 10
        }
        
        # Эмодзи розыгрышей
        giveaway_emojis = ['🎉', '🎁', '💰', '🏆', '🍀', '🎊', '🎈', '🎯']
        
        # Условия участия
        condition_keywords = ['подписка', 'подписаться', 'лайк', 'репост', 'комментарий', 'поделиться']
        
        # Призы
        prize_keywords = ['iphone', 'macbook', 'денег', 'рублей', 'долларов', 'евро', 'подарок']
        
        # Подсчет очков
        confidence = 0
        
        # Проверяем ключевые слова
        for keyword, weight in giveaway_keywords.items():
            if keyword in text_lower:
                confidence += weight
        
        # Проверяем эмодзи
        emoji_count = sum(1 for emoji in giveaway_emojis if emoji in text)
        confidence += emoji_count * 10
        
        # Проверяем условия участия
        condition_count = sum(1 for keyword in condition_keywords if keyword in text_lower)
        confidence += condition_count * 15
        
        # Проверяем призы
        prize_count = sum(1 for keyword in prize_keywords if keyword in text_lower)
        confidence += prize_count * 20
        
        # Проверяем наличие каналов
        channel_pattern = r'@[\w_]+|t\.me/[\w_]+'
        channels = re.findall(channel_pattern, text, re.IGNORECASE)
        if channels:
            confidence += len(channels) * 10
        
        # Проверяем наличие дат
        date_pattern = r'\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b'
        dates = re.findall(date_pattern, text)
        if dates:
            confidence += len(dates) * 15
        
        # Проверяем призыв к действию
        action_words = ['участвуй', 'участвуйте', 'не упусти', 'шанс', 'возможность']
        action_count = sum(1 for word in action_words if word in text_lower)
        confidence += action_count * 10
        
        # Ограничиваем уверенность
        confidence = min(confidence, 100)
        
        # Определяем, является ли это розыгрышем
        is_giveaway = confidence > 40
        
        # Извлекаем дополнительную информацию
        title = None
        if is_giveaway:
            # Пытаемся найти название в начале текста
            lines = text.split('\n')
            for line in lines[:3]:  # Проверяем первые 3 строки
                if any(keyword in line.lower() for keyword in ['розыгрыш', 'конкурс', 'раздача']):
                    title = line.strip()[:100]  # Ограничиваем длину
                    break
        
        # Извлекаем приз
        prize = None
        for prize_keyword in prize_keywords:
            if prize_keyword in text_lower:
                # Ищем контекст вокруг ключевого слова
                words = text_lower.split()
                for i, word in enumerate(words):
                    if prize_keyword in word:
                        # Берем несколько слов вокруг
                        start = max(0, i-2)
                        end = min(len(words), i+3)
                        prize = ' '.join(words[start:end])
                        break
                if prize:
                    break
        
        return {
            'is_giveaway': is_giveaway,
            'confidence': confidence,
            'title': title,
            'prize': prize,
            'date': None,
            'time': None,
            'channels': channels,
            'conditions': [],
            'description': 'Улучшенный анализ без ИИ',
            'fallback': True
        }
    
    def analyze_image_with_ocr(self, image_text: str) -> Dict:
        """
        Анализирует текст, извлеченный из изображения
        
        Args:
            image_text: Текст, извлеченный из изображения через OCR
            
        Returns:
            Dict с результатами анализа
        """
        if not image_text or len(image_text.strip()) < 10:
            return {
                'is_giveaway': False,
                'confidence': 0,
                'error': 'Недостаточно текста для анализа'
            }
        
        # Добавляем контекст для анализа изображений
        enhanced_text = f"[Текст с изображения] {image_text}"
        return self.analyze_giveaway(enhanced_text)
    
    def get_confidence_level(self, confidence: int) -> str:
        """Возвращает уровень уверенности в текстовом виде"""
        if confidence >= 80:
            return "Очень высокая"
        elif confidence >= 60:
            return "Высокая"
        elif confidence >= 40:
            return "Средняя"
        elif confidence >= 20:
            return "Низкая"
        else:
            return "Очень низкая"
    
    def format_analysis_result(self, result: Dict) -> str:
        """Форматирует результат анализа для отображения"""
        if not result.get('is_giveaway', False):
            return f"❌ Розыгрыш не распознан (уверенность: {result.get('confidence', 0)}%)"
        
        confidence_level = self.get_confidence_level(result.get('confidence', 0))
        
        text = f"✅ Розыгрыш распознан!\n"
        text += f"📊 Уверенность: {result.get('confidence', 0)}% ({confidence_level})\n\n"
        
        if result.get('title'):
            text += f"🎯 Название: {result['title']}\n"
        
        if result.get('prize'):
            text += f"🎁 Приз: {result['prize']}\n"
        
        if result.get('date'):
            text += f"📅 Дата: {result['date']}"
            if result.get('time'):
                text += f" в {result['time']}"
            text += "\n"
        
        if result.get('channels'):
            text += f"📺 Каналы: {', '.join(result['channels'])}\n"
        
        if result.get('conditions'):
            text += f"📋 Условия: {', '.join(result['conditions'])}\n"
        
        if result.get('description'):
            text += f"📝 Описание: {result['description']}\n"
        
        return text
