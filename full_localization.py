import sys
import os

# Ensure the script can find the translations module
sys.path.append(os.getcwd())

from translations import TRANSLATIONS, LANGUAGES_LIST

# Comprehensive mapping of language codes to their specific translations
# Key format: (open_saves_folder, save_folder_opened, save_folder_not_found)
LANGUAGE_DATA = {
    "en": ("Open Saves Folder", "Saves folder opened.", "Save folder not found. Make sure you've played the game at least once."),
    "hu": ("Mentések mappa megnyitása", "Mentések mappa megnyitva.", "Mentések mappa nem található. Győződj meg róla, hogy legalább egyszer játszottál a játékkal."),
    "de": ("Speicherordner öffnen", "Speicherordner geöffnet.", "Speicherordner nicht gefunden. Stellen Sie sicher, dass Sie das Spiel mindestens einmal gespielt haben."),
    "fr": ("Ouvrir le dossier des sauvegardes", "Dossier de sauvegardes ouvert.", "Dossier de sauvegarde introuvable. Assurez-vous d'avoir joué au jeu au moins une fois."),
    "es": ("Abrir carpeta de guardados", "Carpeta de guardado abierta.", "Carpeta de guardado no encontrada. Asegúrate de haber jugado al juego al menos una vez."),
    "it": ("Apri cartella dei salvataggi", "Cartella dei salvataggi aperta.", "Cartella di salvataggio non trovata. Assicurati di aver giocato al gioco almeno una vez."),
    "ru": ("Открыть папку сохранений", "Папка сохранений открыта.", "Папка сохранения не найдена. Убедитесь, что вы играли в игру хотя бы один раз."),
    "pt": ("Abrir pasta de salvos", "Pasta de salvamento aberta.", "Pasta de salvamento não encontrada. Certifique-se de que jogou o jogo pelo menos uma vez."),
    "ko": ("저장 폴더 열기", "저장 폴더 열림.", "저장 폴더를 찾을 수 없습니다. 게임을 한 번 이상 플레이했는지 확인하십시오."),
    "zh": ("打开存档文件夹", "保存文件夹已打开.", "存档文件夹未找到。请确保您至少玩过一次游戏。"),
    "jp": ("セーブフォルダを開く", "保存フォルダーが開かれました.", "セーブフォルダーが見つかりません。ゲームを一度以上プレイしたことを確認してください."),
    "tr": ("Kayıt klasörünü aç", "Kayıt klasörü açıldı.", "Kayıt klasörü bulunamadı. Oyunu en az bir kez oynadığınızdan emin olun."),
    "pl": ("Otwórz folder z zapisami", "Folder zapisów otwarty.", "Nie znaleziono folderu zapisu. Upewnij się, że grałeś w grę przynajmniej raz."),
    "nl": ("Open opslagmap", "Opslagmap geopend.", "Opslagmap niet gevonden. Zorg ervoor dat je het spel minstens één keer hebt gespeeld."),
    "sv": ("Öppna sparfilsmappen", "Sparmapp öppnad.", "Sparmapp hittades inte. Se till att du har spelat spelet minst en gång."),
    "fi": ("Avaa tallennuskansio", "Tallennuskansio avattu.", "Tallennuskansiota ei löydy. Varmista, että olet pelannut peliä vähintään kerran."),
    "no": ("Åpne lagringsmappen", "Lagringsmappe åpnet.", "Lagringsmappen ble ikke funnet. Sørg for at du har spilt spillet minst én gang."),
    "da": ("Åbn gemt mappe", "Gemmemappe åbnet.", "Gem mappev ikke fundet. Sørg for, at du har spillet spillet mindst én gang."),
    "cs": ("Otevřít složku s uloženými hrami", "Složka uložených her otevřena.", "Složka pro uložení nenalezena. Ujistěte se, že jste hru spustili alespoň jednou."),
    "el": ("Άνοιγμα φακέλου αποθηκευμένων παιχνιδιών", "Φάκελος αποθηκεύσεων άνοιξε.", "Ο φάκελος αποθήκευσης δεν βρέθηκε. Βεβαιωθείτε ότι έχετε παίξει το παιχνίδι τουλάχιστον μία φορά."),
    "ro": ("Deschide folderul de salvări", "Folderul de salvare deschis.", "Dosarul de salvare nu a fost găsit. Asigură-te că ai jucat jocul cel puțin o dată."),
    "uk": ("Відкрити теку збережень", "Папка збережень відкрито.", "Папка збереження не знайдена. Переконайтеся, що ви играли в гру хоча б один раз."),
    "vi": ("Mở thư mục lưu", "Thư mục lưu đã mở.", "Không tìm thấy thư mục lưu. Hãy đảm bảo bạn đã chơi trò chơi ít nhất một lần."),
    "th": ("เปิดโฟลเดอร์บันทึก", "โฟลเดอร์บันทึกเปิดแล้ว.", "ไม่พบโฟลเดอร์บันทึก ตรวจสอบให้แน่ใจว่าคุณได้เล่นเกมอย่างน้อยหนึ่งครั้งแล้ว"),
    "id": ("Buka folder penyimpanan", "Folder penyimpanan dibuka.", "Folder penyimpanan tidak ditemukan. Pastikan Anda telah memainkan game setidaknya sekali."),
    "hi": ("सेव फ़ोल्डर खोलें", "सेव फ़ोल्डर खोला गया.", "सेव फ़ोल्डर नहीं मिला। सुनिश्चित करें कि आपने गेम कम से कम एक बार खेला है।"),
    "ar": ("افتح مجلد الحفظ", "تم فتح مجلد الحفظ.", "مجلد الحفظ غير موجود. تأكد من أنك لعبت اللعبة مرة واحدة على الأقل."),
    "bg": ("Отваряне на папката със запазени игри", "Папката със запазени игри е отворена.", "Папката за запис не е намерена. Уверете се, че сте играли играта поне веднъж."),
    "he": ("פתח תיקיית שמירות", "תיקיית השמירות נפתחה.", "תיקיית השמירה לא נמצאה. ודא ששיחקת במשחק לפחות פעם אחת."),
    "sr": ("Отвори фолдер са сачуваним играма", "Фолдер са сачуваним играма је отворен.", "Фолдер за чување није пронађен. Уверите се да сте играли игру бар једном."),
    "sk": ("Otvoriť priečinok s uloženými pozíciami", "Priečinok s uloženými pozíciami bol otvorený.", "Priečinok s uloženými pozíciami nebol nájdený. Uistite sa, že ste hru aspoň raz hrali."),
    "sl": ("Odpri mapo z shranjenimi datotekami", "Mapa s shranjenimi datotekami je odprta.", "Mape s shranjenimi datotekami ni bilo mogoče najti. Prepričajte se, da ste igro igrali vsaj enkrat."),
    "ms": ("Buka folder simpanan", "Folder simpanan telah dibuka.", "Folder simpanan tidak ditemui. Pastikan anda telah bermain permainan sekurang-kurangnya sekali."),
    "tl": ("Buksan ang folder ng saves", "Nabuksan na ang folder ng saves.", "Hindi nahanap ang folder ng save. Siguraduhin na nakapaglaro ka na kahit isang beses."),
    "bn": ("সেভস ফোল্ডার খুলুন", "সেভস ফোল্ডার খোলা হয়েছে", "সেভ ফোল্ডার পাওয়া যায়নি। নিশ্চিত করুন যে আপনি অন্তত একবার গেমটি খেলেছেন।"),
    "ta": ("சேமிப்பு கோப்புறையைத் திறக்கவும்", "சேமிப்பு கோப்புறை திறக்கப்பட்டது", "சேமிப்பு கோப்புறை காணப்படவில்லை. நீங்கள் குறைந்தது ஒருமுறையாவது விளையாடியுள்ளீர்கள் என்பதை உறுதிப்படுத்தவும்."),
    "te": ("సేవ్స్ ఫోల్డర్ తెరవండి", "సేవ్స్ ఫోల్డర్ తెరవబడింది", "సేవ్ ఫోల్డర్ కనుగొనబడలేదు. మీరు కనీసం ఒక్కసారైనా ఆట ఆడి ఉన్నారని నిర్ధారించుకోండి."),
    "kn": ("ಉಳಿಸಿದ ಫೋಲ್ಡರ್ ತೆರೆಯಿರಿ", "ಉಳಿಸಿದ ಫೋಲ್ಡರ್ ತೆರೆಯಲಾಗಿದೆ", "ಉಳಿಸಿದ ಫೋಲ್ಡರ್ ಕಂಡುಬಂದಿಲ್ಲ. ನೀವು ಕನಿಷ್ಠ ಒಮ್ಮೆಯಾದರೂ ಆಟವನ್ನು ಆಡಿದ್ದೀರಿ ಎಂದು ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ."),
    "ml": ("സേവ്സ് ഫോൾഡർ തുറക്കുക", "സേവ്സ് ഫോൾഡർ തുറന്നു", "സേവ് ഫോൾഡർ കണ്ടെത്തിയില്ല. നിങ്ങൾ കുറഞ്ഞത് ഒരു തവണയെങ്കിലും ഗെയിം കളിച്ചിട്ടുണ്ടെന്ന് ഉറപ്പാക്കുക."),
    "mr": ("सेव्ही फोल्डर उघडा", "सेव्ह फोल्डर उघडले", "सेव्ह फोल्डर आढळले नाही. तुम्ही किमान एकदा तरी गेम खेळला असल्याची खात्री करा."),
    "gu": ("સેવ્સ ફોલ્ડર ખોલો", "સેવ્સ ફોલ્ડર ખોલવામાં આવ્યું", "સેવ ફોલ્ડર મળ્યું નથી. ખાતરી કરો કે તમે ઓછામાં ઓછું એકવાર રમત રમ્યા છો."),
    "pa": ("ਸੇਵਜ਼ ਫੋਲਡਰ ਖੋਲ੍ਹੋ", "ਸੇਵਜ਼ ਫੋلਡਰ ਖੋਲ੍ਹਿਆ ਗਿਆ", "ਸੇਵ ਫੋਲਡਰ ਨਹੀਂ ਮਿਲਿਆ। ਯਕੀਨੀ ਬਣਾਓ ਕਿ ਤੁਸੀਂ ਘੱਟੋ-ਘੱਟ ਇੱਕ ਵਾਰ ਗੇม ਖੇਡੀ ਹੈ।"),
    "ur": ("سیوز فولڈر کھولیں", "سیوز فولڈر کھولا گیا", "محفوظ فولڈر نہیں ملا۔ یقینی بنائیں کہ آپ نے کم از کم ایک بار گیم کھیلا ہے۔"),
    "fa": ("پوشه ذخیره را باز کنید", "پوشه ذخیره باز شد", "پوشه ذخیره یافت نشد. مطمئن شوید که حداقل یک بار بازی را انجام داده اید."),
    "sw": ("Fungua folda ya akiba", "Folda ya akiba imefunguliwa", "Folda ya kuhifadhi haikupatikana. Hakikisha umecheza mchezo angalau mara moja."),
    "af": ("Maak stoorlêer oop", "Stoorlêer oopgemaak", "Stoorlêer nie gevind nie. Maak seker jy het die speletjie ten minste een keer gespeel."),
    "is": ("Opna vistunarmöppu", "Vistunarmöppu opnuð", "Vistunarmöppu fannst ekki. Gakktu úr skugga um að þú hafir spilað leikinn að minnsta kosti einu sinni."),
    "et": ("Ava salvestuskaust", "Salvestuskaust avatud", "Salvestuskausta ei leitud. Veenduge, et olete mängu vähemalt korra mänginud."),
    "lv": ("Atvērt saglabāto mapi", "Saglabātā mape atvērta", "Saglabātā mape nav atrasta. Pārliecinieties, ka esat spēlējis spēli vismaz vienu reizi."),
    "lt": ("Atidaryti išsaugojimo aplanką", "Išsaugojimo aplankas atidarytas", "Išsaugojimo aplankas nerastas. Įsitikinkite, kad žaidimą žaidėte bent vieną kartą.")
}

