import datetime
import logging
import asyncio
import re
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
import pyodbc


# Налаштування бота
API_TOKEN = '8014449080:AAH8imK7L9uE7nJgzo3wykZmorTp4LRiZV0'
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# Параметри підключення до SQL Server
DB_CONFIG = {
    "DRIVER": "{ODBC Driver 17 for SQL Server}",
    "SERVER": "192.168.152.131",
    "DATABASE": "forKursova",
    "UID": "SA",
    "PWD": "Vlad09876Mouse"
}

def create_game_keyboard(game_id: int, game_title: str) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text="Оцінити гру", callback_data=f"rate_game:{game_id}"))
    return keyboard

@router.callback_query(lambda c: c.data and c.data.startswith("rate_game"))
async def rate_game_handler(callback_query: CallbackQuery, state: FSMContext):
    game_id = int(callback_query.data.split(":")[1])
    await callback_query.message.answer(
        "Оцініть гру за шкалою від 1 до 5. Введіть число.",
        reply_markup=InlineKeyboardBuilder().as_markup()
    )
    # Зберігаємо стан для отримання рейтингу
    await state.update_data(game_id=game_id)
    await state.set_state(RateGameState.waiting_for_rating)

@router.message(F.text.regexp(r"^[1-5](\.\d+)?$"))  # Перевірка, що введено число від 1 до 5
async def save_rating_handler(message: Message, state: FSMContext):
    user_rating = float(message.text)
    state_data = await state.get_data()
    game_id = state_data["game_id"]
    tg_user_id = message.from_user.id

    # Збереження оцінки в базу даних
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                INSERT INTO userReview (tgUserId, GameID, userRating, CreatedAt)
                VALUES (?, ?, ?, ?)
                """
                cursor.execute(query, (tg_user_id, game_id, user_rating, datetime.now()))
                conn.commit()
        await message.answer("Дякую! Вашу оцінку збережено.")
    except Exception as e:
        if "unique_review_per_user" in str(e):
            await message.answer("Ви вже оцінювали цю гру.")
        else:
            await message.answer("Сталася помилка. Спробуйте пізніше.")
    finally:
        await state.clear()

        @router.message(F.text)
        async def invalid_rating_handler(message: Message):
            await message.answer("Будь ласка, введіть число від 1 до 5.")


@router.message(F.text == "/start")
async def handle_start(message: Message):
    await message.answer("Привіт! Я бот для пошуку ігор. Використовуйте: назву гри, теги, жанри або тег + жанри для пошуку.")

# Стан для FSM
class RateGameState(StatesGroup):
    waiting_for_rating = State()

# Функція для отримання підключення до бази
def get_db_connection():
    return pyodbc.connect(
        f"DRIVER={DB_CONFIG['DRIVER']};"
        f"SERVER={DB_CONFIG['SERVER']};"
        f"DATABASE={DB_CONFIG['DATABASE']};"
        f"UID={DB_CONFIG['UID']};"
        f"PWD={DB_CONFIG['PWD']}"
    )

# CallbackData для кнопок
class RateGameCallback(CallbackData, prefix="rate_game"):
    game_id: int

# Генерація кнопок з оцінкою
def generate_game_buttons(results):
    keyboard = InlineKeyboardBuilder()
    for row in results:
        game_id, title = row[0], row[1]
        keyboard.button(
            text=f"Оцінити: {title}",
            callback_data=RateGameCallback(game_id=game_id).pack()
        )
    return keyboard.as_markup()

# Пошук за назвою гри
def get_game_info(game_title):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                SELECT GameID, Title, Genre, Tags, ReleaseYear, Rating
                FROM Games
                WHERE LOWER(Title) LIKE LOWER(?)
                """
                cursor.execute(query, f"%{game_title}%")
                results = cursor.fetchall()

                if not results:
                    return "Гра не знайдена у базі даних.", None

                response = ""
                for row in results:
                    game_id, title, genre, tags, release_year, rating = row
                    response += f"""
<b>Назва:</b> {title}
<b>Жанр:</b> {genre}
<b>Теги:</b> {tags}
<b>Рік випуску:</b> {release_year}
<b>Рейтинг:</b> {rating}
"""
                return response, results
    except Exception as e:
        logging.error(f"Помилка отримання інформації про гру: {e}")
        return "Виникла помилка під час отримання інформації.", None

# Пошук ігор за жанрами та тегами
def search_games_by_filters(genres=None, tags=None):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                SELECT GameID, Title, Genre, Tags, ReleaseYear, Rating
                FROM Games
                WHERE 1=1
                """
                params = []

                if genres:
                    genre_conditions = " OR ".join(["Genre LIKE ?"] * len(genres))
                    query += f" AND ({genre_conditions})"
                    params.extend([f"%{genre.strip()}%" for genre in genres])

                if tags:
                    tag_conditions = " OR ".join(["Tags LIKE ?"] * len(tags))
                    query += f" AND ({tag_conditions})"
                    params.extend([f"%{tag.strip()}%" for tag in tags])

                cursor.execute(query, params)
                results = cursor.fetchall()

                if not results:
                    return "Ігор за вашим запитом не знайдено.", None

                response = ""
                for row in results:
                    game_id, title, genre, tags, release_year, rating = row
                    response += f"""
