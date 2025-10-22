# settings.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import json

USER_PROFILES_FILE = "user_profiles.json"
user_profiles = {}
user_chats = {} # Isse bhi yahan access karna hoga clear history ke liye

def load_user_profiles_settings(profiles, chats):
    """bot.py se user data ko is file mein laata hai."""
    global user_profiles, user_chats
    user_profiles = profiles
    user_chats = chats

def save_user_profiles():
    with open(USER_PROFILES_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_profiles, f, indent=2, ensure_ascii=False)

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setting command ka main entry point."""
    keyboard = [
        [InlineKeyboardButton("👤 Personalisation", callback_data='settings_personalisation')],
        [InlineKeyboardButton("🧠 Memory", callback_data='set_memory')], # Memory button ab main menu mein hai
        [InlineKeyboardButton("🧹 Clear History & Settings", callback_data='clear_history_prompt')],
        [InlineKeyboardButton("⬅️ Close", callback_data='close_settings')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⚙️ **Settings Menu**\nAap yahan se mujhe customize kar sakte hain.", reply_markup=reply_markup)

async def settings_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sabhi settings ke button clicks ko handle karta hai."""
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
            [InlineKeyboardButton("🧠 Memory", callback_data='set_memory')],
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
