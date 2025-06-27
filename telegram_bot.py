import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
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

# Определяем состояния для ConversationHandler
TYPING_USERNAME, CHOOSING_ACTION = range(2)

# Кнопки
KEYBOARD_INPUT_NAME = "Ввести имя"
KEYBOARD_DESCRIPTION = "Краткое описание"
KEYBOARD_DEVELOPER = "О разработчике"

reply_keyboard = [
    [KeyboardButton(KEYBOARD_INPUT_NAME)],
    [KeyboardButton(KEYBOARD_DESCRIPTION), KeyboardButton(KEYBOARD_DEVELOPER)],
]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True)

# Определите обработчики команд.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отправляет приветственное сообщение при команде /start и показывает клавиатуру."""
    await update.message.reply_text(
        "Привет! Я бот для поиска информации о пользователях (OSINT). "
        "Выбери действие на клавиатуре или отправь мне имя пользователя для поиска.",
        reply_markup=markup,
    )
    return CHOOSING_ACTION

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет справочное сообщение при команде /help."""
    await update.message.reply_text(
        "Чтобы начать поиск, нажми кнопку 'Ввести имя' и отправь мне имя пользователя, "
        "или просто отправь имя пользователя.\n"
        "Используй кнопки для получения информации о боте или разработчике.\n\n"
        "Я использую Sherlock для поиска на более чем 400 сайтах.",
        reply_markup=markup,
    )

async def request_username_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает у пользователя ввод имени."""
    await update.message.reply_text("Пожалуйста, введите имя пользователя для поиска:")
    return TYPING_USERNAME

async def show_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отправляет краткое описание бота."""
    await update.message.reply_text(
        "Этот бот предназначен для поиска общедоступной информации о пользователях "
        "в различных социальных сетях и на других онлайн-платформах. "
        "Он использует движок Sherlock. Результаты поиска могут помочь в OSINT-расследованиях."
    )
    return CHOOSING_ACTION

async def show_developer_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отправляет информацию о разработчике."""
    await update.message.reply_text(
        "Этот бот создан с использованием библиотеки Sherlock (https://github.com/sherlock-project/sherlock) "
        "и `python-telegram-bot`. Разработчик этого интерфейса - AI ассистент Jules."
    )
    return CHOOSING_ACTION

async def search_username_direct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает прямое сообщение с именем пользователя (не через кнопку)."""
    username = update.message.text
    await _perform_search(update, context, username)
    return CHOOSING_ACTION


async def search_username_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ищет имя пользователя, введенное после нажатия кнопки 'Ввести имя'."""
    username = update.message.text
    await _perform_search(update, context, username)
    return CHOOSING_ACTION # Возвращаемся к выбору действий

async def _perform_search(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str):
    """Общая функция для выполнения поиска Sherlock."""
    if not username:
        await update.message.reply_text("Пожалуйста, введите имя пользователя.", reply_markup=markup)
        return

    await update.message.reply_text(f"Начинаю поиск по имени пользователя: {username}...", reply_markup=markup)

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
        await update.message.reply_text(f"Произошла ошибка при поиске. Подробности в логах сервера.", reply_markup=markup)

def main() -> None:
    """Запускает бота."""
    # Создаем Application и передаем ему токен вашего бота.
    application = Application.builder().token(TOKEN).build()

    # Создаем ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_ACTION: [
                MessageHandler(filters.Regex(f"^{KEYBOARD_INPUT_NAME}$"), request_username_input),
                MessageHandler(filters.Regex(f"^{KEYBOARD_DESCRIPTION}$"), show_description),
                MessageHandler(filters.Regex(f"^{KEYBOARD_DEVELOPER}$"), show_developer_info),
                # Обработчик для прямого ввода имени пользователя без нажатия кнопки
                MessageHandler(filters.TEXT & ~filters.COMMAND, search_username_direct),
            ],
            TYPING_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, search_username_conversation)
            ],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("help", help_command)],
    )

    application.add_handler(conv_handler)
    # Добавляем CommandHandler для /help отдельно, чтобы он работал всегда
    application.add_handler(CommandHandler("help", help_command))


    # Запускаем бота до тех пор, пока пользователь не нажмет Ctrl-C
    logger.info("Бот запускается...")
    application.run_polling()
    logger.info("Бот остановлен.")

if __name__ == "__main__":
    main()
