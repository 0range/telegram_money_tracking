import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import asyncio
import random
import string
from config import Config
from typing import Union
import uuid
import pytz
from collections import defaultdict

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
dp = Dispatcher(storage=MemoryStorage())

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

# Класс для хранения состояний
class EditExpense(StatesGroup):
    SELECT_FIELD = State()
    ENTER_NEW_VALUE = State()

# Добавляем состояния статистики
class StatsPeriod(StatesGroup):
    WAITING_PERIOD = State()

# Главное меню
def get_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Записать расход")],
            [KeyboardButton(text="Посмотреть статистику")],
            [KeyboardButton(text="Последние траты")],  # Новая кнопка
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
# Обновляем клавиатуру выбора типа статистики
def get_stats_type_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Личная статистика", callback_data="stats_personal")],
            [InlineKeyboardButton(text="Семейная статистика", callback_data="stats_family")],
            [InlineKeyboardButton(text="Вся", callback_data="stats_all")]
        ]
    )

# Клавиатура выбора периода
def get_period_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="За неделю", callback_data="week")],
            [InlineKeyboardButton(text="За месяц", callback_data="month")]
        ]
    )

# Добавить в раздел с клавиатурами -- клавиатура пропуска комментария после ввода суммы
def get_skip_comment_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="skip_comment")]
        ]
    )

# Добавить в раздел клавиатур -- клавиатура редактирования траты
def get_expense_actions_keyboard(expense_id: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_{expense_id}")#,
                #InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_{expense_id}")
            ]
        ]
    )

def get_edit_fields_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Категория", callback_data="category")],
            [InlineKeyboardButton(text="Сумма", callback_data="amount")],
            [InlineKeyboardButton(text="Комментарий", callback_data="comment")]
        ]
    )

# Функция для экранирования специальных символов
def escape_markdown(text):
    # Экранируем символы, которые могут нарушать форматирование Markdown
    escape_chars = r"\_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

def get_user_sheet(user_id):
    try:
        sheet = spreadsheet.worksheet(str(user_id))
        # Проверяем наличие колонки ID
        if sheet.row_values(1)[0] != "ID":
            sheet.insert_cols([{"values": ["ID"]}], 1)  # Добавляем колонку ID в начало
        return sheet
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=str(user_id), rows=100, cols=11)
        sheet.append_row(["ID", "Дата", "Категория", "Сумма", "Теги", "Тип", "Комментарий"])
        return sheet

def get_family_sheet(family_id):
    try:
        sheet = spreadsheet.worksheet(family_id)
        if sheet.row_values(1)[0] != "ID":
            sheet.insert_cols([{"values": ["ID"]}], 1)
        return sheet
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
    #print(user_data)
    
    # Подтверждаем обработку callback
    await query.answer()

@dp.message(lambda message: message.text.replace('.', '').isdigit())
async def handle_amount(message: Message):
    user_id = message.from_user.id
    amount = float(message.text)
    
    # Сохраняем сумму в временных данных пользователя
    user_data[user_id]["amount"] = amount
    
    # Логи
    #print(user_data)

    # Запрашиваем тип траты
    await message.reply(
        "Выберите тип траты:",
        reply_markup=get_expense_type_keyboard()
    )

@dp.callback_query(lambda query: query.data in ["personal", "family"])
async def handle_expense_type(query: CallbackQuery):
    user_id = query.from_user.id
    expense_type = query.data
    user_data[user_id] = {
        "category": user_data.get(user_id, {}).get("category"),
        "amount": user_data.get(user_id, {}).get("amount"),
        "expense_type": expense_type,
        "awaiting_comment": True  # Флаг ожидания комментария
    }
    
    await query.message.answer(
        "Введите комментарий к трате:",
        reply_markup=get_skip_comment_keyboard()  # Кнопка "Пропустить"
    )
    await query.answer()

@dp.callback_query(lambda query: query.data == "skip_comment")
async def handle_skip_comment(query: CallbackQuery):
    user_id = query.from_user.id
    user_data[user_id]["comment"] = ""  # Пустой комментарий
    await process_expense(user_id, query.message)
    await query.answer()

@dp.message(lambda message: user_data.get(message.from_user.id, {}).get("awaiting_comment"))
async def handle_comment(message: Message):
    user_id = message.from_user.id
    user_data[user_id]["comment"] = message.text.strip()
    await process_expense(user_id, message)

