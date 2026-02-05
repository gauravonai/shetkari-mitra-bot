import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
import nest_asyncio

nest_asyncio.apply()

TELEGRAM_TOKEN = "8557400553:AAFBI-Q-sB7FWfvahspUFGZU1DBcnCDwuXs"
GEMINI_API_KEY = "AIzaSyAA3V9l4OfrRlYD-tJS0IBfJ4HQZrKk_38"

VIDEO_DB = {
    "1": {
        "title": "संत्रा व मोसंबी लागवड",
        "url": "https://youtube.com/watch?v=example1",
        "content": "संत्र्याची लागवड जून-जुलै मध्ये करावी. जमीन तयारी चांगली करावी. ६ बाय ६ मीटर अंतर ठेवावे. थेंब सिंचन उत्तम आहे. सेंद्रिय खत वापरावे. फुलोरा फेब्रुवारी-मार्च मध्ये येतो. कापणी नोव्हेंबर ते मार्च पर्यंत."
    },
    "2": {
        "title": "उन्हाळी पिकांचे नियोजन",
        "url": "https://youtube.com/watch?v=example2",
        "content": "उन्हाळी पिके: भुईमूग, मूग, उडीद, तीळ, सूर्यफूल. फेब्रुवारी-मार्च मध्ये लागवड करावी. थेंब सिंचन वापरावे. मल्चिंग केल्यास पाणी वाचते. प्रमाणित बियाणे वापरावे."
    }
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('models/gemini-2.5-flash')

print(f"Model: gemini-2.5-flash")
print(f"Videos: {len(VIDEO_DB)}")

def detect_language(text):
    """Improved language detection with Roman script support"""

    text_lower = text.lower()

    # Devanagari script detection
    marathi_devanagari = ['कसे', 'कशी', 'करावे', 'करावी', 'आहे', 'आहेत', 'पिक', 'शेती', 'ला', 'ची', 'चे', 'व्यवस्थापन', 'लागवड', 'मध्ये', 'वर', 'साठी']
    hindi_devanagari = ['कैसे', 'कैसी', 'करें', 'करना', 'है', 'हैं', 'फसल', 'खेती', 'का', 'की', 'के', 'को', 'में', 'प्रबंधन', 'पर', 'लिए']

    # Roman/English script Marathi words
    marathi_roman = ['kase', 'kashi', 'karave', 'karavi', 'aahe', 'aahet', 'pik', 'sheti', 'war', 'var', 'saathi', 'madhye', 'che', 'la', 'chi']

    # Roman/English script Hindi words
    hindi_roman = ['kaise', 'kaisi', 'kare', 'karna', 'hai', 'hain', 'fasal', 'kheti', 'pe', 'par', 'liye', 'me', 'mein', 'ka', 'ki', 'ke', 'ko', 'konsi', 'konsa']

    # Count matches
    m_dev = sum(1 for w in marathi_devanagari if w in text)
    h_dev = sum(1 for w in hindi_devanagari if w in text)

    m_rom = sum(1 for w in marathi_roman if w in text_lower)
    h_rom = sum(1 for w in hindi_roman if w in text_lower)

    marathi_total = m_dev + m_rom
    hindi_total = h_dev + h_rom

    # Check character types
    english_chars = sum(1 for c in text if 'a' <= c.lower() <= 'z')
    devanagari_chars = sum(1 for c in text if '\u0900' <= c <= '\u097F')

    logger.info(f"Detection - Marathi: {marathi_total} (Dev:{m_dev}, Rom:{m_rom}), Hindi: {hindi_total} (Dev:{h_dev}, Rom:{h_rom})")

    # Decision logic
    if marathi_total > hindi_total and marathi_total > 0:
        return 'marathi'
    elif hindi_total > marathi_total and hindi_total > 0:
        return 'hindi'
    elif devanagari_chars > english_chars:
        return 'marathi'  # Default Devanagari to Marathi
    elif english_chars > 0 and devanagari_chars == 0:
        # Pure English script - check for common words
        if any(w in text_lower for w in ['kase', 'war', 'saathi', 'aahe', 'che', 'kashi']):
            return 'marathi'
        elif any(w in text_lower for w in ['kaise', 'pe', 'konsi', 'kare', 'mein', 'ka']):
            return 'hindi'
        else:
            return 'english'
    else:
        return 'english'

def get_answer(question):
    kb = ""
    for v in VIDEO_DB.values():
        kb += f"Video: {v['title']}\nLink: {v['url']}\nContent: {v['content']}\n\n"

    lang = detect_language(question)
    logger.info(f"Detected language: {lang} for question: {question}")

    # Strong language enforcement in prompt
    lang_instructions = {
        'marathi': {
            'rule': 'तुम्ही फक्त आणि फक्त मराठी भाषेत उत्तर द्या. कोणतेही इंग्रजी किंवा हिंदी शब्द वापरू नका. सर्व bullet points मराठीत लिहा.',
            'format': 'प्रत्येक point मराठीत',
            'ending': 'संपूर्ण माहितीसाठी हा व्हिडिओ पहा:'
        },
        'hindi': {
            'rule': 'आप केवल और केवल हिंदी भाषा में जवाब दें। कोई भी अंग्रेजी या मराठी शब्द का उपयोग न करें। सभी bullet points हिंदी में लिखें।',
            'format': 'हर point हिंदी में',
            'ending': 'पूरी जानकारी के लिए यह वीडियो देखें:'
        },
        'english': {
            'rule': 'Answer ONLY in English language. Do not use any Hindi or Marathi words. Write all bullet points in English.',
            'format': 'Each point in English',
            'ending': 'Watch this video for complete information:'
        }
    }

    lang_info = lang_instructions[lang]

    prompt = f"""You are Shetkari Mitra (Farmer's Friend) for White Gold Trust (Gajanan Jadhao).

CRITICAL LANGUAGE REQUIREMENT:
{lang_info['rule']}
This is MANDATORY. The user asked in {lang}, so answer in {lang} ONLY.

OTHER RULES:
- Answer ONLY from the content provided below
- If information not available, say so in {lang}
- {lang_info['format']}
- Give 5-7 detailed bullet points
- End with: "{lang_info['ending']} [video_link]"

VIDEO CONTENT:
{kb}

FARMER'S QUESTION (in {lang}):
{question}

YOUR ANSWER (MUST be in {lang}):"""

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error: {e}")
        error_msgs = {
            'marathi': f"त्रुटी झाली: {str(e)}\nकृपया पुन्हा प्रयत्न करा.",
            'hindi': f"त्रुटि हुई: {str(e)}\nकृपया फिर से प्रयास करें।",
            'english': f"Error occurred: {str(e)}\nPlease try again."
        }
        return error_msgs.get(lang, f"Error: {e}")

async def start(u: Update, c):
    msg = """🌾 नमस्कार! मी शेतकरी मित्र!
🌾 नमस्ते! मैं किसान मित्र हूं!
🌾 Hello! I am Farmer's Friend!

व्हाईट गोल्ड ट्रस्ट (गजानन जाधव सर)
White Gold Trust (Gajanan Jadhao Sir)

📝 प्रश्न विचारा (कोणत्याही भाषेत):

मराठी में:
- संत्र्याची लागवड कशी करावी?
- संत्रा वर फवारा?

हिंदी में:
- संत्रा पर अब कौन सी स्प्रे करें?
- गर्मी में पानी कैसे दें?

English में:
- How to grow oranges?
- What spray for oranges?"""

    await u.message.reply_text(msg)

async def status(u: Update, c):
    await u.message.reply_text(f"Status:\n✅ Bot Running\n📹 Videos: {len(VIDEO_DB)}\n🌐 मराठी, हिंदी, English")

async def handle(u: Update, c):
    q = u.message.text
    lang = detect_language(q)

    search_msgs = {
        'marathi': '🔍 शोधत आहे...',
        'hindi': '🔍 खोज रहे हैं...',
        'english': '🔍 Searching...'
    }

    await u.message.reply_text(search_msgs[lang])
    answer = get_answer(q)
    await u.message.reply_text(answer)

def run():
    print("\n🌾 SHETKARI MITRA - MULTI-LANGUAGE\n")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("✅ BOT IS LIVE WITH ROMAN SCRIPT SUPPORT!\n")
    app.run_polling()

run()
