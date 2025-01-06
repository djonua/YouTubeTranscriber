# YouTube Transcriber Bot 🎥

Telegram бот для извлечения субтитров из YouTube видео, создания краткого содержания и ответов на вопросы о содержании видео с использованием AI (поддерживает OpenAI и DeepSeek API).

## Возможности 🚀

- 📝 Извлечение субтитров из YouTube видео
- 🔄 Автоматический перевод субтитров на русский язык
- 📋 Генерация краткого содержания видео
- ❓ Ответы на вопросы о содержании видео
- 🌐 Поддержка нескольких AI провайдеров (OpenAI и DeepSeek)
- 🎯 Умное форматирование текста в Telegram

## Установка 🛠

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/YouTubeTranscriber.git
cd YouTubeTranscriber
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте файл `.env` и настройте переменные окружения:
```env
# Telegram Bot Token
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# OpenAI API Settings
OPENAI_API_KEY=your_openai_api_key
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_MODEL=gpt-4o

# DeepSeek API Settings (опционально)
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_API_MODEL=deepseek-chat
```

## Использование 📱

1. Запустите бота:
```bash
python bot.py
```

2. Найдите бота в Telegram и отправьте ему команду `/start`

3. Отправьте ссылку на YouTube видео

4. Бот извлечет субтитры, сгенерирует краткое содержание и будет готов отвечать на ваши вопросы о видео

## Поддерживаемые языки 🌍

- 🇷🇺 Русский (основной язык бота)
- 🇬🇧 Английский (автоматический перевод)
- Другие языки (через автоматический перевод)

## Технические детали 🔧

- Python 3.8+
- python-telegram-bot
- youtube-transcript-api
- openai
- python-dotenv

## Структура проекта 📁

```
YouTubeTranscriber/
├── bot.py              # Основной файл бота
├── requirements.txt    # Зависимости проекта
├── .env               # Конфигурация (не включена в репозиторий)
├── .gitignore         # Игнорируемые файлы
├── logs/              # Директория для логов
└── README.md          # Документация
```

## Безопасность 🔒

- API ключи хранятся в файле `.env`
- Логи не содержат конфиденциальной информации
- Поддержка различных API провайдеров

## Разработка 👨‍💻

Проект открыт для контрибуций! Если у вас есть идеи по улучшению:

1. Форкните репозиторий
2. Создайте ветку для вашей фичи
3. Внесите изменения
4. Создайте Pull Request

## Лицензия 📄

MIT License - делайте с кодом что хотите 😊