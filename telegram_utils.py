# telegram_utils.py
import asyncio
import logging
from typing import AsyncGenerator
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from google.generativeai.types import GenerateContentResponse
import config

logger = logging.getLogger(__name__)

async def send_split_message(update: Update, context: ContextTypes.DEFAULT_TYPE, response_stream: AsyncGenerator[GenerateContentResponse, None]) -> str:
    """
    Streams a response from Gemini, splits it into intelligent chunks, and sends them.
    Returns the full, unsplit text for context history.
    """
    full_response_text = ""
    current_chunk = ""
    split_chars = ['.', '।', '?', '!', '\n']

    try:
        async for chunk in response_stream:
            if not chunk.text:
                continue
                
            current_chunk += chunk.text
            full_response_text += chunk.text
            
            should_split = False
            split_pos = -1

            if len(current_chunk) > config.SENTENCE_SPLIT_THRESHOLD:
                for i in range(len(current_chunk) - 1, config.SENTENCE_SPLIT_THRESHOLD, -1):
                    if current_chunk[i] in split_chars:
                        split_pos = i + 1; should_split = True; break
            
            if not should_split and len(current_chunk) > config.WORD_SPLIT_THRESHOLD:
                pos = current_chunk.rfind(' ', 0, config.WORD_SPLIT_THRESHOLD)
                if pos != -1:
                    split_pos = pos + 1; should_split = True

            if not should_split and len(current_chunk) > config.CHARACTER_SPLIT_THRESHOLD:
                split_pos = config.CHARACTER_SPLIT_THRESHOLD; should_split = True

            if should_split:
                message_to_send = current_chunk[:split_pos]
                remaining_text = current_chunk[split_pos:]
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id, text=message_to_send,
                    parse_mode=ParseMode.HTML, disable_web_page_preview=True
                )
                current_chunk = remaining_text
                await asyncio.sleep(0.5)

    except Exception as e:
        logger.error(f"Error during response streaming/splitting: {e}", exc_info=True)
        if current_chunk:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=current_chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        raise e

    if current_chunk:
        if len(current_chunk) > config.TELEGRAM_MAX_MESSAGE_LENGTH:
            for i in range(0, len(current_chunk), config.TELEGRAM_MAX_MESSAGE_LENGTH):
                await context.bot.send_message(chat_id=update.effective_chat.id, text=current_chunk[i:i+config.TELEGRAM_MAX_MESSAGE_LENGTH], parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=current_chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    
    return full_response_text