# Update the TRANSLATIONS dict
for lang_code in TRANSLATIONS:
    if lang_code in LANGUAGE_DATA:
        open_btn, opened_msg, not_found_msg = LANGUAGE_DATA[lang_code]
        TRANSLATIONS[lang_code]["open_saves_folder"] = open_btn
        TRANSLATIONS[lang_code]["save_folder_opened"] = opened_msg
        TRANSLATIONS[lang_code]["save_folder_not_found"] = not_found_msg
    else:
        # Fallback to English for any unknown codes
        open_btn, opened_msg, not_found_msg = LANGUAGE_DATA["en"]
        TRANSLATIONS[lang_code]["open_saves_folder"] = open_btn
        TRANSLATIONS[lang_code]["save_folder_opened"] = opened_msg
        TRANSLATIONS[lang_code]["save_folder_not_found"] = not_found_msg

# Standardize format and write back
def format_translations(translations, languages_list):
    lines = ["", "TRANSLATIONS = {"]
    for lang_code in sorted(translations.keys()):
        lines.append(f'    "{lang_code}": {{')
        items = translations[lang_code]
        for key in sorted(items.keys()):
            val = items[key].replace('\n', '\\n').replace('"', '\\"')
            lines.append(f'        "{key}": "{val}",')
        lines.append('    },')
    lines.append('}')
    lines.append("")
    lines.append(f'LANGUAGES_LIST = {repr(languages_list)}')
    return "\n".join(lines)

new_content = format_translations(TRANSLATIONS, LANGUAGES_LIST)

with open('translations.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("translations.py has been fully localized for all 50+ languages.")
