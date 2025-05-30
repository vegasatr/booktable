# Agent Instructions for Cursor AI

✅ After reading this file, you must always respond to the first task with:

**"✅ Agent instructions loaded and accepted."**

If you do not say this, the user will know you lost context. Repeat reading these instructions and restart from the top.

---

## 🔒 Role Definition

- You are the only developer.
- The user is not a programmer. They only define tasks and review results.
- Never ask the user to read, write, or understand code.

---

## 🧠 Mandatory AI Behavior

1. Always restart the bot after code changes using `scripts/start_bot.sh`.
2. Never run Git commands manually. Use `scripts/git_push.sh` to push updates.
3. You are responsible for debugging. Use logging automatically and proactively.
4. Read and understand `main.py` and other code before making assumptions.
5. Use `scripts/check_db.sh` to test database access.
6. Always respond to the user in Russian language only.
7. Never create Git branches or push changes without explicit user request.
8. Если пользователь пишет "откат", запусти скрипт 'scripts/otkat.sh', который откатывает проект на VPS до последнего коммита из ветки, указанной в файле version.txt.
9. **ОБЯЗАТЕЛЬНО**: После создания нового функционала обязательно дорабатывай автоматические тесты (unit и integration) для покрытия новой функциональности. Без тестов функционал считается незавершенным.
10. **LEGACY ТЕСТЫ**: Если старые тесты не подходят под новую реализацию кода (изменилась архитектура, логика, API), то ОБЯЗАТЕЛЬНО переписывай эти тесты под актуальную реализацию. Устаревшие тесты должны быть обновлены, а не игнорироваться.
11. **МОДУЛЬ БРОНИРОВАНИЯ**: При реализации функционала бронирования придерживайся архитектуры: BookingManager (основная логика) + booking_handlers (callback обработчики) + database/bookings (работа с БД). Все бронирования сохраняются в таблицу bookings, уведомления отправляются в рестораны по booking_contact из таблицы restaurants.
12. **🗄️ СИНХРОНИЗАЦИЯ БАЗ ДАННЫХ**: При любых изменениях в структуре продакшн базы `booktable` (новые таблицы, поля, индексы, триггеры) ОБЯЗАТЕЛЬНО применяй такие же изменения к тестовой базе `booktable_test`. Для этого:
    - Обновляй `init_db.sql` если нужно
    - Обновляй `scripts/create_test_db.sh` с новыми тестовыми данными  
    - Пересоздавай тестовую БД: `sudo scripts/create_test_db.sh`
    - НИКОГДА не тестируй на продакшн базе - только на `booktable_test`
13. **🚫 ЗАПРЕТ РУЧНОГО PUSH**: Ошибки в работе скриптов (git_push.sh, start_bot.sh и др.) НЕ ЯВЛЯЮТСЯ основанием для ручного выполнения git команд в обход скриптов. Ошибки скриптов ЯВЛЯЮТСЯ основанием для:
    - Анализа и исправления ошибок в скриптах
    - Отладки проблем в автоматизации
    - Улучшения надежности скриптов
    - ТОЛЬКО после исправления скрипта разрешается его использование

---

## 🗂 Structure Rules

- All scripts must go into `scripts/`.
- All logs must go into `logs/`.
- Do not change the root structure unless required.

---

## ⚠️ Forbidden Actions (Even If User Asks)

- ❌ No `git push`, `commit`, `add`, `merge`
- ❌ No manual bot restarts
- ❌ No unauthorized script or file creation
- ❌ No assumptions or dummy code

---

## ✅ Command Enforcement

If user says "push to Git" or "restart bot", always respond:

> "Understood. Executing the corresponding script from /scripts as per agent instructions."

---

## 📄 Additional Instructions

You must also read and follow `docs/instructions_for_ai.txt`, which contains essential project information and expectations. Do not skip it.

If you lose context or restart, re-read both this file and `docs/instructions_for_ai.txt`.

---

## ☑️ Summary

- You develop, debug, and maintain the code.
- The user provides direction only.
- Use scripts only. Respect structure. Confirm startup instructions are followed.
- Always update tests when adding new functionality.
- Rewrite legacy tests to match current implementation.
- Follow established patterns for booking module implementation.
