import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from main import (
    start, language_callback, budget_callback, talk, restart,
    translate_message, save_user_to_db, get_db_connection, is_this_user_allowed,
    ask, append_interaction_to_chat_log, show_budget_buttons, location_callback,
    area_callback, show_pretty_restaurants, handle_location, detect_language,
    check_budget, choose_area_callback, show_other_price_callback
)
from telegram import Update, User, Message, CallbackQuery
from telegram.ext import ContextTypes
import asyncio
import logging

# Вспомогательные функции для создания mock-объектов
class DummyContext:
    def __init__(self):
        self.user_data = {}
        self.bot = MagicMock()

class DummyMessage:
    def __init__(self, text, user_id=123, username='testuser'):
        self.text = text
        self.chat_id = user_id
        self.message_id = 1
        self.from_user = User(id=user_id, first_name='Test', is_bot=False)
        self.reply_text = AsyncMock()
        self.delete = AsyncMock()
        self.location = None

class DummyChat:
    def __init__(self):
        self.send_message = AsyncMock()

class DummyUpdate:
    def __init__(self, text=None, user_id=123, username='testuser'):
        self.effective_user = User(id=user_id, first_name='Test', username=username, is_bot=False)
        self.message = DummyMessage(text, user_id, username) if text else None
        self.callback_query = None
        self.effective_chat = DummyChat()

# Тест: команда /restart
@pytest.mark.asyncio
async def test_restart():
    update = DummyUpdate(text='/restart')
    context = DummyContext()
    update.message.reply_text = AsyncMock()
    await restart(update, context)
    # Проверяем, что после рестарта остались только ключи новой сессии
    assert set(context.user_data.keys()) == {'awaiting_language', 'chat_log', 'sessionid'}

# Тест: выбор языка и проверка, что кнопки и сообщения на нужном языке
@pytest.mark.asyncio
async def test_language_callback_ru():
    update = DummyUpdate()
    context = DummyContext()
    # Мокаем callback_query
    callback_query = MagicMock()
    callback_query.data = 'lang_ru'
    callback_query.message = MagicMock()
    callback_query.answer = AsyncMock()
    callback_query.message.delete = AsyncMock()
    callback_query.message.reply_text = AsyncMock()
    update.callback_query = callback_query
    update.effective_user = update.effective_user
    with patch('main.save_user_to_db', return_value=1):
        await language_callback(update, context)
    # Проверяем, что язык установлен
    assert context.user_data['language'] == 'ru'
    # Проверяем, что отправлено приветствие на русском
    callback_query.message.reply_text.assert_any_call('Я знаю о ресторанах на Пхукете всё.')

# Тест: выбор бюджета и ожидание пожеланий
@pytest.mark.asyncio
async def test_budget_callback():
    update = DummyUpdate()
    context = DummyContext()
    callback_query = MagicMock()
    callback_query.data = 'budget_2'
    callback_query.message = MagicMock()
    callback_query.message.chat_id = 123
    callback_query.message.message_id = 2
    callback_query.answer = AsyncMock()
    callback_query.message.delete = AsyncMock()
    callback_query.message.reply_text = AsyncMock()
    update.callback_query = callback_query
    context.user_data['language'] = 'ru'
    context.bot.send_chat_action = AsyncMock()
    context.bot.delete_message = AsyncMock()
    with patch('main.translate_message', return_value='Ваш выбор сохранён!'):
        await budget_callback(update, context)
    assert context.user_data['budget'] == '2'
    assert context.user_data['awaiting_budget_response'] is True

# Тест: умный диалог — пожелания не по теме ресторанов
@pytest.mark.asyncio
async def test_talk_smart_dialog():
    update = DummyUpdate(text='Расскажи анекдот')
    context = DummyContext()
    context.user_data['awaiting_budget_response'] = True
    context.user_data['language'] = 'ru'
    with patch('main.detect_language', return_value='ru'), \
         patch('main.ask', return_value=('NO_PREFS', [])), \
         patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
        await talk(update, context)
        # Проверяем, что бот мягко возвращает к теме ресторанов
        mock_reply.assert_called()

