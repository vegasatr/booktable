#!/bin/bash

# Убиваем существующий процесс бота
pkill -f gpt-bot.py

# Убиваем старую tmux-сессию, если она есть
if tmux has-session -t booktable_bot 2>/dev/null; then
  tmux kill-session -t booktable_bot
fi

# Создаем новую сессию tmux и запускаем бота
tmux new-session -d -s booktable_bot
tmux send-keys -t booktable_bot 'cd /root/booktable_bot && source venv/bin/activate && python3 main.py' C-m

# Activate virtual environment
source venv/bin/activate

# Run the bot
python main.py 