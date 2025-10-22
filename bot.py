import os
import logging
from dotenv import load_dotenv
import httpx
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Gemini AI Library
import google.generativeai as genai

# --- Flask server setup ---
app_flask = Flask(__name__)

@app_flask.route('/')
def hello_world():
    return "MantraAIBot is alive and kicking!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)

# --- Load env variables ---
load_dotenv()
TOKEN = os.environ['BOT_TOKEN']
GEMINI_KEY = os.environ['GEMINI_KEY']
VERCEL_API_URL = "https://youtube-transcript-dp2flwk98-badals-projects-03fab3df.vercel.app/api/transcript"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_KEY)

# --- System prompt ---
SYSTEM_PROMPT_TEMPLATE = """
You are MantraAI 🤖. You are accessible by Telegram users.  
Use friendly, helpful tone in Hindi (Devanagari) mixed with Hinglish with emojis.  
When up-to-date info is needed, use Google Search tool and cite sources.  
For general queries, answer using internal knowledge.
"""

# --- YouTube transcript function ---
def fetch_youtube_details_from_api(video_id: str) -> str:
    logger.info(f"[GEMINI-WORKER] Gemini extracted ID: {video_id} and is calling the tool.")
    if not video_id or len(video_id) != 11:
        return "Error: Invalid YouTube Video ID received."
    try:
        with httpx.Client() as client:
            response = client.get(f"{VERCEL_API_URL}?v={video_id}", timeout=45.0)
            response.raise_for_status()
            data = response.json()
            if not data or not data.get("success"):
                return "Maaf karna, backend se transcript laane mein dikkat aayi."
            return (
                f"वीडियो टाइटल: {data.get('title','N/A')}
"
                f"चैनल: {data.get('channelTitle','N/A')}
"
                f"सब्सक्राइबर: {data.get('channelSubscribers','N/A')}
"
                f"व्यूज: {data.get('viewCount','N/A')}
"
                f"लाइक्स: {data.get('likeCount','N/A')}
"
                f"━━━━━━━━━━━━━━━
"
                f"ट्रांसक्रिप्ट:
{data.get('transcript','Transcript not available.')}"
            )
    except Exception as e:
        logger.error(f"Error fetching transcript: {e}")
        return "Backend se transcript laane mein dikkat aayi."

# --- Register tools correctly ---
# Custom tool
custom_tool = fetch_youtube_details_from_api

# Google Search tool (official SDK tool instance, note: name must be exact)
google_search_tool = genai.Tool(name="google_search")

# --- Gemini model setup with multiple tools ---
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    tools=[custom_tool, google_search_tool]
)

user_chats = {}

def get_or_create_chat_session(user_id: int, user_name: str) -> genai.ChatSession:
    if user_id not in user_chats:
        system_prompt = SYSTEM_PROMPT_TEMPLATE
        initial_history = [
            {'role': 'user', 'parts': [{'text': system_prompt}]},
            {'role': 'model', 'parts': [{'text': f"Okay, I understand. I am MantraAIBot, ready to chat with {user_name}! 😎"}]}
        ]
        user_chats[user_id] = model.start_chat(
            history=initial_history,
            enable_automatic_function_calling=True,
        )
    return user_chats[user_id]

# --- Telegram handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await context.bot.send_chat_action(update.effective_chat.id, 'typing')
    chat_session = get_or_create_chat_session(user.id, user.first_name)
    welcome_text = "नमस्ते! मैं MantraAIBot हूँ। आप मुझसे सवाल कर सकते हैं या YouTube वीडियो का सारांश पूछ सकते हैं।"
    try:
        response = await chat_session.send_message_async(welcome_text)
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Error in start handler: {e}")
        await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    await context.bot.send_chat_action(update.effective_chat.id, 'typing')
    chat_session = get_or_create_chat_session(user.id, user.first_name)
    try:
        response = await chat_session.send_message_async(message_text)
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Error in message handler: {e}", exc_info=True)
        await update.message.reply_text("ख़ेद है, कुछ तकनीकी दिक्कत आ गई है।")

# --- Run bot ---
def run_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("🚀 Starting Telegram bot polling...")
    app.run_polling()

if __name__ == "__main__":
    logger.info("🚀 Starting Flask web server thread...")
    threading.Thread(target=run_flask).start()

    logger.info("🚀 Starting Telegram bot main thread...")
    run_bot()
