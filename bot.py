# bot.py
import os
import logging
from dotenv import load_dotenv
import threading
import json
from flask import Flask

# Telegram Bot Library
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, PollAnswerHandler, JobQueue

# Project Files
import settings
from shared_data import THREAD_LOCALS 
import gemini_manager
import telegram_utils

# === QUIZ GAME IMPORTS ===
from quizzes.quiz_game import quiz_game_button_handler, quiz_game_poll_answer_handler

# --- 0. SETUP ---
load_dotenv()
TOKEN = os.environ['BOT_TOKEN']

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 1. FLASK WEB SERVER ---
app_flask = Flask(__name__)
@app_flask.route('/')
def hello_world(): return "Xylon AI is alive and kicking!"
def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)

# --- 2. TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    try:
        chat_session = gemini_manager.get_or_create_chat_session(user.id, user.first_name)
        response_stream = await chat_session.send_message_async(
            "User has just started the conversation. Greet them warmly as Xylon AI and briefly mention key features like chat, movie search, and our new pro-level quizzes.",
            stream=True
        )
        full_response = await telegram_utils.send_split_message(update, context, response_stream)
        
        # Manually update history with the full response for context
        if chat_session.history and chat_session.history[-1].role == "model":
             chat_session.history[-1].parts[0].text = full_response

    except Exception as e:
        logger.error(f"FATAL ERROR during /start for user {user.id}: {e}", exc_info=True)
        await context.bot.send_message(chat_id=chat_id, text="🤯 Oops! Failed to generate response. Please try after some time.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    
    try:
        if 'next_message_is' in context.user_data:
            state = context.user_data.pop('next_message_is')
            if user.id not in settings.user_profiles: settings.user_profiles[user.id] = {}
            settings.user_profiles[user.id][state] = message_text
            settings.save_user_profiles()
            await update.message.reply_text(f"✅ Theek hai, maine aapka '{state}' save kar liya hai! Main isse agle conversation se yaad rakhoonga.")
            if user.id in gemini_manager.user_chats: del gemini_manager.user_chats[user.id]
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        chat_session = gemini_manager.get_or_create_chat_session(user.id, user.first_name)
        
        await gemini_manager.manage_chat_history(chat_session)
        
        THREAD_LOCALS.context = context
        THREAD_LOCALS.loop = asyncio.get_running_loop()
        THREAD_LOCALS.context.update = update

        response_stream = await chat_session.send_message_async(message_text, stream=True)
        full_response = await telegram_utils.send_split_message(update, context, response_stream)
        
        # CRITICAL: Manually update the last model message in history with the full text
        if chat_session.history and chat_session.history[-1].role == "model":
             chat_session.history[-1].parts[0].text = full_response
        
    except Exception as e:
        logger.error(f"FATAL ERROR in handle_message for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text("🤯 Oops! Failed to generate response. Please try after some time.")
    finally:
        if hasattr(THREAD_LOCALS, 'context'): del THREAD_LOCALS.context
        if hasattr(THREAD_LOCALS, 'loop'): del THREAD_LOCALS.loop

# --- 3. MAIN BOT EXECUTION ---
def main():
    if os.path.exists(settings.USER_PROFILES_FILE):
        try:
            with open(settings.USER_PROFILES_FILE, 'r', encoding='utf-8') as f:
                profiles = json.load(f)
                # Pass the user_chats dict from gemini_manager
                settings.load_user_profiles_settings({int(k): v for k, v in profiles.items()}, gemini_manager.user_chats)
        except (json.JSONDecodeError, ValueError):
            logger.error("Could not load user profiles, file might be empty or corrupt.")
            settings.load_user_profiles_settings({}, gemini_manager.user_chats)

    job_queue = JobQueue()
    app = ApplicationBuilder().token(TOKEN).job_queue(job_queue).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setting", settings.settings_command))
    app.add_handler(CallbackQueryHandler(settings.settings_button_handler, pattern='^settings_'))
    app.add_handler(CallbackQueryHandler(quiz_game_button_handler, pattern='^quizgame_'))
    app.add_handler(PollAnswerHandler(quiz_game_poll_answer_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info(f"🚀 Xylon AI Bot starting polling with {len(gemini_manager.API_KEYS)} API key(s) in rotation.")
    app.run_polling()

if __name__ == "__main__":
    logger.info("🚀 Starting Flask server for Xylon AI in a separate thread...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    logger.info("🚀 Starting Xylon AI Bot in the main thread...")
    main()
