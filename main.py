from dotenv import load_dotenv
import os
import telebot
import pandas as pd
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message,
)
import sqlite3 as sql
import datetime
from openai import OpenAI


doing_search = []

df = pd.read_excel("data.xlsx")
blacklist = []

load_dotenv()
token = os.getenv("TOKEN")
openai_token = os.getenv("OPENAI")

bot = telebot.TeleBot(token)

print("Bot Started")


@bot.callback_query_handler(func=lambda x: True)
def button_callback(call: CallbackQuery):
    if call.data == "cat":
        bot.answer_callback_query(call.id)
        handle_categories(call.message)
    elif call.data == "apps":
        bot.answer_callback_query(call.id)
        apps_start(call.message)
    elif call.data == "search":
        bot.answer_callback_query(call.id)
        search_starting(call.message)


@bot.message_handler(commands=["start", "help"])
def handle_start(message: Message):

    add_data_to_db("start", str(message.from_user.id))

    cat_button = InlineKeyboardButton("🎯 Категории", callback_data="cat")
    apps_button = InlineKeyboardButton("💻 Приложения", callback_data="apps")
    search_button = InlineKeyboardButton("🔎 Поиск", callback_data="search")
    keyboard = InlineKeyboardMarkup()
    keyboard.add(cat_button, apps_button, search_button)

    bot.send_message(
        message.chat.id,
        """👋 Привет! Этот бот поможет тебе найти бесплатные веб-приложения для любых целей.\n
🎯 Используйте команду /categories для просмотра категорий приложений.
💻 Используйте команду /apps для просмотра приложений в определенной категории.
🔍 Используйте команду /search, чтобы найти нужное вам приложение с помощью ИИ.
❗ Нашли ошибку, или хотите предложить веб-приложение для добавления в базу? Напишите разработчику используя команду /contact.\n
Обозначения значков:
⚠️ - для использования из России нужен VPN.
💻 - для использования нужен аккаунт.""",
        reply_markup=keyboard,
    )


@bot.message_handler(commands=["categories"])
def handle_categories(message: Message):
    categories_list = list(sorted(df["category"].unique()))
    categories_text = "\n".join(
        f"{i + 1}. {category}" for i, category in enumerate(categories_list)
    )

    search_button = InlineKeyboardButton("🔎 Поиск", callback_data="search")
    apps_button = InlineKeyboardButton("💻 Приложения", callback_data="apps")
    keyboard = InlineKeyboardMarkup()
    keyboard.add(apps_button, search_button)

    bot.send_message(
        message.chat.id,
        f"🎯 Вот список категорий:\n\n{categories_text}",
        reply_markup=keyboard,
    )
    add_data_to_db("categories", str(message.from_user.id))


@bot.message_handler(commands=["apps"])
def apps_start(message: Message):
    add_data_to_db("apps", str(message.from_user.id))
    bot.send_message(
        message.chat.id,
        "💻 Отправьте мне номер категории, приложения которой хотите посмотреть.\n\nЧтобы увидеть список категорий используйте команду /categories.",
    )
    bot.register_next_step_handler(message, handle_apps)


def handle_apps(message: Message):
    try:
        if message.text is not None:
            if message.text.strip() != "/apps":
                if message.text.strip() != "/categories":
                    if message.text.strip() != "/start":
                        if message.text.strip() != "/contact":
                            category_number = int(message.text.strip()) - 1
                            if category_number >= 0:
                                category = list(sorted(df["category"].unique()))[
                                    category_number
                                ]
                                apps_in_category = df[df["category"] == category]

                                apps_text = ""
                                for _, app in apps_in_category.iterrows():
                                    vpn_icon = "⚠️ " if app["vpn_needed"] else ""
                                    account_icon = "💻 " if app["login_needed"] else ""
                                    apps_text += f"""{vpn_icon}{account_icon}<a href="{app['link']}">{app['name']}</a>: {app['description']}.\n\n"""

                                bot.send_message(
                                    message.chat.id,
                                    f'♦ Приложения в категории "<b>{category}</b>":\n\n{apps_text}',
                                    parse_mode="HTML",
                                    disable_web_page_preview=True,
                                )
                            else:
                                raise IndexError
                        else:
                            handle_contact(message)
                    else:
                        handle_start(message)
                else:
                    handle_categories(message)
            else:
                handle_apps(message)
        else:
            raise ValueError

    except (IndexError, ValueError):
        bot.send_message(
            message.chat.id,
            "❌ Вы отправили мне неверный номер категории. Вы можете увидеть список категорий с помощью команды /categories. Повторите попытку с помощью команды /apps.",
            parse_mode="Markdown",
        )


