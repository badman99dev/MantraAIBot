import os
import logging
from dotenv import load_dotenv
import threading
import asyncio
from flask import Flask
import json

# Telegram Bot Library
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, PollAnswerHandler, JobQueue
from telegram.constants import ParseMode

# Gemini AI Library
import google.generativeai as genai

# APNI FILES IMPORT KARNA
from prompts import SYSTEM_PROMPT_TEMPLATE
from tools.tool_manager import AVAILABLE_TOOLS
import settings
from shared_data import THREAD_LOCALS 

# === QUIZ GAME IMPORTS START ===
from quizzes.quiz_game import quiz_game_button_handler, quiz_game_poll_answer_handler
# === QUIZ GAME IMPORTS END ===

# Message Splitting Thresholds
SENTENCE_SPLIT_THRESHOLD = 1500
WORD_SPLIT_THRESHOLD = 2500
CHARACTER_SPLIT_THRESHOLD = 2800
TELEGRAM_MAX_MESSAGE_LENGTH = 3700 

# --- 0. FLASK WEB SERVER SETUP ---
app_flask = Flask(__name__)
@app_flask.route('/')
def hello_world(): return "Xylon AI is alive and kicking!"
def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)

# --- 1. SETUP ---
load_dotenv()
TOKEN = os.environ['BOT_TOKEN']
GEMINI_KEY = os.environ.get('GEMINI_KEY')
if not GEMINI_KEY:
    raise ValueError("GEMINI_KEY not found in .env file. Please add it.")

MODEL_NAME = os.environ.get('MODEL_NAME', 'gemini-1.5-flash')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_KEY)

# --- 2. GEMINI MODEL & HISTORY MANAGEMENT ---
model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    tools=AVAILABLE_TOOLS
)

MAX_HISTORY_TOKENS = 50000
TRIM_BUFFER_TOKENS = 5000

async def manage_chat_history(chat_session: genai.ChatSession):
    try:
        token_count = (await model.count_tokens_async(chat_session.history)).total_tokens
        
        if token_count > MAX_HISTORY_TOKENS:
            logger.warning(f"Token count {token_count} is over the limit. Trimming.")
            current_history = chat_session.history
            safe_limit = MAX_HISTORY_TOKENS - TRIM_BUFFER_TOKENS
            while (await model.count_tokens_async(current_history)).total_tokens > safe_limit:
                if len(current_history) > 3:
                    del current_history[2]; del current_history[2]
                else: break
            chat_session.history = current_history
            logger.info(f"History trimmed. New count: {(await model.count_tokens_async(chat_session.history)).total_tokens}")
    except Exception as e:
        logger.error(f"Error during chat history management: {e}", exc_info=True)

# --- 3. CHAT MANAGEMENT ---
user_chats = {} 
settings.load_user_profiles_settings(settings.user_profiles, user_chats)

def get_or_create_chat_session(user_id: int, user_name: str) -> genai.ChatSession:
    if user_id not in user_chats:
        logger.info(f"Creating new chat session for user {user_id}...")
        personalization_section = ""
        if user_id in settings.user_profiles and settings.user_profiles[user_id]:
            profile = settings.user_profiles[user_id]
            personalization_section += "\n--- USER'S PERSONAL DATA (Remember This!) ---\n"
            if 'nickname' in profile: personalization_section += f"- User's Nickname: {profile['nickname']}\n"
            if 'instruction' in profile: personalization_section += f"- Custom Instruction: {profile['instruction']}\n"
            if 'hobby' in profile: personalization_section += f"- User's Hobby: {profile['hobby']}\n"
            if 'memory' in profile: personalization_section += f"- Important Memory: {profile['memory']}\n"
            
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            user_name=user_name,
            user_personalization_section=personalization_section
        )
        initial_history = [
            {'role': 'user', 'parts': [{'text': system_prompt}]},
            {'role': 'model', 'parts': [{'text': f"Okay, I understand. I am 𝐗𝐲𝐥𝐨𝐧 𝐀𝐈, ready to chat with {user_name}! 😎"}]}
        ]
        user_chats[user_id] = model.start_chat(
            history=initial_history,
            enable_automatic_function_calling=True
        )
    return user_chats[user_id]

# --- 4. SMART MESSAGE SENDING & SPLITTING FUNCTION ---
async def split_and_send_string(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    if not text:
        return

    remaining_text = text
    split_chars = ['.', '।', '?', '!', '\n']

    while len(remaining_text) > TELEGRAM_MAX_MESSAGE_LENGTH:
        split_pos = -1
        
        for i in range(min(len(remaining_text) - 1, SENTENCE_SPLIT_THRESHOLD), 0, -1):
            if remaining_text[i] in split_chars:
                split_pos = i + 1; break
        
        if split_pos == -1 and len(remaining_text) > WORD_SPLIT_THRESHOLD:
            pos = remaining_text.rfind(' ', 0, WORD_SPLIT_THRESHOLD)
            if pos != -1: split_pos = pos + 1

        if split_pos == -1:
            split_pos = CHARACTER_SPLIT_THRESHOLD

        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=remaining_text[:split_pos],
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        remaining_text = remaining_text[split_pos:]
        await asyncio.sleep(0.5)

    if remaining_text:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=remaining_text,
            parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )

# --- 5. TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
        chat_session = get_or_create_chat_session(user.id, user.first_name)
        response = await chat_session.send_message_async(
            "User has just started the conversation. Greet them warmly as Xylon AI and briefly mention key features like chat, movie search, and our new pro-level quizzes."
        )
        await split_and_send_string(update, context, response.text)
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
            if user.id in user_chats: del user_chats[user_id]
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        chat_session = get_or_create_chat_session(user.id, user.first_name)
        
        await manage_chat_history(chat_session)
        
        THREAD_LOCALS.context = context
        THREAD_LOCALS.loop = asyncio.get_running_loop()
        THREAD_LOCALS.context.update = update

        response = await chat_session.send_message_async(message_text)
        await split_and_send_string(update, context, response.text)
        
    except Exception as e:
        logger.error(f"FATAL ERROR in handle_message for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text("🤯 Oops! Failed to generate response. Please try after some time.")
    finally:
        if hasattr(THREAD_LOCALS, 'context'): del THREAD_LOCALS.context
        if hasattr(THREAD_LOCALS, 'loop'): del THREAD_LOCALS.loop

# --- 6. MAIN BOT EXECUTION ---
def main():
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
    
    # +++ THE FIX: Register shared data and functions in a central place +++
    app.bot_data['shared_utils'] = {
        'user_chats': user_chats,
        'split_and_send_string': split_and_send_string
    }
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setting", settings.settings_command))
    app.add_handler(CallbackQueryHandler(settings.settings_button_handler, pattern='^settings_'))
    app.add_handler(CallbackQueryHandler(quiz_game_button_handler, pattern='^quizgame_'))
    app.add_handler(PollAnswerHandler(quiz_game_poll_answer_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info(f"🚀 Xylon AI Bot is starting polling with a single API key.")
    app.run_polling()

if __name__ == "__main__":
    logger.info("🚀 Starting Flask server for Xylon AI in a separate thread...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    logger.info("🚀 Starting Xylon AI Bot in the main thread...")
    main()
