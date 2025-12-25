import os

class Config:
    SECRET_KEY = 'ваш-ключ'
    
    # Используйте абсолютный путь
    DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'database.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
    
    # Или даже так (более надежно)
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 
        'instance', 
        'tool_tracker.db'
    ).replace('\\', '/')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SITE_URL = 'http://localhost:5001'