import json
import telegram
import logging

from datetime import datetime
from .model import ExpenseEntry
from .credentials import DEPLOY_URL, DEBUG_URL
from appconfig import AppConfig

if AppConfig.debug:
    URL = DEPLOY_URL
else:
    URL = DEBUG_URL


# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

start_keyboard_buttons = [[telegram.KeyboardButton('create expense')], [telegram.KeyboardButton('my logs')]]
start_keyboard_markup = telegram.ReplyKeyboardMarkup(start_keyboard_buttons)

info_keyboard_buttons = [[telegram.KeyboardButton('view my info')], [telegram.KeyboardButton('enter my info')],
                         [telegram.KeyboardButton('home')]]
info_keyboard_markup = telegram.ReplyKeyboardMarkup(info_keyboard_buttons)

info_input_keyboard_buttons = [[telegram.KeyboardButton('skips')], [telegram.KeyboardButton('home')]]
info_input_keyboard_markup = telegram.ReplyKeyboardMarkup(info_input_keyboard_buttons)

delete_keyboard_buttons = [[telegram.KeyboardButton('confirm delete')],
                           [telegram.KeyboardButton('cancel delete')]]
delete_keyboard_markup = telegram.ReplyKeyboardMarkup(delete_keyboard_buttons)

amount_keyboard_buttons = [[telegram.KeyboardButton('less than 1')], [telegram.KeyboardButton('around 5')],
                           [telegram.KeyboardButton('cancel create')]]
amount_keyboard_markup = telegram.ReplyKeyboardMarkup(amount_keyboard_buttons)

category_keyboard_buttons = [[telegram.KeyboardButton('food')], [telegram.KeyboardButton('drinks')],
                             [telegram.KeyboardButton('cancel create')]]
category_keyboard_markup = telegram.ReplyKeyboardMarkup(category_keyboard_buttons)

date_keyboard_buttons = [[telegram.KeyboardButton('Now (Or recent)')], [telegram.KeyboardButton('cancel create')]]
date_keyboard_markup = telegram.ReplyKeyboardMarkup(date_keyboard_buttons)

item_name_keyboard_buttons = [[telegram.KeyboardButton('None (Leave blank)')],
                              [telegram.KeyboardButton('cancel create')]]
item_name_keyboard_markup = telegram.ReplyKeyboardMarkup(item_name_keyboard_buttons)

purchase_type_keyboard_buttons = [[telegram.KeyboardButton('Impulse buy')],
                                  [telegram.KeyboardButton("""It's a need!""")],
                                  [telegram.KeyboardButton('Planned purchase')],
                                  [telegram.KeyboardButton('cancel create')]]
purchase_type_keyboard_markup = telegram.ReplyKeyboardMarkup(purchase_type_keyboard_buttons)

confirm_create_keyboard_buttons = [[telegram.KeyboardButton('confirm create')],
                                   [telegram.KeyboardButton('cancel create')]]
confirm_create_keyboard_markup = telegram.ReplyKeyboardMarkup(confirm_create_keyboard_buttons)


