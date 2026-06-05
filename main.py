import logging
import asyncio
import os
import aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import BotCommand
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart

# Load environment variables from .env file
load_dotenv()

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
PHOTO_FILE_ID = "AgACAgIAAxkBAAOLagW6deLCtoCnoYrTZAjrjVrgn1UAAkMZaxtOSAlI0xdv3cRE2vcBAAMCAAN5AAM7BA"

# ===== AMOCRM CONFIG =====
AMOCRM_DOMAIN = os.getenv("AMOCRM_DOMAIN")
AMOCRM_ACCESS_TOKEN = os.getenv("AMOCRM_ACCESS_TOKEN")
AMOCRM_PIPELINE_ID = os.getenv("AMOCRM_PIPELINE_ID")
if AMOCRM_PIPELINE_ID:
    AMOCRM_PIPELINE_ID = int(AMOCRM_PIPELINE_ID)

# Validate required environment variables
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env file")
if not AMOCRM_DOMAIN:
    raise ValueError("AMOCRM_DOMAIN is not set in .env file")
if not AMOCRM_ACCESS_TOKEN:
    raise ValueError("AMOCRM_ACCESS_TOKEN is not set in .env file")

# ===== POST MATNI =====
POST_TEXT = (
    "🟢 <b>Uzum market da 0 dan 1000$ ni qisqa vaqt oralig'ida qanday qilib topsa bo'ladi?</b>\n\n"
    "Aynan sizga shu pog'onalar bo'yicha bepul darslik tayyorladim, pastagi havola orqali ko'ring!\n\n"
    "Kirib ko'ring👇👇👇\n"
    "<a href='https://www.youtube.com/watch?v=X2gn3mnteTY'>📚 Bepul darslik</a>\n\n"
    "👤 @biyo_uzum_admin\n"
    "☎️ +998-77-084-55-88\n"
    "☎️ +998-77-083-55-88\n"
    "☎️ +998-88-738-50-07"
)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())


# ===== AMOCRM FUNKSiyasi =====
async def create_lead_with_contact(
    domain: str,
    token: str,
    name: str,
    phone: str,
    pipeline_id: int = None
) -> int:
    """
    amoCRM da contact va lead yaratadi.
    Qaytaradi: lead_id
    """
    headers = {"Authorization": f"Bearer {token}"}
    base_url = f"https://{domain}.amocrm.ru/api/v4"

    async with aiohttp.ClientSession() as session:
        # 1. Contact yaratish
        contact_url = f"{base_url}/contacts"
        contact_data = [{
            "name": name,
            "custom_fields_values": [
                {
                    "field_code": "PHONE",
                    "values": [{"value": phone, "enum_code": "WORK"}]
                }
            ]
        }]

        async with session.post(contact_url, headers=headers, json=contact_data) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                logging.error(f"Contact yaratishda xato {resp.status}: {text}")
                raise Exception(f"Contact yaratishda xato: {resp.status}")

            result = await resp.json()
            contact_id = result["_embedded"]["contacts"][0]["id"]
            logging.info(f"amoCRM contact yaratildi: id={contact_id}")

        # 2. Lead yaratish
        lead_url = f"{base_url}/leads"
        lead_data = [{
            "name": f"Telegram: {name}",
            "_embedded": {
                "contacts": [{"id": contact_id}]
            }
        }]
        if pipeline_id:
            lead_data[0]["pipeline_id"] = pipeline_id

        async with session.post(lead_url, headers=headers, json=lead_data) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                logging.error(f"Lead yaratishda xato {resp.status}: {text}")
                raise Exception(f"Lead yaratishda xato: {resp.status}")

            result = await resp.json()
            lead_id = result["_embedded"]["leads"][0]["id"]
            logging.info(f"amoCRM lead yaratildi: id={lead_id}")
            return lead_id


