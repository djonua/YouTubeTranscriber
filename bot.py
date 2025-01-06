import os
import re
import logging
from typing import Optional, Dict, List
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled, NoTranscriptAvailable
from youtube_transcript_api.formatters import SRTFormatter
import openai
import signal
import sys

# Настройка логирования
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, f"bot_{datetime.now().strftime('%Y%m%d')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
logger.info("Переменные окружения загружены")


class OpenAIConfig:
    """Конфигурация для DEEPSEEK API и OPENAI API"""
    def __init__(self):
        self.api_key: str = os.getenv('DEEPSEEK_API_KEY', os.getenv('OPENAI_API_KEY'))
        self.api_base: str = os.getenv('DEEPSEEK_API_BASE', os.getenv('OPENAI_API_BASE'))
        self.model: str = os.getenv('DEEPSEEK_API_MODEL', os.getenv('OPENAI_API_MODEL'))
        
        if not self.api_key:
            raise ValueError("API ключ не найден в переменных окружения")
        
        logger.info(f"API настроен: endpoint={self.api_base}, model={self.model}")


class HTMLCleaner:
    """Класс для очистки и исправления HTML-разметки"""
    ALLOWED_TAGS = {'b', 'i', 'u', 'strong', 'em', 'code', 'pre'}
    
    @classmethod
    def clean(cls, text: str) -> str:
        """Очистка HTML от неподдерживаемых тегов Telegram и исправление незакрытых тегов"""
        # Удаляем все теги, кроме разрешенных
        pattern = r'</?(?!(?:' + '|'.join(cls.ALLOWED_TAGS) + r')\b)[^>]*>'
        text = re.sub(pattern, '', text)
        
        # Находим все открытые теги
        opened_tags: List[str] = []
        for match in re.finditer(r'<([a-z]+)[^>]*>', text):
            tag = match.group(1)
            if tag in cls.ALLOWED_TAGS:
                opened_tags.append(tag)
        
        # Находим все закрытые теги
        for match in re.finditer(r'</([a-z]+)>', text):
            tag = match.group(1)
            if tag in cls.ALLOWED_TAGS and opened_tags and opened_tags[-1] == tag:
                opened_tags.pop()
        
        # Закрываем оставшиеся открытые теги в обратном порядке
        for tag in reversed(opened_tags):
            text += f'</{tag}>'
        
        return text