@bot.message_handler(commands=["contact"])
def handle_contact(message: Message):
    if message.from_user.id not in blacklist:
        bot.send_message(
            message.chat.id,
            "Отправьте ваше сообщение и я перешлю его владельцу бота! Чтобы отменить отправку напишите /cancel.",
        )
        add_data_to_db("contact", str(message.from_user.id))
        bot.register_next_step_handler(message, forward_contact)
    else:
        bot.send_message(
            message.chat.id,
            "😇 Дружок, ты настолько достал создателя бота, что он добавил тебя в чёрный список. Ты не можешь использовать эту команду!",
        )


def forward_contact(message: Message):
    if message.text != "/cancel":
        user_id = message.from_user.id
        username = message.from_user.username
        forwarded = bot.forward_message(1038099964, message.chat.id, message.message_id)

        bot.send_message(
            forwarded.chat.id,
            f"Это было сообщение от пользователя @{username} (ID: {user_id})",
        )

        bot.send_message(
            message.chat.id,
            "✅ Ваше сообщение было отправлено владельцу бота. Спасибо!",
        )
    else:
        bot.send_message(message.chat.id, "✅ Отправка была отменена.")


@bot.message_handler(commands=["reply"])
def handle_reply(message: Message):
    try:
        _, user_id, reply_text = message.text.split(" ", 2)
        user_id = int(user_id)
        if message.from_user.id == int(1038099964):
            bot.send_message(user_id, f"❗ Ответ от владельца бота:\n\n{reply_text}")
            bot.send_message(message.chat.id, "✅ Ответ был отправлен пользователю.")
        else:
            bot.send_message(
                message.chat.id,
                "Ха-ха хотел меня обмануть? Эта команда только для создателя бота 😈😈😈",
            )

    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌ Используйте команду в формате `/reply {user_id} {message_text}`.",
            parse_mode="Markdown",
        )


@bot.message_handler(commands=["reload_df"])
def handle_reload_df(message: Message):
    global df

    if message.from_user.id == int(1038099964):
        df = pd.read_excel("data.xlsx")
        bot.send_message(message.chat.id, "✅ База обновлена.")
    else:
        bot.send_message(
            message.chat.id,
            "Ха-ха хотел меня обмануть? Эта команда только для создателя бота 😈😈😈",
        )


def get_all_apps():
    all_apps = ""
    for id, app in df.iterrows():
        app_info = f"{id + 1}, {app['name']}, {app['description']}\n"
        all_apps += app_info

    return all_apps


def get_line_by_app_row(row_number):
    try:
        if row_number != 0:
            app = df.iloc[row_number - 1]
            vpn_icon = "⚠️ " if app["vpn_needed"] else ""
            account_icon = "💻 " if app["login_needed"] else ""
            app_text = f"""{vpn_icon}{account_icon}<a href="{app['link']}">{app['name']}</a>: {app['description']}.\n\n"""
            return app_text
        else:
            return f"❗ Кажется, такого приложения у меня пока нет. Ты можешь попробовать поискать вручную используя /categories и /apps. Также ты можешь предложить свое приложение для добавления в бота с помощью /contact."
    except IndexError:
        return "❗ GPT ответил в неправильном формате. Это возникает редко. Пожалуйста, повторите попытку поиска."


@bot.message_handler(commands=["search"])
def search_starting(message: Message):
    if message.from_user.id not in doing_search:
        bot.send_message(
            message.chat.id,
            '🔎 Это функция поиска по базе с помощью нейросети.\nПросто скажи мне свой запрос, например "Приложение для обработки фото", и бот подскажет нужное приложение!\nДля отмены запроса напишите /cancel.',
            parse_mode="Markdown",
        )
        add_data_to_db("search", str(message.from_user.id))

        bot.register_next_step_handler(message, search_handling)
    else:
        bot.send_message(
            message.chat.id,
            "❌ Вы не можете выполнять два поиска одновременно! Дождитесь окончания предыдущего поиска!",
        )


