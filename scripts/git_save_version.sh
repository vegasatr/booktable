#!/bin/bash

if [ -z "$1" ]; then
  echo "Использование: $0 <version>"
  exit 1
fi

VERSION=$1
MESSAGE="Версия $VERSION: обновлена стандартная фраза для location_send, исправлена интеграция Deepl, улучшено логирование"

git add .
git commit -m "$MESSAGE"
git tag v$VERSION
git push
git push --tags

echo "Версия $VERSION сохранена и отправлена в git." 