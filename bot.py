import os
import telebot
import gspread
from google.oauth2.service_account import Credentials
from datetime import date
import json

TOKEN = os.environ.get("BOT_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")
GOOGLE_CREDS = os.environ.get("GOOGLE_CREDS")

bot = telebot.TeleBot(TOKEN)


def get_sheet():
    creds_dict = json.loads(GOOGLE_CREDS)
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet("Books")


def get_name(message_or_user):
    if hasattr(message_or_user, 'from_user'):
        user = message_or_user.from_user
    else:
        user = message_or_user
    name = user.first_name
    if user.last_name:
        name += f" {user.last_name}"
    return name


@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(message.chat.id,
        "📚 Добро пожаловать в школьную библиотеку!\n\n"
        "Команды:\n"
        "🔍 /search [название] — найти книгу\n"
        "📋 /list — все свободные книги\n"
        "📖 /take — взять книгу\n"
        "↩️ /return — вернуть книгу\n"
        "🗂 /mybooks — мои взятые книги\n"
        "➕ /add [название] | [автор] — добавить свою книгу"
    )


@bot.message_handler(commands=["list"])
def list_books(message):
    sheet = get_sheet()
    rows = sheet.get_all_records()
    free = [r for r in rows if str(r["Статус"]) == "Свободна"]
    taken = [r for r in rows if str(r["Статус"]) == "Занята"]
    text = ""
    if free:
        text += "✅ Свободные книги:\n\n"
        for r in free:
            text += f"• {r['Название']} — {r['Автор']} (у {r['Владелец']})\n"
    else:
        text += "😔 Свободных книг нет\n"
    text += "\n"
    if taken:
        text += "❌ Занятые книги:\n\n"
        for r in taken:
            text += f"• {r['Название']} — {r['Автор']}\n  👤 Взял: {r['Кто взял']} ({r['Дата взятия']})\n"
    else:
        text += "🎉 Все книги свободны!\n"
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=["search"])
def search(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Напиши так: /search Гарри Поттер")
        return
    query = parts[1].lower()
    sheet = get_sheet()
    rows = sheet.get_all_records()
    found = [r for r in rows if query in str(r["Название"]).lower() or query in str(r["Автор"]).lower()]
    if not found:
        bot.send_message(message.chat.id, "❌ Книга не найдена")
        return
    text = "🔍 Результаты поиска:\n\n"
    for r in found:
        if str(r["Статус"]) == "Свободна":
            status = "✅ Свободна"
        else:
            try:
                taken_date = date(*reversed([int(x) for x in str(r["Дата взятия"]).split(".")]))
                days = (date.today() - taken_date).days
                status = f"❌ Занята — {r['Кто взял']}\n📅 Взята {r['Дата взятия']} ({days} дн. назад)"
            except:
                status = f"❌ Занята — {r['Кто взял']}"
        text += f"📖 {r['Название']} — {r['Автор']}\n👤 Владелец: {r['Владелец']}\n{status}\n\n"
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=["take"])
def take(message):
    name = get_name(message)
    sheet = get_sheet()
    rows = sheet.get_all_records()
    already = [r for r in rows if str(r["Кто взял"]) == name]
    if len(already) >= 1:
        bot.send_message(message.chat.id, f"❌ Ты уже взял книгу «{already[0]['Название']}». Сначала верни её.")
        return
    free = [(i, r) for i, r in enumerate(rows, 2) if str(r["Статус"]) == "Свободна"]
    if not free:
        bot.send_message(message.chat.id, "😔 Сейчас нет свободных книг")
        return
    keyboard = telebot.types.InlineKeyboardMarkup()
    for i, r in free:
        keyboard.add(telebot.types.InlineKeyboardButton(
            f"📖 {r['Название']} — {r['Автор']}",
            callback_data=f"take_{i}"
        ))
    bot.send_message(message.chat.id, "Выбери книгу:", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data == "take_cancel")
