#!/bin/bash

# Скрипт для загрузки изменений на GitHub
# Правила версионирования:
# - Первое число (1.x.x) - мажорная версия, меняется при несовместимых изменениях
# - Второе число (x.1.x) - минорная версия, меняется при добавлении новой функциональности
# - Третье число (x.x.1) - патч-версия, меняется при исправлении ошибок
#
# Примеры:
# - 1.0.0 -> 1.0.1 - исправление ошибок
# - 1.0.1 -> 1.1.0 - добавление новых функций
# - 1.1.0 -> 2.0.0 - несовместимые изменения
#
# Формат коммитов:
# - Fix: <описание> - для исправлений ошибок
# - Add: <описание> - для добавления новых функций
# - Update: <описание> - для обновления существующих функций
# - Remove: <описание> - для удаления функциональности
# - Refactor: <описание> - для рефакторинга кода

# Читаем текущую версию
CURRENT_VERSION=$(cat version.txt)
echo "Current version: $CURRENT_VERSION"

# Автоматически обновляем версию
IFS='.' read -r major minor patch <<< "$CURRENT_VERSION"
patch=$((patch + 1))  # Всегда увеличиваем патч-версию

NEW_VERSION="$major.$minor.$patch"
echo "New version will be: $NEW_VERSION"

# Формируем описание изменений
commit_message="Automated update: changes made in version $NEW_VERSION"

# Обновляем версию в файле
echo "$NEW_VERSION" > version.txt

# Добавляем изменения в git
git add .
git commit -m "$commit_message (v$NEW_VERSION)"

# Создаем новую ветку с номером версии
BRANCH_NAME="v$NEW_VERSION"
git checkout -b "$BRANCH_NAME"

git push origin "$BRANCH_NAME"

echo "Changes pushed to GitHub with version $NEW_VERSION" 