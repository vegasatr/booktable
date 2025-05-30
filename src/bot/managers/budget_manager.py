"""
Модуль для управления бюджетом
"""
import logging
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction

from ..ai.translation import translate_message
from .user_state import UserState

logger = logging.getLogger(__name__)

class BudgetManager:
    """Централизованное управление бюджетом"""
    
    @staticmethod
    async def show_budget_selection(update, context, return_context=None):
        """Показывает выбор бюджета с возможностью возврата"""
        keyboard = [
            [
                InlineKeyboardButton("$", callback_data="budget_1"),
                InlineKeyboardButton("$$", callback_data="budget_2"),
                InlineKeyboardButton("$$$", callback_data="budget_3"),
                InlineKeyboardButton("$$$$", callback_data="budget_4")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Сохраняем контекст возврата
        if return_context:
            context.user_data['return_context'] = return_context
        
        state = UserState(context)
        message = await translate_message('budget_question', state.language)
        
        chat_id = update.effective_chat.id
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)
    
    @staticmethod
    async def handle_budget_change(update, context, new_budget):
        """Обрабатывает смену бюджета и возвращает пользователя в правильное место"""
        query = update.callback_query
        await query.answer()
        await query.message.delete()
        
        logger.info(f"[BUDGET_MANAGER] Starting budget change to: {new_budget}")
        
        # Удаляем приветственное сообщение, если оно есть
        welcome_message_id = context.user_data.get('welcome_message_id')
        if welcome_message_id:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=welcome_message_id)
                logger.info(f"[BUDGET_MANAGER] Deleted welcome message {welcome_message_id}")
                context.user_data.pop('welcome_message_id', None)
            except Exception as e:
                logger.error(f"[BUDGET_MANAGER] Error deleting welcome message {welcome_message_id}: {e}")
        
        state = UserState(context)
        context._user_id = update.effective_user.id  # Сохраняем для UserState
        state.set_budget(new_budget)
        
        logger.info(f"[BUDGET_MANAGER] Budget set to: {new_budget}")
        logger.info(f"[BUDGET_MANAGER] Current state - budget: {state.budget}, location: {state.location}")
        
        # ОБЯЗАТЕЛЬНО показываем сообщение о сохранении выбора с эффектом печатающей машинки
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        await asyncio.sleep(0.5)  # Короткий эффект для короткой фразы
        budget_saved_msg = await translate_message('budget_saved', state.language)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=budget_saved_msg)
        
        # Получаем контекст возврата
        return_context = context.user_data.get('return_context')
        logger.info(f"[BUDGET_MANAGER] Return context: {return_context}")
        
        if return_context and return_context.get('screen') == 'restaurant_list':
            # Возвращаемся к списку ресторанов с новым бюджетом
            logger.info("[BUDGET_MANAGER] Returning to restaurant list with new budget")
            from .restaurant_display import show_restaurants
            await show_restaurants(update, context)
        elif state.is_ready_for_restaurants():
            # Если есть и бюджет и локация - показываем рестораны
            logger.info("[BUDGET_MANAGER] State ready for restaurants, showing restaurants")
            from .restaurant_display import show_restaurants
            await show_restaurants(update, context)
        else:
            # Иначе переходим к выбору локации
            logger.info("[BUDGET_MANAGER] State not ready, showing location selection")
            from .location_manager import LocationManager
            await LocationManager.show_location_selection(update, context) 