#!/bin/bash

# Убиваем все процессы бота
pkill -f main.py
sleep 2  # Даём время на корректное завершение
pkill -9 -f main.py  # Принудительно убиваем, если остались

# Убиваем старую tmux-сессию, если она есть
if tmux has-session -t booktable_bot 2>/dev/null; then
  tmux kill-session -t booktable_bot
fi

# Создаем новую сессию tmux и запускаем бота
tmux new-session -d -s booktable_bot
tmux send-keys -t booktable_bot 'cd /root/booktable_bot && source venv/bin/activate && python3 main.py' C-m 