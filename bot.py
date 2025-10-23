import os
import logging
from dotenv import load_dotenv
import threading
from flask import Flask
import json

# Telegram Bot Library
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# Gemini AI Library
import google.generativeai as genai

# APNI NAYI FILES IMPORT KARNA
from prompts import SYSTEM_PROMPT_TEMPLATE
from tools.tool_manager import AVAILABLE_TOOLS
import settings

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
GEMINI_KEY = os.environ['GEMINI_KEY']
MODEL_NAME = os.environ.get('MODEL_NAME', 'gemini-1.5-flash')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_KEY)

# --- 2. GEMINI MODEL & CHAT MANAGEMENT ---
model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    tools=AVAILABLE_TOOLS
)
user_chats = {} # Conversation history

# settings.py ko user data pass karna
settings.load_user_profiles_settings(settings.user_profiles, user_chats)

def get_or_create_chat_session(user_id: int, user_name: str) -> genai.ChatSession:
    if user_id not in user_chats:
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
        user_chats[user_id] = model.start_chat(
            history=initial_history,
            enable_automatic_function_calling=True
        )
    return user_chats[user_id]

# --- 3. TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    chat_session = get_or_create_chat_session(user.id, user.first_name)
    welcome_instruction = "Please greet me warmly as a new user. Introduce yourself as 𝐗𝐲𝐥𝐨𝐧 𝐀𝐈 and briefly mention what you can do (chat and summarize YouTube videos, or create a quiz)."
    try:
        response = await chat_session.send_message_async(welcome_instruction)
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Error in /start: {e}")
        await update.message.reply_text(f"नमस्ते {user.first_name}! 😎 मैं 𝐗𝐲𝐥𝐨𝐧 𝐀𝐈 हूँ।")

# YAHI HAI ASLI BADLAV
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    
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
    try:
        response = await chat_session.send_message_async(message_text)
        
        # Step 1: Pehle check karo ki history mein aakhri message hai bhi ya nahi
        if chat_session.history and len(chat_session.history) > 0:
            last_message = chat_session.history[-1]
            
            # Step 2: Ab "SAFE" tareeke se check karo ki kya yeh tool call ka result hai
            if (last_message.role == 'model' and 
                last_message.parts and 
                hasattr(last_message.parts[0], 'function_response') and # YEH HAI ASLI FIX!
                last_message.parts[0].function_response):
                
                tool_response = last_message.parts[0].function_response
                
                if tool_response.name == 'create_quiz':
                    quiz_info = tool_response.response
                    if quiz_info and quiz_info.get('type') == 'quiz':
                        quiz_data = quiz_info.get('data')
                        await context.bot.send_poll(
                            chat_id=update.effective_chat.id,
                            question=quiz_data["question"],
                            options=quiz_data["options"],
                            type='quiz',
                            correct_option_id=quiz_data["correct_option_index"],
                            explanation=quiz_data["explanation"]
                        )
                        return
                    elif quiz_info and quiz_info.get('type') == 'error':
                        await update.message.reply_text(quiz_info.get('data'))
                        return

        # Agar upar kuch nahi hua, iska matlab yeh normal text ya YouTube summary hai
        await update.message.reply_text(response.text)

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await update.message.reply_text("⚠️ माफ करना, कुछ तकनीकी दिक्कत आ गई ਹੈ।")

# --- 4. MAIN BOT EXECUTION ---
def main():
    if os.path.exists(settings.USER_PROFILES_FILE):
        try:
            with open(settings.USER_PROFILES_FILE, 'r', encoding='utf-8') as f:
                profiles = json.load(f)
                settings.load_user_profiles_settings({int(k): v for k, v in profiles.items()}, user_chats)
        except (json.JSONDecodeError, ValueError):
            logger.error("Could not load user profiles, file might be empty or corrupt.")
            settings.load_user_profiles_settings({}, user_chats)

    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setting", settings.settings_command))
    app.add_handler(CallbackQueryHandler(settings.settings_button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info(f"🚀 Xylon AI Bot is starting polling with model: {MODEL_NAME}")
    app.run_polling()

if __name__ == "__main__":
    if os.path.exists(settings.USER_PROFILES_FILE):
        try:
            with open(settings.USER_PROFILES_FILE, 'r', encoding='utf-8') as f:
                profiles = json.load(f)
                settings.load_user_profiles_settings({int(k): v for k, v in profiles.items()}, user_chats)
        except (json.JSONDecodeError, ValueError):
            logger.error("Could not load user profiles on startup.")
            settings.load_user_profiles_settings({}, user_chats)

    logger.info("🚀 Starting Flask server for Xylon AI in a separate thread...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    logger.info("🚀 Starting Xylon AI Bot in the main thread...")
    main()
