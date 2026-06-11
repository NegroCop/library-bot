import os
import telebot
import gspread
from google.oauth2.service_account import Credentials
import json

TOKEN = os.environ.get("BOT_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")
GOOGLE_CREDS = os.environ.get("GOOGLE_CREDS")

bot = telebot.TeleBot(TOKEN)

def get_sheet():
    creds_dict = json.loads(GOOGLE_CREDS)
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet("Books")

@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(message.chat.id,
        "📚 Добро пожаловать в школьную библиотеку!\n\n"
        "Команды:\n"
        "🔍 /search [название] — найти книгу\n"
        "📖 /take [название] — взять книгу\n"
        "↩️ /return [название] — вернуть книгу\n"
        "📋 /list — все свободные книги\n"
        "➕ /add [название] | [автор] — добавить свою книгу"
    )

@bot.message_handler(commands=["list"])
def list_books(message):
    sheet = get_sheet()
    rows = sheet.get_all_records()
    free = [r for r in rows if r["Статус"] == "Свободна"]
    if not free:
        bot.send_message(message.chat.id, "😔 Сейчас нет свободных книг")
        return
    text = "📚 Свободные книги:\n\n"
    for r in free:
        text += f"• {r['Название']} — {r['Автор']} (у {r['Владелец']})\n"
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
    found = [r for r in rows if query in str(r["Название"])() or query in r["Автор"].lower()]
    if not found:
        bot.send_message(message.chat.id, "❌ Книга не найдена")
        return
    text = "🔍 Результаты поиска:\n\n"
    for r in found:
        status = "✅ Свободна" if r["Статус"] == "Свободна" else f"❌ Занята (взял: {r['Кто взял']})"
        text += f"📖 {r['Название']} — {r['Автор']}\n👤 Владелец: {r['Владелец']}\n{status}\n\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["take"])
def take(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Напиши так: /take Гарри Поттер")
        return
    query = parts[1].lower()
    sheet = get_sheet()
    rows = sheet.get_all_records()
    for i, r in enumerate(rows, 2):
        if query in str(r["Название"]).lower():
            if r["Статус"] == "Занята":
                bot.send_message(message.chat.id, f"❌ Книга уже занята — взял {r['Кто взял']}")
                return
            name = message.from_user.first_name
            if message.from_user.last_name:
                name += f" {message.from_user.last_name}"
            sheet.update(f"F{i}", [[name]])
            sheet.update(f"E{i}", [["Занята"]])
            bot.send_message(message.chat.id, f"✅ Ты взял книгу «{r['Название']}»!")
            return
    bot.send_message(message.chat.id, "❌ Книга не найдена")

@bot.message_handler(commands=["return"])
def return_book(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Напиши так: /return Гарри Поттер")
        return
    query = parts[1].lower()
    sheet = get_sheet()
    rows = sheet.get_all_records()
    for i, r in enumerate(rows, 2):
        if query in str(r["Название"]).lower():
            if r["Статус"] == "Свободна":
                bot.send_message(message.chat.id, "📖 Эта книга и так свободна")
                return
            sheet.update(f"F{i}", [[""]])
            sheet.update(f"E{i}", [["Свободна"]])
            bot.send_message(message.chat.id, f"✅ Книга «{r['Название']}» возвращена!")
            return
    bot.send_message(message.chat.id, "❌ Книга не найдена")

@bot.message_handler(commands=["add"])
def add_book(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or "|" not in parts[1]:
        bot.send_message(message.chat.id, "Напиши так: /add Название | Автор")
        return
    title, author = parts[1].split("|", 1)
    name = message.from_user.first_name
    if message.from_user.last_name:
        name += f" {message.from_user.last_name}"
    sheet = get_sheet()
    rows = sheet.get_all_records()
    new_id = len(rows) + 1
    sheet.append_row([new_id, title.strip(), author.strip(), name, "Свободна", "", ""])
    bot.send_message(message.chat.id, f"✅ Книга «{title.strip()}» добавлена в библиотеку!")

bot.infinity_polling()
