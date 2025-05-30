# Настройка сервера для BookTable Bot

## 🕐 Автосинхронизация времени

### Важность точного времени

Точное время критически важно для:
- **Логирования**: Корректные временные метки в логах
- **Бронирования**: Точное время создания и управления бронированиями
- **Уведомления**: Своевременная отправка уведомлений ресторанам
- **Базы данных**: Правильные timestamp в PostgreSQL

### Автоматическая настройка

Запустите скрипт автоматической настройки:

```bash
chmod +x scripts/setup_time_sync.sh
scripts/setup_time_sync.sh
```

### Ручная настройка

Если нужна ручная настройка:

1. **Установка часового пояса:**
```bash
sudo timedatectl set-timezone Asia/Bangkok
```

2. **Включение NTP синхронизации:**
```bash
sudo timedatectl set-ntp true
```

3. **Настройка NTP серверов:**
```bash
sudo mkdir -p /etc/systemd/timesyncd.conf.d/
sudo nano /etc/systemd/timesyncd.conf.d/booktable.conf
```

Содержимое файла:
```ini
[Time]
NTP=pool.ntp.org time.nist.gov time.cloudflare.com
FallbackNTP=ntp.ubuntu.com 0.ubuntu.pool.ntp.org 1.ubuntu.pool.ntp.org
RootDistanceMaxSec=5
PollIntervalMinSec=32
PollIntervalMaxSec=2048
```

4. **Перезапуск службы:**
```bash
sudo systemctl restart systemd-timesyncd
```

### Проверка статуса

```bash
# Общий статус
timedatectl status

# Статус службы синхронизации
systemctl status systemd-timesyncd

# Текущее время
date
```

### Ожидаемый результат

```
               Local time: Fri 2025-05-30 20:12:23 +07
           Universal time: Fri 2025-05-30 13:12:23 UTC
                 RTC time: Fri 2025-05-30 13:12:24
                Time zone: Asia/Bangkok (+07, +0700)
System clock synchronized: yes
              NTP service: active
          RTC in local TZ: no
```

## 🔧 Системные требования

### Операционная система
- Ubuntu 20.04+ LTS
- Python 3.10+
- PostgreSQL 13+

### Пакеты системы
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv postgresql postgresql-contrib tmux git curl
```

### Настройка PostgreSQL
```bash
sudo -u postgres createuser --interactive
sudo -u postgres createdb booktable
sudo -u postgres createdb booktable_test
```

### Виртуальное окружение Python
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 🛡️ Безопасность

### Firewall
```bash
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
```

### Обновления системы
```bash
sudo apt update && sudo apt upgrade -y
sudo apt autoremove -y
```

## 📊 Мониторинг

### Логи системы
```bash
# Логи сервиса времени
journalctl -u systemd-timesyncd -f

# Системные логи
tail -f /var/log/syslog
```

### Автозапуск бота
Добавить в crontab для автоматического запуска после перезагрузки:
```bash
@reboot cd /root/booktable_bot && scripts/start_bot.sh
``` 