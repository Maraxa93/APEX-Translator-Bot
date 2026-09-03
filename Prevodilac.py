import os
import json
import discord
from discord import Embed
from discord.utils import utcnow, get
from dotenv import load_dotenv
import aiohttp

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
LANGUAGE_MESSAGE_ID = int(os.getenv("LANGUAGE_MESSAGE_ID", "0"))

DATA_FILE = "user_lang.json"  # Cuva odabrani jezik

# 
#   DEEPL API 
# 

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"

# -------------------------------
#           INTENTS
# -------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.reactions = True
intents.members = True

client = discord.Client(intents=intents)

# -------------------------------
#   Role/Jezik
# -------------------------------

# Flag emoji -> kod jezika
flag_to_lang = {
    "🇹🇷": "tr",
    "🇮🇩": "id",
    "🇹🇼": "zh",
    "🇪🇸": "es",
    "🇬🇧": "en",
    "🇮🇳": "hi",
    "🇸🇦": "ar",
    "🇯🇵": "ja",
    "🇵🇭": "tl",
    "🇵🇰": "ur",  # Urdu / Pakistani
    "🇧🇷": "pt",  # Brazilian Portuguese
    "🇮🇹": "it",  # Italian
}

# Jezik -> flag emoji
lang_to_flag = {lang: flag for flag, lang in flag_to_lang.items()}

# Jezik -> ime role  (pobrinuti se da rola postoji na serveru)
lang_to_role_name = {
    "tr": "tr",
    "id": "id",
    "zh": "zh",
    "es": "es",
    "en": "en",
    "hi": "hi",
    "ar": "ar",
    "ja": "ja",
    "tl": "tl",
    "ur": "ur",
    "pt": "pt",  # Brazilski/Portugalski rola
    "it": "it",  # Italijanska rola
}

# Jezik -> ID kanala
lang_to_channel_id = {
    "tr": 1439964822509846700,
    "id": 1439964868315709481,
    "zh": 1439964912624467978,
    "es": 1439965019143143525,
    "en": 1439969172955332638,
    "hi": 1439974561348059239,
    "ar": 1439974594906689566,
    "ja": 1439974659214016604,
    "tl": 1439974689257689178,
    "ur": 1440005494298382439,
    "pt": 1440068489187688643,  # Brazilian 
    "it": 1440068599866855526,  # Italian 
}

# korisnicki_id -> lista jezika
user_lang: dict[int, list[str]] = {}

# 
#       JSON PERSISTENCE
# 


def load_user_lang():
    """Load saved user language preferences from disk."""
    global user_lang
    if not os.path.exists(DATA_FILE):
        user_lang = {}
        return

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        new_data: dict[int, list[str]] = {}
        for k, v in data.items():
            uid = int(k)

            # stari format
            if isinstance(v, str):
                new_data[uid] = [v]

            # novi format, vise jezika ["en", "es"]
            elif isinstance(v, list):
                new_data[uid] = [
                    lang for lang in v if lang in lang_to_channel_id
                ]

        user_lang = new_data
        print(f"[INFO] Loaded {len(user_lang)} entries from {DATA_FILE}")

    except Exception as e:
        print("[WARN] Failed to load user_lang.json:", repr(e))
        user_lang = {}


