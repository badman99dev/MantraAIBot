import logging
from html import escape
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# The VIP List.
ALLOWED_TAGS = {
    'b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del',
    'tg-spoiler', 'a', 'code', 'pre'
}

def sanitize_html(text: str) -> str:
    """
    The ultimate, self-healing sanitizer (Upgraded Version).
    It uses BeautifulSoup to auto-correct nesting and neutralize non-VIP tags.
    This version specifically avoids "double escaping" to ensure unsupported tags
    are displayed cleanly inside `<code>` blocks to the user.
    """
    
    # "Proof of Life"
    logger.info("✅✅✅ UPGRADED SELF-HEALING SANITIZER IS ALIVE! ✅✅✅")

    # Step 1: Parse the text with BeautifulSoup. It will automatically fix broken nesting.
    soup = BeautifulSoup(text, 'html.parser')

    # Step 2: Run our "Bouncer" logic on the auto-corrected HTML.
    # We iterate over a copy of the list because we are modifying the tree.
    for tag in list(soup.find_all(True)):
        
        if tag.name not in ALLOWED_TAGS:
            logger.warning(f"Wrapping unsupported tag: <{tag.name}>")
            
            # --- The Surgery (Upgraded) ---
            
            # Recreate the opening tag as a raw string to preserve its attributes
            attrs = " ".join([f'{key}="{escape(str(value))}"' for key, value in tag.attrs.items()])
            opening_tag_str = f"<{tag.name}{' ' if attrs else ''}{attrs}>"
            
            start_code_tag = soup.new_tag("code")
            # THE FIX: No more escape() here! We pass the raw string directly.
            start_code_tag.string = opening_tag_str

            # Create the closing tag as visible code
            end_code_tag = soup.new_tag("code")
            # THE FIX: No more escape() here either!
            end_code_tag.string = f"</{tag.name}>"

            # Place these new code blocks before and after the original content
            tag.insert_before(start_code_tag)
            tag.insert_after(end_code_tag)
            
            # Remove the original unsupported tag, leaving its content
            tag.unwrap()

    # Step 3: The Critical Step - Convert the soup back to a string WITHOUT ghost tags.
    if soup.body:
        sanitized_text = soup.body.encode_contents().decode('utf-8')
    else:
        # Fallback for simple text that doesn't get a <body> tag.
        sanitized_text = str(soup)

    logger.info(f"✨ Final Upgraded Text: {repr(sanitized_text)}")

    return sanitized_text
