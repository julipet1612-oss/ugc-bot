from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def category_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Beauty & Skincare", callback_data="cat_beauty")],
        [InlineKeyboardButton(text="Supplements", callback_data="cat_supplements")],
        [InlineKeyboardButton(text="Apparel", callback_data="cat_apparel")],
        [InlineKeyboardButton(text="Food & Beverage", callback_data="cat_food")],
        [InlineKeyboardButton(text="Home & Kitchen", callback_data="cat_home")],
        [InlineKeyboardButton(text="Baby & Parenting", callback_data="cat_baby")],
        [InlineKeyboardButton(text="Pet", callback_data="cat_pet")],
        [InlineKeyboardButton(text="Tech & Travel", callback_data="cat_tech")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def style_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Телефонное фото 9:16", callback_data="style_phone")],
        [InlineKeyboardButton(text="Флэтлей", callback_data="style_flatlay")],
        [InlineKeyboardButton(text="Лайфстайл", callback_data="style_lifestyle")],
        [InlineKeyboardButton(text="На улице", callback_data="style_outdoor")],
        [InlineKeyboardButton(text="Ванная / уход", callback_data="style_bathroom")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_kb() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="Да, генерируй", callback_data="confirm_yes"),
            InlineKeyboardButton(text="Отмена", callback_data="confirm_no"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
