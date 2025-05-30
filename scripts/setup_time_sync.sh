#!/bin/bash

# Скрипт настройки автосинхронизации времени для BookTable Bot
# Обеспечивает точное время для логов и бронирований

echo "🕐 Настройка автосинхронизации времени..."

# Проверяем статус systemd-timesyncd
echo "📋 Текущий статус синхронизации:"
timedatectl status

# Устанавливаем часовой пояс Таиланда (Bangkok)
echo "🌏 Устанавливаем часовой пояс Asia/Bangkok..."
sudo timedatectl set-timezone Asia/Bangkok

# Включаем автоматическую синхронизацию времени
echo "⏰ Включаем NTP синхронизацию..."
sudo timedatectl set-ntp true

# Настраиваем дополнительные NTP серверы для надежности
echo "🌐 Настраиваем NTP серверы..."
sudo mkdir -p /etc/systemd/timesyncd.conf.d/

# Создаем конфигурацию с несколькими надежными NTP серверами
cat << EOF | sudo tee /etc/systemd/timesyncd.conf.d/booktable.conf
[Time]
NTP=pool.ntp.org time.nist.gov time.cloudflare.com
FallbackNTP=ntp.ubuntu.com 0.ubuntu.pool.ntp.org 1.ubuntu.pool.ntp.org
RootDistanceMaxSec=5
PollIntervalMinSec=32
PollIntervalMaxSec=2048
EOF

# Перезапускаем службу синхронизации
echo "🔄 Перезапускаем службу синхронизации времени..."
sudo systemctl restart systemd-timesyncd

# Ждем синхронизации
echo "⏳ Ожидаем синхронизации..."
sleep 5

# Проверяем результат
echo "✅ Результат настройки:"
timedatectl status

echo ""
echo "🎉 Автосинхронизация времени настроена!"
echo "📝 Конфигурация сохранена в /etc/systemd/timesyncd.conf.d/booktable.conf"
echo "🔍 Для проверки статуса используйте: timedatectl status" 