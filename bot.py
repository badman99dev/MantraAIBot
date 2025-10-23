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
from google.generativeai.types import content_types

# APNI NAYI FILES IMPORT KARNA
from prompts import SYSTEM_PROMPT_TEMPLATE
from tools.youtube_transcript import fetch_youtube_details_from_api
from tools.quiz_tool import create_quiz_data
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
# tool_manager.py se poori list import karna
from tools.tool_manager import ALL_TOOLS

# ...

model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    tools=ALL_TOOLS # Ab yeh zyada saaf-suthra lag raha hai
)
user_chats = {} 

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
        user_chats[user_id] = model.start_chat(history=initial_history)
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
        
        candidate = response.candidates[0]
        # Sabse safe tareeka check karne ka
        if (candidate.content and candidate.content.parts and 
            hasattr(candidate.content.parts[0], 'function_call')):
            
            # YEH TOOL CALL HAI
            fc = candidate.content.parts[0].function_call
            tool_name = fc.name
            tool_args = {key: value for key, value in fc.args.items()}
            
            logger.info(f"Gemini requested tool '{tool_name}' with args: {tool_args}")
            
            if tool_name == "fetch_youtube_details_from_api":
                tool_result = fetch_youtube_details_from_api(**tool_args)
            
            elif tool_name == "create_quiz_data":
                quiz_data = create_quiz_data(**tool_args)
                if quiz_data:
                    await context.bot.send_poll(
                        chat_id=update.effective_chat.id,
                        question=quiz_data["question"],
                        options=quiz_data["options"],
                        type='quiz',
                        correct_option_id=quiz_data["correct_option_index"],
                        explanation=quiz_data["explanation"]
                    )
                    tool_result = "Quiz successfully created and sent to the user."
                else:
                    tool_result = "Error: Could not create quiz data."
            else:
                tool_result = "Error: Unknown tool called."

            second_response = await chat_session.send_message_async(
                content_types.to_part(dict(function_response=dict(name=tool_name, response=dict(content=tool_result))))
            )
            bot_reply_text = second_response.text
        else:
            # YEH NORMAL TEXT HAI
            bot_reply_text = response.text
        
        await update.message.reply_text(bot_reply_text)

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
            settings.load_user_profiles_settings({}, user_chats)

    logger.info("🚀 Starting Flask server for Xylon AI in a separate thread...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    logger.info("🚀 Starting Xylon AI Bot in the main thread...")
    main()
