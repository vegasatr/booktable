#!/bin/bash

# Убиваем все процессы бота
pkill -f main.py
sleep 2  # Даём время на корректное завершение
pkill -9 -f main.py  # Принудительно убиваем, если остались

# Убиваем старую tmux-сессию, если она есть
if tmux has-session -t mybot 2>/dev/null; then
  tmux kill-session -t mybot
fi

# Создаем новую сессию tmux и запускаем бота
tmux new-session -d -s mybot
tmux send-keys -t mybot 'cd /root/booktable_bot && . venv/bin/activate && python3 main.py' C-m 