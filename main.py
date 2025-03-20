import random
import os
# import configparser
import BD.database as database
from telebot import types, TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup



database.initialize()

print('Запуск telegram-бота...')

# Принимаем имя переменной среды
token_bot = os.getenv('token_bot')    
# Проверяем, инициализирована ли переменная
if token_bot is None:
    token_bot = input("Введите телеграмм-токен :")
    os.environ['token_bot'] = token_bot 
        
   
state_storage = StateMemoryStorage()
bot = TeleBot(token_bot, state_storage=state_storage)

# Получить пользователей из БД
known_users = database.get_all_user()
# known_users = []
userStep = {}
buttons = []


def show_hint(*lines):
    return '\n'.join(lines)


def show_target(data):
    return f"{data['target_word']} -> {data['translate_word']}"


class Command:
    ADD_WORD = 'Добавить слово ➕'
    DELETE_WORD = 'Удалить слово🔙'
    NEXT = 'Дальше ⏭'    
    UPDATE_USER_DICT = 'Обновить словарь пользователя'


class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()
    adding_word = State()
    saving_word = State()
    deleting_word = State()


def get_user_step(uid):
    if uid in userStep:
        return userStep[uid]
    else:
        known_users.append(uid)
        userStep[uid] = 0
        database.check_user(uid, uid)
        print("Обнаружен новый пользователь \"/start\" yet")
        return 0


@bot.message_handler(commands=['cards', 'start'])
def create_cards(message):
    cid = message.chat.id
    username  = message.from_user.full_name 
    if username is None: 
        username  = message.from_user.first_name
         
    if cid not in known_users:
        known_users.append(cid)
        # Здесь добавить пользователя в БД
        database.check_user(message.from_user.id, username )
        userStep[cid] = 0
        bot.send_message(cid, f"Привет, {username}, давай изучать английский...")
    else:
        bot.send_message(cid, f"{username}, продолжим изучение...") 
    markup = types.ReplyKeyboardMarkup(row_width=2)

    global buttons
    buttons = []    
    word_1 = database.get_random_words(message.from_user.id,1)[0]
    target_word = word_1[0]  # брать из БД
    translate = word_1[1]  # брать из БД
    target_word_btn = types.KeyboardButton(target_word)
    buttons.append(target_word_btn)
    word_3 = database.get_random_words(message.from_user.id,3,target_word)
    others = [word_3[0][0], word_3[1][0], word_3[2][0]]  # брать из БД
    other_words_btns = [types.KeyboardButton(word) for word in others]
    buttons.extend(other_words_btns)
    random.shuffle(buttons)
    next_btn = types.KeyboardButton(Command.NEXT)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
    ud_btn = types.KeyboardButton(Command.UPDATE_USER_DICT)
    buttons.extend([next_btn, add_word_btn, delete_word_btn, ud_btn])

    markup.add(*buttons)

    greeting = f"Выбери перевод слова:\n🇷🇺 {translate}"
    bot.send_message(message.chat.id, greeting, reply_markup=markup)
    bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['target_word'] = target_word
        data['translate_word'] = translate
        data['other_words'] = others


@bot.message_handler(func=lambda message: message.text == Command.UPDATE_USER_DICT)
def updare_user_dict(message):
    cid = message.chat.id
    database.add_words_for_new_user(message.from_user.id)
    bot.send_message(cid, "Словарь пользователя обновлен! Продолжим..")
    send_main_menu(cid)
    # create_cards(message)
    
@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    create_cards(message)    


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    bot.set_state(user_id=message.from_user.id, chat_id=message.chat.id, state=MyStates.deleting_word)
    bot.send_message(message.chat.id, "Введите слово, которое хотите удалить, на русском:")
    

@bot.message_handler(state=MyStates.deleting_word)
def delete_word(message):
    cid = message.chat.id
    word_to_delete = message.text.strip().capitalize()

    # Удаляем слово и проверяем состояние
    word_to_delete_id = database.delete_user_word(message.from_user.id, word_to_delete)

    if word_to_delete_id:
        bot.send_message(cid, f"Слово '{word_to_delete}' успешно удалено из вашего словаря!")
        print(f"Удалено слово: {word_to_delete}")
    else:
        bot.send_message(cid, "Слово не найдено в вашем персональном словаре.")
        print("Слово не удалено.")
    bot.delete_state(user_id=message.from_user.id, chat_id=message.chat.id)
    send_main_menu(cid)

