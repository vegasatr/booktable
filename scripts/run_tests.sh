#!/bin/bash

# Скрипт для запуска тестов BookTable Bot
echo "=== BookTable Bot Test Suite ==="
echo "Date: $(date)"

# Переходим в директорию проекта
cd /root/booktable_bot || exit 1

# Активируем виртуальное окружение
source venv/bin/activate || exit 1

# Проверяем, что pytest установлен
if ! command -v pytest &> /dev/null; then
    echo "Installing pytest..."
    pip install pytest pytest-asyncio
fi

# Запускаем тесты с ограничением времени и логированием
echo "Running unit tests..."

# Простые тесты без моков (быстрые)
echo "1. Testing AI core (fallback functions)..."
pytest tests/unit/test_ai_core.py::TestAIGenerate::test_ai_generate_fallback_error_ru -v 2>&1 | tee logs/test_results.log

echo "2. Testing AI core (area detection)..."
pytest tests/unit/test_ai_core.py::TestDetectAreaFromText -v 2>&1 | tee -a logs/test_results.log

echo "3. Testing database functions (mocked)..."
pytest tests/unit/test_database_users.py -v 2>&1 | tee -a logs/test_results.log

# Полный запуск тестов (если нужен)
if [ "$1" = "full" ]; then
    echo "Running full test suite..."
    pytest tests/unit/ -v --tb=short 2>&1 | tee -a logs/test_results.log
fi

echo "=== Test Results ==="
echo "Check logs/test_results.log for detailed output"
echo "Test completed at: $(date)" 