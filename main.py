import asyncio
import logging
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8838352023:AAHl9ZPlNcbmXiARZsMnpzQs0Gxsz4nSjbE"
ADMIN_ID = 7652381613
REQUIRED_COMMENTS = 5

user_states = {}
user_data_store = defaultdict(dict)
blocked_users = set()
approved_users = set()

def get_user_info(user):
    return f"👤 {user.full_name} (@{user.username or 'нет username'}) | ID: {user.id}"

def main_menu_keyboard(user_id=None):
    is_admin = user_id == ADMIN_ID
    keyboard = [
        [InlineKeyboardButton("🎯 Рейт", callback_data="rate")],
        [InlineKeyboardButton("🏆 Таблица лидеров", callback_data="leaderboard")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def admin_panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 На проверке комментарии", callback_data="admin_pending")],
        [InlineKeyboardButton("✅ Одобренные", callback_data="admin_approved")],
        [InlineKeyboardButton("📊 Аналитика", callback_data="admin_analytics")],
        [InlineKeyboardButton("🔙 В меню", callback_data="back")]
    ])

def pending_users_keyboard(page=0):
    pending = [(uid, data) for uid, data in user_data_store.items() 
               if data.get('status') in ('pending_comments', 'awaiting_approval') and uid not in blocked_users]
    per_page = 5
    start = page * per_page
    end = start + per_page
    page_users = pending[start:end]
    
    keyboard = []
    for uid, data in page_users:
        username = data.get('username', f'user_{uid}')
        comments_count = len(data.get('comment_screenshots', []))
        status_text = "⏳" if data.get('status') == 'pending_comments' else "📋"
        keyboard.append([InlineKeyboardButton(f"{status_text} @{username} ({comments_count}/5)", callback_data=f"view_user_{uid}")])
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"pending_page_{page-1}"))
    if end < len(pending):
        nav.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"pending_page_{page+1}"))
    if nav:
        keyboard.append(nav)
    
    keyboard.append([InlineKeyboardButton("🔙 В админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def approved_users_keyboard(page=0):
    approved = [(uid, data) for uid, data in user_data_store.items() 
                if uid in approved_users and uid not in blocked_users]
    per_page = 5
    start = page * per_page
    end = start + per_page
    page_users = approved[start:end]
    
    keyboard = []
    for uid, data in page_users:
        username = data.get('username', f'user_{uid}')
        keyboard.append([InlineKeyboardButton(f"✅ @{username}", callback_data=f"view_approved_{uid}")])
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"approved_page_{page-1}"))
    if end < len(approved):
        nav.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"approved_page_{page+1}"))
    if nav:
        keyboard.append(nav)
    
    keyboard.append([InlineKeyboardButton("🔙 В админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def user_screenshots_keyboard(user_id, page=0):
    screenshots = user_data_store[user_id].get('comment_screenshots', [])
    per_page = 3
    start = page * per_page
    end = start + per_page
    page_shots = screenshots[start:end]
    
    keyboard = []
    for i, shot in enumerate(page_shots):
        keyboard.append([InlineKeyboardButton(f"📸 Скриншот {start+i+1}", callback_data=f"view_shot_{user_id}_{start+i}")])
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"shots_page_{user_id}_{page-1}"))
    if end < len(screenshots):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"shots_page_{user_id}_{page+1}"))
    if nav:
        keyboard.append(nav)
    
    status = user_data_store[user_id].get('status', '')
    if status == 'awaiting_approval':
        keyboard.append([
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user_id}")
        ])
    keyboard.append([InlineKeyboardButton("💬 Комментарий", callback_data=f"comment_{user_id}")])
    keyboard.append([InlineKeyboardButton("🔙 К списку", callback_data="admin_pending")])
    return InlineKeyboardMarkup(keyboard)

