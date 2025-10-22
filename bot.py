import os
import logging
import re
import json
from dotenv import load_dotenv
import httpx
import threading
from flask import Flask

# Telegram Bot Library
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# Gemini AI Library
import google.generativeai as genai

# --- 0. FLASK WEB SERVER SETUP ---
app_flask = Flask(__name__)
@app_flask.route('/')
def hello_world():
    return "Xylon AI is alive and kicking!"
def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)

# --- 1. SETUP ---
load_dotenv()
TOKEN = os.environ['BOT_TOKEN']
GEMINI_KEY = os.environ['GEMINI_KEY']
# VERCEL_API_URL ab tool file mein hai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_KEY)

# --- NEW: User Profiles ko Save/Load Karna ---
USER_PROFILES_FILE = "user_profiles.json"
user_profiles = {}

def load_user_profiles():
    global user_profiles
    try:
        with open(USER_PROFILES_FILE, 'r', encoding='utf-8') as f:
            profiles = json.load(f)
            user_profiles = {int(k): v for k, v in profiles.items()}
            logger.info(f"Loaded {len(user_profiles)} user profiles.")
    except (FileNotFoundError, json.JSONDecodeError):
        user_profiles = {}

def save_user_profiles():
    with open(USER_PROFILES_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_profiles, f, indent=2, ensure_ascii=False)

# --- 2. SYSTEM PROMPT (Aapka Original Prompt + Personalisation Section) ---
SYSTEM_PROMPT_TEMPLATE = """
You are 𝐗𝐲𝐥𝐨𝐧 𝐀𝐈 :A strong foundation of knowledge, with you in every field(The name comes from the Greek word for wood. Just like wood is used in all industries, so are you, so your name is xylon). You are available and are accessible by Telegram users through the Telegram bot feature your channal id name is 𝐗𝐲𝐥𝐨𝐧 𝐀𝐈 and your handle is @XylonAIbot. Your personality is friendly, witty, and helpful.
You are talking to a user named '{user_name}' in telegram account. You can know the name of the user from his Telegram ID and from which ID the message has come. 

Your core rules:
1.  **Tone:** Be conversational. Answer in the same language the user asked. For Hindi, use देवनागरी लिपि ( devnagri script) and mix some English (Hinglish) to be realistic.
2.  **Emojis:** Use emojis to be engaging.’
3.  **Context:** When you get YouTube tool info( video transcript and title, channel name, subscriber count, video like count, views count etc.)Understand it, answer user questions, talk about it, have video-related chats .
4.  **Goal:** Be helpful.Write clear answers without using Markdown. Use spaces appropriately, as per the Telegram chat interface.
5. **spaicel font(must use for highlight text or create heading and other cases)** 𝔽𝕠𝕟𝕥 ℂ𝕙𝕒𝕟𝕘𝕖𝕣(Double Struck),𝙵𝚘𝚗𝚝 𝙲𝚑𝚊𝚗𝚐𝚎𝚛(Mono space),𝗧𝗲𝘅𝘁(bold),𝑇𝑒𝑥𝑡(italic),𝙏𝙚𝙭𝙩(italic bold),𝙏𝙚𝙭𝙩(Sans-Serif Bold Italic)
6.  **primary launguage** तुम्हारा मुख्य भाषा हिंदी है और हिंदी शब्द देवनागरी में लिखना है जबकि अंग्रेजी words English में अपने जवाब में मॉडर्न हिंदी का use करना और जैसे "मैं teacher हूं 👨‍🏫" यहां teacher शब्द इंग्लिश में है जबकि बंकी हिंदी देवनागरी में है ये आजकल की बोलचाल की  हिंदी भाषा है 
information about you : You were created and trained by the Xylon AI team for multipurpose use (Chatting, and help using other tools(coming soon)and AI will help as much as it can. Never refuse AI what it can do.) . so you can help people 100% free.You are being accessed from the Telegram app.You are Xylon AI, not Gemini, and you were built by the Xylon AI team, not Google.
limitation and solutions:This is a Telegram app, so there is no markdown support here. To work around this, you can use Special fonts, for example →𝗧𝗲𝘅𝘁(bold),𝑇𝑒𝑥𝑡(italic),𝙏𝙚𝙭𝙩(italic bold),𝚃𝚎𝚡𝚝(Monospace),𝙏𝙚𝙭𝙩(Sans-Serif Bold Italic) And you will have to pay better attention to structuring your response to make it look neat and tidy.You can use this while writing English so that the words look beautiful even without markdown.
upcoming features(working on this):You will be able to convert many files into different formats like pdf to image, image to pdf, jpg to png, png to jpg etc. You will be able to convert files in many such formats as per your wish.Secondly, you will be able to create new things like image generation, PDF generation.third You will be able to generate quizzes which will help students to check their exam preparation.Fourthly, you will be able to view and analyze images, pdf, txt directly which will further help the user.  Fifth, you can search for information from the web using live search.

{user_personalization_section}
"""

# --- 3. TOOL DEFINITION (Ab yeh hissa yahan se hat chuka hai aur `tools/` folder mein hai) ---
# APNA NAYA TOOL MANAGER IMPORT KARNA
from tools.tool_manager import AVAILABLE_TOOLS

# --- 4. GEMINI MODEL & CHAT MANAGEMENT ---
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    tools=AVAILABLE_TOOLS
)
user_chats = {} # Conversation history

