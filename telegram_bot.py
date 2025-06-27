import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from sherlock_project import sherlock
from sherlock_project.sites import SitesInformation
from sherlock_project.notify import QueryNotifyPrint
from sherlock_project.result import QueryStatus

# Включите логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Замените 'YOUR_TOKEN' на ваш реальный токен бота
TOKEN = "8071003552:AAEQNGYKNPNU9mwYNnCdyAl9mOfxBuyqRmE"

# Определите обработчики команд.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при команде /start."""
    await update.message.reply_text(
        "Привет! Я бот для поиска информации о пользователях (OSINT). "
        "Отправь мне имя пользователя, и я постараюсь найти его на различных сайтах."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет справочное сообщение при команде /help."""
    await update.message.reply_text(
        "Чтобы начать поиск, просто отправь мне имя пользователя.\n"
        "Например: `john_doe`\n\n"
        "Я использую Sherlock для поиска на более чем 400 сайтах."
    )

async def search_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ищет имя пользователя с помощью Sherlock."""
    username = update.message.text
    if not username:
        await update.message.reply_text("Пожалуйста, введите имя пользователя.")
        return

    await update.message.reply_text(f"Начинаю поиск по имени пользователя: {username}...")

    # Создаем кастомный QueryNotify для сбора результатов
    class TelegramQueryNotify(QueryNotifyPrint):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.found_sites = []

        def update(self, result):
            super().update(result) # Для логгирования в консоль, если нужно
            if result.status == QueryStatus.CLAIMED:
                self.found_sites.append(result.site_url_user)

        def get_found_sites(self):
            return self.found_sites

    try:
        # Инициализация Sherlock
        # Используем локальный data.json для предсказуемости
        sites = SitesInformation(local_data_file_path="sherlock_project/resources/data.json")
        site_data_all = {site.name: site.information for site in sites}

        # Убираем NSFW сайты по умолчанию
        sites.remove_nsfw_sites()
        site_data_all = {site.name: site.information for site in sites if site.information is not None}


        telegram_query_notify = TelegramQueryNotify(print_all=False, verbose=False, browse=False)

        # Запуск Sherlock
        # Важно: sherlock.sherlock - это функция, а не класс.
        # sherlock() ожидает username, site_data, query_notify, и другие параметры
        sherlock.sherlock(
            username=username,
            site_data=site_data_all,
            query_notify=telegram_query_notify,
            timeout=60,  # Увеличено время ожидания для надежности
            # Можно добавить другие параметры по необходимости, например, proxy, tor
        )

        found_sites = telegram_query_notify.get_found_sites()

        if found_sites:
            response_message = f"Найдены следующие профили для '{username}':\n" + "\n".join(found_sites)
        else:
            response_message = f"Профили для '{username}' не найдены."

        # Отправляем результаты пользователю частями, если их много
        max_message_length = 4096
        for i in range(0, len(response_message), max_message_length):
            await update.message.reply_text(response_message[i:i + max_message_length])

    except Exception as e:
        logger.error(f"Ошибка при поиске пользователя {username}: {e}", exc_info=True)
        # Отправляем более подробное сообщение об ошибке, если это безопасно
        # В продакшене лучше логировать детали и давать пользователю общее сообщение
        await update.message.reply_text(f"Произошла ошибка при поиске. Подробности в логах сервера.")

def main() -> None:
    """Запускает бота."""
    # Создаем Application и передаем ему токен вашего бота.
    application = Application.builder().token(TOKEN).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Регистрируем обработчик сообщений для поиска имени пользователя
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_username))

    # Запускаем бота до тех пор, пока пользователь не нажмет Ctrl-C
    logger.info("Бот запускается...")
    application.run_polling()
    logger.info("Бот остановлен.")

if __name__ == "__main__":
    main()
