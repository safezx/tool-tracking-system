from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import uuid

# Создаём объект SQLAlchemy
db = SQLAlchemy()

def generate_uuid():
    """Генерация уникального ID для QR-кода"""
    return str(uuid.uuid4())[:8].upper()  # Короткий 8-символьный код

class User(db.Model):
    """
    Модель пользователя (сотрудника)
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=True)
    employee_id = db.Column(db.String(20), unique=True, nullable=True)  # Табельный номер
    is_active = db.Column(db.Boolean, default=True, nullable=False)  # Может ли брать инструменты
    department = db.Column(db.String(100), nullable=True)  # Отдел
    phone = db.Column(db.String(20), nullable=True)  # Телефон
    position = db.Column(db.String(100), nullable=True)  # Должность
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь с заявками (один ко многим)
    requests = db.relationship('Request', backref='requester', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.first_name} {self.last_name}>'
    
    def full_name(self):
        """Полное имя пользователя"""
        return f'{self.first_name} {self.last_name}'

class Tool(db.Model):
    """
    Модель инструмента
    """
    __tablename__ = 'tools'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=True)  # Электроинструмент, ручной, измерительный и т.д.
    
    # Уникальный идентификатор для QR-кода
    qr_code_identifier = db.Column(db.String(20), unique=True, nullable=False, default=generate_uuid)
    
    # Место хранения
    location = db.Column(db.String(100), nullable=True)
    storage_place = db.Column(db.String(100), nullable=True)  # Полка, шкаф, ящик
    
    # Статус доступности
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    
    # Дополнительная информация
    serial_number = db.Column(db.String(50), unique=True, nullable=True)
    model = db.Column(db.String(100), nullable=True)  # Модель
    manufacturer = db.Column(db.String(100), nullable=True)  # Производитель
    purchase_date = db.Column(db.Date, nullable=True)
    price = db.Column(db.Float, nullable=True)
    warranty_until = db.Column(db.Date, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь с заявками (один ко многим)
    requests = db.relationship('Request', backref='requested_tool', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Tool {self.name} ({self.qr_code_identifier})>'
    
    @property
    def qr_code_url(self):
        """Генерирует URL для QR-кода"""
        from config import Config
        return f'{Config.SITE_URL}/tool/{self.qr_code_identifier}'

class Request(db.Model):
    """
    Модель заявки на взятие инструмента
    """
    __tablename__ = 'requests'
    
    # Статусы заявки
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_RETURNED = 'returned'
    STATUS_OVERDUE = 'overdue'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Внешние ключи
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tool_id = db.Column(db.Integer, db.ForeignKey('tools.id'), nullable=False)
    
    # Даты и время
    request_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # Когда создана заявка
    approval_time = db.Column(db.DateTime, nullable=True)  # Когда одобрена
    expected_return_time = db.Column(db.DateTime, nullable=True)  # Когда должен вернуть
    actual_return_time = db.Column(db.DateTime, nullable=True)  # Когда фактически вернул
    
    # Статус
    status = db.Column(db.String(20), default=STATUS_PENDING, nullable=False)
    
    # Дополнительная информация
    purpose = db.Column(db.Text, nullable=True)  # Для каких работ нужен инструмент
    admin_notes = db.Column(db.Text, nullable=True)  # Заметки администратора
    condition_before = db.Column(db.Text, nullable=True)  # Состояние до выдачи
    condition_after = db.Column(db.Text, nullable=True)  # Состояние после возврата
    
    def __repr__(self):
        return f'<Request {self.id}: {self.status}>'
    
    def approve(self):
        """Одобрить заявку"""
        self.status = self.STATUS_APPROVED
        self.approval_time = datetime.utcnow()
        if self.requested_tool:
            self.requested_tool.is_available = False
    
    def return_tool(self):
        """Вернуть инструмент"""
        self.status = self.STATUS_RETURNED
        self.actual_return_time = datetime.utcnow()
        if self.requested_tool:
            self.requested_tool.is_available = True
    
    def reject(self):
        """Отклонить заявку"""
        self.status = self.STATUS_REJECTED
    
    @property
    def user(self):
        """Свойство для удобного доступа к пользователю"""
        from database import User
        return User.query.get(self.user_id)
    
    @property
    def tool(self):
        """Свойство для удобного доступа к инструменту"""
        from database import Tool
        return Tool.query.get(self.tool_id)

def init_db(app):
    """Инициализация базы данных в контексте приложения"""
    db.init_app(app)
    
    with app.app_context():
        # Создаём все таблицы
        db.create_all()
        print("✅ База данных создана!")
        
        # Добавляем тестовые данные (только если база пустая)
        add_initial_data()

def add_initial_data():
    """Добавление начальных данных в базу"""
    from sqlalchemy.exc import IntegrityError
    from datetime import date, datetime, timedelta
    import pytz  # Добавьте в начале файла
    
    MOSCOW_TZ = pytz.timezone('Europe/Moscow')
    
    def moscow_now():
        return datetime.now(MOSCOW_TZ)
    
    try:
        # Проверяем, есть ли уже пользователи
        if User.query.count() == 0:
            # Добавляем тестовых пользователей
            users = [
                User(
                    first_name="Иван", 
                    last_name="Петров", 
                    email="ivan.petrov@company.com",
                    employee_id="EMP001",
                    department="Цех №1",
                    phone="+7 (123) 456-78-90",
                    position="Слесарь"
                ),
                User(
                    first_name="Мария", 
                    last_name="Сидорова", 
                    email="maria.sidorova@company.com",
                    employee_id="EMP002",
                    department="Офис",
                    phone="+7 (123) 456-78-91",
                    position="Инженер"
                ),
                User(
                    first_name="Алексей", 
                    last_name="Кузнецов", 
                    email="alex.kuznetsov@company.com",
                    employee_id="EMP003",
                    department="Склад",
                    phone="+7 (123) 456-78-92",
                    position="Кладовщик"
                ),
                User(
                    first_name="Ольга", 
                    last_name="Иванова", 
                    email="olga.ivanova@company.com",
                    employee_id="EMP004",
                    department="Лаборатория",
                    phone="+7 (123) 456-78-93",
                    position="Техник"
                ),
            ]
            
            for user in users:
                db.session.add(user)
            
            db.session.commit()
            print("✅ Добавлены тестовые пользователи")
        
        # Проверяем, есть ли уже инструменты
        if Tool.query.count() == 0:
            # Добавляем тестовые инструменты
            from datetime import date
            
            tools = [
                Tool(
                    name="Шуруповёрт DeWalt DCD791D2",
                    description="Аккумуляторный, 18V, 2 батареи, кейс",
                    category="Электроинструмент",
                    location="Склад инструментов",
                    storage_place="Шкаф А, полка 3",
                    serial_number="DWT-2023-001",
                    model="DCD791D2",
                    manufacturer="DeWalt",
                    purchase_date=date(2023, 5, 15),
                    price=18990.00,
                    warranty_until=date(2025, 5, 15),
                    is_available=True
                ),
                Tool(
                    name="Мультиметр Fluke 117",
                    description="Цифровой, с щупами, автоматический выбор диапазона",
                    category="Измерительный",
                    location="Лаборатория",
                    storage_place="Ящик №2",
                    serial_number="FLK-2022-045",
                    model="117",
                    manufacturer="Fluke",
                    purchase_date=date(2022, 10, 20),
                    price=12500.00,
                    warranty_until=date(2024, 10, 20),
                    is_available=True
                ),
                Tool(
                    name="Набор гаечных ключей",
                    description="Набор 12 предметов, 6-22мм, хром-ванадий",
                    category="Ручной инструмент",
                    location="Цех №1",
                    storage_place="Стол мастера, ящик",
                    serial_number="KIT-2023-012",
                    manufacturer="Stayer",
                    purchase_date=date(2023, 3, 10),
                    price=3200.00,
                    is_available=True
                ),
                Tool(
                    name="Дрель-перфоратор Bosch GBH 2-28",
                    description="Перфоратор, 800Вт, 3 режима, кейс",
                    category="Электроинструмент",
                    location="Склад инструментов",
                    storage_place="Шкаф Б, полка 1",
                    serial_number="BOS-2023-078",
                    model="GBH 2-28",
                    manufacturer="Bosch",
                    purchase_date=date(2023, 8, 5),
                    price=23450.00,
                    warranty_until=date(2025, 8, 5),
                    is_available=True
                ),
                Tool(
                    name="Паяльная станция Lukey 702",
                    description="Цифровая, 60W, регулировка температуры",
                    category="Электроинструмент",
                    location="Лаборатория",
                    storage_place="Стол №3",
                    serial_number="LUK-2022-123",
                    model="702",
                    manufacturer="Lukey",
                    purchase_date=date(2022, 12, 3),
                    price=8900.00,
                    warranty_until=date(2024, 12, 3),
                    is_available=True
                ),
            ]
            
            for tool in tools:
                db.session.add(tool)
            
            db.session.commit()
            print("✅ Добавлены тестовые инструменты")
            
            # Показываем QR-коды для тестовых инструментов
            tools = Tool.query.all()
            print("\n🔗 QR-ссылки для тестирования:")
            for tool in tools:
                print(f"   {tool.name}: {tool.qr_code_url}")
        
        # Проверяем, есть ли уже заявки
        if Request.query.count() == 0:
            # Добавляем тестовые заявки
            from datetime import datetime, timedelta
            
            user1 = User.query.filter_by(employee_id="EMP001").first()
            user2 = User.query.filter_by(employee_id="EMP002").first()
            tool1 = Tool.query.filter_by(serial_number="DWT-2023-001").first()
            tool2 = Tool.query.filter_by(serial_number="FLK-2022-045").first()
            
            if user1 and tool1:
                request1 = Request(
                    user_id=user1.id,
                    tool_id=tool1.id,
                    purpose="Для сборки металлоконструкций на участке №3",
                    status=Request.STATUS_APPROVED,
                    approval_time=datetime.utcnow() - timedelta(days=2),
                    expected_return_time=datetime.utcnow() + timedelta(days=5)
                )
                request1.tool.is_available = False
                db.session.add(request1)
            
            if user2 and tool2:
                request2 = Request(
                    user_id=user2.id,
                    tool_id=tool2.id,
                    purpose="Проверка напряжения в электрических щитах",
                    status=Request.STATUS_RETURNED,
                    approval_time=datetime.utcnow() - timedelta(days=7),
                    actual_return_time=datetime.utcnow() - timedelta(days=1),
                    condition_before="Идеальное",
                    condition_after="Незначительные царапины на корпусе"
                )
                db.session.add(request2)
            
            db.session.commit()
            print("✅ Добавлены тестовые заявки")
        
        # Проверяем, есть ли уже заявки
        if Request.query.count() == 0:
            # Добавляем тестовые заявки
            
            user1 = User.query.filter_by(employee_id="EMP001").first()
            user2 = User.query.filter_by(employee_id="EMP002").first()
            tool1 = Tool.query.filter_by(serial_number="DWT-2023-001").first()
            tool2 = Tool.query.filter_by(serial_number="FLK-2022-045").first()
            
            if user1 and tool1:
                request1 = Request(
                    user_id=user1.id,
                    tool_id=tool1.id,
                    purpose="Для сборки металлоконструкций на участке №3",
                    status=Request.STATUS_APPROVED,
                    approval_time=moscow_now() - timedelta(days=2),
                    expected_return_time=moscow_now() + timedelta(days=5)
                )
                request1.tool.is_available = False
                db.session.add(request1)
            
            if user2 and tool2:
                request2 = Request(
                    user_id=user2.id,
                    tool_id=tool2.id,
                    purpose="Проверка напряжения в электрических щитах",
                    status=Request.STATUS_RETURNED,
                    approval_time=moscow_now() - timedelta(days=7),
                    actual_return_time=moscow_now() - timedelta(days=1),
                    condition_before="Идеальное",
                    condition_after="Незначительные царапины на корпусе"
                )
                db.session.add(request2)
            
            db.session.commit()
            print("✅ Добавлены тестовые заявки")

    except IntegrityError as e:
        db.session.rollback()
        print(f"⚠️  Ошибка при добавлении тестовых данных: {e}")
    except Exception as e:
        db.session.rollback()
        print(f"⚠️  Неожиданная ошибка: {e}")
