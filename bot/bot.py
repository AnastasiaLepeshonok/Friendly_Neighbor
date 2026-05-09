import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id

import database

# Инициализируем базу данных при старте
database.init_db()

# Словарь для хранения временных данных пользователей
user_states = {}

def create_main_keyboard():
    """Создает главную клавиатуру с кнопками"""
    keyboard = VkKeyboard(one_time=False)
    
    keyboard.add_button('🆘 Нужна помощь', color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button('💚 Могу помочь', color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button('🎉 Событие', color=VkKeyboardColor.PRIMARY)
    keyboard.add_button('👀 Смотреть заявки', color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button('📋 Мои заявки', color=VkKeyboardColor.SECONDARY)
    keyboard.add_button('🗑️ Удалить мои заявки', color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button('❓ Помощь', color=VkKeyboardColor.SECONDARY)
    
    return keyboard

def create_requests_view_keyboard():
    """Клавиатура для просмотра заявок"""
    keyboard = VkKeyboard(one_time=False)
    
    keyboard.add_button('🆘 Нужна помощь', color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button('💚 Могу помочь', color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button('🎉 Событие', color=VkKeyboardColor.PRIMARY)
    keyboard.add_button('🔍 Все заявки', color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button('🔙 Назад', color=VkKeyboardColor.SECONDARY)
    
    return keyboard

def create_location_keyboard():
    """Создает клавиатуру с кнопкой для отправки геолокации"""
    keyboard = VkKeyboard(one_time=True)
    
    # Специальная кнопка для геолокации
    keyboard.add_location_button()
    keyboard.add_line()
    keyboard.add_button('✏️ Ввести адрес', color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button('🔙 Отмена', color=VkKeyboardColor.SECONDARY)
    
    return keyboard

def create_confirm_keyboard():
    """Создает клавиатуру для подтверждения удаления"""
    keyboard = VkKeyboard(one_time=True)
    
    keyboard.add_button('✅ Да, удалить все', color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button('🔙 Нет, отмена', color=VkKeyboardColor.SECONDARY)
    
    return keyboard

def send_message(vk, user_id, message, keyboard=None):
    """Отправляет сообщение пользователю"""
    params = {
        'user_id': user_id,
        'message': message,
        'random_id': get_random_id()
    }
    if keyboard:
        params['keyboard'] = keyboard.get_keyboard()
    vk.messages.send(**params)

def format_request_text(request, show_controls=False):
    """Форматирует заявку для отображения"""
    req_id, user_id, user_name, req_type, description, lat, lon, address, status, created_at = request
    
    # Определяем эмодзи для типа заявки
    type_emoji = {
        'help_needed': '🆘',
        'help_offer': '💚',
        'event': '🎉'
    }.get(req_type, '📌')
    
    # Определяем статус
    status_text = "✅ Активна" if status == 'active' else "❌ Выполнена"
    
    # Форматируем дату
    date_str = created_at[:16] if created_at else "неизвестно"
    
    text = f"{type_emoji} **Заявка №{req_id}**\n"
    text += f"👤 От: {user_name}\n"
    text += f"📝 {description}\n"
    text += f"📅 {date_str}\n"
    text += f"📊 Статус: {status_text}\n"
    
    if lat and lon:
        maps_link = f"https://yandex.ru/maps/?pt={lon},{lat}&z=18&l=map"
        text += f"📍 [Карта]({maps_link})\n"
    elif address:
        text += f"📍 Адрес: {address}\n"
    
    return text

def get_coordinates_from_geo_id(vk, geo_id, message_id=None):
    """Получает координаты из ID геолокации"""
    try:
        # Способ 1: через messages.getById
        if message_id:
            messages = vk.messages.getById(message_ids=[message_id])
            if messages and 'items' in messages and messages['items']:
                msg = messages['items'][0]
                if 'geo' in msg and 'coordinates' in msg['geo']:
                    coords = msg['geo']['coordinates']
                    lat = coords.get('lat') or coords.get('latitude')
                    lon = coords.get('long') or coords.get('longitude')
                    if lat and lon:
                        return float(lat), float(lon)
        
        # Способ 2: пробуем через execute
        response = vk.method('execute', {'code': f'return API.utils.getGeo({{"id":"{geo_id}"}});'})
        if response and 'lat' in response and 'long' in response:
            return float(response['lat']), float(response['long'])
        
        # Способ 3: пробуем прямой запрос к API
        geo_info = vk.utils.getGeo(id=geo_id)
        if geo_info and 'lat' in geo_info and 'long' in geo_info:
            return float(geo_info['lat']), float(geo_info['long'])
            
    except Exception as e:
        print(f"⚠️ Ошибка получения координат: {e}")
    
    return None, None

def handle_location(vk, user_id, event, message_id=None):
    """Обрабатывает получение геолокации"""
    global user_states
    
    print(f"🔥 Функция handle_location вызвана для пользователя {user_id}")
    
    if not event.attachments:
        print(f"❌ Нет вложений")
        return False
    
    print(f"📎 Вложения: {event.attachments}")
    
    if 'geo' not in event.attachments:
        print(f"❌ Нет гео во вложениях")
        return False
    
    try:
        # Получаем данные геолокации
        geo_data = event.attachments['geo']
        print(f"📎 geo_data тип: {type(geo_data)}")
        print(f"📎 geo_data: {geo_data}")
        
        lat = None
        lon = None
        
        # Если это строка (ID геолокации)
        if isinstance(geo_data, str):
            print(f"📍 Получаем координаты по ID: {geo_data}")
            lat, lon = get_coordinates_from_geo_id(vk, geo_data, message_id)
            
            if lat and lon:
                print(f"✅ Координаты получены: {lat}, {lon}")
            else:
                print(f"⚠️ Не удалось получить координаты")
                send_message(vk, user_id,
                            f"❌ Не удалось получить координаты автоматически.\n\n"
                            f"Пожалуйста, введите ваш адрес вручную:",
                            create_location_keyboard())
                return True
        
        # Если это словарь с координатами
        elif isinstance(geo_data, dict):
            if 'coordinates' in geo_data:
                coords = geo_data['coordinates']
                if isinstance(coords, dict):
                    lat = coords.get('latitude')
                    lon = coords.get('longitude')
                elif isinstance(coords, str):
                    parts = coords.split()
                    if len(parts) == 2:
                        lat = float(parts[0])
                        lon = float(parts[1])
            elif 'lat' in geo_data and 'long' in geo_data:
                lat = float(geo_data['lat'])
                lon = float(geo_data['long'])
        
        # Если координаты так и не получены
        if lat is None or lon is None:
            print(f"⚠️ Не удалось получить координаты")
            send_message(vk, user_id,
                        f"❌ Не удалось получить координаты.\n\n"
                        f"Пожалуйста, введите ваш адрес вручную:",
                        create_location_keyboard())
            return True
        
        print(f"✅ Итоговые координаты: {lat}, {lon}")
        
        if user_id not in user_states:
            print(f"❌ Пользователь {user_id} не в состояниях")
            send_message(vk, user_id,
                        "📍 Геолокация получена, но активная заявка не найдена.\n"
                        "Создайте новую заявку.",
                        create_main_keyboard())
            return True
        
        state = user_states[user_id]
        print(f"📊 Состояние пользователя: {state}")
        
        if not (isinstance(state, dict) and state.get('step') == 'waiting_location'):
            print(f"❌ Неправильное состояние для геолокации: {state}")
            send_message(vk, user_id,
                        "📍 Геолокация получена, но сейчас она не нужна.",
                        create_main_keyboard())
            return True
        
        # Обновляем заявку с координатами
        database.update_request_location(state['request_id'], lat, lon)
        
        # Создаем ссылку на карту
        maps_link = f"https://yandex.ru/maps/?pt={lon},{lat}&z=18&l=map"
        
        send_message(vk, user_id,
                    f"✅ Заявка №{state['request_id']} полностью опубликована!\n\n"
                    f"{state.get('type_text', 'Заявка')}\n"
                    f"📝 {state.get('description', '')}\n"
                    f"📍 Место отмечено на карте:\n{maps_link}",
                    create_main_keyboard())
        
        # Очищаем состояние
        del user_states[user_id]
        print(f"✅ Заявка обработана, состояние очищено")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в handle_location: {e}")
        import traceback
        traceback.print_exc()
        send_message(vk, user_id,
                    f"❌ Ошибка при обработке геолокации.\n"
                    f"Пожалуйста, введите адрес вручную:",
                    create_location_keyboard())
        return True

def main():
    # Авторизация
    from config import TOKEN
    token = TOKEN
    
    vk_session = vk_api.VkApi(token=token)
    longpoll = VkLongPoll(vk_session)
    vk = vk_session.get_api()
    
    # Получаем информацию о сообществе
    try:
        group_info = vk.groups.getById()[0]
        print(f"✅ Бот для сообщества @{group_info['screen_name']} запущен!")
    except:
        print("✅ Бот запущен!")
    
    # Отправляем тестовое сообщение для проверки
    try:
        test_user_id = 159309311  # Ваш ID
        test_keyboard = create_main_keyboard()
        send_message(vk, test_user_id, "🔄 Бот перезапущен и работает!", test_keyboard)
        print(f"✅ Отправлено тестовое сообщение")
    except Exception as e:
        print(f"❌ Не удалось отправить тестовое сообщение: {e}")
    
    # Основной цикл обработки сообщений
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.user_id
            message_id = event.message_id  # Сохраняем ID сообщения для геолокации
            
            # Получаем имя пользователя
            try:
                user_info = vk.users.get(user_ids=user_id)[0]
                user_name = f"{user_info['first_name']} {user_info['last_name']}"
            except:
                user_info = {'first_name': 'Пользователь'}
                user_name = f"Пользователь {user_id}"
            
            # Отладка
            print(f"\n📱 Сообщение от {user_name} (ID: {user_id})")
            print(f"📱 Текст: '{event.text}'")
            print(f"📱 Вложения: {event.attachments}")
            print(f"📱 user_states: {user_states.get(user_id)}")
            
            # ВАЖНО: Сначала проверяем геолокацию!
            if event.attachments and 'geo' in event.attachments:
                print(f"📍 ЭТО ГЕОЛОКАЦИЯ!")
                if handle_location(vk, user_id, event, message_id):
                    print(f"✅ Геолокация обработана, пропускаем текстовую обработку")
                    continue
            
            # Обычное текстовое сообщение
            text = event.text.strip() if event.text else ""
            
            # Если пользователя нет в состояниях - показываем меню ТОЛЬКО если это не нажатие кнопки
            if user_id not in user_states:
                # Проверяем, не является ли сообщение командой от кнопки
                if text in ["🆘 Нужна помощь", "💚 Могу помочь", "🎉 Событие", "👀 Смотреть заявки", 
                           "📋 Мои заявки", "❓ Помощь", "🔙 Назад", "🔍 Все заявки", 
                           "✏️ Ввести адрес", "🔙 Отмена", "🗑️ Удалить мои заявки",
                           "✅ Да, удалить все", "🔙 Нет, отмена"]:
                    # Это нажатие кнопки - обрабатываем дальше
                    print(f"🔘 Нажата кнопка: {text}")
                    user_states[user_id] = {'step': 'idle'}
                else:
                    # Это обычное сообщение от нового пользователя - показываем меню
                    print(f"🆕 Показываем меню пользователю {user_name}")
                    welcome_message = (
                        f"👋 Привет, {user_info['first_name']}!\n\n"
                        f"Я бот взаимопомощи вашего района. Здесь вы можете:\n"
                        f"🆘 Попросить о помощи\n"
                        f"💚 Предложить помощь или отдать вещи\n"
                        f"🎉 Создать или найти событие\n\n"
                        f"Выберите действие на клавиатуре 👇"
                    )
                    send_message(vk, user_id, welcome_message, create_main_keyboard())
                    # Добавляем пользователя в состояния, чтобы больше не показывать меню
                    user_states[user_id] = {'step': 'idle'}
                    continue
            
            # Нормализуем текст для сравнения
            text_lower = text.lower()
            
            # Обработка команд
            if text_lower in ["начать", "старт", "start", "/start", "назад", "меню"]:
                print(f"✅ Распознана команда: {text}")
                welcome_message = (
                    f"👋 Привет, {user_info['first_name']}!\n\n"
                    f"Я бот взаимопомощи вашего района. Здесь вы можете:\n"
                    f"🆘 Попросить о помощи\n"
                    f"💚 Предложить помощь или отдать вещи\n"
                    f"🎉 Создать или найти событие\n\n"
                    f"Выберите действие на клавиатуре 👇"
                )
                send_message(vk, user_id, welcome_message, create_main_keyboard())
                user_states[user_id] = {'step': 'idle'}
            
            elif text == "🆘 Нужна помощь":
                user_states[user_id] = {
                    'step': 'waiting_description',
                    'type': 'help_needed',
                    'type_text': '🆘 Нужна помощь'
                }
                send_message(vk, user_id, 
                           "Расскажите, какая помощь нужна?\n"
                           "Например: вынести мусор, встретить курьера, купить продуктов")
            
            elif text == "💚 Могу помочь":
                user_states[user_id] = {
                    'step': 'waiting_description',
                    'type': 'help_offer',
                    'type_text': '💚 Могу помочь'
                }
                send_message(vk, user_id, 
                           "Что вы можете предложить?\n"
                           "Например: могу выгулять собаку, отдать стул, помочь с переездом")
            
            elif text == "🎉 Событие":
                user_states[user_id] = {
                    'step': 'waiting_description',
                    'type': 'event',
                    'type_text': '🎉 Событие'
                }
                send_message(vk, user_id, 
                           "Расскажите о событии:\n"
                           "Например: субботник во дворе в субботу в 12:00")
            
            elif text == "👀 Смотреть заявки":
                requests = database.get_active_requests(limit=10)
                
                if not requests:
                    send_message(vk, user_id, 
                               "😕 Пока нет активных заявок. Создайте первую!",
                               create_main_keyboard())
                else:
                    response = "🔍 **Активные заявки:**\n\n"
                    for req in requests[:5]:
                        response += format_request_text(req) + "\n" + "─" * 30 + "\n"
                    
                    response += "\nЧтобы откликнуться, напишите номер заявки"
                    
                    user_states[user_id] = {
                        'step': 'viewing_requests'
                    }
                    
                    send_message(vk, user_id, response, create_requests_view_keyboard())
            
            elif text == "📋 Мои заявки":
                requests = database.get_user_requests(user_id)
                
                if not requests:
                    send_message(vk, user_id, 
                               "📭 У вас пока нет заявок. Создайте первую!",
                               create_main_keyboard())
                else:
                    response = "📋 **Ваши заявки:**\n\n"
                    for req in requests[:5]:
                        status = "✅ Активна" if req[8] == 'active' else "❌ Выполнена"
                        req_type = {
                            'help_needed': '🆘 Нужна помощь',
                            'help_offer': '💚 Могу помочь',
                            'event': '🎉 Событие'
                        }.get(req[3], req[3])
                        
                        response += f"№{req[0]} {req_type}\n"
                        response += f"📝 {req[4][:50]}...\n"
                        response += f"📅 {req[9][:16]}\n"
                        response += f"Статус: {status}\n"
                        
                        # Если заявка активна, показываем количество откликов
                        if req[8] == 'active':
                            responses_count = len(database.get_responses_for_request(req[0]))
                            if responses_count > 0:
                                response += f"👥 Откликов: {responses_count}\n"
                                response += f"💡 Чтобы посмотреть отклики, напишите: отклики {req[0]}\n"
                        
                        response += "\n"
                    
                    response += "💡 Чтобы посмотреть отклики на заявку, напишите: отклики [номер]"
                    
                    send_message(vk, user_id, response, create_main_keyboard())
            
            elif text == "🗑️ Удалить мои заявки":
                # Проверяем, есть ли у пользователя заявки
                active_count = database.get_user_requests_count(user_id, 'active')
                total_count = database.get_user_requests_count(user_id)
                
                if total_count == 0:
                    send_message(vk, user_id,
                               "📭 У вас нет заявок для удаления.",
                               create_main_keyboard())
                else:
                    # Показываем подтверждение
                    confirm_text = (
                        f"⚠️ **ВНИМАНИЕ!**\n\n"
                        f"У вас есть:\n"
                        f"📋 Всего заявок: {total_count}\n"
                        f"✅ Активных: {active_count}\n\n"
                        f"Вы уверены, что хотите **УДАЛИТЬ ВСЕ** свои заявки?\n"
                        f"Это действие нельзя отменить!"
                    )
                    
                    user_states[user_id] = {'step': 'confirm_delete'}
                    send_message(vk, user_id, confirm_text, create_confirm_keyboard())
            
            elif text == "✅ Да, удалить все":
                if user_id in user_states and user_states[user_id].get('step') == 'confirm_delete':
                    # Удаляем все заявки
                    deleted_count = database.delete_user_requests(user_id)
                    
                    # Очищаем состояние пользователя
                    if user_id in user_states:
                        del user_states[user_id]
                    
                    send_message(vk, user_id,
                               f"✅ Удалено {deleted_count} заявок и связанных с ними откликов.",
                               create_main_keyboard())
                else:
                    send_message(vk, user_id,
                               "❌ Операция не подтверждена. Начните сначала.",
                               create_main_keyboard())
            
            elif text == "🔙 Нет, отмена":
                if user_id in user_states and user_states[user_id].get('step') == 'confirm_delete':
                    del user_states[user_id]
                send_message(vk, user_id,
                           "❌ Удаление отменено.",
                           create_main_keyboard())
            
            elif text == "❓ Помощь":
                help_text = (
                    "🔍 **Как пользоваться ботом:**\n\n"
                    "1️⃣ Нажмите нужную кнопку\n"
                    "2️⃣ Опишите, что нужно\n"
                    "3️⃣ Отправьте геолокацию или введите адрес\n\n"
                    "👀 'Смотреть заявки' — увидеть, что нужно соседям\n"
                    "📋 'Мои заявки' — ваши заявки\n"
                    "🗑️ 'Удалить мои заявки' — удалить все свои заявки\n\n"
                    "👥 Чтобы посмотреть отклики: отклики [номер заявки]\n"
                    "✅ Чтобы принять отклик: принять [номер отклика]\n"
                    "❌ Чтобы отклонить отклик: отклонить [номер отклика]\n\n"
                    "💡 Совет: Для отправки геолокации используйте мобильное приложение ВК"
                )
                send_message(vk, user_id, help_text, create_main_keyboard())
            
            elif text == "🔙 Назад":
                if user_id in user_states:
                    del user_states[user_id]
                send_message(vk, user_id, "Главное меню:", create_main_keyboard())
            
            elif text == "🔍 Все заявки":
                requests = database.get_active_requests(limit=20)
                
                if not requests:
                    send_message(vk, user_id, "😕 Нет активных заявок", create_requests_view_keyboard())
                else:
                    response = "🔍 **Все активные заявки:**\n\n"
                    for req in requests[:10]:
                        response += format_request_text(req) + "\n" + "─" * 30 + "\n"
                    
                    send_message(vk, user_id, response, create_requests_view_keyboard())
            
            elif text == "✏️ Ввести адрес":
                if user_id in user_states and user_states[user_id].get('step') == 'waiting_location':
                    user_states[user_id]['step'] = 'waiting_address'
                    send_message(vk, user_id,
                               "Напишите ваш адрес (например: ул. Ленина, д. 10):",
                               None)
            
            elif text == "🔙 Отмена":
                if user_id in user_states:
                    state = user_states[user_id]
                    if isinstance(state, dict) and 'request_id' in state:
                        database.close_request(state['request_id'])
                    del user_states[user_id]
                send_message(vk, user_id, "❌ Действие отменено", create_main_keyboard())
            
            elif text.isdigit() and len(text) <= 5:
                request_id = int(text)
                request = database.get_request_by_id(request_id)
                
                if request and request[8] == 'active':
                    if request[1] == user_id:
                        send_message(vk, user_id,
                                   "❌ Это ваша заявка",
                                   create_main_keyboard())
                    else:
                        user_states[user_id] = {
                            'step': 'responding',
                            'request_id': request_id,
                            'request_owner_id': request[1],
                            'request_owner_name': request[2]
                        }
                        
                        send_message(vk, user_id,
                                   f"Заявка №{request_id} от {request[2]}\n\n"
                                   f"{request[4]}\n\n"
                                   f"Напишите сообщение:",
                                   None)
                else:
                    send_message(vk, user_id, "❌ Заявка не найдена", create_main_keyboard())
            
            elif text_lower.startswith("отклики"):
                # Парсим номер заявки
                parts = text.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    request_id = int(parts[1])
                    request = database.get_request_by_id(request_id)
                    
                    if request and request[1] == user_id:
                        responses = database.get_responses_for_request(request_id)
                        
                        if not responses:
                            send_message(vk, user_id,
                                       f"📭 На заявку №{request_id} пока нет откликов",
                                       create_main_keyboard())
                        else:
                            response_text = f"👥 **Отклики на заявку №{request_id}:**\n\n"
                            for resp in responses:
                                resp_id, req_id, responder_id, responder_name, message, status, created_at = resp
                                date_str = created_at[:16] if created_at else "неизвестно"
                                response_text += f"🔹 **Отклик #{resp_id}**\n"
                                response_text += f"👤 {responder_name}\n"
                                response_text += f"💬 {message}\n"
                                response_text += f"📅 {date_str}\n"
                                response_text += f"💡 Чтобы принять, напишите: принять {resp_id}\n"
                                response_text += f"💡 Чтобы отклонить, напишите: отклонить {resp_id}\n\n"
                            
                            send_message(vk, user_id, response_text, create_main_keyboard())
                    else:
                        send_message(vk, user_id,
                                   "❌ Заявка не найдена или это не ваша заявка",
                                   create_main_keyboard())
                else:
                    send_message(vk, user_id,
                               "❌ Используйте формат: отклики [номер заявки]",
                               create_main_keyboard())
            
            elif text_lower.startswith("принять"):
                parts = text.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    response_id = int(parts[1])
                    response = database.get_response_by_id(response_id)
                    
                    if response:
                        request_id = response[1]
                        request = database.get_request_by_id(request_id)
                        responder_id = response[2]
                        responder_name = response[3]
                        
                        # Проверяем, что пользователь - владелец заявки
                        if request and request[1] == user_id:
                            # Принимаем отклик
                            database.accept_response(response_id)
                            # Закрываем заявку
                            database.close_request(request_id)
                            
                            # Уведомляем того, кто откликнулся
                            try:
                                notification = (
                                    f"🎉 **Ваш отклик на заявку №{request_id} принят!**\n\n"
                                    f"👤 {request[2]} принял(а) вашу помощь.\n"
                                    f"📝 {request[4]}\n\n"
                                    f"Свяжитесь с автором заявки через личные сообщения."
                                )
                                send_message(vk, responder_id, notification, create_main_keyboard())
                            except Exception as e:
                                print(f"❌ Не удалось отправить уведомление: {e}")
                            
                            # Уведомляем владельца
                            send_message(vk, user_id,
                                       f"✅ Вы приняли отклик от {responder_name} на заявку №{request_id}!\n"
                                       f"Заявка закрыта. Свяжитесь с помощником через личные сообщения.",
                                       create_main_keyboard())
                        else:
                            send_message(vk, user_id,
                                       "❌ Это не ваша заявка",
                                       create_main_keyboard())
                    else:
                        send_message(vk, user_id,
                                   "❌ Отклик не найден",
                                   create_main_keyboard())
                else:
                    send_message(vk, user_id,
                               "❌ Используйте формат: принять [номер отклика]",
                               create_main_keyboard())
            
            elif text_lower.startswith("отклонить"):
                parts = text.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    response_id = int(parts[1])
                    response = database.get_response_by_id(response_id)
                    
                    if response:
                        request_id = response[1]
                        request = database.get_request_by_id(request_id)
                        responder_id = response[2]
                        responder_name = response[3]
                        
                        # Проверяем, что пользователь - владелец заявки
                        if request and request[1] == user_id:
                            # Отклоняем отклик
                            database.reject_response(response_id)
                            
                            # Уведомляем того, кто откликнулся
                            try:
                                notification = (
                                    f"ℹ️ **Ваш отклик на заявку №{request_id} был отклонен**\n\n"
                                    f"👤 {request[2]} выбрал(а) другого помощника.\n"
                                    f"Спасибо за готовность помочь!"
                                )
                                send_message(vk, responder_id, notification, create_main_keyboard())
                            except Exception as e:
                                print(f"❌ Не удалось отправить уведомление: {e}")
                            
                            send_message(vk, user_id,
                                       f"✅ Вы отклонили отклик от {responder_name} на заявку №{request_id}",
                                       create_main_keyboard())
                        else:
                            send_message(vk, user_id,
                                       "❌ Это не ваша заявка",
                                       create_main_keyboard())
                    else:
                        send_message(vk, user_id,
                                   "❌ Отклик не найден",
                                   create_main_keyboard())
                else:
                    send_message(vk, user_id,
                               "❌ Используйте формат: отклонить [номер отклика]",
                               create_main_keyboard())
            
            elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get('step') == 'responding':
                state = user_states[user_id]
                
                database.add_response(
                    request_id=state['request_id'],
                    responder_id=user_id,
                    responder_name=user_name,
                    message=text
                )
                
                # Уведомляем владельца
                try:
                    notification = (
                        f"👋 **Новый отклик на вашу заявку!**\n\n"
                        f"📝 Заявка №{state['request_id']}: {state.get('description', '')}\n\n"
                        f"👤 Откликнулся: {user_name}\n"
                        f"💬 Сообщение: {text}\n\n"
                        f"💡 Чтобы посмотреть все отклики, напишите: отклики {state['request_id']}"
                    )
                    send_message(vk, state['request_owner_id'], notification, create_main_keyboard())
                except Exception as e:
                    print(f"❌ Не удалось отправить уведомление: {e}")
                
                send_message(vk, user_id,
                           f"✅ Отклик отправлен!",
                           create_main_keyboard())
                
                del user_states[user_id]
            
            elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get('step') == 'waiting_description':
                state = user_states[user_id]
                
                # Создаем заявку
                request_id = database.add_request(
                    user_id=user_id,
                    user_name=user_name,
                    request_type=state['type'],
                    description=text
                )
                
                # Переходим к геолокации
                user_states[user_id] = {
                    'step': 'waiting_location',
                    'request_id': request_id,
                    'type_text': state['type_text'],
                    'description': text
                }
                
                send_message(vk, user_id,
                            f"✅ Заявка №{request_id} создана!\n\n"
                            f"📍 Теперь отправьте геолокацию (нажмите кнопку ниже)\n"
                            f"или введите адрес вручную:",
                            create_location_keyboard())
            
            elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get('step') == 'waiting_address':
                state = user_states[user_id]
                
                # Сохраняем адрес
                database.update_request_location(
                    state['request_id'],
                    None, None,
                    text
                )
                
                send_message(vk, user_id,
                            f"✅ Заявка №{state['request_id']} опубликована с адресом:\n{text}",
                            create_main_keyboard())
                
                del user_states[user_id]
            
            else:
                # Если пользователь есть в состояниях, но команда не распознана
                send_message(vk, user_id, 
                           "Я не понимаю эту команду.\n"
                           "Воспользуйтесь кнопками 👇", 
                           create_main_keyboard())

if __name__ == '__main__':
    main()