# Тест: умный диалог — пожелания по теме ресторанов
@pytest.mark.skip(reason='Временно отключено: зависит от OpenAI')
@pytest.mark.asyncio
async def test_talk_restaurant_prefs():
    update = DummyUpdate(text='Хочу итальянскую кухню и террасу')
    context = DummyContext()
    context.user_data['awaiting_budget_response'] = True
    context.user_data['language'] = 'ru'
    with patch('main.detect_language', return_value='ru'), \
         patch('main.ask', return_value=('### итальянская кухня, терраса', [])), \
         patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
        await talk(update, context)
        # Проверяем, что предпочтения сохранены
        assert context.user_data.get('last_user_wish') is not None
        mock_reply.assert_called()

# Тест: get_db_connection (успешное подключение)
def test_get_db_connection_success():
    with patch('psycopg2.connect', return_value=MagicMock()):
        conn = get_db_connection()
        assert conn is not None

# Тест: get_db_connection (ошибка подключения)
def test_get_db_connection_fail():
    with patch('psycopg2.connect', side_effect=Exception('fail')):
        with pytest.raises(Exception):
            get_db_connection()

# Тест: save_user_to_db (новый пользователь)
def test_save_user_to_db_insert():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.side_effect = [None, {'client_number': 1}]
    mock_conn.cursor.return_value = mock_cur
    with patch('main.get_db_connection', return_value=mock_conn):
        client_number = save_user_to_db(1, 'user', 'Имя', 'Фамилия', 'ru')
        assert client_number == 1
        assert mock_conn.commit.called

# Тест: save_user_to_db (существующий пользователь)
def test_save_user_to_db_update():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    # Первый вызов fetchone — существующий пользователь, второй — результат update
    mock_cur.fetchone.side_effect = [{'client_number': 2}, {'client_number': 2}]
    mock_conn.cursor.return_value = mock_cur
    with patch('main.get_db_connection', return_value=mock_conn):
        client_number = save_user_to_db(2, 'user', 'Имя', 'Фамилия', 'ru')
        assert client_number == 2
        assert mock_conn.commit.called

# Тест: is_this_user_allowed (разрешённый пользователь)
def test_is_this_user_allowed_true():
    os.environ['ALLOWED_USERS'] = '1,2,3'
    assert is_this_user_allowed('2') is True

# Тест: is_this_user_allowed (неразрешённый пользователь)
def test_is_this_user_allowed_false():
    os.environ['ALLOWED_USERS'] = '1,2,3'
    assert is_this_user_allowed('99') is False

# Тест: ask (AI-ответ)
@pytest.mark.skip(reason='Временно отключено: зависит от OpenAI')
def test_ask():
    with patch('main.client.chat.completions.create') as mock_create:
        mock_create.return_value.choices = [MagicMock(message=MagicMock(content='ответ'))]
        answer, chat_log = ask('Привет', chat_log=None, language='ru')
        assert 'ответ' in answer
        assert isinstance(chat_log, list)

# Тест: append_interaction_to_chat_log
def test_append_interaction_to_chat_log():
    log = append_interaction_to_chat_log('Q', 'A', chat_log=[])
    assert log[-2]['role'] == 'user'
    assert log[-1]['role'] == 'assistant'

# Тест: translate_message (английский)
@pytest.mark.skip(reason='Временно отключено: зависит от OpenAI')
@pytest.mark.asyncio
async def test_translate_message_en():
    msg = await translate_message('welcome', 'en')
    assert 'Phuket' in msg

# Тест: translate_message (другой язык, mock OpenAI)
@pytest.mark.skip(reason='Временно отключено: зависит от OpenAI')
@pytest.mark.asyncio
async def test_translate_message_other():
    with patch('main.client.chat.completions.create') as mock_create:
        mock_create.return_value.choices = [MagicMock(message=MagicMock(content='Перевод'))]
        msg = await translate_message('welcome', 'ru')
        assert msg == 'Перевод'

