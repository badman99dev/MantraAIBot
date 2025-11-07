# --- START OF UPDATED FILE quizzes/user_quiz_data.py ---

"""
This module is the "Artist". It takes raw quiz result data
and formats it into the beautiful, user-facing "Detailed Review" message.
It handles all the special fonts, symbols, HTML tags, and message splitting.
"""

from html import escape

# === REMOVED FUNCTION ===
# get_question_by_id_from_data function yahan se hata diya gaya hai
# aur play_quiz.py mein move kar diya gaya hai to avoid circular imports.

def format_detailed_review(results: list, quiz_name: str, questions_data: list) -> list:
    """
    Takes quiz results and returns a list of formatted message strings,
    split to respect Telegram's message length limits.
    """
    
    # === ADDED HELPER FUNCTION INSIDE ===
    # Hum is function ko yahin locally define kar lenge
    def get_question_by_id(qid, data):
        return next((q for q in data if q["id"] == qid), None)
        
    message_chunks = []
    current_chunk = f"📝 ║  <b>𝐃𝐄𝐓𝐀𝐈𝐋𝐄𝐃 𝐑𝐄𝐕𝐈𝐄𝐖 » {escape(quiz_name)}</b>  ║ 📝\n\n"
    
    for i, result in enumerate(results):
        question_data = get_question_by_id(result['question_id'], questions_data)
        if not question_data:
            continue

        escaped_question = escape(question_data['question'])
        escaped_options = [escape(opt) for opt in question_data['options']]
        
        options_text = ""
        for j, option in enumerate(escaped_options):
            label = ""
            if result.get('answered_option_id') is not None and j == result.get('answered_option_id') and j == question_data['correct_option_id']:
                label = "  ◅◅  <i>Your Answer (Correct)</i>"
            elif result.get('answered_option_id') is not None and j == result.get('answered_option_id'):
                label = "  ◅◅  <i>Your Answer</i>"
            elif j == question_data['correct_option_id']:
                label = "  ◅◅  <i>Correct Answer</i>"
            options_text += f"   ›  {option}{label}\n"

        status_map = {
            'correct': f"Sᴛᴀᴛᴜs: Cᴏʀʀᴇᴄᴛ ║ Pᴏɪɴᴛs: +{result['points_earned']} ║ Tɪᴍᴇ: {result['time_taken']:.1f}s",
            'wrong': f"Sᴛᴀᴛᴜs: Wʀᴏɴɢ ║ Pᴏɪɴᴛs: {result['points_earned']} ║ Tɪᴍᴇ: {result['time_taken']:.1f}s",
            'skipped': "Sᴛᴀᴛᴜs: Sᴋɪᴘᴘᴇᴅ ║ Pᴏɪɴᴛs: +0 ║ Tɪᴍᴇ: ---",
            'timed_out': "Sᴛᴀᴛᴜs: Tɪᴍᴇ's Uᴘ ║ Pᴏɪɴᴛs: +0 ║ Tɪᴍᴇ: ---",
            'stopped': "Sᴛᴀᴛᴜs: Sᴛᴏᴘᴘᴇᴅ ║ Pᴏɪɴᴛs: +0 ║ Tɪᴍᴇ: ---",
            'postponed': "Sᴛᴀᴛᴜs: Pᴏsᴛᴘᴏɴᴇᴅ"
        }
        result_text = status_map.get(result['status'], "Sᴛᴀᴛᴜs: Uɴᴋɴᴏᴡɴ")

        if result['status'] == 'postponed':
            continue

        question_review = (
            "____________________________________\n\n"
            f"❰ <b>𝐐𝐮𝐞𝐬𝐭𝐢𝐨𝐧 {i+1}</b> ❱\n{escaped_question}\n\n"
            f"{options_text}\n↳  {result_text}\n\n"
        )
        
        if len(current_chunk) + len(question_review) > 4000:
            message_chunks.append(current_chunk)
            current_chunk = ""
        current_chunk += question_review

    if not any(r['status'] != 'postponed' for r in results):
        return []

    message_chunks.append(current_chunk)
    return message_chunks

# --- END OF UPDATED FILE quizzes/user_quiz_data.py ---
