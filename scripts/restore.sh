#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -z "${1:-}" ]; then
    echo "Использование: $0 <имя_файла_бэкапа>"
    echo ""
    echo "Доступные бэкапы:"
    ls -lh "$PROJECT_DIR/backups/"*.tar.gz 2>/dev/null || echo "  Бэкапов нет."
    exit 1
fi

BACKUP_FILE="$PROJECT_DIR/backups/$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Файл не найден: $BACKUP_FILE"
    exit 1
fi

echo "Останавливаю сервер..."
cd "$PROJECT_DIR"
docker compose stop minecraft

echo "Восстанавливаю из бэкапа: $1"
tar -xzf "$BACKUP_FILE" -C "$PROJECT_DIR/server/data/"

echo "Запускаю сервер..."
docker compose start minecraft

echo "Готово! Сервер запущен с восстановленным миром."
