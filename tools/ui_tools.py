# tools/ui_tools.py
import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import asyncio

logger = logging.getLogger(__name__)

# Yeh global variables bot.py se set kiye jayenge
_bot_context = None
_chat_id = None

def set_telegram_context(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """
    bot.py se zaroori context ko is file mein laata hai,
    taaki hum yahan se message bhej sakein.
    """
    global _bot_context, _chat_id
    _bot_context = context
    _chat_id = chat_id

async def create_quiz(question: str, options: str, correct_option_index: int, explanation: str) -> str:
    """
    Creates and sends a Telegram quiz poll to the user.
    Gemini MUST provide all parameters: a question, a list of options as a JSON string (e.g., '["Option A", "Option B"]'), the index of the correct option, and an explanation.
    """
    global _bot_context, _chat_id
    if not all([_bot_context, _chat_id]):
        return "Error: Telegram context is not set. Cannot send quiz."
    
    logger.info(f"Tool 'create_quiz' called with question: {question}")
    try:
        # Gemini se options JSON string mein aayenge, unhe parse karna
        options_list = json.loads(options)
        
        await _bot_context.bot.send_poll(
            chat_id=_chat_id,
            question=question,
            options=options_list,
            type='quiz',
            correct_option_id=correct_option_index,
            explanation=explanation
        )
        return "Quiz created and sent to the user successfully."
    except Exception as e:
        logger.error(f"Error in create_quiz tool: {e}")
        return f"Error sending quiz: {e}. Check if 'options' was a valid JSON list string."

async def create_buttons(message_text: str, buttons_json: str) -> str:
    """
    Creates and sends a message with inline clickable buttons to the user.
    Gemini MUST provide the main message_text and a buttons_json string.
    The buttons_json format MUST be a JSON string of a list of lists, like '[ [{"text": "Click Me", "callback_data": "action1"}] ]'.
    """
    global _bot_context, _chat_id
    if not all([_bot_context, _chat_id]):
        return "Error: Telegram context is not set. Cannot send buttons."

    logger.info(f"Tool 'create_buttons' called with text: {message_text}")
    try:
        buttons_data = json.loads(buttons_json)
        keyboard = [[InlineKeyboardButton(b['text'], callback_data=b['callback_data']) for b in row] for row in buttons_data]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await _bot_context.bot.send_message(
            chat_id=_chat_id,
            text=message_text,
            reply_markup=reply_markup
        )
        return "Message with buttons sent successfully."
    except Exception as e:
        logger.error(f"Error in create_buttons tool: {e}")
        return f"Error sending buttons: {e}. Check if 'buttons_json' was a valid JSON string."
