# gemini_manager.py
import os
import logging
import google.generativeai as genai

from prompts import SYSTEM_PROMPT_TEMPLATE
from tools.tool_manager import AVAILABLE_TOOLS
import settings
import config

logger = logging.getLogger(__name__)

# --- SIMPLE, DIRECT API KEY SETUP ---
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("FATAL ERROR: GEMINI_API_KEY environment variable not found. The bot cannot start. Please set it in your Render dashboard.")

# Configure the genai library with the single key
genai.configure(api_key=API_KEY)

MODEL_NAME = os.environ.get('MODEL_NAME', 'gemini-1.5-flash')

# Create a single, shared model instance
try:
    model = genai.GenerativeModel(model_name=MODEL_NAME, tools=AVAILABLE_TOOLS)
    logger.info(f"Successfully initialized a single model instance with the provided API key ending in '...{API_KEY[-4:]}'")
except Exception as e:
    logger.critical(f"Failed to initialize the GenerativeModel. Error: {e}")
    raise e

# --- CHAT SESSION & HISTORY MANAGEMENT ---
user_chats = {} 
settings.load_user_profiles_settings(settings.user_profiles, user_chats)

async def manage_chat_history(chat_session: genai.ChatSession):
    """Checks the chat history's token count and trims it if it exceeds the limit."""
    try:
        token_count = (await model.count_tokens_async(chat_session.history)).total_tokens
        
        if token_count > config.MAX_HISTORY_TOKENS:
            logger.warning(f"Token count {token_count} is over the limit. Trimming.")
            
            current_history = chat_session.history
            safe_limit = config.MAX_HISTORY_TOKENS - config.TRIM_BUFFER_TOKENS
            
            while (await model.count_tokens_async(current_history)).total_tokens > safe_limit:
                if len(current_history) > 3:
                    del current_history[2]; del current_history[2]
                else:
                    break
                    
            chat_session.history = current_history
            new_count = (await model.count_tokens_async(chat_session.history)).total_tokens
            logger.info(f"History trimmed. New token count is {new_count}")
    except Exception as e:
        logger.error(f"Error during chat history management: {e}", exc_info=True)

def get_or_create_chat_session(user_id: int, user_name: str) -> genai.ChatSession:
    """Gets an existing chat session or creates a new one using the single model instance."""
    if user_id not in user_chats:
        logger.info(f"Creating new chat session for user {user_id} using the single model instance.")
        
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
            user_personalization_section=personalization_section
        )
        initial_history = [
            {'role': 'user', 'parts': [{'text': system_prompt}]},
            {'role': 'model', 'parts': [{'text': f"Okay, I understand. I am 𝐗𝐲𝐥𝐨𝐧 𝐀𝐈, ready to chat with {user_name}! 😎"}]}
        ]
        # Start the chat using the single, globally defined model
        user_chats[user_id] = model.start_chat(
            history=initial_history,
            enable_automatic_function_calling=True
        )
    return user_chats[user_id]
