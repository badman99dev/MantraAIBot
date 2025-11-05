# --- START OF UPDATED FILE handlers.py ---

import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import logger
# <<< YAHAN IMPORT ME CHANGE KIYA GAYA HAI >>>
from ai_manager import get_or_create_chat_session, manage_chat_history, user_chats, update_system_prompt_with_current_time
from shared_data import THREAD_LOCALS
from response_filter import sanitize_html
import settings

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start command ko handle karta hai."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
        chat_session = get_or_create_chat_session(user.id, user.first_name)
        response = await chat_session.send_message_async(
            "User has just started the conversation. Greet them warmly as Xylon AI and briefly mention key features like chat, movie search, and our new pro-level quizzes."
        )

        raw_chunks = response.text.split("\n---\n")
        
        for chunk in raw_chunks:
            stripped_chunk = chunk.strip()
            if stripped_chunk:
                sanitized_chunk = sanitize_html(stripped_chunk)
                await context.bot.send_message(
                    chat_id=chat_id, text=sanitized_chunk,
                    parse_mode=ParseMode.HTML, disable_web_page_preview=True
                )
                await asyncio.sleep(1.0)

    except Exception as e:
        logger.error(f"FATAL ERROR during /start for user {user.id}: {e}", exc_info=True)
        await context.bot.send_message(chat_id=chat_id, text="🤯 Oops! Failed to generate response. Please try after some time.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Normal text messages ko handle karta hai."""
    user = update.effective_user
    message_text = update.message.text
    try:
        if 'next_message_is' in context.user_data:
            state = context.user_data.pop('next_message_is')
            if user.id not in settings.user_profiles: settings.user_profiles[user.id] = {}
            settings.user_profiles[user.id][state] = message_text
            settings.save_user_profiles()
            await update.message.reply_text(f"✅ Theek hai, maine aapka '{state}' save kar liya hai! Main isse agle conversation se yaad rakhoonga.")
            if user.id in user_chats: del user_chats[user.id] # 'user_id' ki jagah 'user.id' hoga
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        chat_session = get_or_create_chat_session(user.id, user.first_name)
        
        # <<< YEH LINE ADD KI GAYI HAI >>>
        # Har message se pehle system prompt ko live time ke saath refresh karo
        update_system_prompt_with_current_time(user.id, user.first_name, chat_session)
        
        await manage_chat_history(chat_session)
        
        THREAD_LOCALS.context = context
        THREAD_LOCALS.loop = asyncio.get_running_loop()
        
        response = await chat_session.send_message_async(message_text)
        
        # ... (baaki ka message splitting aur sending logic same rahega) ...
        raw_chunks = response.text.split("\n---\n")
        
        sanitized_chunks = [sanitize_html(chunk.strip()) for chunk in raw_chunks if chunk.strip()]

        if not sanitized_chunks:
            logger.warning("WARNING: AI Response resulted in ZERO chunks after processing.")
        
        for chunk in sanitized_chunks:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=chunk,
                parse_mode=ParseMode.HTML, disable_web_page_preview=True
            )
            await asyncio.sleep(1.0)
        
    except Exception as e:
        logger.error(f"FATAL ERROR in handle_message for user {user.id}: {e}", exc_info=True)
        await update.message.reply_text("🤯 Oops! Failed to generate response. Please try after some time.")
    finally:
        if hasattr(THREAD_LOCALS, 'context'): del THREAD_LOCALS.context
        if hasattr(THREAD_LOCALS, 'loop'): del THREAD_LOCALS.loop

# --- END OF UPDATED FILE handlers.py ---
