
from translations import TRANSLATIONS

reference_keys = set(TRANSLATIONS["en"].keys())
languages = TRANSLATIONS.keys()

missing_report = {}

for lang in languages:
    if lang == "en": continue
    lang_keys = set(TRANSLATIONS[lang].keys())
    missing = reference_keys - lang_keys
    if missing:
        missing_report[lang] = sorted(list(missing))

import json
print(json.dumps(missing_report, indent=2))