def take_cancel(call):
    bot.edit_message_text("Окей, в другой раз 📚", call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("take_yes_"))
def take_final(call):
    row_index = int(call.data.split("_")[2])
    name = get_name(call)
    sheet = get_sheet()
    rows = sheet.get_all_records()
    r = rows[row_index - 2]
    if str(r["Статус"]) == "Занята":
        bot.edit_message_text("❌ Книгу только что взял кто-то другой", call.message.chat.id, call.message.message_id)
        return
    today = date.today().strftime("%d.%m.%Y")
    sheet.update(f"E{row_index}", [["Занята"]])
    sheet.update(f"F{row_index}", [[name]])
    sheet.update(f"G{row_index}", [[today]])
    bot.edit_message_text(f"✅ Ты взял книгу «{r['Название']}»!", call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("take_"))
def take_confirm(call):
    row_index = int(call.data.split("_")[1])
    sheet = get_sheet()
    rows = sheet.get_all_records()
    r = rows[row_index - 2]
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(
        telebot.types.InlineKeyboardButton("✅ Да", callback_data=f"take_yes_{row_index}"),
        telebot.types.InlineKeyboardButton("❌ Нет", callback_data="take_cancel")
    )
    bot.edit_message_text(
        f"Хочешь взять книгу «{r['Название']}» — {r['Автор']}?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard
    )


@bot.message_handler(commands=["return"])
def return_book(message):
    name = get_name(message)
    sheet = get_sheet()
    rows = sheet.get_all_records()
    for i, r in enumerate(rows, 2):
        if str(r["Кто взял"]) == name:
            keyboard = telebot.types.InlineKeyboardMarkup()
            keyboard.add(
                telebot.types.InlineKeyboardButton("✅ Да", callback_data=f"return_{i}"),
                telebot.types.InlineKeyboardButton("❌ Нет", callback_data="return_cancel")
            )
            bot.send_message(message.chat.id,
                f"Хочешь вернуть книгу «{r['Название']}»?",
                reply_markup=keyboard
            )
            return
    bot.send_message(message.chat.id, "📭 У тебя нет взятых книг")


@bot.callback_query_handler(func=lambda call: call.data == "return_cancel")
def return_cancel(call):
    bot.edit_message_text("Окей, книга остаётся у тебя 📚", call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("return_"))
def return_confirm(call):
    row_index = int(call.data.split("_")[1])
    sheet = get_sheet()
    rows = sheet.get_all_records()
    r = rows[row_index - 2]
    sheet.update(f"E{row_index}", [["Свободна"]])
    sheet.update(f"F{row_index}", [[""]])
    sheet.update(f"G{row_index}", [[""]])
    bot.edit_message_text(f"✅ Книга «{r['Название']}» возвращена!", call.message.chat.id, call.message.message_id)


@bot.message_handler(commands=["mybooks"])
def my_books(message):
    name = get_name(message)
    sheet = get_sheet()
    rows = sheet.get_all_records()
    taken = [r for r in rows if str(r["Кто взял"]) == name]
    if not taken:
        bot.send_message(message.chat.id, "📭 У тебя нет взятых книг")
        return
    text = "📚 Твои книги:\n\n"
    for r in taken:
        text += f"• {r['Название']} — {r['Автор']} (взята {r['Дата взятия']})\n"
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=["add"])
def add_book(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or "|" not in parts[1]:
        bot.send_message(message.chat.id, "Напиши так: /add Название | Автор")
        return
    title, author = parts[1].split("|", 1)
    name = get_name(message)
    sheet = get_sheet()
    rows = sheet.get_all_records()
    new_id = len(rows) + 1
    sheet.append_row([new_id, title.strip(), author.strip(), name, "Свободна", "", ""])
    bot.send_message(message.chat.id, f"✅ Книга «{title.strip()}» добавлена в библиотеку!")


bot.infinity_polling()
