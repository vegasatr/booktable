"""
Централизованная система управления состоянием пользователя
"""
from ..database.users import save_user_preferences

class UserState:
    """Централизованное управление состоянием пользователя"""
    
    def __init__(self, context):
        self.context = context
        self.user_data = context.user_data
    
    @property
    def language(self):
        return self.user_data.get('language', 'ru')
    
    @property
    def budget(self):
        return self.user_data.get('budget')
    
    @property
    def location(self):
        return self.user_data.get('location')
    
    @property
    def current_screen(self):
        """Текущий экран/состояние пользователя"""
        return self.user_data.get('current_screen', 'start')
    
    def set_budget(self, budget):
        """Устанавливает бюджет и сохраняет в базу"""
        self.user_data['budget'] = budget
        # Сохраняем в базу данных
        user_id = self.context._user_id if hasattr(self.context, '_user_id') else None
        if user_id:
            save_user_preferences(user_id, {'budget': budget})
    
    def set_location(self, location):
        """Устанавливает локацию"""
        self.user_data['location'] = location
    
    def set_screen(self, screen_name):
        """Устанавливает текущий экран"""
        self.user_data['current_screen'] = screen_name
    
    def is_ready_for_restaurants(self):
        """Проверяет, готов ли пользователь для показа ресторанов"""
        return bool(self.budget and self.location)
    
    def get_context_for_return(self):
        """Возвращает контекст для возврата на предыдущий экран"""
        return {
            'screen': self.current_screen,
            'budget': self.budget,
            'location': self.location,
            'language': self.language
        } 