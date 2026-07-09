# ================= АВТОУСТАНОВКА БИБЛИОТЕК =================
import subprocess
import sys

def install_libraries():
    """Автоматическая установка необходимых библиотек"""
    required = ['aiogram', 'aiosqlite', 'aiohttp']
    
    for lib in required:
        try:
            __import__(lib)
            print(f"✅ {lib} уже установлен")
        except ImportError:
            print(f"📦 Устанавливаю {lib}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
                print(f"✅ {lib} успешно установлен!")
            except Exception as e:
                print(f"❌ Ошибка при установке {lib}: {e}")
                print("Попробуйте установить вручную: pip install " + lib)

# Запускаем установку ПЕРЕД основными импортами
print("🔍 Проверка библиотек...")
install_libraries()
print("=" * 40)

# ================= ОСНОВНЫЕ ИМПОРТЫ =================
import asyncio
import logging
import os
import shutil
import random
import string
import aiosqlite
import aiohttp
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from aiogram.client.bot import DefaultBotProperties

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8895851823:AAHTxS4dYkEWsx9ZYNnNBtuY1eMzwKFWp3Y"
BOT_USERNAME = "serialuIfilmu3_bot"  # Username бота БЕЗ @ (например: serialuifilmu3_bot)
ADMIN_IDS = [6478346332] 
BOTOHUB_TOKEN = "91bce1c4-ff71-47d1-a719-9ec85dc02e65"

PHOTO_DIR = "photos"
os.makedirs(PHOTO_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ================= СОСТОЯНИЯ (FSM) =================
class AdminStates(StatesGroup):
    waiting_folder_name = State()
    waiting_content_title = State()
    waiting_content_url = State()
    waiting_content_photo = State()
    waiting_content_description = State()
    waiting_new_title = State()
    waiting_new_url = State()
    waiting_new_photo = State()
    waiting_new_description = State()
    waiting_link_name = State()

# ================= BOTOHUB API =================
async def get_botohub_links(chat_id: int):
    url = "https://botohub.me/get-tasks"
    headers = {"Content-Type": "application/json", "Auth": BOTOHUB_TOKEN}
    data = {"chat_id": chat_id}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logging.error(f"BotoHub API error: {response.status}")
                    return None
    except Exception as e:
        logging.error(f"BotoHub API exception: {e}")
        return None

# ================= БАЗА ДАННЫХ =================
async def init_db():
    db = await aiosqlite.connect('bot.db')
    await db.execute('''CREATE TABLE IF NOT EXISTS folders 
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')
    await db.execute('''CREATE TABLE IF NOT EXISTS contents 
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, folder_id INTEGER, 
                         title TEXT, url TEXT, photo_file_id TEXT, photo_path TEXT, 
                         description TEXT)''')
    await db.execute('''CREATE TABLE IF NOT EXISTS users 
                        (user_id INTEGER PRIMARY KEY, username TEXT, 
                         first_name TEXT, registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    await db.execute('''CREATE TABLE IF NOT EXISTS ref_links 
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, code TEXT UNIQUE,
                         clicks INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    await db.commit()
    await db.close()

# ================= ПОЛЬЗОВАТЕЛИ =================
async def add_user(user_id: int, username: str, first_name: str):
    db = await aiosqlite.connect('bot.db')
    await db.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user_id, username, first_name)
    )
    await db.commit()
    await db.close()

async def get_users_count():
    db = await aiosqlite.connect('bot.db')
    cursor = await db.execute("SELECT COUNT(*) FROM users")
    result = await cursor.fetchone()
    await db.close()
    return result[0]

async def get_users_today():
    db = await aiosqlite.connect('bot.db')
    cursor = await db.execute("SELECT COUNT(*) FROM users WHERE date(registered_at) = date('now')")
    result = await cursor.fetchone()
    await db.close()
    return result[0]

async def get_users_week():
    db = await aiosqlite.connect('bot.db')
    cursor = await db.execute("SELECT COUNT(*) FROM users WHERE registered_at >= date('now', '-7 days')")
    result = await cursor.fetchone()
    await db.close()
    return result[0]

async def get_users_month():
    db = await aiosqlite.connect('bot.db')
    cursor = await db.execute("SELECT COUNT(*) FROM users WHERE registered_at >= date('now', '-30 days')")
    result = await cursor.fetchone()
    await db.close()
    return result[0]

async def get_last_users(limit: int = 5):
    db = await aiosqlite.connect('bot.db')
    cursor = await db.execute(
        "SELECT user_id, username, first_name, registered_at FROM users ORDER BY registered_at DESC LIMIT ?",
        (limit,)
    )
    result = await cursor.fetchall()
    await db.close()
    return result

# ================= РЕФЕРАЛЬНЫЕ ССЫЛКИ =================
def generate_code(length: int = 8) -> str:
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

async def create_ref_link(name: str) -> tuple:
    code = generate_code()
    link = f"https://t.me/{BOT_USERNAME}?start={code}"
    db = await aiosqlite.connect('bot.db')
    await db.execute("INSERT INTO ref_links (name, code) VALUES (?, ?)", (name, code))
    await db.commit()
    await db.close()
    return code, link

async def get_all_ref_links():
    db = await aiosqlite.connect('bot.db')
    cursor = await db.execute("SELECT id, name, code, clicks, created_at FROM ref_links ORDER BY created_at DESC")
    result = await cursor.fetchall()
    await db.close()
    return result

async def increment_clicks(code: str):
    db = await aiosqlite.connect('bot.db')
    await db.execute("UPDATE ref_links SET clicks = clicks + 1 WHERE code = ?", (code,))
    await db.commit()
    await db.close()

async def get_ref_link_by_code(code: str):
    db = await aiosqlite.connect('bot.db')
    cursor = await db.execute("SELECT id, name, code, clicks, created_at FROM ref_links WHERE code = ?", (code,))
    result = await cursor.fetchone()
    await db.close()
    return result

async def delete_ref_link(link_id: int):
    db = await aiosqlite.connect('bot.db')
    await db.execute("DELETE FROM ref_links WHERE id = ?", (link_id,))
    await db.commit()
    await db.close()

async def get_total_ref_clicks():
    db = await aiosqlite.connect('bot.db')
    cursor = await db.execute("SELECT COALESCE(SUM(clicks), 0) FROM ref_links")
    result = await cursor.fetchone()
    await db.close()
    return result[0]

# ================= ПАПКИ И КОНТЕНТ =================
async def add_folder(name: str):
    db = await aiosqlite.connect('bot.db')
    await db.execute("INSERT INTO folders (name) VALUES (?)", (name,))
    await db.commit()
    await db.close()
    os.makedirs(f"{PHOTO_DIR}/{name}", exist_ok=True)

async def get_folders():
    db = await aiosqlite.connect('bot.db')
    cursor = await db.execute("SELECT id, name FROM folders")
    result = await cursor.fetchall()
    await db.close()
    return result

async def add_content(folder_id: int, title: str, url: str, photo_file_id: str, photo_path: str, description: str):
    db = await aiosqlite.connect('bot.db')
    await db.execute('''INSERT INTO contents 
                        (folder_id, title, url, photo_file_id, photo_path, description) 
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (folder_id, title, url, photo_file_id, photo_path, description))
    await db.commit()
    await db.close()

async def get_contents_by_folder(folder_id: int):
    db = await aiosqlite.connect('bot.db')
    cursor = await db.execute("SELECT id, title, url, photo_file_id, description FROM contents WHERE folder_id = ?", 
                              (folder_id,))
    result = await cursor.fetchall()
    await db.close()
    return result

async def get_content(content_id: int):
    db = await aiosqlite.connect('bot.db')
    cursor = await db.execute('''SELECT id, folder_id, title, url, photo_file_id, photo_path, description 
                                 FROM contents WHERE id = ?''', (content_id,))
    result = await cursor.fetchone()
    await db.close()
    return result

async def update_content_title(content_id: int, new_title: str):
    db = await aiosqlite.connect('bot.db')
    await db.execute("UPDATE contents SET title = ? WHERE id = ?", (new_title, content_id))
    await db.commit()
    await db.close()

async def update_content_url(content_id: int, new_url: str):
    db = await aiosqlite.connect('bot.db')
    await db.execute("UPDATE contents SET url = ? WHERE id = ?", (new_url, content_id))
    await db.commit()
    await db.close()

async def update_content_photo(content_id: int, new_photo_file_id: str, new_photo_path: str):
    db = await aiosqlite.connect('bot.db')
    await db.execute("UPDATE contents SET photo_file_id = ?, photo_path = ? WHERE id = ?", 
                     (new_photo_file_id, new_photo_path, content_id))
    await db.commit()
    await db.close()

async def update_content_description(content_id: int, new_description: str):
    db = await aiosqlite.connect('bot.db')
    await db.execute("UPDATE contents SET description = ? WHERE id = ?", (new_description, content_id))
    await db.commit()
    await db.close()

# ================= ПРОВЕРКА АДМИНА =================
def is_admin(user_id: int):
    return user_id in ADMIN_IDS

# ================= АДМИН ПАНЕЛЬ =================

@router.message(Command("admin2223"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен.")
        return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔗 Реферальные ссылки", callback_data="admin_ref_links")],
        [InlineKeyboardButton(text="📁 Управление папками", callback_data="admin_folders")],
        [InlineKeyboardButton(text="➕ Добавить контент", callback_data="admin_add_content")],
        [InlineKeyboardButton(text="✏️ Редактировать контент", callback_data="admin_edit_content")],
    ])
    await message.answer("⚙️ <b>Админ-панель</b>\nВыберите действие:", reply_markup=kb, parse_mode="HTML")

# ================= СТАТИСТИКА =================

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    try:
        total = await get_users_count()
        today = await get_users_today()
        week = await get_users_week()
        month = await get_users_month()
        folders = await get_folders()
        
        total_contents = 0
        for f in folders:
            contents = await get_contents_by_folder(f[0])
            total_contents += len(contents)
        
        total_ref_clicks = await get_total_ref_clicks()
        ref_links = await get_all_ref_links()
        
        last_users = await get_last_users(5)
        last_users_text = ""
        if last_users:
            last_users_text = "\n<b>👥 Последние пользователи:</b>\n"
            for user in last_users:
                username = f"@{user[1]}" if user[1] else "без username"
                name = user[2] if user[2] else "Аноним"
                reg_date = user[3][:10] if user[3] else "неизвестно"
                last_users_text += f"• {name} ({username}) — {reg_date}\n"
        else:
            last_users_text = "\n<i>Пользователей пока нет</i>"
        
        stats_text = (
            f"📊 <b>Статистика бота</b>\n\n"
            f"👥 <b>Всего пользователей:</b> {total}\n"
            f"📅 <b>Сегодня:</b> +{today}\n"
            f"📆 <b>За неделю:</b> +{week}\n"
            f"🗓 <b>За месяц:</b> +{month}\n\n"
            f"🔗 <b>Реферальных ссылок:</b> {len(ref_links)}\n"
            f"🖱 <b>Переходов по ссылкам:</b> {total_ref_clicks}\n\n"
            f"📁 <b>Папок:</b> {len(folders)}\n"
            f"🎬 <b>Контента:</b> {total_contents}"
            f"{last_users_text}"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📤 Экспорт пользователей", callback_data="admin_export_users")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ])
        
        try:
            await callback.message.edit_text(stats_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await callback.message.answer(stats_text, reply_markup=kb, parse_mode="HTML")
            
    except Exception as e:
        logging.error(f"Ошибка в admin_stats: {e}")
        await callback.answer(f"⚠️ Ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data == "admin_export_users")
async def admin_export_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    db = await aiosqlite.connect('bot.db')
    cursor = await db.execute(
        "SELECT user_id, username, first_name, registered_at FROM users ORDER BY registered_at DESC"
    )
    users = await cursor.fetchall()
    await db.close()
    
    if not users:
        await callback.answer("Нет пользователей для экспорта", show_alert=True)
        return
    
    export_file = "users_export.csv"
    with open(export_file, "w", encoding="utf-8") as f:
        f.write("user_id;username;first_name;registered_at\n")
        for user in users:
            f.write(f"{user[0]};{user[1] or ''};{user[2] or ''};{user[3]}\n")
    
    await callback.message.answer_document(
        document=types.FSInputFile(export_file),
        caption=f"📤 Экспорт пользователей ({len(users)} шт.)"
    )
    os.remove(export_file)

# ================= РЕФЕРАЛЬНЫЕ ССЫЛКИ =================

@router.callback_query(F.data == "admin_ref_links")
async def admin_ref_links_menu(callback: CallbackQuery):
    try:
        links = await get_all_ref_links()
        
        if not links:
            text = "🔗 <b>Реферальные ссылки</b>\n\nПока нет созданных ссылок."
        else:
            text = "🔗 <b>Реферальные ссылки</b>\n\n"
            for link in links:
                text += f"<b>{link[1]}</b>\n"
                text += f"🖱 Переходов: {link[3]}\n"
                text += f"📅 Создана: {link[4][:10] if link[4] else 'неизвестно'}\n"
                text += f"🔗 <code>https://t.me/{BOT_USERNAME}?start={link[2]}</code>\n\n"
        
        kb = []
        if links:
            for link in links:
                kb.append([InlineKeyboardButton(text=f"🗑 {link[1]} ({link[3]} кликов)", 
                                                callback_data=f"del_ref_{link[0]}")])
        kb.append([InlineKeyboardButton(text="➕ Создать ссылку", callback_data="create_ref_link")])
        kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
        
        try:
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
        except Exception:
            await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    except Exception as e:
        logging.error(f"Ошибка в admin_ref_links_menu: {e}")
        await callback.answer(f"⚠️ Ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data == "create_ref_link")
async def create_ref_link_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите <b>название</b> для новой ссылки:\n\n"
                                     "(например: 'Реклама в Instagram', 'Пост в VK')")
    await state.set_state(AdminStates.waiting_link_name)

@router.message(AdminStates.waiting_link_name)
async def create_ref_link_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    
    name = message.text.strip()
    code, link = await create_ref_link(name)
    await state.clear()
    
    text = (
        f"✅ <b>Ссылка создана!</b>\n\n"
        f"📌 <b>Название:</b> {name}\n"
        f"🔑 <b>Код:</b> <code>{code}</code>\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n"
        f"<code>{link}</code>\n\n"
        f"📋 <i>Скопируйте ссылку и используйте для рекламы. "
        f"Все переходы будут учитываться автоматически.</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Скопировать ссылку", url=link)],
        [InlineKeyboardButton(text="🔙 К списку ссылок", callback_data="admin_ref_links")]
    ])
    
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("del_ref_"))
async def delete_ref_link_handler(callback: CallbackQuery):
    link_id = int(callback.data.split("_")[2])
    await delete_ref_link(link_id)
    await callback.answer("Ссылка удалена!")
    await admin_ref_links_menu(callback)

# ================= УПРАВЛЕНИЕ ПАПКАМИ =================

@router.callback_query(F.data == "admin_folders")
async def admin_folders_menu(callback: CallbackQuery):
    try:
        folders = await get_folders()
        kb = [[InlineKeyboardButton(text=f"🗑 {f[1]}", callback_data=f"del_folder_{f[0]}")] for f in folders]
        kb.append([InlineKeyboardButton(text="➕ Создать папку", callback_data="create_folder")])
        kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
        
        await callback.message.edit_text("📁 <b>Управление папками</b>\nНажмите на папку, чтобы удалить её.", 
                                         reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    except Exception as e:
        logging.error(f"Ошибка в admin_folders_menu: {e}")
        await callback.answer(f"⚠️ Ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data == "create_folder")
async def create_folder_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите название для новой папки:")
    await state.set_state(AdminStates.waiting_folder_name)

@router.message(AdminStates.waiting_folder_name)
async def create_folder_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await add_folder(message.text.strip())
    await state.clear()
    await message.answer(f"✅ Папка <b>{message.text.strip()}</b> создана!", parse_mode="HTML")
    await cmd_admin(message, state)

@router.callback_query(F.data.startswith("del_folder_"))
async def delete_folder(callback: CallbackQuery):
    try:
        folder_id = int(callback.data.split("_")[2])
        db = await aiosqlite.connect('bot.db')
        cursor = await db.execute("SELECT name FROM folders WHERE id = ?", (folder_id,))
        folder_name = (await cursor.fetchone())[0]
        await db.execute("DELETE FROM contents WHERE folder_id = ?", (folder_id,))
        await db.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
        await db.commit()
        await db.close()
        shutil.rmtree(f"{PHOTO_DIR}/{folder_name}", ignore_errors=True)
        await callback.answer("Папка удалена!")
        await admin_folders_menu(callback)
    except Exception as e:
        logging.error(f"Ошибка при удалении папки: {e}")
        await callback.answer(f"⚠️ Ошибка: {str(e)}", show_alert=True)

# ================= ДОБАВЛЕНИЕ КОНТЕНТА =================

@router.callback_query(F.data == "admin_add_content")
async def add_content_start(callback: CallbackQuery, state: FSMContext):
    folders = await get_folders()
    if not folders:
        await callback.answer("Сначала создайте папку!", show_alert=True)
        return
    kb = [[InlineKeyboardButton(text=f[1], callback_data=f"add_content_folder_{f[0]}")] for f in folders]
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    await callback.message.edit_text("Выберите папку для добавления контента:", 
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("add_content_folder_"))
async def add_content_select_folder(callback: CallbackQuery, state: FSMContext):
    folder_id = int(callback.data.split("_")[3])
    await state.update_data(folder_id=folder_id)
    await callback.message.edit_text("Введите <b>название</b> контента:")
    await state.set_state(AdminStates.waiting_content_title)

@router.message(AdminStates.waiting_content_title)
async def add_content_title(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(title=message.text.strip())
    await message.answer("Отправьте <b>ссылку</b> (любого формата):")
    await state.set_state(AdminStates.waiting_content_url)

@router.message(AdminStates.waiting_content_url)
async def add_content_url(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(url=message.text.strip())
    await message.answer("Теперь отправьте <b>фото-превью</b> (изображение):")
    await state.set_state(AdminStates.waiting_content_photo)

@router.message(AdminStates.waiting_content_photo, F.photo)
async def add_content_photo(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    folder_id = data['folder_id']
    
    db = await aiosqlite.connect('bot.db')
    cursor = await db.execute("SELECT name FROM folders WHERE id = ?", (folder_id,))
    folder_name = (await cursor.fetchone())[0]
    await db.close()

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_ext = os.path.splitext(file.file_path)[1] or '.jpg'
    local_path = f"{PHOTO_DIR}/{folder_name}/{photo.file_id}{file_ext}"
    
    await bot.download_file(file.file_path, destination=local_path)
    await state.update_data(photo_file_id=photo.file_id, photo_path=local_path)
    await message.answer("Введите <b>описание</b> контента:")
    await state.set_state(AdminStates.waiting_content_description)

@router.message(AdminStates.waiting_content_photo, ~F.photo)
async def add_content_photo_error(message: Message):
    await message.answer("❌ Пожалуйста, отправьте именно фотографию.")

@router.message(AdminStates.waiting_content_description)
async def add_content_description(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    await add_content(data['folder_id'], data['title'], data['url'], 
                      data['photo_file_id'], data['photo_path'], message.text.strip())
    await state.clear()
    await message.answer("✅ <b>Контент успешно добавлен!</b>", parse_mode="HTML")
    await cmd_admin(message, state)

# ================= РЕДАКТИРОВАНИЕ КОНТЕНТА =================

@router.callback_query(F.data == "admin_edit_content")
async def edit_content_start(callback: CallbackQuery):
    folders = await get_folders()
    if not folders:
        await callback.answer("Нет папок!", show_alert=True)
        return
    kb = [[InlineKeyboardButton(text=f[1], callback_data=f"edit_content_folder_{f[0]}")] for f in folders]
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    await callback.message.edit_text("Выберите папку:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("edit_content_folder_"))
async def edit_content_select_folder(callback: CallbackQuery):
    folder_id = int(callback.data.split("_")[3])
    contents = await get_contents_by_folder(folder_id)
    if not contents:
        await callback.answer("В этой папке нет контента", show_alert=True)
        return
    kb = [[InlineKeyboardButton(text=c[1], callback_data=f"edit_content_{c[0]}")] for c in contents]
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_edit_content")])
    await callback.message.edit_text("Выберите контент для редактирования:", 
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("edit_content_"))
async def edit_content_menu(callback: CallbackQuery, state: FSMContext):
    content_id = int(callback.data.split("_")[2])
    await state.update_data(edit_content_id=content_id)
    kb = [
        [InlineKeyboardButton(text="✏️ Название", callback_data="edit_ctitle")],
        [InlineKeyboardButton(text="🔗 Ссылка", callback_data="edit_curl")],
        [InlineKeyboardButton(text="🖼 Фото", callback_data="edit_cphoto")],
        [InlineKeyboardButton(text="📝 Описание", callback_data="edit_cdesc")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_edit_content")]
    ]
    await callback.message.edit_text("Что изменить?", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "edit_ctitle")
async def edit_ctitle_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите новое название:")
    await state.set_state(AdminStates.waiting_new_title)

@router.message(AdminStates.waiting_new_title)
async def edit_ctitle_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    await update_content_title(data['edit_content_id'], message.text.strip())
    await state.clear()
    await message.answer("✅ Название обновлено!")
    await cmd_admin(message, state)

@router.callback_query(F.data == "edit_curl")
async def edit_curl_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите новую ссылку:")
    await state.set_state(AdminStates.waiting_new_url)

@router.message(AdminStates.waiting_new_url)
async def edit_curl_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    await update_content_url(data['edit_content_id'], message.text.strip())
    await state.clear()
    await message.answer("✅ Ссылка обновлена!")
    await cmd_admin(message, state)

@router.callback_query(F.data == "edit_cphoto")
async def edit_cphoto_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отправьте новое фото:")
    await state.set_state(AdminStates.waiting_new_photo)

@router.message(AdminStates.waiting_new_photo, F.photo)
async def edit_cphoto_process(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    content_id = data['edit_content_id']
    old_content = await get_content(content_id)
    folder_id = old_content[1]
    old_photo_path = old_content[5]
    
    db = await aiosqlite.connect('bot.db')
    cursor = await db.execute("SELECT name FROM folders WHERE id = ?", (folder_id,))
    folder_name = (await cursor.fetchone())[0]
    await db.close()

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    if old_photo_path and os.path.exists(old_photo_path):
        os.remove(old_photo_path)
    file_ext = os.path.splitext(file.file_path)[1] or '.jpg'
    local_path = f"{PHOTO_DIR}/{folder_name}/{photo.file_id}{file_ext}"
    await bot.download_file(file.file_path, destination=local_path)
    await update_content_photo(content_id, photo.file_id, local_path)
    await state.clear()
    await message.answer("✅ Фото обновлено!")
    await cmd_admin(message, state)

@router.message(AdminStates.waiting_new_photo, ~F.photo)
async def edit_cphoto_error(message: Message):
    await message.answer("❌ Отправьте фотографию.")

@router.callback_query(F.data == "edit_cdesc")
async def edit_cdesc_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите новое описание:")
    await state.set_state(AdminStates.waiting_new_description)

@router.message(AdminStates.waiting_new_description)
async def edit_cdesc_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    await update_content_description(data['edit_content_id'], message.text.strip())
    await state.clear()
    await message.answer("✅ Описание обновлено!")
    await cmd_admin(message, state)

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await cmd_admin(callback.message, state)

# ================= ПОЛЬЗОВАТЕЛИ =================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    
    args = message.text.split(maxsplit=1)
    ref_code = args[1].strip() if len(args) > 1 else None
    
    if ref_code:
        link = await get_ref_link_by_code(ref_code)
        if link:
            await increment_clicks(ref_code)
            logging.info(f"Переход по ссылке: {link[1]} (код: {ref_code}) от пользователя {message.from_user.id}")
    
    await add_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    
    botohub_result = await get_botohub_links(message.from_user.id)
    if botohub_result and not botohub_result.get('skip', False):
        tasks = botohub_result.get('tasks', [])
        if tasks:
            sponsor_text = "🎁 <b>Рекомендуем подписаться на наших партнёров:</b>\n\n"
            kb_buttons = [[InlineKeyboardButton(text=f"🔗 Партнёр {i}", url=url)] 
                          for i, url in enumerate(tasks, 1)]
            kb_buttons.append([InlineKeyboardButton(text="✅ Продолжить", callback_data="user_continue")])
            await message.answer(sponsor_text, 
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), 
                                 parse_mode="HTML")
            return
    
    await show_main_menu(message)

@router.callback_query(F.data == "user_continue")
async def user_continue(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_main_menu(callback.message)

async def show_main_menu(message: Message):
    folders = await get_folders()
    if not folders:
        await message.answer("📭 Пока нет контента. Загляните позже!")
        return
    kb = [[InlineKeyboardButton(text=f[1], callback_data=f"user_folder_{f[0]}")] for f in folders]
    await message.answer("🎬 <b>Добро пожаловать!</b>\n\nВыберите категорию:",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

@router.callback_query(F.data.startswith("user_folder_"))
async def user_select_folder(callback: CallbackQuery):
    folder_id = int(callback.data.split("_")[2])
    contents = await get_contents_by_folder(folder_id)
    if not contents:
        await callback.answer("В этой папке пока нет контента", show_alert=True)
        return
    kb = [[InlineKeyboardButton(text=c[1], callback_data=f"user_content_{c[0]}")] for c in contents]
    kb.append([InlineKeyboardButton(text="🔙 Назад к категориям", callback_data="user_back")])
    await callback.message.edit_text("📁 <b>Выберите контент:</b>",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

@router.callback_query(F.data.startswith("user_content_"))
async def user_select_content(callback: CallbackQuery, bot: Bot):
    content_id = int(callback.data.split("_")[2])
    content_data = await get_content(content_id)
    if not content_data:
        await callback.answer("Контент не найден", show_alert=True)
        return
    
    title, url, photo_file_id, description = content_data[2], content_data[3], content_data[4], content_data[6]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Открыть ссылку", url=url)]
    ])
    await callback.message.answer_photo(
        photo=photo_file_id,
        caption=f"<b>{title}</b>\n\n{description}",
        reply_markup=kb, parse_mode="HTML"
    )

@router.callback_query(F.data == "user_back")
async def user_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    folders = await get_folders()
    if not folders:
        await callback.message.edit_text("📭 Пока нет контента.")
        return
    kb = [[InlineKeyboardButton(text=f[1], callback_data=f"user_folder_{f[0]}")] for f in folders]
    await callback.message.edit_text("🎬 <b>Выберите категорию:</b>",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

# ================= ЗАПУСК =================
async def main():
    await init_db()
    print("🔍 Проверка библиотек...")
    print("=" * 40)
    print("Бот запущен!")
    print(f"👥 Статистика: ВКЛЮЧЕНА")
    print(f"🔗 Реферальные ссылки: ВКЛЮЧЕНЫ")
    print(f"🤖 Username бота: @{BOT_USERNAME}")
    print(f"💰 BotoHub: {'АКТИВНА' if BOTOHUB_TOKEN else 'ОТКЛЮЧЕНА'}")
    
    # ВАЖНО: Сбрасываем webhook и ожидающие обновления
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook сброшен")
    except Exception as e:
        print(f"⚠️ Не удалось сбросить webhook: {e}")
    
    # Запускаем polling
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Фатальная ошибка: {e}")