def search_handling(message: Message, flag_send_msg=True, searching_message=None):
    try:
        if message.text is not None:
            if message.text.strip() != "/apps":
                if message.text.strip() != "/categories":
                    if message.text.strip() != "/start":
                        if message.text.strip() != "/contact":
                            if message.text.strip() != "/cancel":
                                if message.from_user.id not in doing_search:
                                    doing_search.append(message.from_user.id)
                                user_asks = message.text
                                list_of_apps = get_all_apps()

                                if flag_send_msg:
                                    searching_message = bot.send_message(
                                        message.chat.id, "🔍 Поиск по базе..."
                                    )

                                client = OpenAI(api_key=openai_token)

                                response = client.chat.completions.create(
                                    model="gpt-3.5-turbo",
                                    messages=[
                                        {
                                            "role": "user",
                                            "content": 'Привет! Тебе заплатят $100, за очень простую работу. Главное всё делать правильно. У тебя есть запрос пользователя: "'
                                            + user_asks
                                            + '" Твоя задача - подобрать максимально подходящее этому пользователю ОДНО или НЕСКОЛЬКО веб-приложений (до 5 приложений) из списка. Все приложения можно использовать только по прямому назначению. Тебе даны названия и описания этих приложений. В ответе на запрос напиши только id этого/этих приложений ЦИФРАМИ через пробел и ничего больше. Если ты напишешь что-то кроме числа/чисел, то ты потеряешь работу. Если напрямую подходящего приложения нет, в качестве ответа пришли мне число 0. Напомню, что приложения можно выбирать ТОЛЬКО из списка и максимум можно выбрать 5 приложений. Вот список веб приложений в формате id, название, описание:\n\n'
                                            + list_of_apps,
                                        }
                                    ],
                                )

                                gpt_response = response.choices[0].message.content
                                print(gpt_response)

                                final_response = ""

                                for letter in gpt_response:
                                    if letter.isdigit():
                                        final_response += letter
                                    else:
                                        final_response += " "

                                final_response = final_response.split()
                                final2 = ""
                                for elem in final_response:
                                    final2 += get_line_by_app_row(int(elem))

                                if final2 != "":
                                    bot.delete_message(
                                        message.chat.id, searching_message.message_id
                                    )

                                    bot.send_message(
                                        message.chat.id,
                                        (
                                            f"Вот подходящие приложения:\n\n{final2}"
                                            if not final2.startswith("❗")
                                            else final2
                                        ),
                                        parse_mode="HTML",
                                        disable_web_page_preview=True,
                                    )

                                    doing_search.remove(message.from_user.id)
                                else:
                                    search_handling(
                                        message,
                                        flag_send_msg=False,
                                        searching_message=searching_message,
                                    )
                            else:
                                bot.send_message(
                                    message.chat.id,
                                    "✅ Запрос был отменен.",
                                    parse_mode="Markdown",
                                )
                        else:
                            handle_contact(message)
                    else:
                        handle_start(message)
                else:
                    handle_categories(message)
            else:
                apps_start(message)
        else:
            bot.send_message(
                message.chat.id,
                "❌ Вероятно, вы отправили мне картинку или стикер. Я умею выполнять поиск только используя текст. Повторите попытку с помощью команды /search.",
                parse_mode="Markdown",
            )

    except Exception as e:
        print(e)
        print("Повторяю запрос...")
        search_handling(
            message, flag_send_msg=False, searching_message=searching_message
        )


def add_data_to_db(command_used, user_id):
    conn = sql.connect("users_data.db")
    c = conn.cursor()

    date = datetime.datetime.now()

    c.execute(
        "INSERT INTO data (command_used, date, user_id) VALUES (?, ?, ?)",
        (command_used, date, user_id),
    )

    conn.commit()
    conn.close()


def get_all_user_ids():
    conn = sql.connect("users_data.db")
    c = conn.cursor()

    c.execute("SELECT DISTINCT user_id FROM data")
    user_ids = c.fetchall()

    conn.close()

    return [user_id[0] for user_id in user_ids]


@bot.message_handler(commands=["message_all"])
def message_all_handling(message: Message):
    if message.from_user.id == int(1038099964):
        _, text = message.text.split(" ", 1)

        for id in get_all_user_ids():
            try:
                bot.send_message(id, text, parse_mode="Markdown")
            except Exception:
                pass
    else:
        bot.send_message(
            message.chat.id,
            "Ха-ха хотел меня обмануть? Эта команда только для создателя бота 😈😈😈",
        )


@bot.message_handler(commands=["get_data"])
def message_all_handling(message: Message):
    if message.from_user.id == int(1038099964):
        with open("users_data.db", "rb") as f:
            bot.send_document(message.chat.id, f)
    else:
        bot.send_message(
            message.chat.id,
            "Ха-ха хотел меня обмануть? Эта команда только для создателя бота 😈😈😈",
        )


bot.infinity_polling()
