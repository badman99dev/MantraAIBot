# quizzes/quiz_game.py

import logging
from html import escape
import json
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

# Import project-specific modules from the quizzes directory
from .quiz_manager import get_quiz_set, get_custom_quiz_set
from .play_quiz import QuizSession
from .user_quiz_data import format_detailed_review

logger = logging.getLogger(__name__)

# --- Main Entry Point for Starting a Quiz Game ---
async def start_quiz_game(context: ContextTypes.DEFAULT_TYPE, chat_id: int, set_id: str, message_to_edit, is_temp_quiz: bool = False):
    """
    Creates and starts a new quiz game session. This is called by the quiz_tool.
    """
    if is_temp_quiz:
        quiz_data = get_custom_quiz_set(context, set_id)
    else:
        quiz_data = get_quiz_set(set_id)
        
    if not quiz_data:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_to_edit.message_id,
            text="<b>Error:</b> Requested quiz is not available.", 
            parse_mode='HTML'
        )
        return
    
    # Clean up previous session if any, to avoid conflicts
    if 'active_quiz_sessions' in context.bot_data and chat_id in context.bot_data['active_quiz_sessions']:
        old_session = context.bot_data['active_quiz_sessions'].pop(chat_id)
        if not old_session.is_suspended:
            await old_session.suspend_quiz() # Gracefully end the old one

    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_to_edit.message_id,
        text=f"🚀 Getting the '<b>{escape(quiz_data['name'])}</b>' quiz ready...", 
        parse_mode='HTML'
    )
    
    # Create and start a new game session
    session = QuizSession(context, chat_id, set_id, quiz_data, is_temp_quiz)
    
    if 'active_quiz_sessions' not in context.bot_data:
        context.bot_data['active_quiz_sessions'] = {}
    context.bot_data['active_quiz_sessions'][chat_id] = session
    
    await session.start()


# --- Handlers for User Interactions During the Game ---

async def quiz_game_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all button clicks during a quiz game."""
    query = update.callback_query
    await query.answer()
    
    action, _, value = query.data.partition(':')
    chat_id = update.effective_chat.id
    active_sessions = context.bot_data.get('active_quiz_sessions', {})
    session = active_sessions.get(chat_id)

    if not session:
        await query.edit_message_text("This quiz session has expired. Please start a new one.")
        return

    if action == 'quizgame_try_again':
        is_temp = session.is_temp_quiz
        set_id = value
        try: 
            await query.message.delete()
        except BadRequest: 
            pass
        # We can't use the original 'message_to_edit' so we send a new one to start
        new_msg = await context.bot.send_message(chat_id, "Restarting quiz...")
        await start_quiz_game(context, chat_id, set_id, new_msg, is_temp)

    elif action == 'quizgame_detailed_review':
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

    elif session.active_poll_id:
        poll_id_to_close = session.active_poll_id
        stopped = (action == 'quizgame_stop_quiz')
        postponed = (action == 'quizgame_postpone_question')
        skipped = (action == 'quizgame_skip_permanently')
        
        await session.handle_closure(poll_id=poll_id_to_close, stopped=stopped, postponed=postponed, skipped=skipped)
        if stopped:
            active_sessions.pop(chat_id, None)


async def quiz_game_poll_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Passes poll answers to the correct game session."""
    poll_id = update.poll_answer.poll_id
    if poll_id in context.bot_data and 'session' in context.bot_data[poll_id]:
        session = context.bot_data[poll_id]['session']
        await session.handle_answer(update)
        
        # If the quiz is over, remove the session
        if session.is_suspended: # The session ends itself
            active_sessions = context.bot_data.get('active_quiz_sessions', {})
            active_sessions.pop(session.chat_id, None)
