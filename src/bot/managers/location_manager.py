"""
Модуль для управления локацией
"""
import logging
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction

from .user_state import UserState

logger = logging.getLogger(__name__)

class LocationManager:
    """Управление выбором локации"""
    
    @staticmethod
    async def show_location_selection(update, context):
        """Показывает выбор локации"""
        keyboard = [[
            InlineKeyboardButton("РЯДОМ", callback_data='location_near'),
            InlineKeyboardButton("РАЙОН", callback_data='location_area'),
            InlineKeyboardButton("ВЕЗДЕ", callback_data='location_any')
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        state = UserState(context)
        message = "Подберу для Вас отличный ресторан! Поискать поблизости, в другом районе или в любом месте на Пхукете?"
        
        chat_id = update.effective_chat.id
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup) 