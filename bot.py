import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from google import genai

# Read secrets from environment variables
TOKEN = os.environ['BOT_TOKEN']
GEMINI_KEY = os.environ['GEMINI_KEY']

client = genai.Client(api_key=GEMINI_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("नमस्ते! मैं MantraAIBot हूँ 😎🔥")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_message
    )
    await update.message.reply_text(response.text)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("Bot ready for Render deployment!")
app.run_polling()