class YouTubeTranscriberBot:
    """Telegram бот для транскрибации и анализа YouTube видео"""
    
    def __init__(self):
        """Инициализация бота"""
        self.bot_token: str = os.getenv('TELEGRAM_BOT_TOKEN')
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
            
        # Хранение контекста для каждого чата
        self.chat_contexts: Dict[int, str] = {}
        
        # Инициализация конфигурации OpenAI
        self.openai_config = OpenAIConfig()
        self.openai_client = openai.AsyncOpenAI(
            api_key=self.openai_config.api_key,
            base_url=self.openai_config.api_base
        )

        # Создаем директорию для логов запросов
        self.logs_dir = "logs"
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
        
        # Обработка сигналов завершения
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        
        logger.info("Бот инициализирован")

    def _handle_shutdown(self, signum, frame):
        """Обработчик сигналов завершения"""
        logger.info("Получен сигнал завершения, закрываем бота...")
        sys.exit(0)

    def _log_request(self, user_id: int, username: str, url: str):
        """Логирование запроса пользователя"""
        log_file = os.path.join(self.logs_dir, "requests.log")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp}, User ID: {user_id}, Username: {username}, URL: {url}\n"
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
        logger.info(f"Запрос залогирован: {log_entry.strip()}")

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Извлечение ID видео из URL"""
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start"""
        user = update.effective_user
        logger.info(f"Получена команда /start от пользователя {user.id}")
        await update.message.reply_html(
            f"Привет, {user.mention_html()}!\n"
            "Отправь мне ссылку на YouTube видео, и я:\n"
            "1. Извлеку субтитры\n"
            "2. Сделаю краткое содержание\n"
            "3. Отвечу на твои вопросы по видео"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик входящих сообщений"""
        message = update.message.text
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        logger.info(f"Получено сообщение от {user.id} ({user.username}): {message[:100]}...")

        if "youtube.com" in message or "youtu.be" in message:
            logger.info(f"Обнаружена YouTube ссылка от пользователя {user.id}")
            await self._process_youtube_link(update, context)
        else:
            logger.info(f"Обрабатываем вопрос от пользователя {user.id}")
            await self._process_question(update, context)

    def _clean_transcript(self, transcript_list: list) -> str:
        """Очистка транскрипции от лишней информации"""
        cleaned_text = []
        
        for item in transcript_list:
            # Берем только текст, пропускаем временные метки
            if 'text' in item:
                text = item['text'].strip()
                # Пропускаем пустые строки и строки только с пробелами
                if text and not text.isspace():
                    cleaned_text.append(text)
        
        # Объединяем все строки с текстом
        return ' '.join(cleaned_text)

    async def _process_youtube_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка ссылки на YouTube видео"""
        url = update.message.text
        user = update.effective_user
        try:
            # Логируем запрос
            self._log_request(user.id, user.username or "Unknown", url)
            
            logger.info(f"Начинаем обработку видео {url} для пользователя {user.id}")
            video_id = self.extract_video_id(url)
            
            if not video_id:
                logger.warning(f"Не удалось извлечь ID видео из URL: {url}")
                await update.message.reply_html(
                    "❌ Не удалось распознать ссылку на YouTube видео. "
                    "Пожалуйста, убедитесь, что ссылка корректна."
                )
                return

            await update.message.reply_html("🎬 <b>Начинаю обработку видео...</b>")
            
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                logger.info(f"Получен список субтитров для видео {video_id}")
                
                # Пробуем получить русские субтитры
                try:
                    transcript = transcript_list.find_transcript(['ru'])
                    logger.info("Найдены русские субтитры")
                except NoTranscriptFound:
                    # Если русских нет, берем английские и переводим
                    logger.info("Русские субтитры не найдены, ищем английские")
                    transcript = transcript_list.find_transcript(['en'])
                    transcript = transcript.translate('ru')
                    logger.info("Английские субтитры переведены на русский")
                
            except (NoTranscriptAvailable, TranscriptsDisabled) as e:
                logger.error(f"Ошибка при получении субтитров: {str(e)}")
                await update.message.reply_html(
                    "❌ <b>Не удалось получить субтитры для этого видео.</b>\n"
                    "Возможные причины:\n"
                    "• Субтитры отключены\n"
                    "• Видео не имеет субтитров\n"
                    "• Видео недоступно"
                )
                return
            
            transcript_text = transcript.fetch()
            # Очищаем транскрипт от лишней информации
            cleaned_transcript = self._clean_transcript(transcript_text)
            logger.info(f"Субтитры очищены, длина: {len(cleaned_transcript)} символов")
            
            # Сохраняем очищенный транскрипт в контекст
            context.chat_data['transcript'] = cleaned_transcript
            context.chat_data['video_id'] = video_id
            logger.info(f"Контекст сохранен для чата {update.effective_chat.id}")
            
            logger.info("Отправляем запрос к API для генерации краткого содержания")
            summary = await self._generate_summary(cleaned_transcript)
            
            await update.message.reply_html(
                f"📝 <b>Краткое содержание видео:</b>\n\n{summary}\n\n"
                "🤔 Теперь вы можете задать мне вопросы по содержанию видео!"
            )
            logger.info("Краткое содержание отправлено пользователю")
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Ошибка при обработке видео: {error_message}")
            await update.message.reply_html(
                "❌ <b>Произошла ошибка при обработке видео.</b>\n"
                f"Детали: {error_message}"
            )

    async def _process_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка вопроса по видео"""
        try:
            transcript = context.chat_data.get('transcript')
            if not transcript:
                await update.message.reply_html(
                    "❌ <b>Сначала отправьте ссылку на YouTube видео!</b>"
                )
                return

            question = update.message.text
            logger.info(f"Получен вопрос: {question[:100]}...")
            
            answer = await self._get_answer(question, transcript)
            await update.message.reply_html(
                f"🤖 <b>Ответ:</b>\n\n{answer}"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при обработке вопроса: {str(e)}", exc_info=True)
            await update.message.reply_html(
                f"❌ <b>Произошла ошибка:</b> {str(e)}"
            )

    async def _generate_summary(self, transcript: str) -> str:
        """Генерация краткого содержания через API"""
        logger.info("Начинаем генерацию краткого содержания")
        try:
            logger.info(f"Отправляем запрос к {self.openai_config.api_base} с моделью {self.openai_config.model}")
            response = await self.openai_client.chat.completions.create(
                model=self.openai_config.model,
                messages=[
                    {"role": "system", "content": "Ты - ассистент, который делает краткое изложение видео на основе субтитров на русском языке. "
                                                "Используй только следующие HTML-теги для форматирования (и всегда закрывай их): "
                                                "<b>жирный текст</b>, <i>курсив</i>, <strong>важный текст</strong>, <em>выделенный текст</em>. "
                                                "НЕ ИСПОЛЬЗУЙ никакие другие HTML-теги или специальные форматы."},
                    {"role": "user", "content": f"Сделай краткое изложение этого видео на основе субтитров. Используй HTML-теги для форматирования важных частей:\n\n{transcript}"}
                ]
            )
            summary = response.choices[0].message.content
            cleaned_summary = HTMLCleaner.clean(summary)
            logger.info("Краткое содержание успешно сгенерировано")
            return cleaned_summary
        except Exception as e:
            logger.error(f"Ошибка при запросе к API: {str(e)}", exc_info=True)
            if hasattr(e, 'response'):
                logger.error(f"Ответ API: {e.response.text if hasattr(e.response, 'text') else 'Нет текста ответа'}")
            raise

    async def _get_answer(self, question: str, transcript: str) -> str:
        """Получение ответа на вопрос через API"""
        logger.info(f"Отправляем вопрос: {question[:100]}...")
        try:
            logger.info(f"Отправляем запрос к {self.openai_config.api_base} с моделью {self.openai_config.model}")
            response = await self.openai_client.chat.completions.create(
                model=self.openai_config.model,
                messages=[
                    {"role": "system", "content": "Ты - ассистент, который отвечает на вопросы о содержании видео на основе субтитров на русском языке. "
                                                "Используй только следующие HTML-теги для форматирования (и всегда закрывай их): "
                                                "<b>жирный текст</b>, <i>курсив</i>, <strong>важный текст</strong>, <em>выделенный текст</em>. "
                                                "НЕ ИСПОЛЬЗУЙ никакие другие HTML-теги или специальные форматы."},
                    {"role": "user", "content": f"Контекст (субтитры видео):\n{transcript}\n\nВопрос: {question}"}
                ]
            )
            answer = response.choices[0].message.content
            cleaned_answer = HTMLCleaner.clean(answer)
            logger.info("Ответ получен")
            return cleaned_answer
        except Exception as e:
            logger.error(f"Ошибка при запросе к API: {str(e)}", exc_info=True)
            if hasattr(e, 'response'):
                logger.error(f"Ответ API: {e.response.text if hasattr(e.response, 'text') else 'Нет текста ответа'}")
            raise

    def run(self) -> None:
        """Запуск бота"""
        logger.info("Запускаем бота...")
        application = Application.builder().token(self.bot_token).build()
        
        # Регистрация обработчиков
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Запуск бота
        application.run_polling()
        logger.info("Бот успешно настроен и запущен")


if __name__ == "__main__":
    bot = YouTubeTranscriberBot()
    bot.run()
