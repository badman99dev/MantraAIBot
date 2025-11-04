import re
import logging
from html import escape

logger = logging.getLogger(__name__)

# Rule #1: Hamari VIP list.
ALLOWED_TAGS = {
    'b', 'strong',      # Bold
    'i', 'em',          # Italic
    'u', 'ins',          # Underline
    's', 'strike', 'del',# Strikethrough
    'tg-spoiler',        # Spoiler
    'a',                 # Link
    'code',              # Inline Code
    'pre'                # Code Block
}

def sanitize_html(text: str) -> str:
    """
    The final sanitizer, built on the "Tag, what is that?" philosophy.
    It uses a fast and robust Regex to find all potential HTML tags.
    For each tag, it checks if it's on the VIP list (ALLOWED_TAGS).
    - If YES, the tag is a VIP and is left untouched.
    - If NO, the tag is a "criminal" and is neutralized by wrapping it
      in `<code>` blocks, turning it into harmless plain text.
    This version is specifically updated to correctly handle tags with hyphens, like <tg-spoiler>.
    """
    
    tag_regex = re.compile(r'(<[^>]+>)')

    def tag_wrapper(match):
        tag = match.group(1)

        # Tag ka naam nikal kar check karo.
        # THE FIX: We added a hyphen (-) to the character set [a-zA-Z0-9-]
        # Now it will correctly identify "tg-spoiler" as the tag name.
        tag_name_match = re.search(r'</?([a-zA-Z0-9-]+)', tag)
        
        if tag_name_match:
            tag_name = tag_name_match.group(1).lower()
            
            if tag_name not in ALLOWED_TAGS:
                logger.warning(f"Wrapping unsupported tag with Regex: {tag}")
                return f"<code>{escape(tag)}</code>"

        return tag

    return tag_regex.sub(tag_wrapper, text)
