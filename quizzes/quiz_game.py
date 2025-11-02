# quizzes/quiz_game.py

import logging
from html import escape
import json
import asyncio
import time # +++ NEW: Import time
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from .quiz_manager import get_quiz_set, get_custom_quiz_set, save_custom_quiz_set # +++ NEW: Import save_custom_quiz_set
from .play_quiz import QuizSession
from .user_quiz_data import format_detailed_review

logger = logging.getLogger(__name__)

# ... (start_quiz_game remains the same) ...
async def start_quiz_game(context: ContextTypes.DEFAULT_TYPE, chat_id: int, set_id: str, is_temp_quiz: bool = False):
    logger.info(f"[QUIZ GAME RUNNER] `start_quiz_game` called for chat_id: {chat_id} with set_id: {set_id}")
    try:
        if is_temp_quiz: quiz_data = get_custom_quiz_set(context, set_id)
        else: quiz_data = get_quiz_set(set_id)
        if not quiz_data:
            await context.bot.send_message(chat_id=chat_id, text="<b>Error:</b> Requested quiz is not available.", parse_mode='HTML'); return
        if 'active_quiz_sessions' in context.bot_data and chat_id in context.bot_data['active_quiz_sessions']:
            old_session = context.bot_data['active_quiz_sessions'].pop(chat_id)
            if not old_session.is_suspended: await old_session.suspend_quiz()
        await context.bot.send_message(chat_id=chat_id, text=f"🚀 Getting the '<b>{escape(quiz_data.get('name', 'Custom Quiz'))}</b>' quiz ready...", parse_mode='HTML')
        session = QuizSession(context, chat_id, set_id, quiz_data, is_temp_quiz)
        if 'active_quiz_sessions' not in context.bot_data: context.bot_data['active_quiz_sessions'] = {}
        context.bot_data['active_quiz_sessions'][chat_id] = session
        await session.start()
    except Exception as e:
        logger.error(f"[QUIZ GAME RUNNER] FATAL ERROR inside `start_quiz_game`: {e}", exc_info=True)
        await context.bot.send_message(chat_id=chat_id, text=f"🤯 Oops! Quiz shuru karne mein parde ke peeche ek error aa gaya.")


# --- Handlers for User Interactions During the Game ---
async def quiz_game_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action, _, value = query.data.partition(':')
    chat_id = update.effective_chat.id
    active_sessions = context.bot_data.get('active_quiz_sessions', {})
    session = active_sessions.get(chat_id)

    if not session and action not in ['quizgame_try_again', 'quizgame_retry_from_file', 'quizgame_detailed_review']:
        try: await query.edit_message_text("This quiz session has expired. Please start a new one.")
        except BadRequest: pass
        return

    if action == 'quizgame_try_again':
        set_id = value
        try: await query.message.delete()
        except BadRequest: pass
        await start_quiz_game(context, chat_id, set_id, is_temp_quiz=False)

    # +++ NEW: Logic to replay a custom quiz from a saved file +++
    elif action == 'quizgame_retry_from_file':
        session_id = value
        try:
            with open(f"quiz_results/{session_id}.json", "r", encoding='utf-8') as f:
                stored_data = json.load(f)
        except FileNotFoundError:
            await context.bot.send_message(chat_id, "⚠️ The data for this quiz has expired and is no longer available.")
            return

        # Create a new temporary quiz set from the saved data
        new_set_id = f"custom_{chat_id}_{int(time.time())}"
        save_custom_quiz_set(context, new_set_id, stored_data)

        try: await query.message.delete()
        except BadRequest: pass
        
        await start_quiz_game(context, chat_id, new_set_id, is_temp_quiz=True)

    elif action == 'quizgame_detailed_review':
        # ... (detailed review logic remains the same) ...
        session_id = value
        try:
            with open(f"quiz_results/{session_id}.json", "r", encoding='utf-8') as f:
                stored_data = json.load(f)
        except FileNotFoundError:
            await context.bot.send_message(chat_id, "⚠️ The data for this quiz has expired and is no longer available.")
            return

        message_chunks = format_detailed_review(stored_data['results'], stored_data['quiz_name'], stored_data['questions_data'])
        if not message_chunks:
            await context.bot.send_message(chat_id, "You didn't answer any questions, so there's no review available.")
            return
            
        for chunk in message_chunks:
            await context.bot.send_message(chat_id, text=chunk, parse_mode='HTML')
            await asyncio.sleep(0.5)

    elif session and session.active_poll_id:
        # ... (in-game button logic remains the same) ...
        poll_id_to_close = session.active_poll_id
        stopped = (action == 'quizgame_stop_quiz')
        postponed = (action == 'quizgame_postpone_question')
        skipped = (action == 'quizgame_skip_permanently')
        
        await session.handle_closure(poll_id=poll_id_to_close, stopped=stopped, postponed=postponed, skipped=skipped)
        if stopped:
            active_sessions.pop(chat_id, None)

# ... (poll answer handler remains the same) ...
async def quiz_game_poll_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_id = update.poll_answer.poll_id
    if poll_id in context.bot_data and 'session' in context.bot_data[poll_id]:
        session = context.bot_data[poll_id]['session']
        await session.handle_answer(update)
        
        if session.is_suspended:
            active_sessions = context.bot_data.get('active_quiz_sessions', {})
            active_sessions.pop(session.chat_id, None)
