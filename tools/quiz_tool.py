import google.generativeai as genai
import json
import logging
import os

logger = logging.getLogger(__name__)

# bot.py se model name ko yahan bhi laana
MODEL_NAME = os.environ.get('MODEL_NAME', 'gemini-1.5-flash')

async def create_quiz(topic: str) -> dict:
    """
    Creates a single, interesting multiple-choice quiz question about a given topic.
    Use this tool when the user wants to test their knowledge, play a game, or learn something new in a fun way.
    You must decide the topic based on the conversation.
    """
    logger.info(f"[QUIZ TOOL] Gemini wants to create a quiz on topic: {topic}")
    
    # Step 1: Gemini ke liye special prompt banana
    quiz_prompt = f"""
    Create a single, interesting multiple-choice quiz question about the topic: '{topic}'.
    You MUST provide your response in a single, valid JSON object format only.
    The JSON object must have these exact keys: "question" (string), "options" (a list of 4 strings), "correct_option_index" (a number from 0 to 3), and "explanation" (string, for when the user gets it wrong).
    
    Example for topic 'ISRO':
    {{
        "question": "ISRO ne Chandrayaan-3 ko kis launch vehicle se launch kiya tha?",
        "options": ["PSLV-C57", "GSLV MkIII (LVM3)", "SSLV-D2", "Falcon 9"],
        "correct_option_index": 1,
        "explanation": "Chandrayaan-3 ko GSLV MkIII (LVM3) se launch kiya gaya tha, jo ISRO ka sabse powerful rocket hai."
    }}
    """
    
    try:
        # Step 2: Ek alag Gemini model call karke JSON blueprint maangna
        gemini_model = genai.GenerativeModel(MODEL_NAME)
        response = await gemini_model.generate_content_async(quiz_prompt)
        
        # JSON ko saaf karna
        json_string = response.text.replace("```json", "").replace("```", "").strip()
        quiz_data = json.loads(json_string)

        logger.info(f"[QUIZ TOOL] Successfully generated quiz JSON from Gemini.")
        
        # Step 3: Telegram ko bhejne ke liye ek dictionary return karna
        # Hum yahan se seedha quiz nahi bhej sakte, isliye bot.py ko information wapas bhejenge
        return {
            "type": "quiz",
            "data": quiz_data
        }

    except Exception as e:
        logger.error(f"Error creating quiz JSON: {e}")
        return {
            "type": "error",
            "data": "Maaf karna, main abhi quiz nahi bana paa raha hoon. 😕"
        }