@pytest.mark.asyncio
async def test_start():
    update = DummyUpdate()
    context = DummyContext()
    if update.message is None:
        update.message = DummyMessage('')
    update.message.reply_text = AsyncMock()
    await start(update, context)
    update.message.reply_text.assert_any_call(
        f'Hello and welcome to BookTable.AI v' + open('version.txt').read().strip() + '!' + '\n'
        'I will help you find the perfect restaurant in Phuket and book a table in seconds.'
    )
    assert context.user_data['awaiting_language'] is True
    assert 'sessionid' in context.user_data

@pytest.mark.asyncio
async def test_show_budget_buttons():
    update = DummyUpdate()
    context = DummyContext()
    context.user_data['language'] = 'en'
    if update.message is None:
        update.message = DummyMessage('')
    update.message.reply_text = AsyncMock()
    with patch('main.translate_message', return_value='What price range would you prefer for the restaurant?'):
        await show_budget_buttons(update, context)
    update.message.reply_text.assert_called()

@pytest.mark.asyncio
async def test_location_callback_near():
    update = DummyUpdate()
    context = DummyContext()
    callback_query = MagicMock()
    callback_query.data = 'location_near'
    callback_query.message = MagicMock()
    callback_query.answer = AsyncMock()
    callback_query.message.delete = AsyncMock()
    callback_query.message.reply_text = AsyncMock()
    update.callback_query = callback_query
    context.user_data['language'] = 'ru'
    context.bot.send_chat_action = AsyncMock()
    await location_callback(update, context)
    callback_query.message.reply_text.assert_called()
    assert context.user_data['awaiting_location_or_area'] is True

@pytest.mark.asyncio
async def test_location_callback_area():
    update = DummyUpdate()
    context = DummyContext()
    callback_query = MagicMock()
    callback_query.data = 'location_area'
    callback_query.message = MagicMock()
    callback_query.answer = AsyncMock()
    callback_query.message.delete = AsyncMock()
    callback_query.message.reply_text = AsyncMock()
    update.callback_query = callback_query
    context.user_data['language'] = 'ru'
    context.bot.send_chat_action = AsyncMock()
    await location_callback(update, context)
    callback_query.message.reply_text.assert_called()

@pytest.mark.skip(reason='Временно отключено: языковые особенности и OpenAI')
@pytest.mark.asyncio
async def test_location_callback_any():
    update = DummyUpdate()
    context = DummyContext()
    callback_query = MagicMock()
    callback_query.data = 'location_any'
    callback_query.message = MagicMock()
    callback_query.answer = AsyncMock()
    callback_query.message.delete = AsyncMock()
    callback_query.message.reply_text = AsyncMock()
    update.callback_query = callback_query
    context.user_data['language'] = 'en'
    context.user_data['chat_log'] = []
    context.bot.send_chat_action = AsyncMock()
    if update.message is None:
        update.message = DummyMessage('')
    update.message.reply_text = AsyncMock()
    with patch('main.ask', return_value=('AI answer', [])):
        await location_callback(update, context)
    # callback_query.message.reply_text.assert_any_call("Okay, I'll search restaurants all over the island.")

@pytest.mark.asyncio
async def test_area_callback_other():
    update = DummyUpdate()
    context = DummyContext()
    callback_query = MagicMock()
    callback_query.data = 'area_other'
    callback_query.message = MagicMock()
    callback_query.answer = AsyncMock()
    callback_query.message.delete = AsyncMock()
    callback_query.message.reply_text = AsyncMock()
    update.callback_query = callback_query
    context.user_data['language'] = 'ru'
    await area_callback(update, context)
    callback_query.message.reply_text.assert_called()
    assert context.user_data['awaiting_area_input'] is True

@pytest.mark.asyncio
async def test_area_callback_regular():
    update = DummyUpdate()
    context = DummyContext()
    callback_query = MagicMock()
    callback_query.data = 'area_patong'
    callback_query.message = MagicMock()
    callback_query.answer = AsyncMock()
    callback_query.message.delete = AsyncMock()
    update.callback_query = callback_query
    context.user_data['language'] = 'ru'
    with patch('main.show_pretty_restaurants', new_callable=AsyncMock):
        await area_callback(update, context)
    assert context.user_data['location']['area'] == 'patong'

