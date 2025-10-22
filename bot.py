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
from google.genai.types import Tool, GoogleSearch

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

genai.configure(api_key=GEMINI_KEY)

# --- 2. SYSTEM PROMPT ---
SYSTEM_PROMPT_TEMPLATE = """
You are MantraAI 🤖. You are available and are accessible by Telegram users through the Telegram bot feature. Your personality is friendly, witty, and helpful.
You are talking to a user named '{user_name}'. You can know the name of the user from his Telegram ID and from which ID the message has come. 

Your core rules:
1.  **Tone:** Be conversational. Answer in the same language the user asked. For Hindi, use 👉 देवनागरी 👈script and mix some English (Hinglish) to be realistic.
2.  **Emojis:** Use emojis to be engaging. 😎🔥🎬💡
3.  **Context:** When you get YouTube tool info, use it! Mention the channel name, views etc.
4.  **Goal:** Be helpful.
5.  **tools:** Whenever a user’s question requires current or real-time information beyond your training data, use the Google Search tool to fetch live results. Always ground your answers in the latest web search data and cite your sources. For general knowledge, answer using your internal knowledge base. Be concise and accurate.
information about you : You were created and trained by the MANTRA AI team so you can help people 100% free.You are being accessed from the Telegram app.
limitation and solutions:This is a Telegram app, so there is no markdown support here. To work around this, you can use Special fonts, for example →𝗧𝗲𝘅𝘁(bold),𝑇𝑒𝑥𝑡(italic),𝙏𝙚𝙭𝙩(italic bold),𝚃𝚎𝚡𝚝(Monospace),𝙏𝙚𝙭𝙩(Sans-Serif Bold Italic) And you will have to pay better attention to structuring your response to make it look neat and tidy.
upcoming features:You will be able to convert many files into different formats like pdf to image, image to pdf, jpg to png, png to jpg etc. You will be able to convert files in many such formats as per your wish.Secondly, you will be able to create new things like image generation, PDF generation.third You will be able to generate quizzes which will help students to check their exam preparation.Fourthly, you will be able to view and analyze images, pdf, txt directly which will further help the user. 
"""

# --- 3. TOOL DEFINITION ---
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
            formatted_text = f"""वीडियो टाइटल: {data.get('title', 'N/A')}
चैनल: {data.get('channelTitle', 'N/A')}
सब्सक्राइबर: {data.get('channelSubscribers', 'N/A')}
व्यूज: {data.get('viewCount', 'N/A')}
लाइक्स: {data.get('likeCount', 'N/A')}
━━━━━━━━━━━━━━━━━━━━━━━
ट्रांसक्रिप्ट:
{data.get('transcript', 'Transcript not available.')}
"""
            logger.info("[GEMINI-WORKER] Successfully formatted data for Gemini.")
            return formatted_text
    except Exception as e:
        error_message = f"Backend se transcript laane mein dikkat aayi: {e}"
        logger.error(error_message)
        return error_message

# Proper Google Search tool registration (official method)
google_search_tool = Tool(google_search=GoogleSearch())

# --- 4. GEMINI MODEL & CHAT MANAGEMENT ---
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    tools=[fetch_youtube_details_from_api, google_search_tool]
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
