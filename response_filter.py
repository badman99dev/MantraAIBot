import logging
from html import escape
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# The VIP List.
ALLOWED_TAGS = {
    'b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del',
    'tg-spoiler', 'a', 'code', 'pre', 'blockquote'
}

def sanitize_html(text: str) -> str:
    """
    The ultimate, self-healing sanitizer (UPGRADED to vFINAL).
    It uses BeautifulSoup to auto-correct nesting and neutralize non-VIP tags,
    and now uses the most robust method to extract the final text, preventing
    any possibility of "ghost tags". This is the definitive version.
    """
    
    # "Proof of Life"
    logger.info("✅✅✅ UPGRADED-to-FINAL SANITIZER IS ALIVE! ✅✅✅")

    # Step 1: Parse the text with BeautifulSoup. It will automatically fix broken nesting.
    soup = BeautifulSoup(text, 'html.parser')

    # Step 2: Run our "Bouncer" logic on the auto-corrected HTML.
    # We iterate over a copy of the list because we are modifying the tree.
    for tag in list(soup.find_all(True)):
        
        if tag.name not in ALLOWED_TAGS:
            logger.warning(f"Wrapping unsupported tag: <{tag.name}>")
            
            # --- The Surgery (Your logic, which is correct) ---
            
            attrs = " ".join([f'{key}="{escape(str(value))}"' for key, value in tag.attrs.items()])
            opening_tag_str = f"<{tag.name}{' ' if attrs else ''}{attrs}>"
            
            start_code_tag = soup.new_tag("code")
            start_code_tag.string = opening_tag_str

            end_code_tag = soup.new_tag("code")
            end_code_tag.string = f"</{tag.name}>"

            tag.insert_before(start_code_tag)
            tag.insert_after(end_code_tag)
            
            tag.unwrap()

    # =========================================================================
    # ===> THE UPGRADE: The most reliable way to prevent ghost tags <===
    # =========================================================================
    # Instead of checking for soup.body, we directly get the top-level contents.
    # This is the cleanest and most direct way to get the final string.
    sanitized_text = ''.join(str(c) for c in soup.contents)

    logger.info(f"✨ Final UPGRADED Text: {repr(sanitized_text)}")

    return sanitized_text
