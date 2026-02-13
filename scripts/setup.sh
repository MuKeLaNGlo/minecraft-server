#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

if [ ! -f .env ]; then
    echo "Создаю .env из .env.example..."
    cp .env.example .env
    echo ""
    echo "Отредактируй .env файл перед запуском:"
    echo "  - BOT_TOKEN: токен Telegram бота от @BotFather"
    echo "  - SUPER_ADMIN_ID: твой Telegram ID (узнать: @userinfobot)"
    echo "  - RCON_PASSWORD: пароль для RCON (придумай надёжный)"
    echo ""
    echo "После настройки .env запусти: make build"
else
    echo ".env уже существует."
fi

mkdir -p server/data backups bot/data
echo "Директории созданы."