def save_user_lang():
    """Save user language preferences to disk."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {str(k): v for k, v in user_lang.items()},
                f,
                ensure_ascii=False,
                indent=2
            )
        print("[INFO] Saved user_lang.json")
    except Exception as e:
        print("[WARN] Failed to save user_lang.json:", repr(e))


# 
#         Prevod (DEEPL)
# 

# Map tvojih kodova → DeepL target_lang kodova
DEEPL_LANG_MAP = {
    "tr": "TR",
    "id": "ID",
    "zh": "ZH",
    "es": "ES",
    "en": "EN-US",   # moze i EN-GB
    "pt": "PT-BR",   # posto je brazilian kanal
    "it": "IT",
    "ja": "JA",
    # hi, ar, tl, ur NISU podrzani u DeepL → bice preskoceni ili kasnije update
}


async def translate(text: str, target_lang: str):
    """
    Translate text using DeepL API.
    target_lang je tvoj interni kod (npr. 'tr', 'id', 'es'...),
    ovde ga mapiramo na DeepL kod (TR, ID, ES, EN-US, ...).
    """
    if not DEEPL_API_KEY:
        print("[ERROR] DEEPL_API_KEY nije setovan u .env")
        return None

    deepl_target = DEEPL_LANG_MAP.get(target_lang)
    if not deepl_target:
        # npr. hi, ar, tl, ur – DeepL ih ne podržava
        print(f"[WARN] DeepL ne podržava jezik '{target_lang}', preskačem.")
        return None

    print(
        f"[DEBUG] translate() via DeepL → {target_lang} ({deepl_target}): '{text[:40]}'...")

    params = {
        "auth_key": DEEPL_API_KEY,
        "text": text,
        "target_lang": deepl_target,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(DEEPL_API_URL, data=params, timeout=15) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    print("DeepL API error:", resp.status, body[:200])
                    return None

                try:
                    data = await resp.json()
                except Exception as e:
                    body = await resp.text()
                    print("Failed to decode JSON from DeepL:", repr(e))
                    print("Response body (first 200 chars):", body[:200])
                    return None

                translations = data.get("translations")
                if not translations:
                    print("[DEBUG] No 'translations' field in DeepL response:", data)
                    return None

                translated_text = translations[0].get("text")
                if translated_text:
                    print(f"[DeepL] OK → {target_lang}")
                else:
                    print("[DEBUG] 'text' missing in first translation:",
                          translations[0])

                return translated_text

    except Exception as e:
        print("Exception in translate():", repr(e))
        return None


# 
#           Eventi
# 

@client.event
async def on_ready():
    load_user_lang()
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    print("APEX Translator Bot is ready.")
    if DEEPL_API_KEY:
        print("Using DeepL API for translation.")
    else:
        print("WARNING: DEEPL_API_KEY missing, translations will NOT work.")


# Dodavanje jezika
@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    try:
        if payload.user_id == client.user.id:
            return

        if payload.message_id != LANGUAGE_MESSAGE_ID:
            return

        emoji = str(payload.emoji)
        lang = flag_to_lang.get(emoji)
        if not lang:
            return

        guild = client.get_guild(payload.guild_id)
        if guild is None:
            return

        member = await guild.fetch_member(payload.user_id)

        # dodaj rolu jezika
        role_name = lang_to_role_name.get(lang)
        role = get(guild.roles, name=role_name)
        if role:
            try:
                await member.add_roles(role)
            except Exception as e:
                print(f"Failed to add role {role_name}: {repr(e)}")

        # cuva jezik
        langs = user_lang.get(payload.user_id, [])
        if lang not in langs:
            langs.append(lang)
        user_lang[payload.user_id] = langs
        save_user_lang()

        print(f"User {member} ({member.id}) added language: {lang}")

        try:
            await member.send(
                f"You have added {emoji} ({lang}) to your translation languages."
            )
        except Exception:
            pass

    except Exception as e:
        print("Error in on_raw_reaction_add:", repr(e))


# Ukloniti jezik
@client.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    try:
        if payload.user_id == client.user.id:
            return

        if payload.message_id != LANGUAGE_MESSAGE_ID:
            return

        emoji = str(payload.emoji)
        lang = flag_to_lang.get(emoji)
        if not lang:
            return

        guild = client.get_guild(payload.guild_id)
        if guild is None:
            return

        member = await guild.fetch_member(payload.user_id)

        # Uklanjanje iz liste
        langs = user_lang.get(payload.user_id, [])
        if lang in langs:
            langs.remove(lang)
            if langs:
                user_lang[payload.user_id] = langs
            else:
                user_lang.pop(payload.user_id, None)
            save_user_lang()

        # Uklanjanje role
        role_name = lang_to_role_name.get(lang)
        role = get(guild.roles, name=role_name)
        if role and role in member.roles:
            try:
                await member.remove_roles(role)
            except Exception as e:
                print(f"Failed to remove role {role_name}: {repr(e)}")

        print(f"User {member} ({member.id}) removed language: {lang}")

        try:
            await member.send(
                f"You have removed {emoji} ({lang}) from your translation languages."
            )
        except Exception:
            pass

    except Exception as e:
        print("Error in on_raw_reaction_remove:", repr(e))


# Poruka prevoda
@client.event
async def on_message(message: discord.Message):
    try:
        if message.author.bot:
            return

        if message.guild is None:
            return

        content = (message.content or "").strip()
        if not content:
            return

        # Bez lupova - ignorisanje kanala prevoda
        if message.channel.id in lang_to_channel_id.values():
            return

        print(
            f"[DEBUG] on_message in #{message.channel.name} from {message.author}: '{content[:60]}'")

        # Svi aktivni jezicki kanali
        active_langs = {
            lang
            for langs in user_lang.values()
            for lang in langs
            if lang in lang_to_channel_id
        }

        print(f"[DEBUG] active_langs = {active_langs}")

        if not active_langs:
            return

        # Jedan prevod po jeziku
        translations = {}
        for lang in active_langs:
            translated = await translate(content, lang)
            if translated:
                translations[lang] = translated

        if not translations:
            print("[DEBUG] No translations produced.")
            return

        # Slanje prevoda po kanalu
        for lang, text in translations.items():
            channel_id = lang_to_channel_id.get(lang)
            channel = message.guild.get_channel(channel_id)

            if not channel:
                try:
                    channel = await message.guild.fetch_channel(channel_id)
                except Exception as e:
                    print(
                        f"[WARN] Could not fetch channel {channel_id}: {repr(e)}")
                    continue

            embed = Embed(
                title=f"{lang_to_flag.get(lang, '')} Translation",
                description=text[:4096],
                timestamp=utcnow(),
            )

            embed.set_footer(
                text=f"From #{message.channel.name} • Author: {message.author}"
            )

            embed.add_field(
                name="Original message",
                value=f"[Jump to original]({message.jump_url})",
                inline=False,
            )

            try:
                await channel.send(embed=embed)
                print(
                    f"[INFO] Sent translation to #{channel.name} for lang={lang}")
            except Exception as e:
                print(f"Failed sending to {channel_id}: {repr(e)}")

    except Exception as e:
        print("Error in on_message:", repr(e))


# 
#              MAIN
# 

def main():
    if not BOT_TOKEN or LANGUAGE_MESSAGE_ID == 0:
        print("Check your environment variables (BOT_TOKEN, LANGUAGE_MESSAGE_ID).")
        return

    print("Starting bot...")
    client.run(BOT_TOKEN)


if __name__ == "__main__":
    main()
