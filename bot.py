import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import asyncio
import random
import string
from config import Config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),  # Логи записываются в файл bot.log
        logging.StreamHandler()  # Логи выводятся в консоль
    ]
)
logger = logging.getLogger(__name__)

# Настройки
GOOGLE_SHEETS_CREDS = 'creds.json'  # Путь к JSON-ключу

# Подключение к Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_CREDS, scope)
client = gspread.authorize(creds)
spreadsheet = client.open_by_url(Config.SPREADSHEET_URL)

# Инициализация бота
bot = Bot(
    token=Config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)  # Указываем parse_mode здесь
)
dp = Dispatcher()

# Словарь для хранения временных данных пользователя
user_data = {}

# Обновленный список категорий
CATEGORIES = [
    "🍔 Еда вне дома",
    "🛒 Продукты",
    "🎮 Развлечения",
    "👕 Одежда",
    "✈️ Путешествия",
    "🧠 Психология/Обучение",
    "🏃‍♀️ Здоровье/Спорт",
    "👶 Дети",
    "👵 Родители",
    "🎁 Подарки",
    "🚗 Транспорт",
    "🏠 Жилье",
    "💳 Кредиты",
    "💰 Откладываем",
    "💵 Алименты",
    "⚡️ Маркетплейсы",
    "💼 Прочее"
]

# Главное меню
def get_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Записать расход")],
            [KeyboardButton(text="Посмотреть статистику")],
            [KeyboardButton(text="Создать семью"), KeyboardButton(text="Вступить в семью")]
        ],
        resize_keyboard=True  # Клавиатура подстраивается под размер экрана
    )
    return keyboard

# Лист со списком семей
def setup_families_list():
    try:
        return spreadsheet.worksheet("families_list")
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title="families_list", rows=100, cols=3)
        worksheet.append_row(["family_id", "user_id", "role"])
        return worksheet

# Inline-клавиатура с категориями
def get_categories_keyboard():
    keyboard = []
    for i in range(0, len(CATEGORIES), 2):
        row = []
        row.append(InlineKeyboardButton(
            text=CATEGORIES[i], 
            callback_data=CATEGORIES[i]
        ))
        if i+1 < len(CATEGORIES):
            row.append(InlineKeyboardButton(
                text=CATEGORIES[i+1], 
                callback_data=CATEGORIES[i+1]
            ))
        keyboard.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Клавиатура для ввода суммы (нативная числовая клавиатура)
def get_amount_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[],  # Пустой список кнопок
        resize_keyboard=True,  # Клавиатура подстраивается под размер экрана
        input_field_placeholder="Введите сумму"  # Подсказка в поле ввода
    )
    return keyboard

# Inline-клавиатура для выбора типа траты (личная/семейная)
def get_expense_type_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Личная", callback_data="personal")],
            [InlineKeyboardButton(text="Семейная", callback_data="family")]
        ]
    )
    return keyboard

# Inline-клавиатура для выбора типа статистики
def get_stats_type_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Личная", callback_data="personal_stats")],
            [InlineKeyboardButton(text="Семейная", callback_data="family_stats")],
            [InlineKeyboardButton(text="Вся моя", callback_data="all_stats")]
        ]
    )
    return keyboard

# Функция для экранирования специальных символов
def escape_markdown(text):
    # Экранируем символы, которые могут нарушать форматирование Markdown
    escape_chars = r"\_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

def get_user_sheet(user_id):
    try:
        return spreadsheet.worksheet(str(user_id))
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=str(user_id), rows=100, cols=10)
        worksheet.append_row(["Дата", "Категория", "Сумма", "Теги", "Тип"])
        return worksheet

def get_family_sheet(family_id):
    try:
        return spreadsheet.worksheet(family_id)
    except gspread.WorksheetNotFound:
        return None

def generate_family_id():
    # Генерация случайного идентификатора семьи (6 символов)
    chars = string.ascii_letters + string.digits
    return 'family-' + ''.join(random.choice(chars) for _ in range(6))

@dp.message(Command("start"))
async def send_welcome(message: Message):
    user_id = message.from_user.id
    get_user_sheet(user_id)  # Создаем лист при первом обращении
    await message.reply(
        "Добро пожаловать! 🤑\nВыберите действие:",
        reply_markup=get_main_menu()
    )

