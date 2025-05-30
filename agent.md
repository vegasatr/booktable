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
8. If user writes "откат" (rollback), run script 'scripts/otkat.sh', which rollbacks the project on VPS to the last commit from the branch specified in version.txt file.
9. **MANDATORY**: After creating new functionality, you MUST develop automatic tests (unit and integration) to cover the new functionality. Functionality without tests is considered incomplete.
10. **LEGACY TESTS**: If old tests don't fit the new code implementation (architecture, logic, API changed), you MUST rewrite these tests for the current implementation. Outdated tests must be updated, not ignored.
11. **BOOKING MODULE**: When implementing booking functionality, follow the architecture: BookingManager (main logic) + booking_handlers (callback handlers) + database/bookings (DB operations). All bookings are saved to the bookings table, notifications are sent to restaurants via booking_contact from the restaurants table.
12. **🗄️ DATABASE SYNCHRONIZATION**: For any changes in production database `booktable` structure (new tables, fields, indexes, triggers) you MUST apply the same changes to test database `booktable_test`. To do this:
    - Update `init_db.sql` if needed
    - Update `scripts/create_test_db.sh` with new test data  
    - Recreate test DB: `sudo scripts/create_test_db.sh`
    - NEVER test on production database - only on `booktable_test`
13. **🚫 MANUAL PUSH PROHIBITION**: Errors in script operation (git_push.sh, start_bot.sh etc.) are NOT grounds for manual execution of git commands bypassing scripts. Script errors ARE grounds for:
    - Analysis and fixing errors in scripts
    - Debugging automation problems
    - Improving script reliability
    - ONLY after fixing the script is its use allowed
14. **📁 FILE ARCHITECTURE**: FORBIDDEN to create files in project root folder except exceptional cases that architecturally require it (e.g., README.md, .env, package.json). File placement rules:
    - Temporary files → `temp/` (create folder if doesn't exist)
    - Documentation → `docs/`
    - Tests → `tests/unit/` or `tests/integration/`
    - Scripts → `scripts/`
    - Source code → `src/`
    - Logs → `logs/`
    - DB configuration → `sql/`
    - ALWAYS place files in the correct folder IMMEDIATELY upon creation, don't postpone
15. **🔧 DATABASE OPERATIONS**: FORBIDDEN to create new specialized scripts for database operations. Use ONLY the universal tool `scripts/db_tool.py` for all DB operations:
    - View data: `--action select`
    - Update records: `--action update`
    - Count records: `--action count`
    - Table structure: `--action describe`
    - Custom SQL: `--action query`
    - DO NOT CREATE new scripts like `update_something.py`, `check_something.py` etc.
    - Examples in `scripts/README.md`

---

## 🗂 Structure Rules

- All scripts must go into `scripts/`.
- All logs must go into `logs/`.
- All documentation must go into `docs/`.
- All temporary files must go into `temp/`.
- Do not change the root structure unless required.
- Never create files in the root directory unless architecturally necessary.

---

## ⚠️ Forbidden Actions (Even If User Asks)

- ❌ No `git push`, `commit`, `add`, `merge`
- ❌ No manual bot restarts
- ❌ No unauthorized script or file creation
- ❌ No assumptions or dummy code
- ❌ No files in root directory (use proper folders)

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
- Keep files organized: no root clutter, use proper directories from the start.
- Use only `scripts/db_tool.py` for all database operations.
