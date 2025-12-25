from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from config import Config
from database import db, init_db, User, Tool, Request
from datetime import datetime, timedelta
import pytz  # Нужно установить: pip install pytz
import os
import sys

MOSCOW_TZ = pytz.timezone('Europe/Moscow')


app = Flask(__name__)
app.config.from_object(Config)

# Контекстный процессор - делает функции доступными во всех шаблонах
@app.context_processor
def utility_processor():
    return dict(
        format_moscow_time=format_moscow_time,
        get_moscow_time=get_moscow_time
    )

def get_moscow_time():
    """Получить текущее время в Московском часовом поясе"""
    return datetime.now(MOSCOW_TZ)

def convert_to_moscow(utc_dt):
    """Конвертировать UTC время в Московское время"""
    if not utc_dt:
        return None
    
    # Если время уже с таймзоной, конвертируем
    if utc_dt.tzinfo:
        return utc_dt.astimezone(MOSCOW_TZ)
    
    # Если время без таймзоны, считаем что это UTC
    utc_tz = pytz.utc
    return utc_tz.localize(utc_dt).astimezone(MOSCOW_TZ)

def format_time(dt, format_str='%d.%m.%Y %H:%M'):
    """Простое форматирование времени без конвертации"""
    if not dt:
        return "—"
    
    # Если это datetime объект
    if hasattr(dt, 'strftime'):
        return dt.strftime(format_str)
    # Если это строка или другой тип
    return str(dt)

def format_moscow_time(dt, format_str='%d.%m.%Y %H:%M'):
    """Устаревшая функция, используйте format_time"""
    return format_time(dt, format_str)

# ====== СОЗДАЁМ ПАПКИ ======
base_dir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(base_dir, 'instance')
templates_dir = os.path.join(base_dir, 'templates')

if not os.path.exists(instance_dir):
    os.makedirs(instance_dir, exist_ok=True)
    print(f"✅ Создана папка: {instance_dir}")

if not os.path.exists(templates_dir):
    os.makedirs(templates_dir, exist_ok=True)
    print(f"✅ Создана папка: {templates_dir}")
# ===========================

app = Flask(__name__)
app.config.from_object(Config)

# Инициализируем базу данных
try:
    init_db(app)
    print("✅ База данных инициализирована")
except Exception as e:
    print(f"❌ Ошибка при инициализации БД: {e}")
    print("Проверьте права доступа к папке instance")
    sys.exit(1)

@app.route('/')
def home():
    """Главная страница"""
    # Статистика для главной страницы (внутри контекста запроса)
    stats = {
        'total_tools': Tool.query.count(),
        'available_tools': Tool.query.filter_by(is_available=True).count(),
        'total_users': User.query.filter_by(is_active=True).count(),
        'active_requests': Request.query.filter_by(status=Request.STATUS_APPROVED).count(),
    }
    
    return render_template('index.html', stats=stats)

@app.route('/test')
def test():
    """Тестовая страница"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Тест системы</title>
        <style>
            body { font-family: Arial; text-align: center; padding: 50px; }
            .success { color: green; font-size: 2em; }
            .links { margin-top: 30px; }
            .links a { display: block; margin: 10px; padding: 15px; 
                      background: #4CAF50; color: white; text-decoration: none;
                      border-radius: 5px; max-width: 300px; margin: 10px auto; }
        </style>
    </head>
    <body>
        <div class="success">✅ Система работает!</div>
        <p>База данных подключена успешно.</p>
        
        <div class="links">
            <a href="/admin/">📊 Статистика</a>
            <a href="/admin/tools">🛠️ Управление инструментами</a>
            <a href="/admin/users">👥 Управление пользователями</a>
            <a href="/tool/TEST001">🔗 Тест: взять инструмент</a>
        </div>
        
        <div style="margin-top: 30px; padding: 20px; background: #f5f5f5; border-radius: 10px;">
            <h3>📊 Статистика:</h3>
            <p>Пользователей: """ + str(User.query.count()) + """</p>
            <p>Инструментов: """ + str(Tool.query.count()) + """</p>
            <p>Заявок: """ + str(Request.query.count()) + """</p>
        </div>
    </body>
    </html>
    """

