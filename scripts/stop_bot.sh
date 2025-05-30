#!/bin/bash

# Скрипт остановки BookTable Bot Project

echo "$(date): Stopping BookTable Bot Project..."

# Убиваем процессы ботов
echo "$(date): Stopping bot processes..."
pkill -f "python3 main.py" && echo "$(date): Main bot process killed" || echo "$(date): Main bot process not found"
pkill -f "python3 bt_bookings_bot.py" && echo "$(date): Managers bot process killed" || echo "$(date): Managers bot process not found"

# Ждем завершения процессов
sleep 2

# Принудительно убиваем если остались
pkill -9 -f "python3 main.py" 2>/dev/null
pkill -9 -f "python3 bt_bookings_bot.py" 2>/dev/null

# Убиваем tmux сессию
if tmux has-session -t booktable 2>/dev/null; then
    echo "$(date): Killing tmux session 'booktable'..."
    tmux kill-session -t booktable
    echo "$(date): Tmux session killed"
else
    echo "$(date): Tmux session 'booktable' not found"
fi

# Проверяем что все остановлено
MAIN_BOT_PID=$(pgrep -f "python3 main.py")
MANAGERS_BOT_PID=$(pgrep -f "python3 bt_bookings_bot.py")

if [ -z "$MAIN_BOT_PID" ] && [ -z "$MANAGERS_BOT_PID" ]; then
    echo ""
    echo "✅ BookTable Bot Project остановлен успешно!"
    echo ""
else
    echo ""
    echo "⚠️  Внимание: некоторые процессы могут все еще работать:"
    [ -n "$MAIN_BOT_PID" ] && echo "   🔄 Основной бот: PID $MAIN_BOT_PID"
    [ -n "$MANAGERS_BOT_PID" ] && echo "   📋 Бот менеджеров: PID $MANAGERS_BOT_PID"
    echo ""
fi

echo "$(date): Stop script completed" 