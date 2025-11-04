import os
import logging
from dotenv import load_dotenv
import threading
import asyncio
from flask import Flask
import json
import re # Import Regex

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
from time_utils import get_current_ist_string

# === QUIZ GAME IMPORTS START ===
from quizzes.quiz_game import quiz_game_button_handler, quiz_game_poll_answer_handler
# === QUIZ GAME IMPORTS END ===

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
model = genai.GenerativeModel(model_name=MODEL_NAME, tools=AVAILABLE_TOOLS)
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
            current_ist_time_string=get_current_ist_string(),
            user_personalization_section=personalization_section
        )
        initial_history = [
            {'role': 'user', 'parts': [{'text': system_prompt}]},
            {'role': 'model', 'parts': [{'text': f"Okay, I understand. I am 𝐗𝐲𝐥𝐨𝐧 𝐀𝐈, ready to chat with {user_name}! 😎"}]}
        ]
        user_chats[user_id] = model.start_chat(history=initial_history, enable_automatic_function_calling=True)
    return user_chats[user_id]


# +++ NEW: The Intelligent "HTML Validator & Cleaner" +++
def clean_html(text: str) -> str:
    if not text:
        return ""
    
    # 1. Remove unsupported tags (both start and end)
    unsupported_tags = ['ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span']
    for tag in unsupported_tags:
        text = re.sub(rf'</?{tag}[^>]*>', '', text)

    # 2. Remove <a> tags that do not have an href attribute
    text = re.sub(r'<a(?![^>]*\shref=)[^>]*>(.*?)</a>', r'\1', text, flags=re.IGNORECASE | re.DOTALL)

    # 3. Find and remove unbalanced/unclosed supported tags
    supported_tags = ["b", "i", "u", "s", "tg-spoiler", "code", "pre"]
    for tag in supported_tags:
        # Loop until all unbalanced tags of this type are removed
        while True:
            # Case-insensitive matching for tags
            start_tag_pattern = re.compile(f"<{tag}[>\\s]", re.IGNORECASE)
            end_tag_pattern = re.compile(f"</{tag}>", re.IGNORECASE)
            
            start_tag_count = len(start_tag_pattern.findall(text))
            end_tag_count = len(end_tag_pattern.findall(text))

            if start_tag_count == end_tag_count:
                break # All balanced, move to the next tag
            
            logger.warning(f"Unbalanced '{tag}' tag found in chunk. Cleaning...")
            # If there's an imbalance, remove all tags of this type to be safe
            text = re.sub(rf'</?{tag}[^>]*>', '', text, flags=re.IGNORECASE)
    
    return text


# --- 4. TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
        chat_session = get_or_create_chat_session(user.id, user.first_name)
        response = await chat_session.send_message_async(
            "User has just started the conversation. Greet them warmly as Xylon AI and briefly mention key features like chat, movie search, and our new pro-level quizzes."
        )

        for chunk in response.text.split("\n---\n"):
            if chunk.strip():
                # +++ USE THE CLEANER BEFORE SENDING +++
                cleaned_chunk = clean_html(chunk.strip())
                await context.bot.send_message(
                    chat_id=chat_id, text=cleaned_chunk,
                    parse_mode=ParseMode.HTML, disable_web_page_preview=True
                )
                await asyncio.sleep(1.0)

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
        
        chunks = [c.strip() for c in response.text.split("\n---\n") if c.strip()]
        if chunks:
            # +++ USE THE CLEANER BEFORE SENDING +++
            cleaned_first_chunk = clean_html(chunks[0])
            await update.message.reply_text(
                cleaned_first_chunk,
                parse_mode=ParseMode.HTML, disable_web_page_preview=True
            )
            for i in range(1, len(chunks)):
                await asyncio.sleep(1.0)
                # +++ USE THE CLEANER BEFORE SENDING +++
                cleaned_chunk = clean_html(chunks[i])
                await context.bot.send_message(
                    chat_id=update.effective_chat.id, text=cleaned_chunk,
                    parse_mode=ParseMode.HTML, disable_web_page_preview=True
                )
        
    except Exception as e:
        logger.error(f"FATAL ERROR in handle_message for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text("🤯 Oops! Failed to generate response. Please try after some time.")
    finally:
        if hasattr(THREAD_LOCALS, 'context'): del THREAD_LOCALS.context
        if hasattr(THREAD_LOCALS, 'loop'): del THREAD_LOCALS.loop

# --- 5. MAIN BOT EXECUTION ---
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
    
    app.bot_data['shared_utils'] = {
        'user_chats': user_chats
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