@app.route('/tool/<qr_code>')
def take_tool(qr_code):
    """Страница для взятия и возврата инструмента"""
    tool = Tool.query.filter_by(qr_code_identifier=qr_code).first()
    
    if not tool:
        return render_template('error.html', 
                             error_message=f"Инструмент с QR-кодом '{qr_code}' не найден"), 404
    
    # Находим активную заявку для этого инструмента
    active_request = None
    if not tool.is_available:
        active_request = Request.query.filter_by(
            tool_id=tool.id, 
            status=Request.STATUS_APPROVED
        ).first()
    
    return render_template('take_tool.html', 
                         tool=tool,
                         active_request=active_request,
                         format_moscow_time=format_moscow_time)

@app.route('/api/check-user', methods=['POST'])
def check_user():
    """Проверяем, есть ли пользователь в базе"""
    data = request.json
    
    if not data:
        return jsonify({'success': False, 'message': 'Нет данных'}), 400
    
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    employee_id = data.get('employee_id', '').strip()
    
    if not (first_name and last_name):
        return jsonify({'success': False, 'message': 'Заполните имя и фамилию'}), 400
    
    # Ищем пользователя
    query = User.query.filter(
        User.first_name.ilike(first_name),
        User.last_name.ilike(last_name)
    )
    
    if employee_id:
        query = query.filter(User.employee_id.ilike(employee_id))
    
    user = query.first()
    
    if not user:
        # В тестовом режиме создаём пользователя
        new_user = User(
            first_name=first_name,
            last_name=last_name,
            employee_id=employee_id or None,
            department="Автоматически добавлен",
            is_active=True
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            user = new_user
        except:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': 'Пользователь не найден'
            }), 404
    
    if not user.is_active:
        return jsonify({
            'success': False,
            'message': 'Пользователь не активен'
        }), 403
    
    return jsonify({
        'success': True,
        'user': {
            'id': user.id,
            'full_name': user.full_name(),
            'department': user.department,
            'employee_id': user.employee_id
        }
    })

@app.route('/api/create-request', methods=['POST'])
def create_request():
    """Создаём заявку на инструмент"""
    data = request.json
    
    if not data:
        return jsonify({'success': False, 'message': 'Нет данных'}), 400
    
    user_id = data.get('user_id')
    tool_id = data.get('tool_id')
    purpose = data.get('purpose', '')
    
    user = User.query.get(user_id)
    tool = Tool.query.get(tool_id)
    
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404
    
    if not tool:
        return jsonify({'success': False, 'message': 'Инструмент не найден'}), 404
    
    if not tool.is_available:
        return jsonify({'success': False, 'message': 'Инструмент уже занят'}), 400
    
    # Используем Московское время
    moscow_now = get_moscow_time()
    
    # Создаём заявку
    new_request = Request(
        user_id=user.id,
        tool_id=tool.id,
        purpose=purpose,
        status=Request.STATUS_APPROVED,
        approval_time=moscow_now,
        expected_return_time=moscow_now + timedelta(days=7)
    )
    
    # Меняем статус инструмента
    tool.is_available = False
    
    try:
        db.session.add(new_request)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'✅ Инструмент "{tool.name}" выдан {user.full_name()}',
            'request_id': new_request.id,
            'timestamp': moscow_now.strftime('%d.%m.%Y %H:%M:%S')
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка при создании заявки: {str(e)}'
        }), 500

