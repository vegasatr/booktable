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

# Запрашиваем тип изменений
echo "Select type of changes:"
echo "1) Bug fix (patch version)"
echo "2) New feature (minor version)"
echo "3) Breaking changes (major version)"
read -p "Enter choice (1-3): " choice

# Обновляем версию
IFS='.' read -r major minor patch <<< "$CURRENT_VERSION"
case $choice in
    1)
        patch=$((patch + 1))
        ;;
    2)
        minor=$((minor + 1))
        patch=0
        ;;
    3)
        major=$((major + 1))
        minor=0
        patch=0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

NEW_VERSION="$major.$minor.$patch"
echo "New version will be: $NEW_VERSION"

# Запрашиваем описание изменений
read -p "Enter commit message: " commit_message

# Обновляем версию в файле
echo "$NEW_VERSION" > version.txt

# Добавляем изменения в git
git add .
git commit -m "$commit_message (v$NEW_VERSION)"
git push origin main

echo "Changes pushed to GitHub with version $NEW_VERSION" 