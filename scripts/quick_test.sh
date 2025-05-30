#!/bin/bash

cd /root/booktable_bot
source venv/bin/activate

echo "=== Quick Test Run ==="

# Тестируем AI функции (работают)
echo "Testing AI functions..."
pytest tests/unit/test_ai_core.py -q --tb=no

# Тестируем исправленные database функции
echo "Testing database functions..."
pytest tests/unit/test_database_users.py -q --tb=no

# Тестируем переводы
echo "Testing translation functions..."
pytest tests/unit/test_ai_translation.py -q --tb=no

echo "=== Quick Test Completed ===" 