@dp.message(lambda message: message.text == "Создать семью")
async def create_family(message: Message):
    user_id = message.from_user.id

    # Проверяем, не состоит ли пользователь уже в семье
    families_list = setup_families_list()
    records = families_list.get_all_records()
    if any(str(user_id) == record.get("user_id") for record in records):
        await message.reply("Вы уже состоите в семье. Создание новой семьи невозможно.")
        return

    # Генерация идентификатора семьи
    family_id = generate_family_id()

    # Создание листа для семьи
    try:
        family_sheet = spreadsheet.add_worksheet(title=f"family-{family_id}", rows=100, cols=10)
        family_sheet.append_row(["Дата", "Категория", "Сумма", "Теги", "Тип", "user_id"])
        
        # Добавляем создателя семьи в families_list
        families_list.append_row([family_id, str(user_id), "creator"])
        logger.info(f"Семья создана: {family_id}, создатель: {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при создании семьи: {e}")
        await message.reply("❌ Произошла ошибка при создании семьи. Пожалуйста, попробуйте позже.")
        return

    await message.reply(f"Семья успешно создана! 🎉\nИдентификатор вашей семьи: `{family_id}`\nПоделитесь этим идентификатором с другими участниками.")

@dp.message(lambda message: message.text == "Вступить в семью")
async def join_family(message: Message):
    user_id = message.from_user.id

    # Проверяем, не состоит ли пользователь уже в семье
    for sheet in spreadsheet.worksheets():
        if sheet.title.startswith('family-'):
            records = sheet.get_all_records()
            if any(record.get("user_id") == str(user_id) for record in records):
                await message.reply("Вы уже состоите в семье.")
                return

    await message.reply("Введите идентификатор семьи:")

@dp.message(lambda message: message.text.startswith('family-'))
async def handle_family_id(message: Message):
    user_id = message.from_user.id
    family_id = message.text

    # Проверяем, существует ли такая семья
    families_list = setup_families_list()
    records = families_list.get_all_records()
    if not any(family_id == record.get("family_id") for record in records):
        await message.reply("Семья с таким идентификатором не найдена. Пожалуйста, проверьте идентификатор и попробуйте снова.")
        return

    # Проверяем, не состоит ли пользователь уже в семье
    if any(str(user_id) == record.get("user_id") for record in records):
        await message.reply("Вы уже состоите в семье.")
        return

    # Добавляем пользователя в семью
    try:
        families_list.append_row([family_id, str(user_id), "member"])
        logger.info(f"Пользователь {user_id} вступил в семью {family_id}")
    except Exception as e:
        logger.error(f"Ошибка при вступлении в семью: {e}")
        await message.reply("❌ Произошла ошибка при вступлении в семью. Пожалуйста, попробуйте позже.")
        return

    await message.reply("Вы успешно вступили в семью! 🎉")

@dp.message(lambda message: message.text == "Записать расход")
async def start_add_expense(message: Message):
    await message.reply(
        "Выберите категорию:",
        reply_markup=get_categories_keyboard()
    )

@dp.callback_query(lambda query: query.data in CATEGORIES)
async def handle_category(query: CallbackQuery):
    # Сохраняем выбранную категорию в словаре user_data
    user_id = query.from_user.id
    category = query.data
    user_data[user_id] = {"category": category}  # Сохраняем категорию
    
    # Отправляем сообщение с запросом суммы и включаем числовую клавиатуру
    await query.message.answer(
        f"Вы выбрали категорию: {category}\nТеперь введите сумму:",
        reply_markup=get_amount_keyboard(),
        parse_mode=None  # Отключаем форматирование Markdown
    )

    # Логи
    print(user_data)
    
    # Подтверждаем обработку callback
    await query.answer()

@dp.message(lambda message: message.text.replace('.', '').isdigit())
async def handle_amount(message: Message):
    user_id = message.from_user.id
    amount = float(message.text)
    
    # Сохраняем сумму в временных данных пользователя
    user_data[user_id]["amount"] = amount
    
    # Логи
    print(user_data)

    # Запрашиваем тип траты
    await message.reply(
        "Выберите тип траты:",
        reply_markup=get_expense_type_keyboard()
    )

