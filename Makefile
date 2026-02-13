.PHONY: up down restart build logs logs-mc logs-bot backup shell-mc shell-bot status

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

build:
	docker compose up -d --build

logs:
	docker compose logs -f

logs-mc:
	docker compose logs -f minecraft

logs-bot:
	docker compose logs -f bot

status:
	docker compose ps

shell-mc:
	docker compose exec minecraft bash

shell-bot:
	docker compose exec bot bash

backup:
	docker compose exec bot python -c "import asyncio; from minecraft.backup_manager import backup_manager; asyncio.run(backup_manager.create_backup())"