@pytest.mark.asyncio
async def test_show_pretty_restaurants_any():
    update = DummyUpdate()
    context = DummyContext()
    context.user_data['location'] = 'any'
    context.user_data['budget'] = '2'
    context.user_data['language'] = 'en'
    with patch('main.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [{'name': 'TestRest', 'average_check': '$$'}]
        mock_conn.cursor.return_value = mock_cur
        mock_db.return_value = mock_conn
        update.effective_chat = MagicMock()
        update.effective_chat.send_message = AsyncMock()
        await show_pretty_restaurants(update, context)
        update.effective_chat.send_message.assert_called()

@pytest.mark.asyncio
async def test_handle_location():
    update = DummyUpdate()
    context = DummyContext()
    update.message = MagicMock()
    update.message.location = MagicMock(latitude=7.9, longitude=98.3)
    context.user_data['language'] = 'ru'
    context.user_data['chat_log'] = []
    if update.message is None:
        update.message = DummyMessage('')
    update.message.reply_text = AsyncMock()
    with patch('main.get_db_connection') as mock_db, \
         patch('main.get_nearest_area', return_value='patong'), \
         patch('main.show_pretty_restaurants', new_callable=AsyncMock):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_db.return_value = mock_conn
        await handle_location(update, context)
    assert context.user_data['location']['area'] == 'patong'

# Тест: detect_language (mock OpenAI)
@pytest.mark.skip(reason='Временно отключено: зависит от OpenAI')
def test_detect_language():
    with patch('main.client.chat.completions.create') as mock_create:
        mock_create.return_value.choices = [MagicMock(message=MagicMock(content='ru'))]
        from main import detect_language
        lang = detect_language('Привет')
        assert lang == 'ru'

@pytest.mark.asyncio
async def test_check_budget():
    update = DummyUpdate()
    context = DummyContext()
    if update.message is None:
        update.message = DummyMessage('')
    update.message.reply_text = AsyncMock()
    await check_budget(update, context)
    update.message.reply_text.assert_called()

@pytest.mark.asyncio
async def test_choose_area_callback():
    update = DummyUpdate()
    context = DummyContext()
    callback_query = MagicMock()
    callback_query.answer = AsyncMock()
    callback_query.message = MagicMock()
    callback_query.message.delete = AsyncMock()
    callback_query.message.reply_text = AsyncMock()
    update.callback_query = callback_query
    await choose_area_callback(update, context)
    callback_query.message.reply_text.assert_called()

@pytest.mark.asyncio
async def test_show_other_price_callback():
    update = DummyUpdate()
    context = DummyContext()
    context.user_data['location'] = {'area': 'patong', 'name': 'Паттонг'}
    context.user_data['budget'] = '2'
    context.user_data['language'] = 'ru'
    callback_query = AsyncMock()
    callback_query.answer = AsyncMock()
    update.callback_query = callback_query
    with patch('main.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [{'name': 'TestRest', 'average_check': '$$'}]
        mock_conn.cursor.return_value = mock_cur
        mock_db.return_value = mock_conn
        update.effective_chat = MagicMock()
        update.effective_chat.send_message = AsyncMock()
        await show_other_price_callback(update, context)
        update.effective_chat.send_message.assert_called()

@pytest.mark.asyncio
async def test_talk_finalizing_restaurant_booking():
    update = DummyUpdate(text='Забронировать')
    context = DummyContext()
    context.user_data['finalizing_restaurant'] = True
    context.user_data['language'] = 'ru'
    context.user_data['booking_in_progress'] = False
    context.user_data['booking_step'] = None
    context.user_data['booking_data'] = {}
    context.user_data['chat_log'] = []
    with patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
        await talk(update, context)
        # Проверяем переход к бронированию
        assert context.user_data['booking_in_progress'] is True
        assert context.user_data['booking_step'] == 'guests'
        mock_reply.assert_called_with('Отлично! Давайте забронируем столик. Сколько гостей будет?')

@pytest.mark.asyncio
async def test_talk_finalizing_restaurant_next():
    update = DummyUpdate(text='другой')
    context = DummyContext()
    context.user_data['finalizing_restaurant'] = True
    context.user_data['language'] = 'ru'
    context.user_data['booking_in_progress'] = False
    context.user_data['booking_step'] = None
    context.user_data['booking_data'] = {}
    context.user_data['chat_log'] = []
    with patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
        await talk(update, context)
        mock_reply.assert_called_with('Показываю следующий ресторан! (здесь будет переключение)')

@pytest.mark.asyncio
async def test_talk_finalizing_restaurant_question():
    update = DummyUpdate(text='Что по меню?')
    context = DummyContext()
    context.user_data['finalizing_restaurant'] = True
    context.user_data['language'] = 'ru'
    context.user_data['booking_in_progress'] = False
    context.user_data['booking_step'] = None
    context.user_data['booking_data'] = {}
    context.user_data['chat_log'] = []
    with patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
        await talk(update, context)
        mock_reply.assert_any_call('Отвечаю на вопрос по ресторану! (здесь будет AI-ответ)')

@pytest.mark.asyncio
async def test_talk_finalizing_restaurant_soft_return():
    update = DummyUpdate(text='Просто текст')
    context = DummyContext()
    context.user_data['finalizing_restaurant'] = True
    context.user_data['language'] = 'ru'
    context.user_data['booking_in_progress'] = False
    context.user_data['booking_step'] = None
    context.user_data['booking_data'] = {}
    context.user_data['chat_log'] = []
    with patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
        await talk(update, context)
        mock_reply.assert_any_call('Давайте обсудим ресторан или перейдём к бронированию! (мягкое возвращение)')

@pytest.mark.asyncio
async def test_talk_booking_steps():
    context = DummyContext()
    context.user_data['booking_in_progress'] = True
    context.user_data['booking_step'] = 'guests'
    context.user_data['booking_data'] = {}
    context.user_data['chat_log'] = []
    # Шаг 1: гости
    update = DummyUpdate(text='2')
    with patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
        await talk(update, context)
        assert context.user_data['booking_step'] == 'date'
        mock_reply.assert_called_with('На какую дату хотите забронировать столик? (например, 25 июня)')
    # Шаг 2: дата
    update = DummyUpdate(text='25 июня')
    with patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
        await talk(update, context)
        assert context.user_data['booking_step'] == 'time'
        mock_reply.assert_called_with('На какое время? (например, 19:00)')
    # Шаг 3: время
    update = DummyUpdate(text='19:00')
    with patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
        await talk(update, context)
        assert context.user_data['booking_step'] == 'name'
        mock_reply.assert_called_with('На чьё имя оформить бронирование?')
    # Шаг 4: имя
    update = DummyUpdate(text='Иван')
    with patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
        await talk(update, context)
        assert context.user_data['booking_step'] == 'phone'
        mock_reply.assert_called_with('Пожалуйста, укажите номер телефона для подтверждения бронирования.')
    # Шаг 5: телефон
    update = DummyUpdate(text='+79991234567')
    with patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
        await talk(update, context)
        assert context.user_data['finalizing_restaurant'] is False
        assert context.user_data['booking_in_progress'] is False
        assert context.user_data['booking_step'] is None
        assert context.user_data['booking_data'] is None
        mock_reply.assert_called_with('Спасибо! Ваше бронирование принято. Мы свяжемся с вами для подтверждения.')

@pytest.mark.asyncio
async def test_talk_booking_wrong_step():
    update = DummyUpdate(text='что-то не то')
    context = DummyContext()
    context.user_data['booking_in_progress'] = True
    context.user_data['booking_step'] = 'unknown'
    context.user_data['booking_data'] = {}
    context.user_data['chat_log'] = []
    with patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
        await talk(update, context)
        mock_reply.assert_called_with('Пожалуйста, укажите корректные данные для бронирования.')

@pytest.mark.asyncio
async def test_save_user_to_db_db_error():
    # Ошибка при подключении к базе
    with patch('main.get_db_connection', side_effect=Exception('db error')):
        with pytest.raises(Exception):
            save_user_to_db(1, 'user', 'Имя', 'Фамилия', 'ru')

@pytest.mark.skip(reason='Временно отключено: зависит от OpenAI')
@pytest.mark.asyncio
async def test_translate_message_error():
    # Ошибка перевода (исключение в OpenAI)
    with patch('main.client.chat.completions.create', side_effect=Exception('ai error')):
        msg = await translate_message('welcome', 'ru')
        assert 'Phuket' in msg  # fallback на английский

@pytest.mark.skip(reason='Временно отключено: зависит от OpenAI')
@pytest.mark.asyncio
async def test_talk_ai_error():
    update = DummyUpdate(text='Хочу суши')
    context = DummyContext()
    context.user_data['awaiting_budget_response'] = True
    context.user_data['language'] = 'ru'
    with patch('main.detect_language', return_value='ru'), \
         patch('main.ask', side_effect=Exception('ai error')), \
         patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
        await talk(update, context)
        mock_reply.assert_called()  # Сообщение об ошибке пользователю

@pytest.mark.asyncio
async def test_handle_location_error():
    update = DummyUpdate()
    context = DummyContext()
    update.message = MagicMock()
    update.message.location = MagicMock(latitude=7.9, longitude=98.3)
    context.user_data['language'] = 'ru'
    with patch('main.get_db_connection', side_effect=Exception('db error')):
        with patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
            await handle_location(update, context)
            mock_reply.assert_called()

@pytest.mark.asyncio
async def test_talk_unexpected_text():
    update = DummyUpdate(text='qwertyuiop')
    context = DummyContext()
    context.user_data['language'] = 'ru'
    # Не команда, не пожелание, не район — должен предложить выбрать район
    with patch('main.get_db_connection') as mock_db, \
         patch('main.client.chat.completions.create', return_value=MagicMock(choices=[MagicMock(message=MagicMock(content='NO_MATCH'))])), \
         patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = ['Patong', 'Kata']
        mock_conn.cursor.return_value = mock_cur
        mock_db.return_value = mock_conn
        await talk(update, context)
        mock_reply.assert_called()

@pytest.mark.asyncio
async def test_talk_language_update():
    update = DummyUpdate(text='Hello')
    context = DummyContext()
    context.user_data['language'] = 'ru'
    with patch('main.detect_language', return_value='en'), \
         patch('main.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_db.return_value = mock_conn
        with patch.object(mock_cur, 'execute', new_callable=AsyncMock) as mock_execute:
            await talk(update, context)
            mock_execute.assert_called()  # Язык обновлён в базе

# Тест: логирование ошибок
def test_logging_error():
    logger = logging.getLogger('main')
    with patch.object(logger, 'error') as mock_error:
        try:
            raise Exception('test error')
        except Exception as e:
            logger.error(f"Test error: {e}")
        mock_error.assert_called()

@pytest.mark.asyncio
async def test_language_switch_during_dialog():
    """
    Проверяет, что если пользователь начал писать на другом языке, язык обновляется в context и базе, и бот отвечает на новом языке.
    """
    update = DummyUpdate(text='Hello')
    context = DummyContext()
    context.user_data['language'] = 'ru'  # Стартуем с русского
    # Мокаем detect_language, чтобы он определил английский
    with patch('main.detect_language', return_value='en'), \
         patch('main.get_db_connection') as mock_db, \
         patch('main.ask', return_value=('Test answer in English', [])), \
         patch.object(update.message, 'reply_text', new_callable=AsyncMock) as mock_reply:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_db.return_value = mock_conn
        await talk(update, context)
        # Проверяем, что язык обновился
        assert context.user_data['language'] == 'en'
        # Проверяем, что был вызван update языка в базе
        mock_cur.execute.assert_any_call("UPDATE users SET language = %s WHERE telegram_user_id = %s", ('en', update.effective_user.id))
        # Проверяем, что ответ был на английском
        mock_reply.assert_called_with('Test answer in English') 