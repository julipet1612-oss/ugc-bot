import asyncio
import logging
import base64
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiohttp
import replicate
import os

from keyboards import category_kb, style_kb, confirm_kb
from config import BOT_TOKEN, REPLICATE_API_TOKEN

logging.basicConfig(level=logging.INFO)
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class GenStates(StatesGroup):
    waiting_photo = State()
    choosing_category = State()
    choosing_style = State()
    confirming = State()


CATEGORIES = {
    "beauty": "BEAUTY & SKINCARE",
    "supplements": "SUPPLEMENTS & WELLNESS",
    "apparel": "APPAREL & ACCESSORIES",
    "food": "FOOD & BEVERAGE",
    "home": "HOME & KITCHEN",
    "baby": "BABY & PARENTING",
    "pet": "PET",
    "tech": "TECH & TRAVEL ACCESSORIES",
}

STYLES = {
    "phone": "realistic smartphone photo, vertical 9:16, natural lighting, slight grain, authentic UGC style, candid",
    "flatlay": "flat lay photography, top view, clean background, soft natural light, product centered",
    "lifestyle": "lifestyle photo with hands holding the product, realistic, candid, phone camera aesthetic",
    "outdoor": "outdoor natural setting, daylight, realistic smartphone photo, natural environment",
    "bathroom": "bathroom or vanity setting, soft lighting, realistic phone photo, clean aesthetic",
}

NEGATIVE_PROMPT = "text, watermark, logo, signature, blurry, low quality, distorted, ugly, cartoon, illustration, painting, drawing, extra fingers, deformed, oversaturated"


def build_prompt(category_name: str, style_desc: str) -> str:
    return (
        f"authentic UGC smartphone photo of a {category_name.lower()} product, "
        f"{style_desc}, vertical composition, highly realistic, natural lighting, "
        f"no text, no watermark, looks like real user generated content from phone camera, "
        f"sharp product details, good composition"
    )


async def image_to_data_uri(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


async def generate_with_replicate(product_bytes: bytes, style_bytes: bytes | None, prompt: str) -> bytes | None:
    try:
        product_uri = await image_to_data_uri(product_bytes)
        ip_image = await image_to_data_uri(style_bytes) if style_bytes else product_uri

        output = replicate.run(
            "usamaehsan/controlnet-x-ip-adapter-realistic-vision-v5",
            input={
                "prompt": prompt,
                "negative_prompt": NEGATIVE_PROMPT,
                "image": product_uri,
                "ip_adapter_image": ip_image,
                "controlnet_conditioning_scale": 0.7,
                "ip_adapter_scale": 0.6,
                "num_inference_steps": 30,
                "guidance_scale": 7.0,
                "width": 768,
                "height": 1344,
            }
        )

        if isinstance(output, list) and output:
            image_url = str(output[0])
        else:
            image_url = str(output)

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status == 200:
                    return await resp.read()
        return None
    except Exception as e:
        logging.exception(f"Replicate error: {e}")
        return None


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Йо. Кидай фото продукта — сделаю UGC с ControlNet + IP-Adapter.\n\n"
        "Можешь потом кинуть ещё референс стиля (опционально)."
    )
    await state.set_state(GenStates.waiting_photo)


@dp.message(GenStates.waiting_photo, F.photo)
async def got_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_io = await bot.download_file(file.file_path)
    image_data = file_io.read()

    await state.update_data(product_bytes=image_data)
    await message.answer(
        "Фотка продукта принята.\n"
        "Теперь можешь кинуть референс стиля (ещё одно фото) или сразу выбрать категорию.",
        reply_markup=category_kb()
    )
    await state.set_state(GenStates.choosing_category)


@dp.message(GenStates.choosing_category, F.photo)
async def got_style_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_io = await bot.download_file(file.file_path)
    style_data = file_io.read()
    await state.update_data(style_bytes=style_data)
    await message.answer("Референс стиля принят. Теперь выбери категорию:", reply_markup=category_kb())


@dp.message(GenStates.waiting_photo)
async def not_photo(message: Message):
    await message.answer("Бро, кидай именно фото.")


@dp.callback_query(GenStates.choosing_category, F.data.startswith("cat_"))
async def choose_category(callback: CallbackQuery, state: FSMContext):
    cat_key = callback.data.split("_", 1)[1]
    await state.update_data(category=cat_key, category_name=CATEGORIES.get(cat_key, cat_key))
    await callback.message.edit_text(
        f"Категория: {CATEGORIES.get(cat_key)}\n\nТеперь стиль:",
        reply_markup=style_kb()
    )
    await state.set_state(GenStates.choosing_style)
    await callback.answer()


@dp.callback_query(GenStates.choosing_style, F.data.startswith("style_"))
async def choose_style(callback: CallbackQuery, state: FSMContext):
    style_key = callback.data.split("_", 1)[1]
    data = await state.get_data()
    await state.update_data(style=style_key)
    has_style_ref = "style_bytes" in data
    text = (
        f"Проверь:\n"
        f"Категория: {data.get('category_name')}\n"
        f"Стиль: {style_key}\n"
        f"Референс стиля: {'есть' if has_style_ref else 'нет'}\n\n"
        f"Генерим?"
    )
    await callback.message.edit_text(text, reply_markup=confirm_kb())
    await state.set_state(GenStates.confirming)
    await callback.answer()


@dp.callback_query(GenStates.confirming, F.data == "confirm_yes")
async def confirm_generate(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text("Генерирую... 15-40 сек.")

    product_bytes = data.get("product_bytes")
    style_bytes = data.get("style_bytes")
    category_name = data.get("category_name", "product")
    style_key = data.get("style", "phone")
    style_desc = STYLES.get(style_key, STYLES["phone"])

    prompt = build_prompt(category_name, style_desc)

    try:
        result_bytes = await generate_with_replicate(product_bytes, style_bytes, prompt)
        if result_bytes:
            photo = BufferedInputFile(result_bytes, filename="ugc.png")
            await callback.message.answer_photo(
                photo,
                caption=f"Готово\nКатегория: {category_name}\nСтиль: {style_key}"
            )
        else:
            await callback.message.answer("Не вышло. Проверь токены и модель.")
    except Exception as e:
        logging.exception("Gen failed")
        await callback.message.answer(f"Ошибка: {e}")

    await callback.message.answer("Кидай новое фото или /start")
    await state.clear()
    await callback.answer()


@dp.callback_query(F.data == "confirm_no")
async def confirm_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Отменил. /start чтобы начать заново")
    await callback.answer()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
