#!/bin/bash

# Скрипт проверки статуса BookTable Bot Project

echo "📊 BookTable Bot Project - Статус системы"
echo "=========================================="
echo ""

# Проверяем процессы ботов
echo "🤖 Статус процессов:"
MAIN_BOT_PID=$(pgrep -f "python3 main.py")
MANAGERS_BOT_PID=$(pgrep -f "python3 bt_bookings_bot.py")

if [ -n "$MAIN_BOT_PID" ]; then
    echo "   ✅ Основной бот (main.py): Работает (PID: $MAIN_BOT_PID)"
else
    echo "   ❌ Основной бот (main.py): Не запущен"
fi

if [ -n "$MANAGERS_BOT_PID" ]; then
    echo "   ✅ Бот менеджеров (bt_bookings_bot.py): Работает (PID: $MANAGERS_BOT_PID)"
else
    echo "   ❌ Бот менеджеров (bt_bookings_bot.py): Не запущен"
fi

echo ""

# Проверяем tmux сессию
echo "📺 Статус tmux сессии:"
if tmux has-session -t booktable 2>/dev/null; then
    echo "   ✅ Сессия 'booktable': Активна"
    
    # Проверяем окна
    WINDOWS=$(tmux list-windows -t booktable 2>/dev/null)
    if echo "$WINDOWS" | grep -q "main_bot"; then
        echo "   ✅ Окно 'main_bot': Существует"
    else
        echo "   ❌ Окно 'main_bot': Не найдено"
    fi
    
    if echo "$WINDOWS" | grep -q "managers_bot"; then
        echo "   ✅ Окно 'managers_bot': Существует"
    else
        echo "   ❌ Окно 'managers_bot': Не найдено"
    fi
else
    echo "   ❌ Сессия 'booktable': Не найдена"
fi

echo ""

# Проверяем логи
echo "📝 Статус логов:"
LOG_FILES=("logs/bot.log" "logs/bookings_bot.log" "logs/bot_startup.log")

for log_file in "${LOG_FILES[@]}"; do
    if [ -f "$log_file" ]; then
        SIZE=$(du -h "$log_file" | cut -f1)
        LINES=$(wc -l < "$log_file")
        echo "   ✅ $log_file: $SIZE ($LINES строк)"
    else
        echo "   ❌ $log_file: Не найден"
    fi
done

echo ""

# Проверяем базу данных
echo "🗄️  Статус базы данных:"
if [ -f "restaurants.db" ]; then
    SIZE=$(du -h "restaurants.db" | cut -f1)
    echo "   ✅ restaurants.db: $SIZE"
else
    echo "   ❌ restaurants.db: Не найдена"
fi

echo ""

# Проверяем виртуальное окружение
echo "🐍 Статус виртуального окружения:"
if [ -d "venv" ]; then
    echo "   ✅ venv: Существует"
    if [ -f "venv/bin/python3" ]; then
        PYTHON_VERSION=$(venv/bin/python3 --version 2>&1)
        echo "   ✅ Python: $PYTHON_VERSION"
    else
        echo "   ❌ Python: Не найден в venv"
    fi
else
    echo "   ❌ venv: Не найдено"
fi

echo ""

# Проверяем сетевое подключение
echo "🌐 Статус сети:"
if ping -c 1 api.telegram.org > /dev/null 2>&1; then
    echo "   ✅ Telegram API: Доступен"
else
    echo "   ❌ Telegram API: Недоступен"
fi

echo ""

# Итоговый статус
echo "📋 Итоговый статус:"
ISSUES=0

[ -z "$MAIN_BOT_PID" ] && ((ISSUES++))
[ -z "$MANAGERS_BOT_PID" ] && ((ISSUES++))
! tmux has-session -t booktable 2>/dev/null && ((ISSUES++))
[ ! -f "restaurants.db" ] && ((ISSUES++))
[ ! -d "venv" ] && ((ISSUES++))

if [ $ISSUES -eq 0 ]; then
    echo "   🎉 Все системы работают нормально!"
    echo ""
    echo "🔧 Управление:"
    echo "   📺 Подключиться: tmux attach -t booktable"
    echo "   🔄 Основной бот: tmux select-window -t booktable:main_bot"
    echo "   📋 Бот менеджеров: tmux select-window -t booktable:managers_bot"
else
    echo "   ⚠️  Обнаружено проблем: $ISSUES"
    echo "   🔧 Попробуйте перезапустить: ./scripts/start_bot.sh"
fi

echo "" 