def analytics_keyboard(page=0):
    all_users = [(uid, data) for uid, data in user_data_store.items() if uid != ADMIN_ID]
    per_page = 5
    start = page * per_page
    end = start + per_page
    page_users = all_users[start:end]
    
    keyboard = []
    for uid, data in page_users:
        username = data.get('username', f'user_{uid}')
        status = "🚫" if uid in blocked_users else ("✅" if uid in approved_users else "⏳")
        keyboard.append([InlineKeyboardButton(f"{status} @{username}", callback_data=f"analytics_user_{uid}")])
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"analytics_page_{page-1}"))
    if end < len(all_users):
        nav.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"analytics_page_{page+1}"))
    if nav:
        keyboard.append(nav)
    
    keyboard.append([InlineKeyboardButton("🔙 В админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def user_analytics_keyboard(user_id):
    is_blocked = user_id in blocked_users
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Заблокировать" if not is_blocked else "✅ Разблокировать", 
                              callback_data=f"block_{user_id}" if not is_blocked else f"unblock_{user_id}")],
        [InlineKeyboardButton("🔙 К списку", callback_data="admin_analytics")]
    ])

def rate_photo_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Комментарий", callback_data=f"rate_comment_{user_id}")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in blocked_users:
        await (update.message or update.callback_query.message).reply_text("🚫 Вы заблокированы в боте.")
        return
    
    user_data_store[user_id]['username'] = update.effective_user.username
    user_data_store[user_id]['full_name'] = update.effective_user.full_name
    
    text = "👋 Привет! Добро пожаловать в бот рейтинга внешности.\n\nВыберите действие:"
    markup = main_menu_keyboard(user_id)
    
    if update.message:
        await update.message.reply_text(text, reply_markup=markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == "rate":
        if user_id in blocked_users:
            await query.edit_message_text("🚫 Вы заблокированы.")
            return
        
        if user_id not in approved_users:
            user_states[user_id] = 'waiting_comments'
            user_data_store[user_id]['comment_screenshots'] = []
            user_data_store[user_id]['status'] = 'pending_comments'
            
            await query.edit_message_text(
                f"📝 Условие для получения рейта:\n\n"
                f"Оставьте {REQUIRED_COMMENTS} комментариев в TikTok/Instagram с рекламой бота.\n"
                f"Пришлите скриншоты каждого комментария (всего {REQUIRED_COMMENTS}).\n\n"
                f"После проверки админом вам откроется доступ к рейту."
            )
        else:
            user_states[user_id] = 'waiting_rate_photo'
            await query.edit_message_text("📸 Отправьте фото для рейта")
    
    elif data == "leaderboard":
        await query.edit_message_text(
            "🏆 Таблица лидеров\n\nСкоро...",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]])
        )
    
    elif data == "back":
        await start(update, context)
    
    elif data == "admin_panel" and user_id == ADMIN_ID:
        await query.edit_message_text("👑 Админ-панель", reply_markup=admin_panel_keyboard())
    
    elif data == "admin_pending":
        await query.edit_message_text("📋 Пользователи на проверке комментариев:", reply_markup=pending_users_keyboard())
    
    elif data.startswith("pending_page_"):
        page = int(data.split("_")[-1])
        await query.edit_message_text("📋 Пользователи на проверке:", reply_markup=pending_users_keyboard(page))
    
    elif data == "admin_approved":
        await query.edit_message_text("✅ Одобренные пользователи:", reply_markup=approved_users_keyboard())
    
    elif data.startswith("approved_page_"):
        page = int(data.split("_")[-1])
        await query.edit_message_text("✅ Одобренные пользователи:", reply_markup=approved_users_keyboard(page))
    
    elif data.startswith("view_approved_"):
        target_id = int(data.split("_")[-1])
        data_u = user_data_store[target_id]
        await query.edit_message_text(
            f"✅ Одобренный пользователь:\n"
            f"🆔 ID: {target_id}\n"
            f"👤 Имя: {data_u.get('full_name', '—')}\n"
            f"🔗 Username: @{data_u.get('username', 'нет')}\n"
            f"📸 Скриншотов комментариев: {len(data_u.get('comment_screenshots', []))}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К списку", callback_data="admin_approved")]])
        )
    
    elif data.startswith("view_user_"):
        target_id = int(data.split("_")[-1])
        await query.edit_message_text(
            f"📸 Скриншоты комментариев от @{user_data_store[target_id].get('username', 'unknown')}:",
            reply_markup=user_screenshots_keyboard(target_id)
        )
    
    elif data.startswith("shots_page_"):
        _, _, target_id, page = data.split("_")
        await query.edit_message_text(
            f"📸 Скриншоты от @{user_data_store[int(target_id)].get('username', 'unknown')}:",
            reply_markup=user_screenshots_keyboard(int(target_id), int(page))
        )
    
    elif data.startswith("view_shot_"):
        _, _, target_id, idx = data.split("_")
        target_id = int(target_id)
        idx = int(idx)
        shot = user_data_store[target_id]['comment_screenshots'][idx]
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=shot,
            caption=f"Скриншот {idx+1} от @{user_data_store[target_id].get('username', 'unknown')}"
        )
    
    elif data.startswith("approve_"):
        target_id = int(data.split("_")[-1])
        approved_users.add(target_id)
        user_data_store[target_id]['status'] = 'approved'
        await context.bot.send_message(target_id, "✅ Ваши комментарии одобрены! можете кидать фото для рейта /start")
        await query.edit_message_text("✅ Пользователь одобрен.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К списку", callback_data="admin_pending")]]))
    
    elif data.startswith("reject_"):
        target_id = int(data.split("_")[-1])
        user_data_store[target_id]['status'] = 'rejected'
        user_data_store[target_id]['comment_screenshots'] = []
        user_states[target_id] = 'waiting_comments'
        await context.bot.send_message(target_id, "❌ Комментарии не прошли проверку. Пришлите новые скриншоты.")
        await query.edit_message_text("❌ Отклонено. Пользователь должен прислать новые скриншоты.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К списку", callback_data="admin_pending")]]))
    
    elif data.startswith("comment_"):
        target_id = int(data.split("_")[-1])
        user_states[ADMIN_ID] = f'writing_comment_{target_id}'
        await query.edit_message_text(
            f"💬 Напишите комментарий для @{user_data_store[target_id].get('username', 'unknown')} (придёт ему в боте):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=f"view_user_{target_id}")]])
        )
    
    elif data == "admin_analytics":
        total = len([u for u in user_data_store if u != ADMIN_ID])
        approved_count = len(approved_users)
        await query.edit_message_text(
            f"📊 Аналитика\n\n👥 Всего пользователей: {total}\n✅ Одобрено: {approved_count}\n🚫 Заблокировано: {len(blocked_users)}",
            reply_markup=analytics_keyboard()
        )
    
    elif data.startswith("analytics_page_"):
        page = int(data.split("_")[-1])
        total = len([u for u in user_data_store if u != ADMIN_ID])
        await query.edit_message_text(
            f"📊 Аналитика\n\n👥 Всего пользователей: {total}\n✅ Одобрено: {len(approved_users)}\n🚫 Заблокировано: {len(blocked_users)}",
            reply_markup=analytics_keyboard(page)
        )
    
    elif data.startswith("analytics_user_"):
        target_id = int(data.split("_")[-1])
        data_u = user_data_store[target_id]
        status = "🚫 Заблокирован" if target_id in blocked_users else ("✅ Одобрен" if target_id in approved_users else "⏳ На проверке")
        await query.edit_message_text(
            f"👤 Пользователь:\n"
            f"🆔 ID: {target_id}\n"
            f"👤 Имя: {data_u.get('full_name', '—')}\n"
            f"🔗 Username: @{data_u.get('username', 'нет')}\n"
            f"📊 Статус: {status}\n"
            f"📸 Скриншотов: {len(data_u.get('comment_screenshots', []))}",
            reply_markup=user_analytics_keyboard(target_id)
        )
    
    elif data.startswith("block_"):
        target_id = int(data.split("_")[-1])
        blocked_users.add(target_id)
        approved_users.discard(target_id)
        await context.bot.send_message(target_id, "🚫 Вы заблокированы в боте.")
        await query.edit_message_text("🚫 Пользователь заблокирован.", reply_markup=user_analytics_keyboard(target_id))
    
    elif data.startswith("unblock_"):
        target_id = int(data.split("_")[-1])
        blocked_users.discard(target_id)
        await context.bot.send_message(target_id, "✅ Вы разблокированы в боте.")
        await query.edit_message_text("✅ Пользователь разблокирован.", reply_markup=user_analytics_keyboard(target_id))
    
    elif data.startswith("rate_comment_"):
        target_id = int(data.split("_")[-1])
        user_states[ADMIN_ID] = f'writing_rate_{target_id}'
        await query.edit_message_text(
            f"💬 Напишите комментарий для @{user_data_store[target_id].get('username', 'unknown')}:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]])
        )

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in blocked_users:
        return
    
    state = user_states.get(user_id)
    
    if state == 'waiting_comments':
        photo = update.message.photo[-1]
        screenshots = user_data_store[user_id].get('comment_screenshots', [])
        screenshots.append(photo.file_id)
        user_data_store[user_id]['comment_screenshots'] = screenshots
        
        count = len(screenshots)
        remaining = REQUIRED_COMMENTS - count
        
        if count < REQUIRED_COMMENTS:
            await update.message.reply_text(
                f"✅ Скриншот принят ({count}/{REQUIRED_COMMENTS}).\n"
                f"Осталось отправить: {remaining}"
            )
            
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo.file_id,
                caption=f"📸 Скриншот комментария {count}/{REQUIRED_COMMENTS} от @{user_data_store[user_id].get('username', 'unknown')}"
            )
        else:
            user_data_store[user_id]['status'] = 'awaiting_approval'
            user_states[user_id] = 'awaiting_approval'
            
            await update.message.reply_text(
                f"✅ Все {REQUIRED_COMMENTS} скриншотов получены!\n"
                "Ожидайте проверки администратором."
            )
            
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📋 Пользователь @{user_data_store[user_id].get('username', 'unknown')} прислал все {REQUIRED_COMMENTS} скриншотов комментариев.\nГотов к проверке.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user_id}"),
                     InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user_id}")],
                    [InlineKeyboardButton("💬 Комментарий", callback_data=f"comment_{user_id}")]
                ])
            )
    
    elif state == 'waiting_rate_photo':
        if user_id not in approved_users:
            await update.message.reply_text("❌ Сначала выполните условие с комментариями.")
            return
        
        photo = update.message.photo[-1]
        user_data_store[user_id]['rate_photo'] = photo.file_id
        user_states[user_id] = 'rate_done'
        
        await update.message.reply_text(
            "⚠️ Сервера перегружены, ответ может быть задержан"
        )
        
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo.file_id,
            caption=f"📸 Фото для рейта\n{get_user_info(update.effective_user)}",
            reply_markup=rate_photo_keyboard(user_id)
        )
    
    elif user_id == ADMIN_ID:
        pass

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = user_states.get(user_id, '')
    
    if state.startswith('writing_comment_'):
        target_id = int(state.split('_')[-1])
        await context.bot.send_message(target_id, f"💬 Комментарий от админа:\n\n{text}")
        user_states[user_id] = ''
        await update.message.reply_text("✅ Комментарий отправлен пользователю.", reply_markup=main_menu_keyboard(user_id))
    
    elif state.startswith('writing_rate_'):
        target_id = int(state.split('_')[-1])
        await context.bot.send_message(target_id, f"комент:\n\n{text}")
        user_states[user_id] = ''
        await update.message.reply_text("✅ Оценка отправлена.", reply_markup=main_menu_keyboard(user_id))
    
    else:
        await update.message.reply_text("Используйте кнопки меню. Напишите /start для начала.", reply_markup=main_menu_keyboard(user_id))

async def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    print("Бот запущен...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