# ===== AMOCRM NOTE FUNKSiyasi =====
async def add_telegram_note_to_lead(
    domain: str,
    token: str,
    lead_id: int,
    chat_id: int,
    username: str = None,
    first_name: str = None,
    last_name: str = None
) -> None:
    """
    Yaratilgan lead ga Telegram metadata'sini note sifatida biriktiradi.
    Xato bo'lsa faqat log qiladi — registratsiya oqimini buzmaydi.
    """
    headers = {"Authorization": f"Bearer {token}"}
    note_url = f"https://{domain}.amocrm.ru/api/v4/leads/{lead_id}/notes"

    note_text = (
        f"Telegram Chat ID: {chat_id}\n"
        f"Telegram Username: @{username if username else 'N/A'}\n"
        f"Telegram First Name: {first_name if first_name else 'N/A'}\n"
        f"Telegram Last Name: {last_name if last_name else 'N/A'}"
    )

    note_data = [{
        "note_type": "common",
        "params": {"text": note_text}
    }]

    async with aiohttp.ClientSession() as session:
        async with session.post(note_url, headers=headers, json=note_data) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                logging.error(f"Note yaratishda xato {resp.status}: {text}")
                raise Exception(f"Note yaratishda xato: {resp.status}")

            logging.info(f"amoCRM note biriktirildi: lead_id={lead_id}")


# ===== HOLATLAR =====
class Royxat(StatesGroup):
    ism = State()
    telefon = State()


# ===== /start =====
@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(Royxat.ism)
    await message.answer(
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "Ro'yxatdan o'tish uchun to'liq <b>ism-familiyangizni</b> kiriting:"
    )


# ===== ISM =====
@dp.message(Royxat.ism)
async def ism_qabul(message: types.Message, state: FSMContext):
    ism = message.text.strip()
    if len(ism) < 3:
        await message.answer("⚠️ Iltimos, to'liq <b>ism-familiyangizni</b> kiriting:")
        return

    await state.update_data(ism=ism)
    await state.set_state(Royxat.telefon)
    await message.answer(
        "📞 <b>Telefon raqamingizni</b> kiriting:\n"
        "<i>Masalan: +998901234567</i>"
    )


# ===== TELEFON =====
@dp.message(Royxat.telefon)
async def telefon_qabul(message: types.Message, state: FSMContext):
    tel = message.text.strip().replace(" ", "").replace("-", "")
    tozalangan = tel.replace("+", "")

    if not tozalangan.isdigit() or len(tozalangan) < 9:
        await message.answer(
            "⚠️ Noto'g'ri raqam. Qaytadan kiriting:\n"
            "<i>Masalan: +998901234567</i>"
        )
        return

    data = await state.get_data()
    ism = data.get("ism", "—")
    await state.clear()

    # --- amoCRM ga yuborish ---
    try:
        lead_id = await create_lead_with_contact(
            domain=AMOCRM_DOMAIN,
            token=AMOCRM_ACCESS_TOKEN,
            name=ism,
            phone=tel,
            pipeline_id=AMOCRM_PIPELINE_ID
        )
        logging.info(f"amoCRM lead yaratildi: {lead_id}")

        # --- Telegram metadata'sini lead ga note qilib biriktirish ---
        try:
            await add_telegram_note_to_lead(
                domain=AMOCRM_DOMAIN,
                token=AMOCRM_ACCESS_TOKEN,
                lead_id=lead_id,
                chat_id=message.chat.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
        except Exception as e:
            logging.error(f"amoCRM note biriktirishda xato: {e}")
    except Exception as e:
        logging.error(f"amoCRM ga yuborishda xato: {e}")

    # 1. Post yuborish (rasm + matn)
    await bot.send_photo(
        chat_id=message.chat.id,
        photo=PHOTO_FILE_ID,
        caption=POST_TEXT,
        parse_mode="HTML"
    )

    # 2. Tasdiqlash xabari
    await message.answer(
        f"✅ <b>Ro'yxatdan muvaffaqiyatli o'tdingiz!</b>\n\n"
        f"👤 Ism: <b>{ism}</b>\n"
        f"📞 Telefon: <b>{tel}</b>\n\n"
        f"🕐 Tez orada <b>admin</b> siz bilan bog'lanadi!"
    )


# ===== BOT KOMANDALARI =====
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Ro'yxatdan o'tish"),
    ]
    await bot.set_my_commands(commands)


# ===== MAIN =====
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands(bot)
    print("✅ Bot ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