<b>Назва:</b> {title}
<b>Жанр:</b> {genre}
<b>Теги:</b> {tags}
<b>Рік випуску:</b> {release_year}
<b>Рейтинг:</b> {rating}
"""
                return response, results
    except Exception as e:
        logging.error(f"Помилка пошуку ігор: {e}")
        return "Виникла помилка під час пошуку.", None

async def send_long_message(chat_id, text, keyboard=None):
    max_length = 4096
    while len(text) > max_length:
        await bot.send_message(chat_id, text[:max_length], parse_mode="HTML")
        text = text[max_length:]
    await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=keyboard)

# Збереження відгуку
def save_user_review(tg_user_id, game_id, user_rating, review=None):
    try:
        review = review if review is not None else ""
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM userReview WHERE tgUserId = ? AND GameID = ?", tg_user_id, game_id)
                exists = cursor.fetchone()

                if exists:
                    cursor.execute("""
                        UPDATE userReview
                        SET userRating = ?, review = ?
                        WHERE tgUserId = ? AND GameID = ?
                    """, user_rating, review, tg_user_id, game_id)
                else:
                    cursor.execute("""
                        INSERT INTO userReview (tgUserId, GameID, userRating, review)
                        VALUES (?, ?, ?, ?)
                    """, tg_user_id, game_id, user_rating, review)

                conn.commit()
    except Exception as e:
        logging.error(f"Помилка збереження відгуку: {e}")
        raise


# Обробка команди /review
@router.message(F.text.startswith("/review"))
async def handle_review(message: Message):
    try:
        # Використання регулярного виразу для захоплення назви гри, рейтингу та відгуку
        match = re.match(r'^/review\s+(.+?)\s+(\d(?:\.\d)?)\s*(.*)$', message.text)
        if not match:
            await message.answer("Неправильний формат. Використовуйте: /review <назва гри> <рейтинг> <коментар (необов'язково)>", parse_mode="HTML")
            return

        game_title, user_rating, review = match.groups()

        try:
            user_rating = float(user_rating)
            if not (1 <= user_rating <= 5):
                raise ValueError("Рейтинг поза допустимим діапазоном.")
        except ValueError:
            await message.answer("Рейтинг повинен бути числом від 1 до 5.", parse_mode="HTML")
            return

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT GameID FROM Games WHERE Title LIKE ?", f"%{game_title}%")
                game_id = cursor.fetchone()

        if game_id:
            save_user_review(message.from_user.id, game_id[0], user_rating, review)
            await message.answer("Дякуємо за ваш відгук!", parse_mode="HTML")
        else:
            await message.answer("Гра не знайдена у базі даних.", parse_mode="HTML")
    except Exception as e:
        logging.error(f"Помилка обробки відгуку: {e}")
        await message.answer("Виникла помилка під час обробки вашого запиту.", parse_mode="HTML")

# Обробка текстових повідомлень
@router.message(F.text)
async def fetch_game(message: Message):
    text = message.text.strip()

    # Якщо текст відповідає форматам жанру або тегів
    genres, tags = None, None
    if text.lower().startswith("жанр:"):
        genres = text[5:].split(",")
    elif text.lower().startswith("тег:"):
        tags = text[4:].split(",")
    elif text.lower().startswith("жанр і тег:"):
        parts = text[10:].split(";")
        genres = parts[0].split(",") if len(parts) > 0 else None
        tags = parts[1].split(",") if len(parts) > 1 else None
    else:
        # Пошук гри за назвою
        response, results = get_game_info(text)
        if results:
            keyboard = generate_game_buttons(results)
            await send_long_message(message.chat.id, response, keyboard)
        else:
            await message.answer(response, parse_mode="HTML")
        return

    # Пошук за жанрами або тегами
    response, results = search_games_by_filters(genres, tags)
    if results:
        keyboard = generate_game_buttons(results)
        await send_long_message(message.chat.id, response, keyboard)
    else:
        await message.answer(response, parse_mode="HTML")

# Обробка callback запитів
@router.callback_query(RateGameCallback.filter())
async def handle_rate_game(callback_query: CallbackQuery, callback_data: RateGameCallback, state: FSMContext):
    await callback_query.message.answer(f"Ви обрали гру з ID: {callback_data.game_id}. Введіть ваш рейтинг від 1 до 5:")
    await state.update_data(game_id=callback_data.game_id)
    await state.set_state(RateGameState.waiting_for_rating)

@router.message(RateGameState.waiting_for_rating)
async def process_rating(message: Message, state: FSMContext):
    try:
        user_rating = float(message.text)
        if not (1 <= user_rating <= 5):
            raise ValueError("Рейтинг поза допустимим діапазоном.")
    except ValueError:
        await message.answer("Рейтинг повинен бути числом від 1 до 5. Спробуйте ще раз.")
        return

    data = await state.get_data()
    game_id = data.get("game_id")

    if game_id:
        save_user_review(message.from_user.id, game_id, user_rating)
        await message.answer("Дякуємо за ваш рейтинг!")
        await state.clear()
    else:
        await message.answer("Гра не знайдена у базі даних.")
# Обробка команди /search
@router.message(F.text == "/search")
async def handle_search_instruction(message: Message):
    await message.answer(
        "Будь ласка, введіть запит у форматі:\n"
        "<b>жанр:</b> Action, Adventure\n"
        "<b>тег:</b> Multiplayer, Open World\n"
        "<b>жанр і тег:</b> RPG, Shooter; Online, Fantasy\n"
        "Або введіть назву гри (наприклад: GTA).",
        parse_mode="HTML"
    )


# Запуск бота
async def main():
    logging.info("Бот запущений!")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())