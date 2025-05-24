#!/bin/bash

# Применяем SQL-скрипт
PGPASSWORD=postgres psql -h /var/run/postgresql -U root -d booktable -f sql/update_users_table.sql

echo "Database structure updated successfully" 