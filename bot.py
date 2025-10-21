import os
import logging
from dotenv import load_dotenv
import httpx
import threading
from flask import Flask

# Telegram Bot Library
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Gemini AI Library
import google.generativeai as genai

# --- 0. FLASK WEB SERVER SETUP ---
app_flask = Flask(__name__)
@app_flask.route('/')
def hello_world():
    return "MantraAIBot is alive and kicking!"
def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)

# --- 1. SETUP ---
load_dotenv()
TOKEN = os.environ['BOT_TOKEN']
GEMINI_KEY = os.environ['GEMINI_KEY']
VERCEL_API_URL = "https://gyanflow-backend-n5clvllqw-badals-projects-03fab3df.vercel.app/api/getTranscript"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_KEY)

# --- 2. SYSTEM PROMPT ---
SYSTEM_PROMPT_TEMPLATE = """
You are MantraAIBot 🤖. Your personality is friendly, witty, and helpful.
You are talking to a user named '{user_name}'.

Your core rules:
1.  **Tone:** Be conversational. Answer in the same language the user asked. For Hindi, use Devanagari script and mix some English (Hinglish) to be realistic.
2.  **Emojis:** Use emojis to be engaging. 😎🔥🎬💡
3.  **Context:** When you get YouTube tool info, use it! Mention the channel name, views etc.
4.  **Goal:** Be helpful.
"""

# --- 3. TOOL DEFINITION ---
async def fetch_youtube_details_from_api(video_url: str) -> str:
    logger.info(f"[AUTOMATIC] Gemini is calling the tool for URL: {video_url}")
    try:
        # NOTE: Automatic function calling library works best with synchronous functions.
        # We will use httpx's sync client here.
        with httpx.Client() as client:
            params = {"youtubeUrl": video_url}
            response = client.get(VERCEL_API_URL, params=params, timeout=45.0)
            response.raise_for_status()
            logger.info("[AUTOMATIC] Successfully received data from Vercel API.")
            return response.text
    except Exception as e:
        error_message = f"Transcript laane mein dikkat aayi: {e}"
        logger.error(error_message)
        return error_message

# --- 4. GEMINI MODEL & CHAT MANAGEMENT ---
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    tools=[fetch_youtube_details_from_api]
)
user_chats = {}

def get_or_create_chat_session(user_id: int, user_name: str) -> genai.ChatSession:
    if user_id not in user_chats:
        logger.info(f"Creating new chat session for user {user_name} ({user_id}).")
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(user_name=user_name)
        initial_history = [
            {'role': 'user', 'parts': [{'text': system_prompt}]},
            {'role': 'model', 'parts': [{'text': f"Okay, I understand. I am MantraAIBot, ready to chat with {user_name}! 😎"}]}
        ]
        # YAHI HAI GOOGLE KA MAGIC!
        user_chats[user_id] = model.start_chat(
            history=initial_history,
            enable_automatic_function_calling=True # <-- IS LINE KO ENABLE KAR DIYA
        )
    return user_chats[user_id]

# --- 5. TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    chat_session = get_or_create_chat_session(user.id, user.first_name)
    welcome_instruction = "Please greet me warmly as a new user. Introduce yourself as MantraAIBot and briefly mention what you can do (chat and summarize YouTube videos)."
    try:
        response = await chat_session.send_message_async(welcome_instruction)
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Error in /start: {e}")
        await update.message.reply_text(f"नमस्ते {user.first_name}! 😎 मैं MantraAIBot हूँ।")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    chat_session = get_or_create_chat_session(user.id, user.first_name)
    try:
        # DEKHIYE! Ab code kitna saaf ho gaya hai.
        # Library saara jaadu khud kar legi.
        response = await chat_session.send_message_async(message_text)
        await update.message.reply_text(response.text)

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await update.message.reply_text("⚠️ माफ करना, कुछ तकनीकी दिक्कत आ गई है।")

# --- 6. MAIN BOT EXECUTION ---
def run_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("🚀 Telegram Bot is starting polling...")
    app.run_polling()

if __name__ == "__main__":
    logger.info("🚀 Starting Flask server in a separate thread...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    logger.info("🚀 Starting Bot in the main thread...")
    run_bot()
