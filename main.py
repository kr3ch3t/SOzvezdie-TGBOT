from typing import Dict, Any
import telebot
from telebot import types


class TelegramBot:
    def __init__(self, token: str) -> None:

        self.bot = telebot.TeleBot(token)
        self.users: Dict[int, Dict[str, Any]] = {}  # {chat_id: user_data}
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Регистрация всех обработчиков сообщений."""
        self.bot.message_handler(commands=['start'])(self.start_message)
        self.bot.message_handler(commands=['help'])(self.help_message)
        self.bot.message_handler(commands=['register'])(self.register)
        self.bot.message_handler(commands=['login'])(self.login)
        self.bot.message_handler(commands=['logout'])(self.logout)
        self.bot.message_handler(commands=['luxury'])(self.luxury_command)
        self.bot.message_handler(func=lambda m: True)(self.handle_text)

    # === Команды ===

    def start_message(self, message: types.Message) -> None:
        self.bot.send_message(message.chat.id, "Привет! Я бот СПО Созвездия")

    def help_message(self, message: types.Message) -> None:
        help_text = (
            "Команды:\n\n"
            "/help - справка\n"
            "/register - регистрация\n"
            "/login - вход в систему\n"
            "/logout - выход из системы\n"
            "/luxury - спец команда"
        )
        self.bot.send_message(message.chat.id, help_text)

    def register(self, message: types.Message) -> None:
        chat_id = message.chat.id
        if chat_id in self.users and self.users[chat_id].get('registered'):
            self.bot.send_message(chat_id, "Вы уже зарегистрированы.")
            return

        self.users[chat_id] = {
            'registered': False,
            'login': False,
            'predict': False,
            'waiting_for_password': True
        }
        self.bot.send_message(
            chat_id,
            "Введите пароль для регистрации:",
            reply_markup=types.ReplyKeyboardRemove()
        )

    def login(self, message: types.Message) -> None:
        chat_id = message.chat.id
        user = self.users.get(chat_id, {})

        if not user.get('registered'):
            self.bot.send_message(chat_id, "Вы не зарегистрированы. Используйте /register.")
            return
        if user.get('login'):
            self.bot.send_message(chat_id, "Вы уже вошли в систему.")
            return

        self.users[chat_id]['waiting_for_password'] = True
        self.bot.send_message(chat_id, "Введите пароль для входа:")

    def logout(self, message: types.Message) -> None:
        chat_id = message.chat.id
        user = self.users.get(chat_id, {})

        if user.get('login'):
            user['login'] = False
            self.bot.send_message(chat_id, "Выход из системы успешен.")
        else:
            self.bot.send_message(chat_id, "Вы не авторизованы.")

    def luxury_command(self, message: types.Message) -> None:
        chat_id = message.chat.id
        user = self.users.get(chat_id, {})

        if not (user.get('registered') and user.get('login')):
            self.bot.send_message(chat_id, "Сначала войдите: /login")
            return

        user['luxury'] = True
        self.bot.send_message(chat_id, "Получите тяжёлый люкс")

    # === Обработка текста ===

    def handle_text(self, message: types.Message) -> None:
        chat_id = message.chat.id
        user = self.users.get(chat_id, {})

        if user.get('waiting_for_password'):
            password = message.text.strip()

            if not user.get('registered'):
                # Регистрация
                user['password'] = password
                user['registered'] = True
                user['waiting_for_password'] = False
                self.bot.send_message(chat_id, "Регистрация успешна! Теперь войдите: /login")
            else:
                # Вход
                if user.get('password') == password:
                    user['login'] = True
                    user['waiting_for_password'] = False
                    self.bot.send_message(chat_id, "Вход выполнен успешно!")
                else:
                    self.bot.send_message(chat_id, "Неправильный пароль.")
        else:
            self.bot.send_message(
                chat_id,
                "Неизвестная команда. Используйте /help для справки."
            )

    # === Запуск бота ===

    def run(self) -> None:
        """Запуск бота в режиме polling."""
        print("Бот запущен...")
        self.bot.infinity_polling()


# === Запуск ===
if __name__ == "__main__":
    TOKEN = "8575715519:AAGk2Lk2yrGEjYvlvbm9X-Ia_AhOjgalzNw"

    bot = TelegramBot(token=TOKEN)
    bot.run()