@dp.callback_query(lambda query: query.data in ["personal", "family"])
async def handle_expense_type(query: CallbackQuery):
    user_id = query.from_user.id
    expense_type = query.data
    amount = user_data.get(user_id, {}).get("amount", 0)
    
    try:
        # Получаем категорию из временных данных пользователя
        category = user_data.get(user_id, {}).get("category", "💼 Прочее")  # Используем сохраненную категорию
        
        if expense_type == "personal":
            # Личная трата: сохраняем в личный лист пользователя
            sheet = get_user_sheet(user_id)
            row = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                category,  # Используем сохраненную категорию
                amount,
                "",  # Теги можно добавить позже
                "Личная"  # Тип траты
            ]
            sheet.append_row(row)
            logger.info(f"Личная трата добавлена: пользователь {user_id}, категория {category}, сумма {amount}")
            await query.message.answer(
                f"✅ Личная трата: {category} - {amount} руб. добавлена!",
                reply_markup=get_main_menu(),
                parse_mode=None  # Отключаем форматирование Markdown
            )
        
        elif expense_type == "family":
            # Семейная трата: сохраняем в лист семьи
            families_list = setup_families_list()
            records = families_list.get_all_records()
            family_id = None
            
            # Ищем family_id, в которой состоит пользователь
            for record in records:
                if str(user_id) == str(record.get("user_id")):
                    family_id = record.get("family_id")
                    break
            
            if family_id:
                # Получаем лист семьи
                family_sheet = get_family_sheet(f"family-{family_id}")
                if family_sheet:
                    row = [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        category,  # Используем сохраненную категорию
                        amount,
                        "",  # Теги можно добавить позже
                        str(user_id),  # user_id пользователя, который внес трату
                        "Семейная"  # Тип траты
                    ]
                    family_sheet.append_row(row)
                    logger.info(f"Семейная трата добавлена: пользователь {user_id}, категория {category}, сумма {amount}")
                    await query.message.answer(
                        f"✅ Семейная трата: {category} - {amount} руб. добавлена!",
                        reply_markup=get_main_menu(),
                        parse_mode=None  # Отключаем форматирование Markdown
                    )
                else:
                    logger.error(f"Лист семьи {family_id} не найден")
                    await query.message.answer(
                        "❌ Произошла ошибка при записи траты. Пожалуйста, попробуйте позже.",
                        reply_markup=get_main_menu(),
                        parse_mode=None  # Отключаем форматирование Markdown
                    )
            else:
                logger.warning(f"Пользователь {user_id} не состоит в семье, но попытался добавить семейную трату")
                await query.message.answer(
                    "❌ Вы не состоите в семье. Невозможно добавить семейную трату.",
                    reply_markup=get_main_menu(),
                    parse_mode=None  # Отключаем форматирование Markdown
                )
        
        # Очищаем временные данные пользователя
        user_data.pop(user_id, None)
    
    except Exception as e:
        logger.error(f"Ошибка при записи траты: {e}")
        await query.message.answer(
            "❌ Произошла ошибка при записи траты. Пожалуйста, попробуйте позже.",
            reply_markup=get_main_menu(),
            parse_mode=None  # Отключаем форматирование Markdown
        )
    
    await query.answer()

@dp.message(lambda message: message.text == "Посмотреть статистику")
async def show_stats_menu(message: Message):
    await message.reply(
        "Выберите тип статистики:",
        reply_markup=get_stats_type_keyboard()
    )

@dp.callback_query(lambda query: query.data in ["personal_stats", "family_stats", "all_stats"])
async def handle_stats_type(query: CallbackQuery):
    user_id = query.from_user.id
    stats_type = query.data
    
    # Получаем текущий месяц
    current_month = datetime.now().strftime("%Y-%m")
    
    # Словарь для хранения статистики
    stats = {}
    total = 0
    
    try:
        if stats_type == "personal_stats":
            # Личная статистика: только личные траты пользователя
            sheet = get_user_sheet(user_id)
            records = sheet.get_all_records()
            monthly_expenses = [record for record in records if record["Дата"].startswith(current_month) and record.get("Тип") == "Личная"]
            
            for record in monthly_expenses:
                category = record["Категория"]
                amount = float(record["Сумма"])
                stats[category] = stats.get(category, 0) + amount
                total += amount
        
        elif stats_type == "family_stats":
            # Семейная статистика: только общие траты семьи
            families_list = setup_families_list()
            records = families_list.get_all_records()
            family_id = None
            
            # Логируем все записи из families_list для отладки
            logger.info(f"Записи в families_list: {records}")
            
            # Ищем family_id, в которой состоит пользователь
            for record in records:
                if str(user_id) == str(record.get("user_id")):
                    family_id = record.get("family_id")
                    break
            
            if family_id:
                # Получаем лист семьи
                family_sheet = get_family_sheet(f"family-{family_id}")
                if family_sheet:
                    records = family_sheet.get_all_records()
                    monthly_expenses = [record for record in records if record["Дата"].startswith(current_month)]
                    
                    for record in monthly_expenses:
                        category = record["Категория"]
                        amount = float(record["Сумма"])
                        stats[category] = stats.get(category, 0) + amount
                        total += amount
                else:
                    logger.error(f"Лист семьи {family_id} не найден")
                    await query.message.answer("❌ Произошла ошибка при расчете статистики. Пожалуйста, попробуйте позже.", reply_markup=get_main_menu())
                    return
            else:
                logger.warning(f"Пользователь {user_id} не состоит в семье, но запросил семейную статистику")
                await query.message.answer("❌ Вы не состоите в семье. Невозможно показать семейную статистику.", reply_markup=get_main_menu())
                return
        
        elif stats_type == "all_stats":
            # Вся моя статистика: личные + общие траты
            # Личные траты
            sheet = get_user_sheet(user_id)
            records = sheet.get_all_records()
            monthly_expenses = [record for record in records if record["Дата"].startswith(current_month) and record.get("Тип") == "Личная"]
            
            for record in monthly_expenses:
                category = record["Категория"]
                amount = float(record["Сумма"])
                stats[category] = stats.get(category, 0) + amount
                total += amount
            
            # Общие траты
            families_list = setup_families_list()
            records = families_list.get_all_records()
            family_id = None
            
            # Ищем family_id, в которой состоит пользователь
            for record in records:
                if str(user_id) == str(record.get("user_id")):
                    family_id = record.get("family_id")
                    break
            
            if family_id:
                # Получаем лист семьи
                family_sheet = get_family_sheet(f"family-{family_id}")
                if family_sheet:
                    records = family_sheet.get_all_records()
                    monthly_expenses = [record for record in records if record["Дата"].startswith(current_month)]
                    
                    for record in monthly_expenses:
                        category = record["Категория"]
                        amount = float(record["Сумма"])
                        stats[category] = stats.get(category, 0) + amount
                        total += amount
        
        # Формируем сообщение со статистикой
        if stats:
            stats_message = f"📊 Статистика ({stats_type}) за текущий месяц ({current_month}):\n"
            for category, sum_amount in stats.items():
                stats_message += f"{category}: {sum_amount:.2f} руб.\n"
            stats_message += f"\n💵 Общая сумма: {total:.2f} руб."
        else:
            stats_message = f"📊 Нет данных ({stats_type}) за текущий месяц ({current_month})."
        
        # Отправляем сообщение без форматирования Markdown
        await query.message.answer(stats_message, reply_markup=get_main_menu(), parse_mode=None)
    
    except Exception as e:
        logger.error(f"Ошибка при расчете статистики: {e}")
        await query.message.answer("❌ Произошла ошибка при расчете статистики. Пожалуйста, попробуйте позже.", reply_markup=get_main_menu())
    
    await query.answer()

