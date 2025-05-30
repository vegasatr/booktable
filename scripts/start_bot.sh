#!/bin/bash

# Настройка логирования
LOG_FILE="logs/bot_startup.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2> >(tee -a "$LOG_FILE" >&2)

echo "$(date): Starting BookTable Bot Project (Main + Managers)"

# Загрузка переменных окружения из .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
    echo "$(date): .env loaded"
fi

# Функция для проверки статуса
check_status() {
    if [ $? -eq 0 ]; then
        echo "$(date): $1 - OK"
    else
        echo "$(date): $1 - FAILED"
        exit 1
    fi
}

# Проверяем, существует ли виртуальное окружение
if [ ! -d "venv" ]; then
    echo "$(date): Virtual environment not found. Creating..."
    python3 -m venv venv
    check_status "Creating virtual environment"
    
    source venv/bin/activate
    check_status "Activating virtual environment"
    
    pip install --upgrade pip
    check_status "Upgrading pip"
    
    pip install -r requirements.txt
    check_status "Installing requirements"
else
    echo "$(date): Virtual environment found"
    source venv/bin/activate
    check_status "Activating virtual environment"
fi

# Убиваем все процессы ботов
echo "$(date): Stopping existing bot processes"
pkill -f main.py || true
pkill -f bt_bookings_bot.py || true
sleep 2  # Даём время на корректное завершение
pkill -9 -f main.py || true  # Принудительно убиваем, если остались
pkill -9 -f bt_bookings_bot.py || true

# Убиваем старую tmux-сессию, если она есть
if tmux has-session -t booktable 2>/dev/null; then
    echo "$(date): Killing existing tmux session"
    tmux kill-session -t booktable
    check_status "Killing tmux session"
fi

# Создаем новую сессию tmux для проекта BookTable
echo "$(date): Creating new tmux session 'booktable'"
tmux new-session -d -s booktable -n main_bot
check_status "Creating tmux session"

# Окно 1: Основной бот (main.py)
echo "$(date): Starting main bot in window 'main_bot'"
tmux send-keys -t booktable:main_bot 'cd /root/booktable_bot' C-m
sleep 1
tmux send-keys -t booktable:main_bot 'source venv/bin/activate' C-m
sleep 1
tmux send-keys -t booktable:main_bot 'python3 main.py' C-m
check_status "Starting main bot"

# Создаем второе окно для бота менеджеров
echo "$(date): Creating window for managers bot"
tmux new-window -t booktable -n managers_bot
check_status "Creating managers bot window"

# Окно 2: Бот менеджеров (bt_bookings_bot.py)
echo "$(date): Starting managers bot in window 'managers_bot'"
tmux send-keys -t booktable:managers_bot 'cd /root/booktable_bot' C-m
sleep 1
tmux send-keys -t booktable:managers_bot 'source venv/bin/activate' C-m
sleep 1
tmux send-keys -t booktable:managers_bot 'python3 bt_bookings_bot.py' C-m
check_status "Starting managers bot"

# Переключаемся обратно на основного бота
tmux select-window -t booktable:main_bot

# Проверяем, что оба бота запустились
sleep 8  # Даём время на запуск
echo "$(date): Checking bot processes..."

MAIN_BOT_PID=$(pgrep -f "python3 main.py")
MANAGERS_BOT_PID=$(pgrep -f "python3 bt_bookings_bot.py")

if [ -n "$MAIN_BOT_PID" ]; then
    echo "$(date): Main bot started successfully (PID: $MAIN_BOT_PID)"
else
    echo "$(date): Main bot failed to start"
    echo "$(date): Checking main bot tmux output:"
    tmux capture-pane -pt booktable:main_bot
    exit 1
fi

if [ -n "$MANAGERS_BOT_PID" ]; then
    echo "$(date): Managers bot started successfully (PID: $MANAGERS_BOT_PID)"
else
    echo "$(date): Managers bot failed to start"
    echo "$(date): Checking managers bot tmux output:"
    tmux capture-pane -pt booktable:managers_bot
    exit 1
fi

echo ""
echo "🎉 BookTable Bot Project запущен успешно!"
echo ""
echo "📋 Статус ботов:"
echo "   ✅ Основной бот (main.py): PID $MAIN_BOT_PID"
echo "   ✅ Бот менеджеров (bt_bookings_bot.py): PID $MANAGERS_BOT_PID"
echo ""
echo "🔧 Управление tmux сессией:"
echo "   📺 Подключиться: tmux attach -t booktable"
echo "   🔄 Основной бот: tmux select-window -t booktable:main_bot"
echo "   📋 Бот менеджеров: tmux select-window -t booktable:managers_bot"
echo "   ⛔ Остановить все: tmux kill-session -t booktable"
echo ""
echo "📊 Логи:"
echo "   📝 Основной бот: tail -f logs/bot.log"
echo "   📝 Бот менеджеров: tail -f logs/bookings_bot.log"
echo "   📝 Запуск: tail -f logs/bot_startup.log"
echo ""

echo "$(date): BookTable Bot Project startup completed successfully" 