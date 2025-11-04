import re
import logging
from html import escape

logger = logging.getLogger(__name__)

# Hamari VIP list. Yahi tags asli format me dikhenge.
# Is set ka use hum check karne ke liye karenge.
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
    The ultimate, non-destructive sanitizer. It intelligently processes the AI's response.
    1. It identifies all sections that are already inside <code>...</code> blocks.
    2. It leaves those sections untouched, assuming they are safe.
    3. For all other sections, it finds every HTML tag.
    4. If a tag is in ALLOWED_TAGS, it's kept as is.
    5. If a tag is NOT in ALLOWED_TAGS, it is wrapped in <code>...</code> to be
       displayed safely as plain text to the user.
    """
    
    # Ye complex regex text ko do tarah ke hisson me todta hai:
    # 1. Wo hisse jo `<code>` ya `<pre>` ke andar hain (safe hain, inhe nahi chhedna)
    # 2. Wo hisse jo in blocks ke bahar hain (jinhe check karna hai)
    # re.split isko ek list me daal dega: [outside, inside, outside, inside, ...]
    parts = re.split(r'(<code.*?>.*?</code>|<pre.*?>.*?</pre>)', text, flags=re.DOTALL)
    
    sanitized_parts = []
    
    # Ab hum is list ke har hisse par kaam karenge
    for i, part in enumerate(parts):
        # Even indices (0, 2, 4...) `<code>` ya `<pre>` ke bahar wale hisse hain.
        # Sirf inhi hisson ko humein check karna hai.
        if i % 2 == 0:
            
            # Ye inner function har tag ko check karega
            def tag_wrapper(match):
                tag = match.group(0) # Poora tag, jaise '<h3 style="color:red">'
                
                # Tag ka naam nikalte hain (e.g., 'h3' from '<h3>')
                tag_name_match = re.search(r'</?([a-zA-Z0-T]+)', tag) # Correction: a-zA-Z0-9
                
                if tag_name_match:
                    tag_name = tag_name_match.group(1).lower()
                    
                    # Agar tag VIP list me nahi hai, to use `<code>` se wrap karo
                    if tag_name not in ALLOWED_TAGS:
                        logger.warning(f"Wrapping unsupported tag: {tag}")
                        return f"<code>{escape(tag)}</code>"
                
                # Agar tag VIP list me hai, ya koi ajeeb tag hai jise hum samajh nahi paaye,
                # to use waise hi rehne do (safety ke liye)
                return tag
            
            # Sirf `<code>` ke bahar wale hisse par hi wrapper function chalao
            # Ye regex saare possible HTML tags ko dhoondhega
            processed_part = re.sub(r'</?.*?>', tag_wrapper, part)
            sanitized_parts.append(processed_part)
            
        # Odd indices (1, 3, 5...) `<code>` ya `<pre>` ke andar wale, safe hisse hain.
        # Inhe bina chhede waise hi list me daal do.
        else:
            sanitized_parts.append(part)
            
    # Saare saaf-suthre hisson ko wapas jod kar final text bana do
    return "".join(sanitized_parts)
