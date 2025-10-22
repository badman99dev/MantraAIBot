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
VERCEL_API_URL = "https://youtube-transcript-dp2flwk98-badals-projects-03fab3df.vercel.app/api/transcript"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gemini API key setup
genai.configure(api_key=GEMINI_KEY)

# --- 2. SYSTEM PROMPT ---
SYSTEM_PROMPT_TEMPLATE = """
You are MantraAI 🤖. You are accessible by Telegram users. Your personality is friendly, witty, and helpful.
When real-time or fresh data is needed, always use the live search tool (Google Search grounding) to fetch latest results. Provide grounded answers with clear citations.
You are talking to a user named '{user_name}'. You can know the name of the user from his Telegram ID.
Tone: Hindi (Devanagari) with Hinglish touches, emojis, concise.
"""

# --- 3. TOOL DEFINITION ---
# YouTube Transcript Getter
def fetch_youtube_details_from_api(video_id: str) -> str:
    logger.info(f"[GEMINI-WORKER] Gemini extracted ID: {video_id} and is calling the tool.")
    if not video_id or len(video_id) != 11:
        return "Error: Invalid YouTube Video ID received."
    try:
        with httpx.Client() as client:
            api_url_with_param = f"{VERCEL_API_URL}?v={video_id}"
            response = client.get(api_url_with_param, timeout=45.0)
            response.raise_for_status()
            data = response.json()
            if not data or not data.get("success"):
                return "Maaf karna, backend se transcript laane mein dikkat aayi."
            formatted_text = (
                f"वीडियो टाइटल: {data.get('title', 'N/A')}
"
                f"चैनल: {data.get('channelTitle', 'N/A')}
"
                f"सब्सक्राइबर: {data.get('channelSubscribers', 'N/A')}
"
                f"व्यूज: {data.get('viewCount', 'N/A')}
"
                f"लाइक्स: {data.get('likeCount', 'N/A')}
"
                "━━━━━━━━━━━━━━━━━━━━━━━
"
                f"ट्रांसक्रिप्ट:
{data.get('transcript', 'Transcript not available.')}"
            )
            return formatted_text
    except Exception as e:
        logger.error(f"Backend se transcript laane mein dikkat aayi: {e}")
        return "Backend se transcript laane mein dikkat aayi."

# Google Search grounding tool placeholder (actual integration is handled by Gemini SDK)
# We simply declare a placeholder to illustrate the intent in this standalone code.
# In real deployment, register the official tool object as per the SDK version.

def google_search_placeholder(query: str) -> str:
    # This is a placeholder function. In actual deployment, the Gemini SDK will handle
    # invocation of the live search tool and return grounded results with citations.
    return "कृपया अपनी क्वेरी दें ताकि live search results आपके लिए fetch किये जा सकें।"

# --- 4. GEMINI MODEL & CHAT MANAGEMENT ---
# Proper tool registrations depend on your SDK version.
# The following assumes the SDK accepts a list of tool callables or properly registered tools.

# Build tool list: include both the custom function and the Google Search grounding tool
tools = [
    fetch_youtube_details_from_api,           # custom YouTube transcript tool
    google_search_placeholder                 # placeholder for Google Search grounding
]

model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    # In a real setup, replace the placeholder with the actual tool registration object, e.g.:
    # tools=[custom_tool, google_search_tool]
    tools=tools
)

user_chats = {}

def get_or_create_chat_session(user_id: int, user_name: str) -> genai.ChatSession:
    if user_id not in user_chats:
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(user_name=user_name)
        initial_history = [
            {'role': 'user', 'parts': [{'text': system_prompt}]},
            {'role': 'model', 'parts': [{'text': f"Okay, I understand. I am MantraAIBot, ready to chat with {user_name}! 😎"}]}
        ]
        user_chats[user_id] = model.start_chat(
            history=initial_history,
            enable_automatic_function_calling=True
        )
    return user_chats[user_id]

# --- 5. TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    chat_session = get_or_create_chat_session(user.id, user.first_name)
    welcome_instruction = "नमस्ते! मैं MantraAIBot हूँ। आप मुझसे सवाल कर सकते हैं या YouTube वीडियो का सारांश पूछ सकते हैं।"
    try:
        response = await chat_session.send_message_async(welcome_instruction)
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Error in /start: {e}")
        await update.message.reply_text(f"नमस्ते {user.first_name}! मैं MantraAIBot हूँ।")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    await context.bot.send_chat_action(update.effective_chat.id, 'typing')
    chat_session = get_or_create_chat_session(user.id, user.first_name)
    try:
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