async def process_expense(user_id: int, message: Union[Message, CallbackQuery]):
    data = user_data.get(user_id, {})
    comment = data.get("comment", "")
    expense_id = str(uuid.uuid4())  # Генерируем UUID
    
    try:
        if data["expense_type"] == "personal":
            sheet = get_user_sheet(user_id)
            row = [
                expense_id,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                data["category"],
                data["amount"],
                "",  # Теги
                "Личная",
                comment  # Комментарий
            ]
            sheet.append_row(row)
            
        elif data["expense_type"] == "family":
            families_list = setup_families_list()
            family_id = next(
                (r["family_id"] for r in families_list.get_all_records() 
                if str(user_id) == str(r["user_id"])), None
            )
            
            if family_id:
                logger.info(f"Найдена семья: {family_id}")  # <--- Логируем family_id
                family_sheet = get_family_sheet(f"family-{family_id}")
                if family_sheet:
                    logger.info(f"Лист семьи найден: {family_sheet.title}") 
                    row = [
                        expense_id,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        data["category"],
                        data["amount"],
                        "",  # Теги
                        "Семейная",
                        str(user_id),
                        comment  # Комментарий
                    ]
                    family_sheet.append_row(row)
                else:
                    logger.error("Лист семьи не найден!")  # <--- Ошибка
            else:
                logger.warning("Пользователь не состоит в семье!")  # <--- Предупреждение
        
        # Очистка данных и возврат в меню
        del user_data[user_id]
        #print(data)
        category_p = data["category"]
        amount_p = data["amount"]
        expense_type_p = data["expense_type"]
        await message.answer(
            f"✅ Трата сохранена! Категория: {category_p} Сумма: {amount_p} Тип: {expense_type_p} Комментарий: {comment if comment else 'нет'}",
            reply_markup=get_main_menu()
        )
        
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        await message.answer("❌ Ошибка, попробуйте снова", reply_markup=get_main_menu())

@dp.message(lambda message: message.text == "Посмотреть статистику")
async def show_stats_menu(message: Message):
    await message.reply(
        "Выберите тип статистики:",
        reply_markup=get_stats_type_keyboard()
    )

# Общая функция расчета статистики
async def calculate_stats(user_id: int, stats_type: str, start_date: datetime.date, end_date: datetime.date):
    stats = defaultdict(float)
    
    # Личные траты
    if stats_type in ["stats_personal", "stats_all"]:
        personal_sheet = get_user_sheet(user_id)
        records = personal_sheet.get_all_records()
        for record in records:
            record_date = datetime.strptime(record["Дата"], "%Y-%m-%d %H:%M:%S").date()
            if start_date <= record_date <= end_date:
                stats[record["Категория"]] += float(record["Сумма"])
    
    # Семейные траты
    if stats_type in ["stats_family", "stats_all"]:
        families_list = setup_families_list()
        for family in filter(lambda r: str(user_id) == str(r["user_id"]), families_list.get_all_records()):
            family_sheet = get_family_sheet(f"family-{family['family_id']}")
            if family_sheet:
                records = family_sheet.get_all_records()
                for record in records:
                    record_date = datetime.strptime(record["Дата"], "%Y-%m-%d %H:%M:%S").date()
                    if start_date <= record_date <= end_date:
                        stats[record["Категория"]] += float(record["Сумма"])
    
    return stats

# Обработчик выбора типа статистики
@dp.callback_query(lambda query: query.data in ["stats_personal", "stats_family", "stats_all"])
async def handle_stats_type(query: CallbackQuery, state: FSMContext):
    await state.update_data(stats_type=query.data)
    await query.message.answer(
        "Выберите период:",
        reply_markup=get_period_keyboard()
    )
    await state.set_state(StatsPeriod.WAITING_PERIOD)
    await query.answer()

# Обработчик выбора периода
@dp.callback_query(StatsPeriod.WAITING_PERIOD, lambda query: query.data in ["week", "month"])
async def handle_stats_period(query: CallbackQuery, state: FSMContext):
    user_id = query.from_user.id
    data = await state.get_data()
    stats_type = data["stats_type"]
    period = query.data

    try:
        # Определяем даты периода
        today = datetime.now(pytz.timezone('Europe/Moscow')).date()
        
        if period == "week":
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
            period_title = f"неделю ({start_date:%d.%m} - {end_date:%d.%m})"
        else:
            start_date = today.replace(day=1)
            end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            period_title = f"месяц ({start_date:%m.%Y})"

        # Получаем статистику
        #print(user_id,stats_type,start_date,end_date)
        stats = await calculate_stats(
            user_id=user_id,
            stats_type=stats_type,
            start_date=start_date,
            end_date=end_date
        )

        # Формируем сообщение
        message = f"📊 *Статистика за {period_title}*\n\n"
        for category, amount in stats.items():
            message += f"{category}: {amount:.2f} руб.\n"
        message += f"\n💵 *Итого:* {sum(stats.values()):.2f} руб."

        await query.message.answer(message, parse_mode="Markdown")
    
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        await query.answer("❌ Не удалось сформировать отчет")

    await state.clear()
    await query.answer()

