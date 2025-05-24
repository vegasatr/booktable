# Agent Instructions for Cursor AI

## 🔒 Rules of Engagement

1. Only AI develops the code. The user is not a programmer.
2. The user defines tasks and verifies results. All code implementation is AI's responsibility.
3. Do not ask the user to review, edit, or understand the code.
4. Never ask the user to write or modify code.
5. After making any change, always restart the bot using the provided restart script — without user reminder.
6. Debugging is AI's responsibility. Use logging immediately to identify and resolve issues.
7. Before doing anything, read and understand the code in `main.py` and all relevant project files.
8. To test database access, use `scripts/check_db.py`. Use it for diagnostics if needed.
9. Never push to the remote Git repository unless explicitly instructed by the user. Git operations are performed only through a dedicated script that creates a new version and a new branch.

## 🧠 AI Behavior Requirements

- Work in Cursor Agent Mode.
- Always auto-apply your code edits (`autoAcceptAiEdits = true`).
- Automatically run scripts after making changes (`autoRunOnEdit = true`).
- Use model `gpt-4o` if available.
- Do not change project structure unless strictly required.
- If logging is used in the project, prefer `logger.debug` instead of `console.log`.

## ⚠️ Execution Restrictions

- Do not run `git push`, `git commit`, or `git merge` manually. Use the project script only.
- Do not create or replace scripts related to startup, database, or logs — reuse what exists.
- All scripts must go inside the `scripts/` folder.
- All logs must be saved inside the `logs/` folder.

## 🚫 Do Not

- Do not treat the user as a developer.
- Avoid phrases like "you can check", "let’s edit together", "you should change".
- Do not generate boilerplate code unless the user asks.
- Do not create or modify files unrelated to the current task.

## ✅ Validation

- Before restarting the bot, ensure all edits are saved.
- Before interacting with the database, always run `check_db.py`.
- Log all changes and actions to console when appropriate.
