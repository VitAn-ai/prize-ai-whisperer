#!/bin/bash

# Скрипт установки для Linux/macOS

echo "🤖 Установка Telegram-ботов для розыгрышей"
echo "=========================================="

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не найден. Установите Python 3.8+"
    exit 1
fi

echo "✅ Python найден: $(python3 --version)"

# Создание виртуального окружения
echo "📦 Создание виртуального окружения..."
python3 -m venv venv

# Активация виртуального окружения
echo "🔧 Активация виртуального окружения..."
source venv/bin/activate

# Обновление pip
echo "⬆️ Обновление pip..."
pip install --upgrade pip

# Установка зависимостей
echo "📚 Установка зависимостей..."
if [ "$1" = "full" ]; then
    echo "🔧 Установка полной версии с OCR и ИИ..."
    pip install -r config/requirements_premium.txt
else
    echo "🔧 Установка упрощенной версии..."
    pip install -r config/requirements_simple.txt
fi

# Проверка Tesseract
echo "🔍 Проверка Tesseract OCR..."
if ! command -v tesseract &> /dev/null; then
    echo "⚠️ Tesseract не найден. Установите:"
    echo "   Ubuntu/Debian: sudo apt-get install tesseract-ocr tesseract-ocr-rus"
    echo "   macOS: brew install tesseract tesseract-lang"
    echo "   Windows: скачайте с https://github.com/UB-Mannheim/tesseract/wiki"
else
    echo "✅ Tesseract найден: $(tesseract --version | head -n1)"
fi

# Создание .env файла
if [ ! -f .env ]; then
    echo "📝 Создание файла конфигурации..."
    cp config/env.example .env
    echo "⚠️ Отредактируйте файл .env и добавьте ваш BOT_TOKEN"
else
    echo "✅ Файл .env уже существует"
fi

echo ""
echo "🎉 Установка завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Отредактируйте файл .env"
echo "2. Добавьте ваш BOT_TOKEN от @BotFather"
echo "3. Запустите бота:"
if [ "$1" = "full" ]; then
    echo "   python src/bots/ultimate_giveaway_bot.py"
else
    echo "   python src/bots/simplified_giveaway_bot.py"
fi
echo ""
echo "📖 Подробная документация в README.md"