# Обновленная функция для получения последних трат
async def get_last_expenses(user_id: int, limit: int = 5):
    expenses = []
    seen_ids = set()  # Множество для отслеживания уникальных ID

    # Личные траты
    personal_sheet = get_user_sheet(user_id)
    personal_records = personal_sheet.get_all_records()
    for record in personal_records:
        if record["ID"] not in seen_ids:
            seen_ids.add(record["ID"])
            expenses.append({
                "id": record["ID"],
                "type": "personal",
                "data": record
            })

    # Семейные траты
    families_list = setup_families_list()
    user_families = {r["family_id"] for r in families_list.get_all_records() if str(r["user_id"]) == str(user_id)}
    
    for family_id in user_families:
        family_sheet = get_family_sheet(f"family-{family_id}")
        if family_sheet:
            family_records = family_sheet.get_all_records()
            for record in family_records:
                if record["ID"] not in seen_ids:
                    seen_ids.add(record["ID"])
                    expenses.append({
                        "id": record["ID"],
                        "type": "family",
                        "data": record
                    })

    # Сортировка и ограничение
    expenses.sort(
        key=lambda x: datetime.strptime(x["data"]["Дата"], "%Y-%m-%d %H:%M:%S"),
        reverse=True
    )
    return expenses[:limit]

# Обновленный обработчик последних трат
@dp.message(lambda message: message.text == "Последние траты")
async def show_last_expenses(message: Message):
    user_id = message.from_user.id
    expenses = await get_last_expenses(user_id)
    
    if not expenses:
        await message.answer("📭 У вас пока нет записанных трат.")
        return
    
    for expense in expenses:
        emoji = "👤" if expense["type"] == "personal" else "👨👩👧👦"
        text = (
            f"{emoji} *{'Личная' if expense['type'] == 'personal' else 'Семейная'} трата*\n"
            f"🗓 {expense['data']['Дата']}\n"
            f"🏷 {expense['data']['Категория']}\n"
            f"💵 {expense['data']['Сумма']} руб.\n"
            f"📝 {expense['data'].get('Комментарий', 'нет комментария')}"
        )
        
        callback_data = f"delete_{expense['id']}"
        
        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(
                    text="❌ Удалить", 
                    callback_data=callback_data
                )]]
            ),
            parse_mode="Markdown"
        )

# Обновленный обработчик удаления
@dp.callback_query(lambda query: query.data.startswith("delete_"))
async def handle_delete_expense(query: CallbackQuery):
    try:
        expense_id = query.data.split("_")[1]
        
        # Ищем трату во всех листах пользователя
        user_id = query.from_user.id
        
        # 1. Проверяем личные траты
        personal_sheet = get_user_sheet(user_id)
        cell = personal_sheet.find(expense_id)
        if cell:
            personal_sheet.delete_rows(cell.row)
            await query.message.edit_text("✅ Личная трата удалена!")
            return
        
        # 2. Проверяем семейные траты
        families_list = setup_families_list()
        user_families = [
            r["family_id"] for r in families_list.get_all_records() 
            if str(r["user_id"]) == str(user_id)
        ]
        
        for family_id in user_families:
            family_sheet = get_family_sheet(f"family-{family_id}")
            if not family_sheet:
                continue
            cell = family_sheet.find(expense_id)
            if cell:
                family_sheet.delete_rows(cell.row)
                await query.message.edit_text("✅ Семейная трата удалена!")
                return
        
        # Если не найдено
        await query.answer("❌ Трата не найдена")
    
    except Exception as e:
        logger.error(f"Ошибка удаления: {e}")
        await query.answer("❌ Ошибка при удалении")

# Обработчик редактирования
@dp.callback_query(lambda query: query.data.startswith("edit_"), EditExpense.SELECT_FIELD)
async def handle_edit_expense(query: CallbackQuery, state: FSMContext):
    expense_id = query.data.split("_")[1]
    await state.update_data(expense_id=expense_id)
    
    await query.message.answer(
        "Выберите поле для редактирования:",
        reply_markup=get_edit_fields_keyboard()
    )
    await state.set_state(EditExpense.SELECT_FIELD)
    await query.answer()