@app.route('/admin/')
def admin_dashboard():
    """Страница статистики и управления"""
    # Получаем все заявки
    requests = Request.query.order_by(Request.request_time.desc()).limit(50).all()
    
    # Статистика
    stats = {
        'total_requests': Request.query.count(),
        'active_requests': Request.query.filter_by(status=Request.STATUS_APPROVED).count(),
        'total_tools': Tool.query.count(),
        'available_tools': Tool.query.filter_by(is_available=True).count(),
        'total_users': User.query.filter_by(is_active=True).count(),
        'inactive_users': User.query.filter_by(is_active=False).count(),
    }
    
    # Простой HTML для админки
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>📊 Статистика системы</title>
        <style>
            body {{ font-family: Arial; margin: 20px; }}
            h1 {{ color: #333; }}
            .header-links {{ margin-bottom: 20px; }}
            .header-links a {{ 
                display: inline-block; margin-right: 10px; padding: 8px 15px;
                background: #4CAF50; color: white; text-decoration: none;
                border-radius: 5px; font-weight: bold;
            }}
            .dashboard-menu {{ 
                display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px; margin: 30px 0;
            }}
            .dashboard-menu a {{ 
                display: block; padding: 25px; background: #4CAF50; 
                color: white; text-decoration: none; border-radius: 8px;
                text-align: center; font-weight: bold; font-size: 16px;
                transition: all 0.3s;
            }}
            .dashboard-menu a:hover {{ 
                background: #45a049; transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }}
            .stats {{ display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap; }}
            .stat-card {{ 
                background: white; padding: 20px; border-radius: 8px; 
                box-shadow: 0 2px 5px rgba(0,0,0,0.1); min-width: 150px;
            }}
            .stat-value {{ font-size: 2em; font-weight: bold; color: #4CAF50; margin: 10px 0; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #4CAF50; color: white; }}
            .btn {{ 
                padding: 5px 10px; background-color: #4CAF50; color: white; 
                border: none; border-radius: 4px; cursor: pointer;
            }}
            .time-cell {{ font-family: monospace; font-size: 0.9em; }}
            .section {{ 
                background: white; padding: 20px; border-radius: 8px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 30px;
            }}
            .section h2 {{ margin-top: 0; color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        </style>
    </head>
    <body>
        <h1>📊 Статистика системы</h1>
        
        <div class="header-links">
            <a href="/">🏠 Главная</a>
        </div>
        
        <div class="dashboard-menu">
            <a href="/admin/tools">🛠️ Управление инструментами</a>
            <a href="/admin/users">👥 Управление пользователями</a>
            <a href="/admin/qr-codes">🔗 Все QR-коды</a>
        </div>
        
        <div class="section">
            <h2>📈 Общая статистика</h2>
            <div class="stats">
    """
    
    for key, value in stats.items():
        # Преобразуем название для отображения
        display_name = key.replace('_', ' ').title()
        if 'requests' in key:
            display_name = display_name.replace('Requests', 'Заявок')
        elif 'tools' in key:
            display_name = display_name.replace('Tools', 'Инструментов')
        elif 'users' in key:
            display_name = display_name.replace('Users', 'Пользователей')
        elif 'active' in key:
            display_name = display_name.replace('Active', 'Активных')
        elif 'inactive' in key:
            display_name = display_name.replace('Inactive', 'Неактивных')
        elif 'available' in key:
            display_name = display_name.replace('Available', 'Доступно')
        elif 'total' in key:
            display_name = display_name.replace('Total', 'Всего')
        
        html += f"""
                <div class="stat-card">
                    <h3>{display_name}</h3>
                    <div class="stat-value">{value}</div>
                </div>
        """
    
    html += """
            </div>
        </div>
        
        <div class="section">
            <h2>📋 Последние заявки</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Пользователь</th>
                    <th>Инструмент</th>
                    <th>Время получения</th>
                    <th>Время возврата</th>
                    <th>Статус</th>
                    <th>Действия</th>
                </tr>
    """
    
    for req in requests:
        user = User.query.get(req.user_id)
        tool = Tool.query.get(req.tool_id)
        
        if user and tool:
            # Форматируем время в Московском часовом поясе
            approval_time_formatted = format_time(req.approval_time)
            actual_return_time_formatted = format_time(req.actual_return_time)
            
            html += f"""
            <tr>
                <td>{req.id}</td>
                <td>{user.full_name()}</td>
                <td>{tool.name}</td>
                <td class="time-cell">{approval_time_formatted}</td>
                <td class="time-cell">{actual_return_time_formatted}</td>
                <td>{req.status}</td>
                <td>
                    { '<button class="btn" onclick="returnTool(' + str(req.id) + ')">Вернуть</button>' if req.status == Request.STATUS_APPROVED else '-' }
                </td>
            </tr>
            """
    
    html += """
            </table>
        </div>
        
        <div class="section">
            <h2>🛠️ Последние добавленные инструменты</h2>
            <table>
                <tr>
                    <th>Название</th>
                    <th>QR-код</th>
                    <th>Статус</th>
                    <th>Ссылка</th>
                </tr>
    """
    
    tools = Tool.query.order_by(Tool.id.desc()).limit(10).all()
    for tool in tools:
        html += f"""
            <tr>
                <td>{tool.name}</td>
                <td>{tool.qr_code_identifier}</td>
                <td>{'✅ Доступен' if tool.is_available else '❌ Занят'}</td>
                <td><a href="/tool/{tool.qr_code_identifier}">Взять</a></td>
            </tr>
        """
    
    html += """
            </table>
        </div>
        
        <script>
            async function returnTool(requestId) {
                if (!confirm('Отметить как возвращённый?')) return;
                
                const response = await fetch('/admin/return/' + requestId, {
                    method: 'POST'
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert(data.message);
                    location.reload();
                } else {
                    alert('Ошибка: ' + data.message);
                }
            }
        </script>
    </body>
    </html>
    """
    
    return html

@app.route('/admin/return/<int:request_id>', methods=['POST'])
def return_tool(request_id):
    """Отметить инструмент как возвращённый"""
    request_obj = Request.query.get_or_404(request_id)
    
    if request_obj.status != Request.STATUS_APPROVED:
        return jsonify({
            'success': False,
            'message': f'Заявка #{request_id} уже не активна'
        }), 400
    
    # Используем Московское время для возврата
    request_obj.return_tool()
    request_obj.actual_return_time = get_moscow_time()
    
    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'✅ Инструмент возвращён'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500

def get_stats():
    """Получаем статистику внутри контекста приложения"""
    with app.app_context():
        return {
            'users': User.query.count(),
            'tools': Tool.query.count(),
            'requests': Request.query.count()
        }
    

@app.route('/admin/qr-codes')
def qr_codes():
    print("📋 Запрос к /admin/qr-codes")
    print(f"📁 Шаблон существует: {os.path.exists('templates/qr_codes.html')}")
    """Страница со всеми QR-кодами инструментов"""
    # Группируем инструменты по категориям
    all_tools = Tool.query.all()
    
    tools_by_category = {}
    for tool in all_tools:
        category = tool.category or "Без категории"
        if category not in tools_by_category:
            tools_by_category[category] = []
        tools_by_category[category].append(tool)
    
    return render_template('qr_codes.html', 
                         tools_by_category=tools_by_category,
                         Tool=Tool,
                         format_moscow_time=format_moscow_time,  # Передаем явно
                         get_moscow_time=get_moscow_time)  # Передаем явно




@app.route('/admin/tools')
def admin_tools():
    print("📋 Запрос к /admin/tools")
    print(f"📁 Шаблон admin_tools.html существует: {os.path.exists('templates/admin_tools.html')}")
    """Страница управления инструментами"""
    # Получаем все инструменты
    tools = Tool.query.order_by(Tool.id.desc()).all()
    
    # Для каждого инструмента получаем активную заявку
    for tool in tools:
        # Находим активную заявку (статус approved)
        active_request = Request.query.filter_by(
            tool_id=tool.id, 
            status=Request.STATUS_APPROVED
        ).first()
        # Добавляем в объект инструмента для использования в шаблоне
        tool.active_request = active_request
    
    # Получаем уникальные категории
    categories = sorted(set([tool.category for tool in tools if tool.category]))
    
    # Статистика
    stats = {
        'total': Tool.query.count(),
        'available': Tool.query.filter_by(is_available=True).count(),
        'taken': Tool.query.filter_by(is_available=False).count(),
        'by_category': {}
    }
    
    # Статистика по категориям
    for category in categories:
        total_in_category = Tool.query.filter_by(category=category).count()
        available_in_category = Tool.query.filter_by(category=category, is_available=True).count()
        
        stats['by_category'][category] = {
            'total': total_in_category,
            'available': available_in_category
        }
    
    return render_template('admin_tools.html', 
                         tools=tools,
                         categories=categories,
                         stats=stats,
                         format_moscow_time=format_moscow_time,  # Передаем явно
                         get_moscow_time=get_moscow_time)  # Передаем явно

@app.route('/admin/tools/delete/<int:tool_id>', methods=['POST'])
def delete_tool(tool_id):
    """Удаление инструмента"""
    tool = Tool.query.get_or_404(tool_id)
    
    # Проверяем, не выдан ли инструмент
    active_requests = Request.query.filter_by(
        tool_id=tool_id, 
        status=Request.STATUS_APPROVED
    ).count()
    
    if active_requests > 0:
        return jsonify({
            'success': False,
            'message': f'Нельзя удалить инструмент "{tool.name}" - он сейчас выдан пользователю'
        }), 400
    
    try:
        # Удаляем связанные заявки
        Request.query.filter_by(tool_id=tool_id).delete()
        
        # Удаляем сам инструмент
        db.session.delete(tool)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Инструмент "{tool.name}" успешно удалён'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка при удалении: {str(e)}'
        }), 500
    
@app.route('/admin/tools/edit/<int:tool_id>', methods=['GET', 'POST'])
def edit_tool(tool_id):
    """Редактирование инструмента"""
    tool = Tool.query.get_or_404(tool_id)
    
    if request.method == 'GET':
        return render_template('edit_tool.html', tool=tool)
    
    # Обработка POST запроса (обновление инструмента)
    try:
        # Получаем данные из формы
        tool.name = request.form.get('name', '').strip()
        tool.description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        custom_category = request.form.get('custom_category', '').strip()
        
        # Обработка категории (как в add_tool)
        if category == 'custom' and custom_category:
            tool.category = custom_category
        elif category == 'custom':
            tool.category = 'Прочее'
        else:
            tool.category = category
        
        tool.location = request.form.get('location', '').strip()
        tool.storage_place = request.form.get('storage_place', '').strip()
        tool.serial_number = request.form.get('serial_number', '').strip()
        tool.model = request.form.get('model', '').strip()
        tool.manufacturer = request.form.get('manufacturer', '').strip()
        
        # Обработка цены
        price = request.form.get('price')
        if price:
            try:
                tool.price = float(price)
            except ValueError:
                tool.price = None
        else:
            tool.price = None
        
        # Обработка дат
        purchase_date_str = request.form.get('purchase_date')
        if purchase_date_str:
            try:
                tool.purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date()
            except ValueError:
                tool.purchase_date = None
        else:
            tool.purchase_date = None
        
        warranty_until_str = request.form.get('warranty_until')
        if warranty_until_str:
            try:
                tool.warranty_until = datetime.strptime(warranty_until_str, '%Y-%m-%d').date()
            except ValueError:
                tool.warranty_until = None
        else:
            tool.warranty_until = None
        
        # Сохраняем изменения
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Инструмент "{tool.name}" успешно обновлен'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка при обновлении инструмента: {str(e)}'
        }), 500

@app.route('/admin/add-tool', methods=['GET', 'POST'])
def add_tool():
    """Добавление нового инструмента"""
    if request.method == 'GET':
        return render_template('add_tool.html')
    
    # Обработка POST запроса (добавление инструмента)
    try:
        # Получаем данные из формы
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        location = request.form.get('location', '').strip()
        storage_place = request.form.get('storage_place', '').strip()
        serial_number = request.form.get('serial_number', '').strip()
        model = request.form.get('model', '').strip()
        manufacturer = request.form.get('manufacturer', '').strip()
        price = request.form.get('price')
        purchase_date_str = request.form.get('purchase_date')
        warranty_until_str = request.form.get('warranty_until')
        
        category = request.form.get('category', '').strip()
        custom_category = request.form.get('custom_category', '').strip()

        # Если выбрана опция "другая категория" и введена новая категория
        if category == 'custom' and custom_category:
            category = custom_category
        elif category == 'custom':
            category = 'Прочее'  # Значение по умолчанию

        # Проверяем обязательные поля
        if not name:
            return jsonify({
                'success': False,
                'message': 'Название инструмента обязательно для заполнения'
            }), 400
        
        # Преобразуем цену
        price_float = None
        if price:
            try:
                price_float = float(price)
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Некорректное значение цены'
                }), 400
        
        # Преобразуем даты
        purchase_date = None
        if purchase_date_str:
            try:
                purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Некорректный формат даты приобретения'
                }), 400
        
        warranty_until = None
        if warranty_until_str:
            try:
                warranty_until = datetime.strptime(warranty_until_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Некорректный формат даты гарантии'
                }), 400
        
        # Создаем новый инструмент
        new_tool = Tool(
            name=name,
            description=description or None,
            category=category or None,
            location=location or None,
            storage_place=storage_place or None,
            serial_number=serial_number or None,
            model=model or None,
            manufacturer=manufacturer or None,
            price=price_float,
            purchase_date=purchase_date,
            warranty_until=warranty_until,
            is_available=True
        )
        
        # Сохраняем в базу данных
        db.session.add(new_tool)
        db.session.commit()
        
        # Получаем сгенерированный QR-код
        qr_code = new_tool.qr_code_identifier
        tool_url = f"{request.host_url}tool/{qr_code}"
        
        return jsonify({
            'success': True,
            'message': f'Инструмент "{name}" успешно добавлен',
            'tool_id': new_tool.id,
            'qr_code': qr_code,
            'tool_url': tool_url
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка при добавлении инструмента: {str(e)}'
        }), 500

@app.route('/admin/users')
def admin_users():
    """Страница управления пользователями"""
    # Получаем всех пользователей
    users = User.query.order_by(User.id.desc()).all()
    
    # Получаем уникальные отделы
    departments = sorted(set([user.department for user in users if user.department]))
    
    # Статистика
    stats = {
        'total': User.query.count(),
        'active': User.query.filter_by(is_active=True).count(),
        'inactive': User.query.filter_by(is_active=False).count()
    }
    
    return render_template('admin_users.html', 
                         users=users,
                         departments=departments,
                         stats=stats)


@app.route('/admin/users/toggle-status/<int:user_id>', methods=['POST'])
def toggle_user_status(user_id):
    """Переключение статуса пользователя (активен/неактивен)"""
    user = User.query.get_or_404(user_id)
    
    # Переключаем статус
    user.is_active = not user.is_active
    user.updated_at = datetime.utcnow()
    
    try:
        db.session.commit()
        
        status_text = "активирован" if user.is_active else "деактивирован"
        return jsonify({
            'success': True,
            'message': f'Пользователь {user.full_name()} {status_text}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка при изменении статуса: {str(e)}'
        }), 500

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    """Удаление пользователя"""
    user = User.query.get_or_404(user_id)
    user_name = user.full_name()
    
    try:
        # Удаляем пользователя (заявки удалятся каскадно благодаря cascade='all, delete-orphan')
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Пользователь {user_name} успешно удалён'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка при удалении пользователя: {str(e)}'
        }), 500

@app.route('/admin/add-user', methods=['GET', 'POST'])
def add_user():
    """Добавление нового пользователя"""
    if request.method == 'GET':
        return render_template('add_user.html')
    
    # Обработка POST запроса
    try:
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        employee_id = request.form.get('employee_id', '').strip()
        department = request.form.get('department', '').strip()
        phone = request.form.get('phone', '').strip()
        position = request.form.get('position', '').strip()
        
        # Проверяем обязательные поля
        if not (first_name and last_name):
            return jsonify({
                'success': False,
                'message': 'Имя и фамилия обязательны для заполнения'
            }), 400
        
        # Проверяем уникальность email, если указан
        if email:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                return jsonify({
                    'success': False,
                    'message': 'Пользователь с таким email уже существует'
                }), 400
        
        # Проверяем уникальность табельного номера, если указан
        if employee_id:
            existing_user = User.query.filter_by(employee_id=employee_id).first()
            if existing_user:
                return jsonify({
                    'success': False,
                    'message': 'Пользователь с таким табельным номером уже существует'
                }), 400
        
        # Создаем нового пользователя
        new_user = User(
            first_name=first_name,
            last_name=last_name,
            email=email or None,
            employee_id=employee_id or None,
            department=department or None,
            phone=phone or None,
            position=position or None,
            is_active=True
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Пользователь {first_name} {last_name} успешно добавлен',
            'user_id': new_user.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка при добавлении пользователя: {str(e)}'
        }), 500


@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    """Редактирование пользователя"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'GET':
        return render_template('edit_user.html', user=user)
    
    # Обработка POST запроса (обновление пользователя)
    try:
        # Получаем данные из формы
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        employee_id = request.form.get('employee_id', '').strip()
        department = request.form.get('department', '').strip()
        phone = request.form.get('phone', '').strip()
        position = request.form.get('position', '').strip()
        is_active = request.form.get('is_active') == '1'
        
        # Проверяем обязательные поля
        if not (first_name and last_name):
            return jsonify({
                'success': False,
                'message': 'Имя и фамилия обязательны для заполнения'
            }), 400
        
        # Проверяем уникальность email, если он изменился
        if email and email != user.email:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                return jsonify({
                    'success': False,
                    'message': 'Пользователь с таким email уже существует'
                }), 400
        
        # Проверяем уникальность табельного номера, если он изменился
        if employee_id and employee_id != user.employee_id:
            existing_user = User.query.filter_by(employee_id=employee_id).first()
            if existing_user:
                return jsonify({
                    'success': False,
                    'message': 'Пользователь с таким табельным номером уже существует'
                }), 400
        
        # Обновляем данные пользователя
        user.first_name = first_name
        user.last_name = last_name
        user.email = email or None
        user.employee_id = employee_id or None
        user.department = department or None
        user.phone = phone or None
        user.position = position or None
        user.is_active = is_active
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Пользователь {user.full_name()} успешно обновлен'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка при обновлении пользователя: {str(e)}'
        }), 500

@app.route('/api/verify-return', methods=['POST'])
def verify_return():
    """Проверяем, может ли пользователь вернуть инструмент"""
    data = request.json
    
    if not data:
        return jsonify({'success': False, 'message': 'Нет данных'}), 400
    
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    employee_id = data.get('employee_id', '').strip()
    tool_id = data.get('tool_id')
    
    if not (first_name and last_name and tool_id):
        return jsonify({'success': False, 'message': 'Не все обязательные поля заполнены'}), 400
    
    # Ищем активную заявку на этот инструмент
    active_request = Request.query.filter_by(
        tool_id=tool_id,
        status=Request.STATUS_APPROVED
    ).first()
    
    if not active_request:
        return jsonify({'success': False, 'message': 'Нет активной заявки на этот инструмент'}), 404
    
    # Получаем пользователя из заявки
    user = User.query.get(active_request.user_id)
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404
    
    # Проверяем совпадение данных
    if (user.first_name.lower() != first_name.lower() or 
        user.last_name.lower() != last_name.lower()):
        return jsonify({
            'success': False, 
            'message': 'Данные не совпадают с пользователем, взявшим инструмент'
        }), 403
    
    # Проверяем табельный номер, если он был указан при взятии
    if employee_id and user.employee_id:
        if user.employee_id.lower() != employee_id.lower():
            return jsonify({
                'success': False, 
                'message': 'Табельный номер не совпадает'
            }), 403
    
    return jsonify({
        'success': True,
        'message': 'Проверка пройдена успешно',
        'request_id': active_request.id,
        'user': {
            'id': user.id,
            'full_name': user.full_name(),
            'employee_id': user.employee_id
        }
    })


@app.route('/api/return-tool', methods=['POST'])
def api_return_tool():
    """API для возврата инструмента пользователем"""
    data = request.json
    
    if not data:
        return jsonify({'success': False, 'message': 'Нет данных'}), 400
    
    request_id = data.get('request_id')
    condition_after = data.get('condition_after', '').strip()
    notes = data.get('notes', '').strip()
    
    if not request_id:
        return jsonify({'success': False, 'message': 'ID заявки не указан'}), 400
    
    request_obj = Request.query.get(request_id)
    if not request_obj:
        return jsonify({'success': False, 'message': 'Заявка не найдена'}), 404
    
    if request_obj.status != Request.STATUS_APPROVED:
        return jsonify({
            'success': False,
            'message': f'Заявка #{request_id} уже не активна'
        }), 400
    
    # Возвращаем инструмент
    try:
        request_obj.return_tool()
        request_obj.actual_return_time = get_moscow_time()
        
        if condition_after:
            request_obj.condition_after = condition_after
        
        if notes:
            request_obj.admin_notes = notes
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'✅ Инструмент "{request_obj.tool.name}" возвращен',
            'timestamp': datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка при возврате инструмента: {str(e)}'
        }), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 СИСТЕМА УЧЁТА ИНСТРУМЕНТОВ")
    print("="*60)
    print(f"📍 URL: http://localhost:5001")
    
    # Получаем статистику внутри контекста
    with app.app_context():
        stats = get_stats()
        print(f"📊 Пользователей: {stats['users']}")
        print(f"🛠️  Инструментов: {stats['tools']}")
        print(f"📋 Заявок: {stats['requests']}")
    
    print("="*60)
    print("✅ Система готова к работе!")
    print("="*60)
    
    app.run(debug=True, host='0.0.0.0', port=5001)