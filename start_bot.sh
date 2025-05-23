#!/bin/bash

# Настройка логирования
LOG_FILE="bot_startup.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2> >(tee -a "$LOG_FILE" >&2)

echo "$(date): Starting bot startup script"

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

# Убиваем все процессы бота
echo "$(date): Stopping existing bot processes"
pkill -f main.py || true
sleep 2  # Даём время на корректное завершение
pkill -9 -f main.py || true  # Принудительно убиваем, если остались

# Убиваем старую tmux-сессию, если она есть
if tmux has-session -t mybot 2>/dev/null; then
    echo "$(date): Killing existing tmux session"
    tmux kill-session -t mybot
    check_status "Killing tmux session"
fi

# Создаем новую сессию tmux и запускаем бота
echo "$(date): Creating new tmux session"
tmux new-session -d -s mybot
check_status "Creating tmux session"

# Загружаем переменные окружения из .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
    echo "$(date): .env loaded"
fi

# Запускаем бота
echo "$(date): Starting bot"
tmux send-keys -t mybot 'cd /root/booktable_bot' C-m
sleep 1
tmux send-keys -t mybot 'source venv/bin/activate' C-m
sleep 1
tmux send-keys -t mybot 'python3 main.py' C-m
check_status "Sending start command to tmux"

# Проверяем, что бот запустился
sleep 5  # Даём время на запуск
if pgrep -f "python3 main.py" > /dev/null; then
    echo "$(date): Bot started successfully"
else
    echo "$(date): Bot failed to start"
    # Проверяем вывод в tmux
    echo "$(date): Checking tmux output:"
    tmux capture-pane -pt mybot
    exit 1
fi

echo "$(date): Bot startup script completed successfully" 