# Обработчик выбора поля
@dp.callback_query(EditExpense.SELECT_FIELD)
async def handle_select_field(query: CallbackQuery, state: FSMContext):
    field = query.data
    await state.update_data(field=field)
    await query.message.answer("Введите новое значение:")
    await state.set_state(EditExpense.ENTER_NEW_VALUE)
    await query.answer()

# Обработчик ввода нового значения
@dp.message(EditExpense.ENTER_NEW_VALUE)
async def handle_new_value(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    
    try:
        sheet = get_user_sheet(user_id)
        row = int(data['expense_id'])
        col = {
            "category": 2,  # B столбец
            "amount": 3,    # C столбец
            "comment": 6     # F столбец
        }[data['field']]
        
        # Обновляем ячейку
        sheet.update_cell(row, col, message.text)
        await message.answer("✅ Трата обновлена!")
    except Exception as e:
        logger.error(f"Ошибка редактирования: {e}")
        await message.answer("❌ Не удалось обновить трату")
    
    await state.clear()

@dp.message()
async def handle_unknown(message: Message):
    await message.reply("Пожалуйста, выберите действие из меню.", reply_markup=get_main_menu())

# Функция для отправки ежедневного напоминания
async def send_daily_reminder(bot: Bot):
    msk = pytz.timezone('Europe/Moscow')  # Московский часовой пояс
    
    while True:
        now = datetime.now(msk)  # Текущее время в МСК
        target_time = now.replace(hour=21, minute=0, second=0, microsecond=0, tzinfo=msk)
        
        # Если текущее время позже целевого, переносим на завтра
        if now > target_time:
            target_time += timedelta(days=1)
        
        # Ждем до целевого времени
        wait_seconds = (target_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        
        # Текущая дата в МСК
        today = now.strftime("%Y-%m-%d")
        
        # Проверяем все листы
        for worksheet in spreadsheet.worksheets():
            # Пропускаем семейные и нечисловые листы
            if worksheet.title.startswith('family-') or not worksheet.title.isdigit():
                continue
            
            try:
                user_id = int(worksheet.title)
                records = worksheet.get_all_records()
                
                # Пропускаем пустые листы или без колонки "Дата"
                if not records or "Дата" not in records[0]:
                    continue
                
                # Ищем сегодняшние траты
                today_expenses = [
                    record for record in records 
                    if record.get("Дата", "").startswith(today)
                ]
                
                # Отправляем уведомление, если трат нет
                if not today_expenses:
                    await bot.send_message(
                        chat_id=user_id,
                        text="Неужели ничего не потратили? Давайте вспомним и запишем основные категории.",
                        reply_markup=get_categories_keyboard()
                    )
                    
            except Exception as e:
                logger.error(f"Ошибка у пользователя {worksheet.title}: {str(e)}")

# Функция для отправки еженедельного напоминания
async def send_weekly_reminder(bot: Bot):
    msk = pytz.timezone('Europe/Moscow')  # Часовой пояс Москвы
    
    while True:
        now = datetime.now(msk)  # Текущее время в МСК
        target_time = now.replace(hour=11, minute=0, second=0, microsecond=0, tzinfo=msk)
        
        # Вычисляем дни до следующего воскресенья
        days_until_sunday = (6 - now.weekday()) % 7  # 6 - воскресенье в Python
        
        # Если сегодня воскресенье и время уже прошло:
        if days_until_sunday == 0 and now > target_time:
            days_until_sunday = 7  # Ждем следующее воскресенье
        
        target_time += timedelta(days=days_until_sunday)
        
        # Если target_time всё равно в прошлом (например, из-за перехода на летнее время)
        if target_time < now:
            target_time += timedelta(days=7)
        
        # Ждем до целевого времени
        wait_seconds = (target_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        
        # Отправка уведомлений...
        for worksheet in spreadsheet.worksheets():
            if worksheet.title.startswith('family-'):
                continue
            
            user_id = worksheet.title
            try:
                await bot.send_message(
                    chat_id=int(user_id),
                    text="Все траты за неделю записаны? Время посмотреть статистику!",
                    reply_markup=get_main_menu()
                )
            except Exception as e:
                logger.error(f"Ошибка отправки: {user_id} - {e}")

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
