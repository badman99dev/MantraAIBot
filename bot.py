import os
import logging
from dotenv import load_dotenv
import threading
import asyncio
from flask import Flask
import json
from typing import AsyncGenerator

# Telegram Bot Library
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, PollAnswerHandler, JobQueue
from telegram.constants import ParseMode

# Gemini AI Library
import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse

# APNI FILES IMPORT KARNA
from prompts import SYSTEM_PROMPT_TEMPLATE
from tools.tool_manager import AVAILABLE_TOOLS
import settings
from shared_data import THREAD_LOCALS 

# === QUIZ GAME IMPORTS START ===
from quizzes.quiz_game import quiz_game_button_handler, quiz_game_poll_answer_handler
# === QUIZ GAME IMPORTS END ===

# +++ NEW: MESSAGE SPLITTING THRESHOLDS +++
SENTENCE_SPLIT_THRESHOLD = 1500
WORD_SPLIT_THRESHOLD = 2500
CHARACTER_SPLIT_THRESHOLD = 2800
TELEGRAM_MAX_MESSAGE_LENGTH = 3700 # Safety buffer for Telegram's ~4096 limit

# --- 0. FLASK WEB SERVER SETUP ---
# ... (Flask code remains unchanged) ...
app_flask = Flask(__name__)
@app_flask.route('/')
def hello_world(): return "Xylon AI is alive and kicking!"
def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)

# --- 1. SETUP ---
# ... (Setup code remains mostly unchanged) ...
load_dotenv()
TOKEN = os.environ['BOT_TOKEN']
GEMINI_KEYS_STRING = os.environ.get('GEMINI_KEYS')
if not GEMINI_KEYS_STRING:
    raise ValueError("GEMINI_KEYS not found in .env file. Please add it.")
API_KEYS = [key.strip() for key in GEMINI_KEYS_STRING.split(',')]
if not API_KEYS:
    raise ValueError("GEMINI_KEYS is empty. Please provide at least one API key.")

MODEL_NAME = os.environ.get('MODEL_NAME', 'gemini-1.5-flash')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 2. MODEL POOL AND KEY ROTATION LOGIC ---
# ... (Model pool logic remains unchanged) ...
MODEL_POOL = []
for key in API_KEYS:
    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_name=MODEL_NAME, tools=AVAILABLE_TOOLS)
    MODEL_POOL.append(model)
    logger.info(f"Initialized a model instance for key ending with '...{key[-4:]}'")

current_model_index = 0
model_lock = threading.Lock()

def get_next_model() -> genai.GenerativeModel:
    global current_model_index
    with model_lock:
        model = MODEL_POOL[current_model_index]
        current_model_index = (current_model_index + 1) % len(MODEL_POOL)
        return model

# --- 3. HISTORY MANAGEMENT ---
# ... (History management logic remains unchanged) ...
MAX_HISTORY_TOKENS = 50000
TRIM_BUFFER_TOKENS = 5000

async def manage_chat_history(chat_session: genai.ChatSession):
    try:
        model = chat_session.model
        token_count = (await model.count_tokens_async(chat_session.history)).total_tokens
        
        if token_count > MAX_HISTORY_TOKENS:
            logger.warning(f"Token count {token_count} is over the limit. Trimming.")
            current_history = chat_session.history
            safe_limit = MAX_HISTORY_TOKENS - TRIM_BUFFER_TOKENS
            while (await model.count_tokens_async(current_history)).total_tokens > safe_limit:
                if len(current_history) > 3:
                    del current_history[2]; del current_history[2]
                else:
                    break
            chat_session.history = current_history
            logger.info(f"History trimmed. New count: {(await model.count_tokens_async(chat_session.history)).total_tokens}")
    except Exception as e:
        logger.error(f"Error during chat history management: {e}", exc_info=True)

# --- 4. CHAT MANAGEMENT ---
# ... (Chat management logic remains unchanged) ...
user_chats = {} 
settings.load_user_profiles_settings(settings.user_profiles, user_chats)

def get_or_create_chat_session(user_id: int, user_name: str) -> genai.ChatSession:
    if user_id not in user_chats:
        logger.info(f"Creating new chat session for user {user_id}...")
        selected_model = get_next_model()
        logger.info(f"Assigned model with key '...{selected_model._client._api_key[-4:]}' to user {user_id}")
        # ... (rest of the function is the same) ...
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
        user_chats[user_id] = selected_model.start_chat(
            history=initial_history,
            enable_automatic_function_calling=True
        )
    return user_chats[user_id]


