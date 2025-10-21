import os
import logging
from dotenv import load_dotenv
import httpx
import threading  # Bot aur web server ko ek saath chalaane ke liye
from flask import Flask # Render ko "alive" signal dene ke liye

# Telegram Bot Library
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Gemini AI Library
import google.generativeai as genai
from google.generativeai.types import content_types

# --- 0. FLASK WEB SERVER SETUP ---
# Yeh chhota sa web server Render ko busy rakhega
app_flask = Flask(__name__)

@app_flask.route('/')
def hello_world():
    return "MantraAIBot is alive and kicking!"

def run_flask():
    # Render.com apne aap PORT environment variable set karta hai
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)

# --- 1. SETUP ---
load_dotenv()
TOKEN = os.environ['BOT_TOKEN']
GEMINI_KEY = os.environ['GEMINI_KEY']
VERCEL_API_URL = "https://gyanflow-backend-n5clvllqw-badals-projects-03fab3df.vercel.app/api/getTranscript"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_KEY)

# --- 2. SYSTEM PROMPT ---
SYSTEM_PROMPT_TEMPLATE = """
You are MantraAIBot 🤖. Your personality is friendly, witty, and helpful, like a knowledgeable friend.
You are talking to a user named '{user_name}'.

Your core rules:
1.  **Human-like Tone:** Always respond in a natural, conversational tone. And answer in the same language in which the user asked. And in Hindi language, by default write Hindi in Devanagari script and mix English in Hindi to keep your language and answers realistic.
2.  **Emoji Power:** Use emojis in every response to make the conversation more engaging and lively. 😎🔥🎬💡
3.  **Use Full Context:** When you get information from the YouTube tool, use this rich data! For example, you can say "Ah, I see this video is from the channel 'Channel Name'...".
4.  **Be Helpful:** Your main goal is to assist the user.
"""

# --- 3. TOOL DEFINITION ---
async def fetch_youtube_details_from_api(video_url: str) -> str:
    logger.info(f"Calling Vercel API for URL: {video_url}")
    try:
        async with httpx.AsyncClient() as client:
            params = {"youtubeUrl": video_url}
            response = await client.get(VERCEL_API_URL, params=params, timeout=45.0)
            response.raise_for_status()
            logger.info("Successfully received data from Vercel API.")
            return response.text
    except Exception as e:
        error_message = f"Transcript laane mein dikkat aayi: {e}"
        logger.error(error_message)
        return error_message

# --- 4. GEMINI MODEL & CHAT MANAGEMENT ---
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash', # Yahan 1.5 use karein, 2.5 abhi nahi aaya hai
    tools=[fetch_youtube_details_from_api]
)
user_chats = {}

def get_or_create_chat_session(user_id: int, user_name: str) -> genai.ChatSession:
    if user_id not in user_chats:
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(user_name=user_name)
        initial_history = [
            {'role': 'user', 'parts': [{'text': system_prompt}]},
            {'role': 'model', 'parts': [{'text': f"Okay, I understand. I am MantraAIBot, ready to chat with {user_name}! 😎"}]}
        ]
        user_chats[user_id] = model.start_chat(history=initial_history)
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
    except Exception:
        await update.message.reply_text(f"नमस्ते {user.first_name}! 😎 मैं MantraAIBot हूँ।")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    chat_session = get_or_create_chat_session(user.id, user.first_name)
    try:
        response = await chat_session.send_message_async(message_text)
        candidate = response.candidates[0]
        if candidate.finish_reason == 'TOOL_CALLS':
            tool_call = candidate.content.parts[0].function_call
            tool_name = tool_call.name
            if tool_name == 'fetch_youtube_details_from_api':
                tool_args = {key: value for key, value in tool_call.args.items()}
                tool_response_data = await fetch_youtube_details_from_api(**tool_args)
                tool_response_part = content_types.to_part({
                    "function_response": {"name": tool_name, "response": {"content": tool_response_data}}
                })
                second_response = await chat_session.send_message_async(tool_response_part)
                final_text = second_response.text
            else:
                final_text = "Maaf karna, mujhe ek anjaan tool istemaal karne ke liye kaha gaya. 😕"
        else:
            final_text = response.text
        await update.message.reply_text(final_text)
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await update.message.reply_text("⚠️ माफ करना, कुछ तकनीकी दिक्कत आ गई है।")

# --- 6. MAIN BOT EXECUTION ---
def run_bot():
    """Telegram bot ko polling mode mein start karta hai."""
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
