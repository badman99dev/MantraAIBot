import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from google import genai

# Load secrets
load_dotenv()
TOKEN = os.environ['BOT_TOKEN']
GEMINI_KEY = os.environ['GEMINI_KEY']

# Initialize Gemini client
client = genai.Client(api_key=GEMINI_KEY)

# User context memory
user_context = {}  # user_id: list of previous messages
MAX_HISTORY = 20  # Adjust based on memory needs

# Current and future features
CURRENT_FEATURES = [
    "Gemini AI chat 🤖"
]
FUTURE_FEATURES = [
    "File convert / compress 🗂️",
    "PDF edit ✏️",
    "YouTube transcript 🎬",
    "Other AI tools ⚡"
]

# -------------------- Gemini Chat Logic --------------------
async def gemini_chat(user_id: int, user_name: str, user_username: str, chat_id: int, user_message: str):
    # Initialize context
    if user_id not in user_context:
        user_context[user_id] = []

    # Append user message
    user_context[user_id].append(f"{user_name}: {user_message}")

    # Trim history
    if len(user_context[user_id]) > MAX_HISTORY:
        user_context[user_id] = user_context[user_id][-MAX_HISTORY:]

    conversation_history = "\n".join(user_context[user_id])

    # System prompt for Gemini
    SYSTEM_PROMPT = f"""
You are MantraAIBot 🤖.
The user interacting with you is {user_name} (Telegram username: {user_username}, chat ID: {chat_id}).
- Currently, you can chat with the user.
- In the future, you will be able to convert/compress files, edit PDFs, get YouTube transcripts, and other AI tools.
- Decide by yourself when to call tools and request JSON input/output. Only call tools when necessary.
- Always respond in friendly tone with emojis 😎🔥.
- Keep replies concise, helpful, and avoid repetition.
- Mention current capabilities and future features when user asks.
- If user sends a URL for YouTube, you may decide to call the transcript tool and summarize.
"""

    # Call Gemini
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{SYSTEM_PROMPT}\nConversation so far:\n{conversation_history}\nBot:"
        )
        bot_reply = response.text

        # Append bot reply to context
        user_context[user_id].append(f"Bot: {bot_reply}")
        return bot_reply
    except Exception as e:
        return f"⚠️ Error contacting Gemini AI: {e}"

# -------------------- Telegram Handlers --------------------
# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    first_name = user.first_name or "User"
    last_name = user.last_name or ""
    username = f"@{user.username}" if user.username else "NoUsername"
    display_name = first_name + (f" {last_name}" if last_name else "")
    chat_id = update.effective_chat.id

    # Gemini dynamic reply
    start_message = f"{display_name} has started the chat."
    bot_reply = await gemini_chat(user_id, display_name, username, chat_id, start_message)
    await update.message.reply_text(bot_reply)

# Normal chat messages
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    first_name = user.first_name or "User"
    last_name = user.last_name or ""
    username = f"@{user.username}" if user.username else "NoUsername"
    display_name = first_name + (f" {last_name}" if last_name else "")
    chat_id = update.effective_chat.id

    message_text = update.message.text

    # Gemini dynamic reply
    bot_reply = await gemini_chat(user_id, display_name, username, chat_id, message_text)
    await update.message.reply_text(bot_reply)

# -------------------- Setup Telegram Bot --------------------
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("🚀 MantraAIBot ready for Render deployment!")
app.run_polling()