# +++ NEW: SMART MESSAGE SENDING & SPLITTING FUNCTION +++
async def send_split_message(update: Update, context: ContextTypes.DEFAULT_TYPE, response_stream: AsyncGenerator[GenerateContentResponse, None]) -> str:
    """
    Streams a response from Gemini, splits it into intelligent chunks based on length thresholds,
    and sends them to the user. Returns the full, unsplit text.
    """
    full_response_text = ""
    current_chunk = ""
    split_chars = ['.', '।', '?', '!', '\n']

    try:
        async for chunk in response_stream:
            # Sometimes empty chunks with function calls come through, ignore them.
            if not chunk.text:
                continue
                
            current_chunk += chunk.text
            full_response_text += chunk.text
            
            # Use a variable to decide if we need to split in this iteration
            should_split = False
            split_pos = -1

            # Rule 1: Sentence-level split
            if len(current_chunk) > SENTENCE_SPLIT_THRESHOLD:
                for i in range(len(current_chunk) - 1, SENTENCE_SPLIT_THRESHOLD, -1):
                    if current_chunk[i] in split_chars:
                        split_pos = i + 1
                        should_split = True
                        break
            
            # Rule 2: Word-level split
            if not should_split and len(current_chunk) > WORD_SPLIT_THRESHOLD:
                pos = current_chunk.rfind(' ', 0, WORD_SPLIT_THRESHOLD)
                if pos != -1:
                    split_pos = pos + 1
                    should_split = True

            # Rule 3: Character-level split (Hard limit)
            if not should_split and len(current_chunk) > CHARACTER_SPLIT_THRESHOLD:
                split_pos = CHARACTER_SPLIT_THRESHOLD
                should_split = True

            # If a split point was found, send the message
            if should_split:
                message_to_send = current_chunk[:split_pos]
                remaining_text = current_chunk[split_pos:]
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=message_to_send,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                current_chunk = remaining_text
                # A small delay can make the streaming feel more natural
                await asyncio.sleep(0.5)

    except Exception as e:
        logger.error(f"Error during response streaming/splitting: {e}", exc_info=True)
        # Send any remaining partial text before raising the error
        if current_chunk:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=current_chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        # Re-raise the exception so the main handler can catch it and inform the user
        raise e

    # Send the final remaining chunk if any exists
    if current_chunk:
        # Final check to prevent sending a message that is still too long
        if len(current_chunk) > TELEGRAM_MAX_MESSAGE_LENGTH:
            for i in range(0, len(current_chunk), TELEGRAM_MAX_MESSAGE_LENGTH):
                await context.bot.send_message(chat_id=update.effective_chat.id, text=current_chunk[i:i+TELEGRAM_MAX_MESSAGE_LENGTH], parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=current_chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    
    return full_response_text


# --- 5. TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (start function remains unchanged) ...
    user = update.effective_user
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    try:
        chat_session = get_or_create_chat_session(user.id, user.first_name)
        response_stream = await chat_session.send_message_async(
            "User has just started the conversation. Greet them warmly as Xylon AI and briefly mention key features like chat, movie search, and our new pro-level quizzes.",
            stream=True
        )
        full_response = await send_split_message(update, context, response_stream)
        # Manually update history with the full response for context
        if chat_session.history and chat_session.history[-1].role == "model":
             chat_session.history[-1].parts[0].text = full_response

    except Exception as e:
        logger.error(f"FATAL ERROR during /start for user {user.id}: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=chat_id,
            text="🤯 Oops! Failed to generate response. Please try after some time."
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    
    try:
        # ... (settings logic remains unchanged) ...
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

        # --- MODIFIED: USE STREAMING AND SPLITTING ---
        response_stream = await chat_session.send_message_async(message_text, stream=True)
        full_response = await send_split_message(update, context, response_stream)
        
        # Manually update the last model message in history with the full, unsplit text
        # This is CRITICAL for maintaining proper context for the AI
        if chat_session.history and chat_session.history[-1].role == "model":
             chat_session.history[-1].parts[0].text = full_response
        
    except Exception as e:
        logger.error(f"FATAL ERROR in handle_message for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text("🤯 Oops! Failed to generate response. Please try after some time.")
    finally:
        if hasattr(THREAD_LOCALS, 'context'):
            del THРОЕAD_LOCALS.context
        if hasattr(THREAD_LOCALS, 'loop'):
            del THREAD_LOCALS.loop

# --- 6. MAIN BOT EXECUTION ---
# ... (main function remains unchanged) ...
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
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setting", settings.settings_command))
    app.add_handler(CallbackQueryHandler(settings.settings_button_handler, pattern='^settings_'))
    app.add_handler(CallbackQueryHandler(quiz_game_button_handler, pattern='^quizgame_'))
    app.add_handler(PollAnswerHandler(quiz_game_poll_answer_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info(f"🚀 Xylon AI Bot starting polling with {len(API_KEYS)} API key(s) in rotation.")
    app.run_polling()

if __name__ == "__main__":
    logger.info("🚀 Starting Flask server for Xylon AI in a separate thread...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    logger.info("🚀 Starting Xylon AI Bot in the main thread...")
    main()
