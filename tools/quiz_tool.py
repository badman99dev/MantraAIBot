# tools/quiz_tool.py

import logging
import asyncio
import json
import time
from typing import Optional, List, Dict, Any
from shared_data import THREAD_LOCALS 
from quizzes.quiz_manager import get_all_sets, save_custom_quiz_set
from quizzes.quiz_game import start_quiz_game

logger = logging.getLogger(__name__)

# --- Helper function for single polls ---
async def _send_poll_async(chat_id: int, question: str, options: list, correct_option_id: int, explanation: str):
    """Helper function to send a single, non-game poll asynchronously."""
    try:
        context = THREAD_LOCALS.context
        await context.bot.send_poll(
            chat_id=chat_id,
            question=question,
            options=options,
            type='quiz',
            correct_option_id=correct_option_id,
            explanation=explanation
        )
        logger.info(f"Successfully sent a single quiz poll to chat_id: {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send single poll asynchronously to {chat_id}: {e}")

# --- THE UPGRADED MULTI-PURPOSE QUIZ TOOL ---

def manage_quiz(
    mode: str,
    sub_mode: Optional[str] = None,
    set_id: Optional[str] = None,
    question: Optional[str] = None,
    options: Optional[List[str]] = None,
    correct_option_index: Optional[int] = None,
    explanation: Optional[str] = None,
    question_data: Optional[str] = None
) -> str:
    """
    Manages all quiz-related activities. Can send a single poll, search for quiz sets, or start a full multi-question quiz game.

    Args:
        mode (str): The primary action. Must be 'single_question' or 'multi_question'.
        sub_mode (Optional[str]): The secondary action for 'multi_question' mode. Can be 'search_sets', 'play_set', or 'play_custom'.
        set_id (Optional[str]): The unique ID of the quiz set to play (used with sub_mode 'play_set' or for creating a custom game ID).
        question (Optional[str]): The question text for a 'single_question' poll.
        options (Optional[List[str]]): A list of 4 answer options for a 'single_question' poll.
        correct_option_index (Optional[int]): The 0-based index of the correct answer for a 'single_question' poll.
        explanation (Optional[str]): An explanation for the correct answer for a 'single_question' poll.
        question_data (Optional[str]): A JSON string representing a list of question objects for a custom quiz (used with sub_mode 'play_custom').
    
    Returns:
        str: A confirmation message or data for the AI to process and show to the user.
    """
    logger.info(f"[QUIZ TOOL] Called with mode: {mode}, sub_mode: {sub_mode}")
    
    try:
        context = THREAD_LOCALS.context
        loop = THREAD_LOCALS.loop
        chat_id = context._chat_id
        update = context.update
    except AttributeError:
        return "Error: Could not get the necessary context to run the tool. This is an internal issue."

    # === MODE 1: SINGLE QUESTION (Legacy functionality) ===
    if mode == 'single_question':
        if not all([question, options, correct_option_index is not None]):
            return "Error: For 'single_question' mode, 'question', 'options', and 'correct_option_index' are required."
        
        asyncio.run_coroutine_threadsafe(
            _send_poll_async(chat_id, question, options, correct_option_index, explanation),
            loop
        )
        return "Quiz poll has been successfully created and sent. Confirm this to the user."

    # === MODE 2: MULTI-QUESTION GAME ===
    elif mode == 'multi_question':
        if sub_mode == 'search_sets':
            all_sets = get_all_sets()
            if not all_sets:
                return "No quiz sets were found in the database. Inform the user about this."
            # Format the list for the AI to present beautifully
            formatted_list = [f"- <b>{data['name']}</b> (ID: <code>{set_id}</code>)" for set_id, data in all_sets.items()]
            return "Here is a list of available quiz sets. Present this list to the user and ask them which one they'd like to play:\n" + "\n".join(formatted_list)

        elif sub_mode == 'play_set':
            if not set_id:
                return "Error: To play a quiz set, you must provide the 'set_id'."
            
            # Start the game asynchronously
            asyncio.run_coroutine_threadsafe(
                start_quiz_game(context, chat_id, set_id, update.message, is_temp_quiz=False),
                loop
            )
            return "The multi-question quiz game is starting now. You don't need to say anything else."

        elif sub_mode == 'play_custom':
            if not question_data:
                return "Error: For 'play_custom' sub_mode, you must provide the 'question_data' as a JSON string."
            
            try:
                # Use a unique ID for the temporary quiz
                custom_set_id = f"custom_{chat_id}_{int(time.time())}"
                data = json.loads(question_data)
                save_custom_quiz_set(context, custom_set_id, data)
                
                # Start the game asynchronously
                asyncio.run_coroutine_threadsafe(
                    start_quiz_game(context, chat_id, custom_set_id, update.message, is_temp_quiz=True),
                    loop
                )
                return "The custom multi-question quiz you created is starting now. You don't need to say anything else."
            except json.JSONDecodeError:
                return "Error: The 'question_data' provided was not a valid JSON string. Please check the format."
            except Exception as e:
                logger.error(f"Error starting custom quiz: {e}")
                return f"An internal error occurred while starting the custom quiz: {e}"
        
        else:
            return f"Error: Invalid 'sub_mode' ('{sub_mode}') provided for 'multi_question' mode. Use 'search_sets', 'play_set', or 'play_custom'."

    else:
        return f"Error: Invalid 'mode' ('{mode}') provided. Use 'single_question' or 'multi_question'."

# --- We must now replace the old tool with the new one ---
# In tool_manager.py, the old 'send_quiz_poll' will be replaced by 'manage_quiz'
send_quiz_poll = manage_quiz # Keep old name for compatibility in tool_manager for now
