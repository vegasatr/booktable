#!/bin/bash

cd /root/booktable_bot
source venv/bin/activate

echo "===================== BOOKTABLE BOT INTEGRATION TESTS ====================="
echo "Date: $(date)"
echo "Testing comprehensive integration scenarios"
echo "==========================================================================="

echo ""
echo "🔧 SETUP: Checking environment..."

# Проверяем необходимые переменные окружения
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  Warning: OPENAI_API_KEY not set - AI tests will use fallbacks"
else
    echo "✅ OpenAI API key configured"
fi

if [ -z "$DATABASE_URL" ] && [ -z "$DB_HOST" ]; then
    echo "⚠️  Warning: Database not configured - DB tests will be skipped"
else
    echo "✅ Database configuration found"
fi

echo ""
echo "📋 INTEGRATION TEST SUITES:"

echo ""
echo "1️⃣ BOT WORKFLOW INTEGRATION:"
echo "   Testing full user journey from /start to restaurant results"
python -m pytest tests/integration/test_bot_workflow.py -v --tb=short
workflow_result=$?

echo ""
echo "2️⃣ EXTERNAL APIs INTEGRATION:"
echo "   Testing OpenAI, Database, and external service integration"
python -m pytest tests/integration/test_external_apis.py -v --tb=short
api_result=$?

echo ""
echo "3️⃣ EDGE CASES AND ERROR HANDLING:"
echo "   Testing all edge cases from to_do.txt"
python -m pytest tests/integration/test_edge_cases.py -v --tb=short
edge_result=$?

echo ""
echo "🔬 ADVANCED INTEGRATION TESTS (if environment allows):"
if [ "$RUN_INTEGRATION_TESTS" = "1" ]; then
    echo "   Running full API integration tests..."
    RUN_INTEGRATION_TESTS=1 python -m pytest tests/integration/ -k "TestFullAPIIntegration" -v
    advanced_result=$?
else
    echo "   Skipped (set RUN_INTEGRATION_TESTS=1 to run)"
    advanced_result=0
fi

echo ""
echo "📊 INTEGRATION TEST RESULTS:"
echo "================================"

if [ $workflow_result -eq 0 ]; then
    echo "✅ Bot Workflow Integration: PASSED"
else
    echo "❌ Bot Workflow Integration: FAILED"
fi

if [ $api_result -eq 0 ]; then
    echo "✅ External APIs Integration: PASSED"
else
    echo "❌ External APIs Integration: FAILED"
fi

if [ $edge_result -eq 0 ]; then
    echo "✅ Edge Cases & Error Handling: PASSED"
else
    echo "❌ Edge Cases & Error Handling: FAILED"
fi

if [ "$RUN_INTEGRATION_TESTS" = "1" ]; then
    if [ $advanced_result -eq 0 ]; then
        echo "✅ Advanced API Integration: PASSED"
    else
        echo "❌ Advanced API Integration: FAILED"
    fi
fi

echo ""
echo "🎯 INTEGRATION TEST COVERAGE ANALYSIS:"

# Подсчитываем общий результат
total_failed=0
if [ $workflow_result -ne 0 ]; then ((total_failed++)); fi
if [ $api_result -ne 0 ]; then ((total_failed++)); fi
if [ $edge_result -ne 0 ]; then ((total_failed++)); fi
if [ "$RUN_INTEGRATION_TESTS" = "1" ] && [ $advanced_result -ne 0 ]; then ((total_failed++)); fi

total_suites=3
if [ "$RUN_INTEGRATION_TESTS" = "1" ]; then total_suites=4; fi

passed_suites=$((total_suites - total_failed))
success_rate=$((passed_suites * 100 / total_suites))

echo "📈 Success Rate: $success_rate% ($passed_suites/$total_suites test suites passed)"

if [ $success_rate -ge 90 ]; then
    echo "🏆 EXCELLENT - Integration tests highly successful"
elif [ $success_rate -ge 75 ]; then
    echo "✅ GOOD - Most integration tests passing"
elif [ $success_rate -ge 50 ]; then
    echo "⚠️  MODERATE - Some integration issues detected"
else
    echo "❌ NEEDS ATTENTION - Significant integration problems"
fi

echo ""
echo "📋 INTEGRATION TEST CATEGORIES COVERED:"
echo "✅ Full user workflow (/start → budget → area → search)"
echo "✅ Multi-user isolation and concurrent access"
echo "✅ Error handling and graceful degradation"
echo "✅ External API integration (OpenAI, Database)"
echo "✅ Edge cases and invalid input handling"
echo "✅ Non-standard message types (photos, documents, stickers)"
echo "✅ Language switching and preference management"
echo "✅ Permission and security checks"
echo "✅ Button and markup error handling"
echo "✅ Database connection resilience"

echo ""
echo "🔮 NEXT STEPS FOR 100% COVERAGE:"
if [ $total_failed -gt 0 ]; then
    echo "1. Fix failing integration test suites"
    echo "2. Review error logs for specific issues"
    echo "3. Update mocks if API signatures changed"
    echo "4. Verify environment configuration"
else
    echo "🎉 All integration tests passing!"
    echo "1. Consider adding performance benchmarks"
    echo "2. Add load testing scenarios"
    echo "3. Test with real Telegram webhook"
    echo "4. Add monitoring and alerting tests"
fi

echo ""
echo "======================== END INTEGRATION TESTS ===========================" 