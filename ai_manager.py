# ai_manager.py

import google.generativeai as genai
from config import logger, MODEL_NAME, MAX_HISTORY_TOKENS, TRIM_BUFFER_TOKENS
from prompts import SYSTEM_PROMPT_TEMPLATE
from time_utils import get_current_ist_string
import settings
from tools.tool_manager import AVAILABLE_TOOLS

# Gemini Model ko yahan initialize karenge
model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    tools=AVAILABLE_TOOLS
)

# User chats ka data yahan manage hoga
user_chats = {} 

async def manage_chat_history(chat_session: genai.ChatSession):
    """Token limit check karke history ko trim karta hai."""
    try:
        token_count = (await model.count_tokens_async(chat_session.history)).total_tokens
        if token_count > MAX_HISTORY_TOKENS:
            logger.warning(f"Token count {token_count} is over the limit. Trimming.")
            current_history = chat_session.history
            safe_limit = MAX_HISTORY_TOKENS - TRIM_BUFFER_TOKENS
            while (await model.count_tokens_async(current_history)).total_tokens > safe_limit:
                if len(current_history) > 3:
                    del current_history[2]; del current_history[2]
                else: break
            chat_session.history = current_history
            logger.info(f"History trimmed. New count: {(await model.count_tokens_async(chat_session.history)).total_tokens}")
    except Exception as e:
        logger.error(f"Error during chat history management: {e}", exc_info=True)

def get_or_create_chat_session(user_id: int, user_name: str) -> genai.ChatSession:
    """User ke liye chat session create ya fetch karta hai."""
    if user_id not in user_chats:
        logger.info(f"Creating new chat session for user {user_id}...")
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
            current_ist_time_string=get_current_ist_string(),
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
