import re

# Read the translations file
with open(r'f:\Source\er_launcher\translations.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the new keys to add (in English, will be used as fallback)
new_keys = {
    "save_convert_label": "Save File Conversion:",
    "convert_to_seamless": "Convert to Seamless (.co2)",
    "convert_to_online": "Convert to Online (.sl2)",
    "convert_success": "Conversion successful! {count} files converted.",
    "convert_no_files": "No save files found to convert.",
    "convert_error": "Conversion error: {error}",
    "save_folder_not_found": "Save folder not found. Make sure you've played the game at least once."
}

# Find all language blocks (excluding 'en' and 'hu' which are already done)
pattern = r'("(?!en|hu)[a-z]{2}"):\s*\{([^}]+)"tip_5":\s*"([^"]+)"'

def add_keys_to_lang(match):
    lang_code = match.group(1)
    existing_content = match.group(2)
    tip_5_value = match.group(3)
    
    # Build the new keys string
    new_keys_str = ',\n        "save_convert_label": "Save File Conversion:",\n'
    new_keys_str += '        "convert_to_seamless": "Convert to Seamless (.co2)",\n'
    new_keys_str += '        "convert_to_online": "Convert to Online (.sl2)",\n'
    new_keys_str += '        "convert_success": "Conversion successful! {count} files converted.",\n'
    new_keys_str += '        "convert_no_files": "No save files found to convert.",\n'
    new_keys_str += '        "convert_error": "Conversion error: {error}",\n'
    new_keys_str += '        "save_folder_not_found": "Save folder not found. Make sure you\'ve played the game at least once."\n'
    
    return f'{lang_code}: {{{existing_content}"tip_5": "{tip_5_value}"{new_keys_str}'

# Apply the transformation
new_content = re.sub(pattern, add_keys_to_lang, content, flags=re.DOTALL)

# Write back
with open(r'f:\Source\er_launcher\translations.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Translation keys added to all languages!")
