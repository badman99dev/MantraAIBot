import logging
import asyncio
# YAHI HAI ASLI BADLAV
from shared_data import THREAD_LOCALS # bot.py se nahi, shared_data se import karna

logger = logging.getLogger(__name__)

async def _send_poll_async(chat_id: int, question: str, options: list, correct_option_id: int, explanation: str):
    """Helper function to actually send the poll asynchronously."""
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
        logger.info(f"Successfully sent quiz poll to chat_id: {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send poll asynchronously: {e}")

def send_quiz_poll(question: str, options: list, correct_option_index: int, explanation: str) -> str:
    """
    Receives quiz data from Gemini and queues a job to send a native Telegram poll.
    This function itself is synchronous.
    """
    try:
        # bot.py se nahi, shared_data se context aur loop ko access karna
        context = THREAD_LOCALS.context
        loop = THREAD_LOCALS.loop
        chat_id = context._chat_id
        
        asyncio.run_coroutine_threadsafe(
            _send_poll_async(chat_id, question, options, correct_option_index, explanation),
            loop
        )
        
        logger.info("Quiz poll has been successfully queued for sending.")
        return "Quiz has been successfully created and sent to the user. Now, just give a short confirmation message to the user, like 'Here is your quiz!' or 'Let's see if you can answer this!'"
    except Exception as e:
        logger.error(f"Failed to queue quiz poll: {e}")
        return f"Error: Failed to send quiz. {e}"
