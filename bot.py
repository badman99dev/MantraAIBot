import os
import logging
import re
import json
from dotenv import load_dotenv
import threading
from flask import Flask
from unittest.mock import Mock # Button clicks ko handle karne ke liye

# Telegram Bot Library
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    welcome_instruction = "Please greet me warmly as a new user. Introduce yourself as 𝐗𝐲𝐥𝐨𝐧 𝐀𝐈 and offer some choices with buttons, like asking about my features or just chatting."
    try:
        # Start command ko bhi normal message ki tarah handle karna taaki woh bhi buttons bana sake
        await handle_message_logic(update, context, custom_text=welcome_instruction)
    except Exception as e:
        logger.error(f"Error in /start: {e}")
        await update.message.reply_text(f"नमस्ते {user.first_name}! 😎 मैं 𝐗𝐲𝐥𝐨𝐧 𝐀𝐈 हूँ।")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message_logic(update, context)

async def handle_message_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, custom_text: str = None):
    user = update.effective_user
    message_text = custom_text or update.message.text
    
    # Settings waale input ko handle karna
    if 'next_message_is' in context.user_data:
        state = context.user_data.pop('next_message_is')
        if user.id not in settings.user_profiles: settings.user_profiles[user.id] = {}
        settings.user_profiles[user.id][state] = message_text
        settings.save_user_profiles()
        await update.message.reply_text(f"✅ Theek hai, maine aapka '{state}' save kar liya hai! Main isse agle conversation se yaad rakhoonga.")
        if user.id in user_chats: del user_chats[user.id] # Chat session reset karna
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    chat_session = get_or_create_chat_session(user.id, user.first_name)
    
    try:
        response = await chat_session.send_message_async(message_text)
        gemini_response_text = response.text
        
        main_message = gemini_response_text
        
        # Dispatcher Logic: Check karna ki Gemini ne kya bheja hai
        
        # 1. Kya response mein Buttons hain?
        button_match = re.search(r'\[BUTTONS_JSON\](.*?)\[/BUTTONS_JSON\]', gemini_response_text, re.DOTALL)
        if button_match:
            json_string = button_match.group(1).strip()
            main_message = gemini_response_text.split('[BUTTONS_JSON]')[0].strip()
            try:
                buttons_data = json.loads(json_string)
                keyboard = [[InlineKeyboardButton(b['text'], callback_data=b['callback_data']) for b in row] for row in buttons_data]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(main_message, reply_markup=reply_markup)
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Gemini produced invalid Button JSON: {json_string} | Error: {e}")
                await update.message.reply_text(gemini_response_text)
            return

        # 2. Kya response mein Quiz hai?
        quiz_match = re.search(r'\[QUIZ_JSON\](.*?)\[/QUIZ_JSON\]', gemini_response_text, re.DOTALL)
        if quiz_match:
            json_string = quiz_match.group(1).strip()
            main_message = gemini_response_text.split('[QUIZ_JSON]')[0].strip()
            if main_message:
                await update.message.reply_text(main_message)
            try:
                quiz_data = json.loads(json_string)
                await context.bot.send_poll(
                    chat_id=update.effective_chat.id,
                    question=quiz_data["question"],
                    options=quiz_data["options"],
                    type='quiz',
                    correct_option_id=quiz_data["correct_option_index"],
                    explanation=quiz_data.get("explanation", "")
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Gemini produced invalid Quiz JSON: {json_string} | Error: {e}")
                await update.message.reply_text(gemini_response_text)
            return

        # 3. Agar kuch nahi hai, toh yeh Normal Text hai
        await update.message.reply_text(main_message)

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await update.message.reply_text("⚠️ माफ करना, कुछ तकनीकी दिक्कत आ गई ਹੈ।")

async def dynamic_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    clicked_data = query.data
    logger.info(f"User {query.from_user.first_name} clicked dynamic button: '{clicked_data}'")
    
    try:
        await query.edit_message_text(text=f"👉 You selected: {query.message.text.splitlines()[0]} -> {clicked_data}")
    except Exception:
        pass # Agar message edit na ho paaye toh koi baat nahi
    
    # Fake update object banakar handle_message_logic ko call karna
    fake_update = Mock()
    fake_update.effective_user = query.from_user
    fake_update.message = Mock()
    fake_update.message.text = clicked_data
    fake_update.message.chat_id = query.message.chat_id # Chat ID zaroori hai
    
    await handle_message_logic(fake_update, context)

# --- 4. MAIN BOT EXECUTION ---
def main():
    settings.load_user_profiles_settings(json.load(open(settings.USER_PROFILES_FILE)) if os.path.exists(settings.USER_PROFILES_FILE) else {}, user_chats)
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setting", settings.settings_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Yahan do alag-alag button handler hain:
    # 1. Yeh sirf settings ke buttons ko handle karega (jinka data 'settings_' se shuru hota hai)
    app.add_handler(CallbackQueryHandler(settings.settings_button_handler, pattern=r'^set_|^settings_|^clear_|^close_'))
    # 2. Yeh baaki sabhi dynamic buttons ko handle karega
    app.add_handler(CallbackQueryHandler(dynamic_button_handler))
    
    logger.info(f"🚀 Xylon AI Bot is starting polling with model: {MODEL_NAME}")
    app.run_polling()

if __name__ == "__main__":
    settings.load_user_profiles_settings(json.load(open(settings.USER_PROFILES_FILE, 'r', encoding='utf-8')) if os.path.exists(settings.USER_PROFILES_FILE) else {}, user_chats)
    
    logger.info("🚀 Starting Flask server for Xylon AI in a separate thread...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    logger.info("🚀 Starting Xylon AI Bot in the main thread...")
    main()
