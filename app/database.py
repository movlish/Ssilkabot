import sqlite3

# Создание таблицы пользователей, если она не существует
def create_table():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE
    )
    ''')
    conn.commit()
    conn.close()

# Добавление нового пользователя в базу данных
def add_user(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Пользователь уже существует в базе данных
    conn.close()

# Получение количества пользователей
def get_user_count():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    return count

# Вызов создания таблицы при импорте модуля
create_table()