import sys
import os

# Ensure the script can find the translations module
sys.path.append(os.getcwd())

from translations import TRANSLATIONS, LANGUAGES_LIST

# Define the definitive keys and their values
# We'll use the existing English and Hungarian values
EN_KEYS = {
    "open_saves_folder": "Open Saves Folder",
    "save_folder_opened": "Saves folder opened.",
    "save_folder_not_found": "Save folder not found. Make sure you've played the game at least once."
}

HU_KEYS = {
    "open_saves_folder": "Mentések mappa megnyitása",
    "save_folder_opened": "Mentések mappa megnyitva.",
    "save_folder_not_found": "Mentések mappa nem található. Győződj meg róla, hogy legalább egyszer játszottál a játékkal."
}

# Update the TRANSLATIONS dict
for lang_code in TRANSLATIONS:
    if lang_code == 'hu':
        TRANSLATIONS[lang_code].update(HU_KEYS)
    elif lang_code == 'en':
        TRANSLATIONS[lang_code].update(EN_KEYS)
    else:
        # For all other languages, use English as fallback if not already present or if we want to overwrite
        # We'll overwrite to ensure consistency
        TRANSLATIONS[lang_code].update(EN_KEYS)

# Remove old keys that are no longer needed
old_keys = [
    "save_convert_label", "convert_to_seamless", "convert_to_online", 
    "convert_success", "convert_no_files", "convert_error"
]

for lang_code in TRANSLATIONS:
    for key in old_keys:
        if key in TRANSLATIONS[lang_code]:
            del TRANSLATIONS[lang_code][key]

# Function to format the output as a clean Python file
def format_translations(translations, languages_list):
    lines = ["", "TRANSLATIONS = {"]
    
    # Sort language codes for consistency
    for lang_code in sorted(translations.keys()):
        lines.append(f'    "{lang_code}": {{')
        items = translations[lang_code]
        # Sort keys to make diffs cleaner and lookup easier
        for key in sorted(items.keys()):
            val = items[key].replace('\n', '\\n').replace('"', '\\"')
            lines.append(f'        "{key}": "{val}",')
        # Remove trailing comma from last item for cleaner look, but Python allows it
        # Actually, let's keep it for simplicity or remove last comma
        if lines[-1].endswith(','):
            lines[-1] = lines[-1][:-1]
        lines.append('    },')
    
    lines.append('}')
    lines.append("")
    lines.append(f'LANGUAGES_LIST = {repr(languages_list)}')
    return "\n".join(lines)

new_content = format_translations(TRANSLATIONS, LANGUAGES_LIST)

with open('translations.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("translations.py has been rebuilt and standardized.")
