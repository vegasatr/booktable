#!/bin/bash

# BookTable Bot Test Suite

echo "=== BookTable Bot Test Suite ==="
echo "Date: $(date)"

# Clear previous test results log
: > logs/test_results.log

echo "Running unit tests..."

# AI Core tests
echo "1. Testing AI core (fallback functions)..."
python -m pytest tests/unit/test_ai_core.py::TestAIGenerate::test_ai_generate_fallback_error_ru -v 2>&1 | tee -a logs/test_results.log

# AI Core area detection tests
echo "2. Testing AI core (area detection)..."
python -m pytest tests/unit/test_ai_core.py::TestDetectAreaFromText -v 2>&1 | tee -a logs/test_results.log

# Database tests (mocked)
echo "3. Testing database functions (mocked)..."
python -m pytest tests/unit/test_database_users.py -v 2>&1 | tee -a logs/test_results.log

# Booking module tests
echo "4. Testing booking notifications..."
python -m pytest tests/unit/test_booking_notifications.py -v 2>&1 | tee -a logs/test_results.log

echo "=== Test Results ==="
echo "Check logs/test_results.log for detailed output"
echo "Test completed at: $(date)"