@dp.message()
async def handle_unknown(message: Message):
    await message.reply("Пожалуйста, выберите действие из меню.", reply_markup=get_main_menu())

# Функция для отправки ежедневного напоминания
async def send_daily_reminder(bot: Bot):
    while True:
        now = datetime.now()
        target_time = now.replace(hour=21, minute=0, second=0, microsecond=0)  # 21:00 МСК
        if now > target_time:
            target_time += timedelta(days=1)  # На следующий день
        time_to_wait = (target_time - now).total_seconds()
        await asyncio.sleep(time_to_wait)

        # Проверяем, были ли сегодня траты
        for worksheet in spreadsheet.worksheets():
            if worksheet.title.startswith('family-'):
                # Пропускаем листы семьи, так как напоминания отправляются только для личных трат
                continue
            
            user_id = worksheet.title
            records = worksheet.get_all_records()
            today = datetime.now().strftime("%Y-%m-%d")
            today_expenses = [record for record in records if record["Дата"].startswith(today)]

            if not today_expenses:
                try:
                    await bot.send_message(
                        chat_id=int(user_id),
                        text="Неужели ничего не потратили? Давайте вспомним и запишем основные категории.",
                        reply_markup=get_categories_keyboard()
                    )
                except Exception as e:
                    logger.error(f"Ошибка при отправке ежедневного напоминания пользователю {user_id}: {e}")

# Функция для отправки еженедельного напоминания
async def send_weekly_reminder(bot: Bot):
    while True:
        now = datetime.now()
        target_time = now.replace(hour=11, minute=0, second=0, microsecond=0)  # 11:00 МСК
        if now > target_time:
            target_time += timedelta(days=(7 - now.weekday()))  # Следующее воскресенье
        time_to_wait = (target_time - now).total_seconds()
        await asyncio.sleep(time_to_wait)

        # Отправляем напоминание
        for worksheet in spreadsheet.worksheets():
            if worksheet.title.startswith('family-'):
                # Пропускаем листы семьи, так как напоминания отправляются только для личных трат
                continue
            
            user_id = worksheet.title
            try:
                await bot.send_message(
                    chat_id=int(user_id),
                    text="Все траты за неделю записаны? Время посмотреть статистику!",
                    reply_markup=get_main_menu()
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке еженедельного напоминания пользователю {user_id}: {e}")

# Запуск планировщика
async def scheduler(bot: Bot):
    asyncio.create_task(send_daily_reminder(bot))
    asyncio.create_task(send_weekly_reminder(bot))

# Запуск бота
async def main():
    await scheduler(bot)  # Запускаем планировщик
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
