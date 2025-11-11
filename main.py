import hashlib
import sqlite3
from typing import Dict, Any, Optional

import telebot
from telebot import types


class TelegramBot:
    def __init__(self, token: str, db_path: str = "users.db") -> None:
        self.bot = telebot.TeleBot(token)
        self.db_path = db_path
        self.pending_registration = set()
        self._init_db()
        self._register_handlers()

    # === База данных ===

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    chat_id INTEGER PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    login INTEGER DEFAULT 0,
                    luxury_access INTEGER DEFAULT 0,
                    waiting_for_password INTEGER DEFAULT 0
                )
            ''')
            conn.commit()

    def _get_user(self, chat_id: int) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE chat_id = ?', (chat_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def _update_user(self, chat_id: int, **kwargs) -> None:
        user = self._get_user(chat_id)
        if not user:
            # Создаём нового
            columns = ', '.join(kwargs.keys())
            placeholders = ', '.join('?' for _ in kwargs)
            values = list(kwargs.values())
            values.insert(0, chat_id)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    INSERT INTO users (chat_id, {columns})
                    VALUES (?, {placeholders})
                ''', values)
                conn.commit()
        else:
            # Обновляем
            set_clause = ', '.join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values())
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    UPDATE users SET {set_clause} WHERE chat_id = ?
                ''', values + [chat_id])
                conn.commit()

    def _hash_password(self, password: str) -> str:
        """Хэширование пароля (SHA-512)."""
        return hashlib.sha512(password.encode()).hexdigest()

    # === Обработчики ===

    def _register_handlers(self) -> None:
        self.bot.message_handler(commands=['start'])(self.start_message)
        self.bot.message_handler(commands=['help'])(self.help_message)
        self.bot.message_handler(commands=['register'])(self.register)
        self.bot.message_handler(commands=['login'])(self.login)
        self.bot.message_handler(commands=['logout'])(self.logout)
        self.bot.message_handler(commands=['luxury'])(self.luxury_command)
        self.bot.message_handler(func=lambda m: True)(self.handle_text)

    # === Команды ===

    def start_message(self, message: types.Message) -> None:
        self.bot.send_message(
            message.chat.id,
            "Привет! Я бот СПО Созвездия\n"
            "Используйте /help для списка команд."
        )

    def help_message(self, message: types.Message) -> None:
        help_text = (
            "Доступные команды:\n\n"
            "/help — показать справку\n"
            "/register — регистрация\n"
            "/login — вход в систему\n"
            "/logout — выход\n"
            "/luxury — получить тяжёлый люкс (только для авторизованных)"
        )
        self.bot.send_message(message.chat.id, help_text)

    def register(self, message: types.Message) -> None:
        chat_id = message.chat.id
        if self._get_user(chat_id):
            self.bot.send_message(chat_id, "Вы уже зарегистрированы.")
            return

        # НЕ создаём запись в БД!
        # Только помечаем в памяти, что ждём пароль
        if not hasattr(self, 'pending_registration'):
            self.pending_registration = set()
        
        self.pending_registration.add(chat_id)
        
        self.bot.send_message(
            chat_id,
            "Введите пароль для регистрации:",
            reply_markup=types.ReplyKeyboardRemove()
        )

    def login(self, message: types.Message) -> None:
        chat_id = message.chat.id
        user = self._get_user(chat_id)

        if not user:
            self.bot.send_message(chat_id, "Сначала зарегистрируйтесь: /register")
            return
        if user['login']:
            self.bot.send_message(chat_id, "Вы уже вошли в систему.")
            return

        self._update_user(chat_id, waiting_for_password=1)
        self.bot.send_message(chat_id, "Введите пароль для входа:")

    def logout(self, message: types.Message) -> None:
        chat_id = message.chat.id
        user = self._get_user(chat_id)

        if user and user['login']:
            self._update_user(chat_id, login=0)
            self.bot.send_message(chat_id, "Выход из системы успешен.")
        else:
            self.bot.send_message(chat_id, "Вы не авторизованы.")
        
        # Убираем из временной регистрации, если был
        self.pending_registration.discard(chat_id)

    def luxury_command(self, message: types.Message) -> None:
        chat_id = message.chat.id
        user = self._get_user(chat_id)

        if not (user and user['login']):
            self.bot.send_message(chat_id, "Сначала войдите: /login")
            return

        # Даём доступ к "люксу"
        self._update_user(chat_id, luxury_access=1)
        self.bot.send_message(chat_id, "Тяжёлый люкс активирован!\nТеперь вы в элите.")

    # === Обработка текста ===

    def handle_text(self, message: types.Message) -> None:
        chat_id = message.chat.id
        user = self._get_user(chat_id)

        # === Регистрация (если начали, но ещё нет в БД) ===
        if chat_id in getattr(self, 'pending_registration', set()):
            password = message.text.strip()
            if not password:
                self.bot.send_message(chat_id, "Пароль не может быть пустым. Попробуйте снова.")
                return

            hashed = self._hash_password(password)
            # Теперь создаём пользователя в БД
            self._update_user(
                chat_id,
                password_hash=hashed,
                waiting_for_password=0,
                login=0
            )
            # Убираем из временного списка
            self.pending_registration.discard(chat_id)
            self.bot.send_message(chat_id, "Регистрация успешна! Войдите: /login")
            return

        # === Вход (если уже есть в БД и ждём пароль) ===
        if user and user['waiting_for_password']:
            password = message.text.strip()
            hashed = self._hash_password(password)

            if user['password_hash'] == hashed:
                self._update_user(chat_id, login=1, waiting_for_password=0)
                self.bot.send_message(chat_id, "Вход выполнен успешно!")
            else:
                self.bot.send_message(chat_id, "Неправильный пароль.")
            return

        # === Неизвестная команда ===
        self.bot.send_message(chat_id, "Неизвестная команда. /help — справка.")

    # === Запуск ===

    def run(self) -> None:
        """Запуск бота."""
        print("Бот СПО Созвездия запущен...")
        self.bot.infinity_polling()

if __name__ == "__main__":
    TOKEN = "8575715519:AAGk2Lk2yrGEjYvlvbm9X-Ia_AhOjgalzNw"

    bot = TelegramBot(token=TOKEN)
    bot.run()