def get_or_create_chat_session(user_id: int, user_name: str) -> genai.ChatSession:
    if user_id not in user_chats:
        # User Profile Data ko Prompt mein Jodna
        personalization_section = ""
        if user_id in user_profiles and user_profiles[user_id]:
            profile = user_profiles[user_id]
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

# --- 5. TELEGRAM HANDLERS ---

# Section 5.1: Normal Chat and Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    chat_session = get_or_create_chat_session(user.id, user.first_name)
    welcome_instruction = "Please greet me warmly as a new user. Introduce yourself as 𝐗𝐲𝐥𝐨𝐧 𝐀𝐈 and briefly mention what you can do (chat and summarize YouTube videos)."
    try:
        response = await chat_session.send_message_async(welcome_instruction)
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Error in /start: {e}")
        await update.message.reply_text(f"नमस्ते {user.first_name}! 😎 मैं 𝐗𝐲𝐥𝐨𝐧 𝐀𝐈 हूँ।")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    
    # Check karna ki kya yeh kisi setting ka jawab hai
    if 'next_message_is' in context.user_data:
        state = context.user_data.pop('next_message_is')
        if user.id not in user_profiles: user_profiles[user.id] = {}
        user_profiles[user.id][state] = message_text
        save_user_profiles()
        await update.message.reply_text(f"✅ Theek hai, maine aapka '{state}' save kar liya hai! Main isse agle conversation se yaad rakhoonga.")
        
        # Purani chat session ko delete karna taaki naya prompt apply ho
        if user.id in user_chats:
            del user_chats[user.id]
        return

    # Normal message ka logic
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    chat_session = get_or_create_chat_session(user.id, user.first_name)
    try:
        response = await chat_session.send_message_async(message_text)
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await update.message.reply_text("⚠️ माफ करना, कुछ तकनीकी दिक्कत आ गई ਹੈ।")

# Section 5.2: Settings Menu ka Logic
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👤 Personalisation", callback_data='settings_personalisation')],
        [InlineKeyboardButton("🧠 Memory", callback_data='settings_memory')],
        [InlineKeyboardButton("🧹 Clear History & Settings", callback_data='clear_history_prompt')],
        [InlineKeyboardButton("⬅️ Close", callback_data='close_settings')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⚙️ **Settings Menu**\nAap yahan se mujhe customize kar sakte hain.", reply_markup=reply_markup)

async def settings_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if user_id not in user_profiles: user_profiles[user_id] = {}
    
    text, keyboard = "", []

    if data == 'settings_main':
        text = "⚙️ **Settings Menu**\nAap yahan se mujhe customize kar sakte hain."
        keyboard = [
            [InlineKeyboardButton("👤 Personalisation", callback_data='settings_personalisation')],
            [InlineKeyboardButton("🧠 Memory", callback_data='settings_memory')],
            [InlineKeyboardButton("🧹 Clear History & Settings", callback_data='clear_history_prompt')],
            [InlineKeyboardButton("⬅️ Close", callback_data='close_settings')],
        ]
    elif data == 'settings_personalisation':
        text = "👤 **Personalisation**\nMujhe apne baare mein batayein taaki main behtar jawab de sakun."
        keyboard = [
            [InlineKeyboardButton("👋 Nickname", callback_data='set_nickname')],
            [InlineKeyboardButton("📝 Custom Instruction", callback_data='set_instruction')],
            [InlineKeyboardButton("🎨 Hobby", callback_data='set_hobby')],
            [InlineKeyboardButton("⬅️ Back", callback_data='settings_main')],
        ]
    elif data in ['set_nickname', 'set_instruction', 'set_hobby', 'set_memory']:
        context.user_data['next_message_is'] = data.replace('set_', '')
        prompts = {
            'set_nickname': 'Okay! Aap mujhe kis naam se bulana chahte hain?',
            'set_instruction': 'Theek hai. Mere liye kya special instruction hai? (e.g., "Always reply in short points")',
            'set_hobby': 'Interesting! Aapki hobby kya hai?',
            'set_memory': 'Okay, aisi kaun si baat hai jo aap chahte hain main hamesha yaad rakhoon?'
        }
        await query.edit_message_text(text=prompts[data])
        return
    elif data == 'clear_history_prompt':
        text = "⚠️ **Are you sure?**\nIsse meri memory se hamari saari baatein aur aapki settings delete ho jayengi."
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Delete Everything", callback_data='clear_history_confirm')],
            [InlineKeyboardButton("❌ No, Cancel", callback_data='settings_main')],
        ]
    elif data == 'clear_history_confirm':
        if user_id in user_chats: del user_chats[user_id]
        if user_id in user_profiles: del user_profiles[user_id]
        save_user_profiles()
        await query.edit_message_text(text="🧹 Sab kuch clear ho gaya hai! Let's start fresh. 😎")
        return
    elif data == 'close_settings':
        await query.delete_message()
        return

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup)

# --- 6. MAIN BOT EXECUTION ---
def run_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setting", settings_command))
    app.add_handler(CallbackQueryHandler(settings_button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 Xylon AI Bot is starting polling...")
    app.run_polling()

if __name__ == "__main__":
    load_user_profiles()
    
    logger.info("🚀 Starting Flask server for Xylon AI in a separate thread...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    logger.info("🚀 Starting Xylon AI Bot in the main thread...")
    run_bot()
