#!/bin/bash

# Скрипт для очистки зависших bash процессов от Cursor
# Решает проблему высокой загрузки CPU

echo "🧹 CLEANUP HUNG PROCESSES"
echo "=========================="

# Проверяем загрузку до очистки
echo "📊 CPU загрузка ДО очистки:"
top -b -n1 | head -3

echo ""
echo "🔍 Ищем зависшие bash процессы..."

# Считаем зависшие процессы
HUNG_COUNT=$(ps aux | grep "/usr/bin/bash" | grep -v grep | wc -l)
echo "Найдено зависших bash процессов: $HUNG_COUNT"

if [ $HUNG_COUNT -gt 0 ]; then
    echo ""
    echo "💀 Убиваем зависшие bash процессы..."
    
    # Мягко убиваем
    ps aux | grep "/usr/bin/bash" | grep -v grep | awk '{print $2}' | xargs -r kill 2>/dev/null || true
    sleep 2
    
    # Проверяем что осталось
    REMAINING=$(ps aux | grep "/usr/bin/bash" | grep -v grep | wc -l)
    
    if [ $REMAINING -gt 0 ]; then
        echo "⚡ Принудительно убиваем оставшиеся процессы..."
        ps aux | grep "/usr/bin/bash" | grep -v grep | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
        sleep 1
    fi
    
    echo "✅ Очистка завершена!"
else
    echo "✅ Зависших процессов не найдено!"
fi

echo ""
echo "🤖 Проверяем состояние ботов:"
ps aux | grep -E "(main.py|bt_bookings_bot.py)" | grep -v grep || echo "❌ Боты не найдены!"

echo ""
echo "📊 CPU загрузка ПОСЛЕ очистки:"
top -b -n1 | head -3

echo ""
echo "�� CLEANUP COMPLETED" 