@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    cid = message.chat.id
    userStep[cid] = 1
    print(message.text)  # сохранить в БД
    bot.set_state(user_id=message.from_user.id, chat_id=cid, state=MyStates.adding_word)
    bot.send_message(cid, "Введите слово, на английском:")
    

@bot.message_handler(state=MyStates.adding_word)
def add_translate_word(message):
    cid = message.chat.id
    word = message.text.strip().capitalize()

    # Проверяем, что слова нет в общем словаре
    if database.check_word_existence(word):
        bot.send_message(cid, "Это слово уже есть в общем словаре. Пожалуйста, введите другое слово.")
        return

    # Сохраняем слово в состоянии
    with bot.retrieve_data(user_id=message.from_user.id, chat_id=cid) as data:
        data['target_word'] = word

    bot.set_state(user_id=message.from_user.id, chat_id=cid, state=MyStates.saving_word)
    bot.send_message(cid, f"Теперь введите перевод для слова '{word}':")
    

@bot.message_handler(state=MyStates.saving_word)
def save_word(message):
    cid = message.chat.id
    translation = message.text.strip().capitalize()

    # Проверяем, что перевод не пустой
    if not translation:
        bot.send_message(cid, "Перевод не может быть пустым. Пожалуйста, введите перевод.")
        return

    try:
        # Извлекаем данные из состояния
        with bot.retrieve_data(user_id=message.from_user.id, chat_id=cid) as data:
            target_word = data.get('target_word').capitalize()

        if not target_word:
            bot.send_message(cid, "Ошибка! Попробуй снова начать с /start.")
            bot.delete_state(user_id=message.from_user.id, chat_id=cid)
            return

        # Сохраняем новое слово 
        database.add_word_to_user(message.from_user.id, target_word, translation)

        bot.send_message(cid, f"Слово '{target_word}' и его перевод '{translation}' успешно добавлены!")
    except Exception as e:
        print(f"Произошла ошибка при сохранении слова: {e}")
        bot.send_message(cid, f"Произошла ошибка при сохранении слова: {e}")
    finally:
        bot.delete_state(user_id=message.from_user.id, chat_id=cid)

    send_main_menu(cid)
    
def send_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(row_width=2)
    buttons = [
        types.KeyboardButton(Command.ADD_WORD),
        types.KeyboardButton(Command.DELETE_WORD),
        types.KeyboardButton(Command.NEXT),
        types.KeyboardButton(Command.UPDATE_USER_DICT) 
        
    ]
    markup.add(*buttons)
    bot.send_message(chat_id, "Выберите дальнейшее действие:", reply_markup=markup)    



@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
    text = message.text
    markup = types.ReplyKeyboardMarkup(row_width=2)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        target_word = data['target_word']
        if text == target_word:
            hint = show_target(data)
            hint_text = ["Отлично!❤", hint]   
            database.update_word_to_user_dict(message.from_user.id, target_word, data['translate_word'])        
            # next_btn = types.KeyboardButton(Command.NEXT)
            # add_word_btn = types.KeyboardButton(Command.ADD_WORD)
            # delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
            # buttons.extend([next_btn, add_word_btn, delete_word_btn])
            hint = show_hint(*hint_text)
        else:
            for btn in buttons:
                if btn.text == text:
                    btn.text = text + '❌'
                    break
            hint = show_hint("Допущена ошибка!",
                             f"Попробуй ещё раз вспомнить слово 🇷🇺{data['translate_word']}")
    markup.add(*buttons)
    bot.send_message(message.chat.id, hint, reply_markup=markup)


bot.add_custom_filter(custom_filters.StateFilter(bot))

bot.infinity_polling(timeout=10, long_polling_timeout=5,skip_pending=True)