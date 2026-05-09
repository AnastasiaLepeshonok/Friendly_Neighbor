import sqlite3
from datetime import datetime

def init_db():
    """Создает таблицы в базе данных, если их еще нет"""
    conn = sqlite3.connect('help_bot.db')
    cursor = conn.cursor()
    
    # Таблица для заявок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_name TEXT,
            request_type TEXT NOT NULL,
            description TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            address TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица для откликов на заявки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            responder_id INTEGER NOT NULL,
            responder_name TEXT,
            message TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES requests (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("База данных инициализирована")

def add_request(user_id, user_name, request_type, description, latitude=None, longitude=None, address=None):
    """Добавляет новую заявку в базу"""
    conn = sqlite3.connect('help_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO requests (user_id, user_name, request_type, description, latitude, longitude, address)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, user_name, request_type, description, latitude, longitude, address))
    
    conn.commit()
    request_id = cursor.lastrowid
    conn.close()
    
    return request_id

def update_request_location(request_id, latitude, longitude, address=None):
    """Обновляет координаты заявки"""
    conn = sqlite3.connect('help_bot.db')
    cursor = conn.cursor()
    
    if address:
        cursor.execute('''
            UPDATE requests SET latitude = ?, longitude = ?, address = ? WHERE id = ?
        ''', (latitude, longitude, address, request_id))
    else:
        cursor.execute('''
            UPDATE requests SET latitude = ?, longitude = ? WHERE id = ?
        ''', (latitude, longitude, request_id))
    
    conn.commit()
    conn.close()

def get_active_requests(request_type=None, limit=10):
    """Получает все активные заявки (можно отфильтровать по типу)"""
    conn = sqlite3.connect('help_bot.db')
    cursor = conn.cursor()
    
    if request_type:
        cursor.execute('''
            SELECT * FROM requests 
            WHERE status = 'active' AND request_type = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (request_type, limit))
    else:
        cursor.execute('''
            SELECT * FROM requests 
            WHERE status = 'active' 
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
    
    requests = cursor.fetchall()
    conn.close()
    
    return requests

def get_request_by_id(request_id):
    """Получает заявку по ID"""
    conn = sqlite3.connect('help_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM requests WHERE id = ?', (request_id,))
    request = cursor.fetchone()
    conn.close()
    
    return request

def get_user_requests(user_id):
    """Получает все заявки конкретного пользователя"""
    conn = sqlite3.connect('help_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM requests 
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (user_id,))
    
    requests = cursor.fetchall()
    conn.close()
    
    return requests

def close_request(request_id):
    """Закрывает заявку (помощь оказана)"""
    conn = sqlite3.connect('help_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE requests SET status = 'closed' WHERE id = ?
    ''', (request_id,))
    
    conn.commit()
    conn.close()

def add_response(request_id, responder_id, responder_name, message):
    """Добавляет отклик на заявку"""
    conn = sqlite3.connect('help_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO responses (request_id, responder_id, responder_name, message, status)
        VALUES (?, ?, ?, ?, 'pending')
    ''', (request_id, responder_id, responder_name, message))
    
    conn.commit()
    response_id = cursor.lastrowid
    conn.close()
    
    return response_id

def get_responses_for_request(request_id):
    """Получает все отклики на заявку"""
    conn = sqlite3.connect('help_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM responses 
        WHERE request_id = ? AND status = 'pending'
        ORDER BY created_at DESC
    ''', (request_id,))
    
    responses = cursor.fetchall()
    conn.close()
    
    return responses

def get_response_by_id(response_id):
    """Получает отклик по ID"""
    conn = sqlite3.connect('help_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM responses WHERE id = ?', (response_id,))
    response = cursor.fetchone()
    conn.close()
    
    return response

def accept_response(response_id):
    """Принимает отклик"""
    conn = sqlite3.connect('help_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE responses SET status = 'accepted' WHERE id = ?
    ''', (response_id,))
    
    conn.commit()
    conn.close()

def reject_response(response_id):
    """Отклоняет отклик"""
    conn = sqlite3.connect('help_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE responses SET status = 'rejected' WHERE id = ?
    ''', (response_id,))
    
    conn.commit()
    conn.close()

def delete_user_requests(user_id):
    """Удаляет все заявки пользователя"""
    conn = sqlite3.connect('help_bot.db')
    cursor = conn.cursor()
    
    # Удаляем все отклики на заявки пользователя
    cursor.execute('''
        DELETE FROM responses 
        WHERE request_id IN (SELECT id FROM requests WHERE user_id = ?)
    ''', (user_id,))
    
    # Удаляем все заявки пользователя
    cursor.execute('''
        DELETE FROM requests WHERE user_id = ?
    ''', (user_id,))
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    return deleted_count

def get_user_requests_count(user_id, status=None):
    """Получает количество заявок пользователя"""
    conn = sqlite3.connect('help_bot.db')
    cursor = conn.cursor()
    
    if status:
        cursor.execute('''
            SELECT COUNT(*) FROM requests WHERE user_id = ? AND status = ?
        ''', (user_id, status))
    else:
        cursor.execute('''
            SELECT COUNT(*) FROM requests WHERE user_id = ?
        ''', (user_id,))
    
    count = cursor.fetchone()[0]
    conn.close()
    
    return count