def main_command_handler(incoming_message, telebot_instance, redis_client, db):
    """Echo the user message."""
    chat_id = incoming_message.chat.id
    msg_id = incoming_message.message_id
    user = incoming_message.from_user
    username = user['username']

    text = incoming_message.text.encode('utf-8').decode()

    # check if current user has state
    if redis_client.get(user['username'] + "state") is not None:
        if text == "cancel delete" or text == "cancel create" or text == "back to home":
            redis_client.delete(user['username'] + "state")
            telebot_instance.sendMessage(chat_id=chat_id, text="What would you like to do",
                                         reply_to_message_id=msg_id, reply_markup=start_keyboard_markup)
            return

        # step 1 of creating an expense entry
        state = redis_client.get(user['username'] + "state").decode('utf-8')
        print("state:" + state)

        if state == "user_enter_amount":
            telebot_instance.sendMessage(chat_id=chat_id, text="When did you make this expense",
                                         reply_to_message_id=msg_id, reply_markup=date_keyboard_markup)
            current_data_string = json.dumps({'username': user['username'], 'amount': text})
            redis_client.set(user['username'], current_data_string)

            return "user_enter_date"

        elif state == "user_enter_date":
            telebot_instance.sendMessage(chat_id=chat_id, text="enter the category of your expense",
                                         reply_to_message_id=msg_id, reply_markup=category_keyboard_markup)
            this_entry_obj = json.loads(redis_client.get(user['username']))
            if text == "Now (Or recent)":
                dt_string = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                this_entry_obj['datetime'] = dt_string
            else:
                this_entry_obj['datetime'] = text
            redis_client.set(user['username'], json.dumps(this_entry_obj))

            return "user_enter_category"

        elif state == "user_enter_category":
            telebot_instance.sendMessage(chat_id=chat_id, text="What item/service did you purchase?",
                                         reply_to_message_id=msg_id, reply_markup=item_name_keyboard_markup)

            this_entry_obj = json.loads(redis_client.get(user['username']))
            this_entry_obj['category'] = text
            redis_client.set(user['username'], json.dumps(this_entry_obj))

            return "user_enter_name"

        elif state == "user_enter_name":
            telebot_instance.sendMessage(chat_id=chat_id, text="Classify your expense",
                                         reply_to_message_id=msg_id, reply_markup=purchase_type_keyboard_markup)

            this_entry_obj = json.loads(redis_client.get(user['username']))
            this_entry_obj['description'] = text
            redis_client.set(user['username'], json.dumps(this_entry_obj))

            return "user_enter_type"

        elif state == "user_enter_type":
            this_entry_obj = json.loads(redis_client.get(user['username']))
            this_entry_obj['type'] = text
            redis_client.set(user['username'], json.dumps(this_entry_obj))

            telebot_instance.sendMessage(chat_id=chat_id,
                                         text=f"Confirm you entry?\nAmount - {this_entry_obj['amount']}\nCategory - {this_entry_obj['category']}\nDescription - {this_entry_obj['description']}\nPurchase Type - {this_entry_obj['type']} (are you sure?)\nExpense Time - {this_entry_obj['datetime']}",
                                         reply_to_message_id=msg_id, reply_markup=confirm_create_keyboard_markup)
            return "user_finish_input"

        elif state == "user_finish_input":
            this_entry_obj = json.loads(redis_client.get(user['username']))

            db_entry = ExpenseEntry()
            db_entry.username = this_entry_obj['username']
            db_entry.amount = this_entry_obj['amount']
            db_entry.category = this_entry_obj['category']
            db_entry.datetime = this_entry_obj['datetime']
            db_entry.description = this_entry_obj['description']
            db_entry.type = this_entry_obj['type']
            db_entry.submit_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            try:
                db.session.add(db_entry)
                db.session.commit()
            except Exception as e:
                print(f"exception {e}")

            telebot_instance.sendMessage(chat_id=chat_id, text="Creation Success! Thank you for logging",
                                         reply_to_message_id=msg_id, reply_markup=start_keyboard_markup)

            redis_client.delete(user['username'] + "state")
            redis_client.delete(user['username'])
            return

        elif state == "user_enter_info_age":
            telebot_instance.sendMessage(chat_id=chat_id, text="Creation Success! Thank you for logging",
                                         reply_to_message_id=msg_id, reply_markup=info_input_keyboard_markup)
            return "user_enter_info_gender"

        elif state == "user_enter_info_gender":
            telebot_instance.sendMessage(chat_id=chat_id, text="Creation Success! Thank you for logging",
                                         reply_to_message_id=msg_id, reply_markup=info_input_keyboard_markup)
            return "user_enter_info_occupation"

        elif state == "user_enter_info_occupation":
            return

    # no state
    else:
        if text == "/start" or text == "cancel delete" or text == "cancel create" or text == "back to home":
            telebot_instance.sendMessage(chat_id=chat_id, text="What would you like to do",
                                         reply_to_message_id=msg_id, reply_markup=start_keyboard_markup)
        elif text == "create expense":
            telebot_instance.sendMessage(chat_id=chat_id,
                                         text="To create an entry, enter the amount you have spent (Use the buttons or enter yourself)",
                                         reply_to_message_id=msg_id, reply_markup=amount_keyboard_markup)
            return "user_enter_amount"
        elif text == "view my info":
            telebot_instance.sendMessage(chat_id=chat_id,
                                         text="Your details are ",
                                         reply_to_message_id=msg_id, reply_markup=info_keyboard_markup)
            return
        elif text == "enter my info":
            telebot_instance.sendMessage(chat_id=chat_id,
                                         text="You can view or edit your personal details",
                                         reply_to_message_id=msg_id, reply_markup=info_keyboard_markup)
            return "user_enter_info_age"
        elif text == "delete":
            telebot_instance.sendMessage(chat_id=chat_id, text="Delete the last entry?", reply_to_message_id=msg_id,
                                         reply_markup=delete_keyboard_markup)
        elif text == "my logs":
            telebot_instance.sendMessage(chat_id=chat_id,
                                         text=f"View your logs here {URL}view-data?username={username}",
                                         reply_to_message_id=msg_id,
                                         reply_markup=start_keyboard_markup)
        else:
            telebot_instance.sendMessage(chat_id=chat_id, text="Whatchu wanna do, use /start to open up the menu",
                                         reply_to_message_id=msg_id,
                                         reply_markup=start_keyboard_markup)

    try:
        info = "got text message: " + text + " from " + user.username
        print(info)
    except:
        print("no message is received")
    return
