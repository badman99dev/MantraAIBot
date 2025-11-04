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
    The ultimate, self-healing sanitizer. It uses BeautifulSoup for two critical tasks:
    1. Auto-correcting malformed HTML nesting (e.g., <b><i></b></i> -> <b><i></i></b>).
    2. Finding and neutralizing any non-VIP tags.
    It's designed to be the final solution to all possible HTML-related errors.
    """
    
    # "Proof of Life"
    logger.info("✅✅✅ SELF-HEALING SANITIZER IS ALIVE! ✅✅✅")

    # Step 1: Parse the text with BeautifulSoup. It will automatically fix broken nesting.
    soup = BeautifulSoup(text, 'html.parser')

    # Step 2: Run our "Bouncer" logic on the auto-corrected HTML.
    # We iterate over a copy of the list because we are modifying the tree.
    for tag in list(soup.find_all(True)):
        
        if tag.name not in ALLOWED_TAGS:
            logger.warning(f"Wrapping unsupported tag: <{tag.name}>")
            
            # Create the opening tag as visible code
            attrs = " ".join([f'{key}="{escape(str(value))}"' for key, value in tag.attrs.items()])
            opening_tag_str = f"<{tag.name}{' ' if attrs else ''}{attrs}>"
            start_code_tag = soup.new_tag("code")
            start_code_tag.string = escape(opening_tag_str)

            # Create the closing tag as visible code
            end_code_tag = soup.new_tag("code")
            end_code_tag.string = escape(f"</{tag.name}>")

            # Place these new code blocks before and after the original content
            tag.insert_before(start_code_tag)
            tag.insert_after(end_code_tag)
            
            # Remove the original unsupported tag, leaving its content
            tag.unwrap()

    # Step 3: The Critical Step - Convert the soup back to a string WITHOUT ghost tags.
    # .encode_contents() gives us the raw inner HTML of the <body> tag.
    # We decode it to get a normal string.
    if soup.body:
        sanitized_text = soup.body.encode_contents().decode('utf-8')
    else:
        # Fallback for simple text that doesn't get a <body> tag.
        sanitized_text = str(soup)

    logger.info(f"✨ Final Self-Healed Text: {repr(sanitized_text)}")

    return sanitized_text
