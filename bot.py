import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from google import genai

# Load secrets
load_dotenv()
TOKEN = os.environ['BOT_TOKEN']
GEMINI_KEY = os.environ['GEMINI_KEY']

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

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_name = user.first_name or "User"

    message = (
        f"नमस्ते {user_name}! 😎🔥 मैं MantraAIBot हूँ। आप मुझसे चैट कर सकते हैं!\n\n"
        f"📌 Current features:\n" + "\n".join(CURRENT_FEATURES) + "\n\n"
        f"🔮 Future features:\n" + "\n".join(FUTURE_FEATURES)
    )
    await update.message.reply_text(message)

# Chat handler
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    user_name = user.first_name or "User"
    user_username = user.username or "NoUsername"
    chat_id = update.effective_chat.id

    message_text = update.message.text

    # Initialize context
    if user_id not in user_context:
        user_context[user_id] = []

    # Append new message
    user_context[user_id].append(f"{user_name}: {message_text}")

    # Trim history
    if len(user_context[user_id]) > MAX_HISTORY:
        user_context[user_id] = user_context[user_id][-MAX_HISTORY:]

    conversation_history = "\n".join(user_context[user_id])

    # System prompt for Gemini
    SYSTEM_PROMPT = f"""
You are MantraAIBot 🤖.
The user interacting with you is {user_name} (Telegram username: {user_username}, chat ID: {chat_id}).
- Currently, you can chat with the user.
- In the future, you will be able to convert/compress files, edit PDFs, and get YouTube transcripts.
- Always respond in friendly tone with emojis 😎🔥.
- Keep replies concise, helpful, and avoid repetition.
"""

    # Send request to Gemini
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{SYSTEM_PROMPT}\nConversation so far:\n{conversation_history}\nBot:"
        )
        bot_reply = response.text
        # Append bot reply to context
        user_context[user_id].append(f"Bot: {bot_reply}")

        await update.message.reply_text(bot_reply)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error contacting Gemini AI: {e}")

# Setup Telegram bot
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("🚀 MantraAIBot ready for Render deployment!")
app.run_polling()
