import re

# Read the translations file
with open(r'f:\Source\er_launcher\translations.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to find and replace the old conversion keys with new ones
# We'll look for the block starting with save_convert_label and ending with save_folder_not_found
pattern = r'("save_convert_label":[^\n]+\n\s+"convert_to_seamless":[^\n]+\n\s+"convert_to_online":[^\n]+\n\s+"convert_success":[^\n]+\n\s+"convert_no_files":[^\n]+\n\s+"convert_error":[^\n]+\n\s+"save_folder_not_found":[^\n]+)'

replacement = '''        "open_saves_folder": "Open Saves Folder",
        "save_folder_opened": "Saves folder opened.",
        "save_folder_not_found": "Save folder not found. Make sure you've played the game at least once."'''

# Replace all occurrences
new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

# Write back
with open(r'f:\Source\er_launcher\translations.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Translation keys updated for all languages!")
