# --- START OF UPDATED FILE bot.py ---

# bot.py (Final Corrected Version)

import os
import threading
import json
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    PollAnswerHandler,
    filters,
    JobQueue
)

from config import TOKEN, logger
from handlers import start, handle_message
from web_server import run_flask
import settings

# Yahan se import karna zaroori hai taaki 'user_chats' object create ho jaye
from ai_manager import user_chats 
from quizzes.quiz_game import quiz_game_button_handler, quiz_game_poll_answer_handler

def main():
    """Bot ko set up aur run karta hai."""
    
    if os.path.exists(settings.USER_PROFILES_FILE):
        try:
            with open(settings.USER_PROFILES_FILE, 'r', encoding='utf-8') as f:
                profiles = json.load(f)
                settings.load_user_profiles_settings({int(k): v for k, v in profiles.items()}, user_chats)
        except (json.JSONDecodeError, ValueError):
            logger.error("Could not load user profiles, file might be empty or corrupt.")
            settings.load_user_profiles_settings({}, user_chats)

    job_queue = JobQueue()
    app = ApplicationBuilder().token(TOKEN).job_queue(job_queue).build()
    
    # === THE FIX IS HERE ===
    # Hum 'user_chats' ko bot_data mein share kar rahe hain
    # Ab koi bhi module context ke through isse access kar sakta hai
    app.bot_data['user_chats'] = user_chats
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setting", settings.settings_command))
    
    app.add_handler(CallbackQueryHandler(settings.settings_button_handler, pattern='^settings_'))
    app.add_handler(CallbackQueryHandler(quiz_game_button_handler, pattern='^quizgame_'))
    
    app.add_handler(PollAnswerHandler(quiz_game_poll_answer_handler))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 Xylon AI Bot is starting polling...")
    app.run_polling()

if __name__ == "__main__":
    logger.info("🚀 Starting Flask server in a separate thread...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    logger.info("🚀 Starting Xylon AI Bot in the main thread...")
    main()

# --- END OF UPDATED FILE bot.py ---
