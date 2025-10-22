import os
import logging
import json
from dotenv import load_dotenv
import threading
from flask import Flask
from unittest.mock import Mock
import asyncio

# Telegram Bot Library
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# Gemini AI Library
import google.generativeai as genai
from google.generativeai.types import content_types

# APNI FILES IMPORT KARNA
from prompts import SYSTEM_PROMPT_TEMPLATE
from tools.tool_manager import AVAILABLE_TOOLS
from tools import ui_tools
import settings

# --- 0. FLASK & SETUP ---
app_flask = Flask(__name__)
@app_flask.route('/')
def hello_world(): return "Xylon AI is alive and kicking!"
def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)

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
    tools=list(AVAILABLE_TOOLS.values()) # Sirf naam bhejna
)
user_chats = {}

# --- 3. TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message_logic(update, context, is_start_command=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message_logic(update, context)
    
async def handle_message_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, is_start_command: bool = False):
    user = update.effective_user
    
    if is_start_command:
        message_text = "User has just started. Greet them and offer choices with the `create_buttons` tool."
    else:
        message_text = update.message.text

    if 'next_message_is' in context.user_data:
        # ... (Settings waala logic waisa hi rahega) ...
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # UI tools ko batana ki message kahan bhejna hai
    ui_tools.set_telegram_context(context, update.effective_chat.id)

    if user.id not in user_chats:
        personalization_section = ""
        # ... (Personalisation waala logic waisa hi rahega) ...
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(user_name=user.first_name, user_personalization_section=personalization_section)
        user_chats[user.id] = [{'role': 'user', 'parts': [{'text': system_prompt}]}, {'role': 'model', 'parts': [{'text': f"Okay, I am 𝐗𝐲𝐥𝐨𝐧 𝐀𝐈, ready to chat! 😎"}]}]
    
    user_chats[user.id].append({'role': 'user', 'parts': [{'text': message_text}]})
    
    try:
        # --- MANUAL FUNCTION CALLING LOOP ---
        while True:
            response = await model.generate_content_async(user_chats[user.id])
            
            # Check karna ki response mein function call hai ya nahi
            if not response.candidates or not response.candidates[0].content.parts or not response.candidates[0].content.parts[0].function_call:
                # Agar nahi, toh yeh final text hai. Loop tod do.
                break
            
            # Agar hai, toh tool call process karo
            fc = response.candidates[0].content.parts[0].function_call
            tool_name = fc.name
            
            if tool_name not in AVAILABLE_TOOLS:
                tool_result = f"Error: Tool '{tool_name}' not found."
            else:
                logger.info(f"Gemini wants to call tool: {tool_name}")
                tool_function = AVAILABLE_TOOLS[tool_name]
                tool_args = {key: value for key, value in fc.args.items()}
                
                if asyncio.iscoroutinefunction(tool_function):
                    tool_result = await tool_function(**tool_args)
                else:
                    tool_result = tool_function(**tool_args)

            # History mein function call aur uska result dono jodna
            user_chats[user.id].append(content_types.to_dict(response.candidates[0].content))
            user_chats[user.id].append({
                'role': 'model',
                'parts': [content_types.to_part(dict(function_response=dict(name=tool_name, response=dict(content=tool_result))))]
            })

        # Jab loop khatm ho jaye, toh final text response milega
        bot_reply_text = response.text
        
        # Final jawab ko history mein save karna
        user_chats[user.id].append({'role': 'model', 'parts': [{'text': bot_reply_text}]})
        
        # User ko final jawab bhejna (agar text khaali nahi hai)
        if bot_reply_text.strip():
            await update.message.reply_text(bot_reply_text)

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
        pass
    
    fake_update = Mock()
    fake_update.effective_user = query.from_user
    fake_update.message = Mock(text=clicked_data, chat_id=query.message.chat_id)
    
    await handle_message_logic(fake_update, context)

# --- 4. MAIN BOT EXECUTION ---
def main():
    settings.load_user_profiles_settings(json.load(open(settings.USER_PROFILES_FILE)) if os.path.exists(settings.USER_PROFILES_FILE) else {}, user_chats)
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setting", settings.settings_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(settings.settings_button_handler, pattern=r'^set_|^settings_|^clear_|^close_'))
    app.add_handler(CallbackQueryHandler(dynamic_button_handler))
    
    logger.info(f"🚀 Xylon AI Bot is starting polling with model: {MODEL_NAME}")
    app.run_polling()

if __name__ == "__main__":
    if os.path.exists(settings.USER_PROFILES_FILE):
        with open(settings.USER_PROFILES_FILE, 'r', encoding='utf-8') as f:
            profiles = json.load(f)
            settings.load_user_profiles_settings({int(k): v for k, v in profiles.items()}, user_chats)

    logger.info("🚀 Starting Flask server for Xylon AI in a separate thread...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    logger.info("🚀 Starting Xylon AI Bot in the main thread...")
    main()
