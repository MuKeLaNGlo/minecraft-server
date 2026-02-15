# Перенос данных игрока при смене online-mode

## Проблема

При переключении `online-mode=true` → `online-mode=false` в `server.properties` сервер назначает игрокам новые (оффлайн) UUID. Из-за этого теряется:
- Инвентарь и позиция (`playerdata/`)
- Достижения (`advancements/`)
- Статистика (`stats/`)

Сервер считает игрока с тем же ником новым, потому что UUID другой.

## Как найти UUID игрока

### 1. Онлайн (лицензионный) UUID

Запрос к Mojang API:
```bash
curl -s https://api.mojang.com/users/profiles/minecraft/НИК_ИГРОКА
```

### 2. Оффлайн UUID

**Нельзя** надёжно вычислить вручную — Forge/Fabric могут генерировать UUID по-своему.

Самый надёжный способ — посмотреть в `usercache.json`:
```bash
cat server/data/usercache.json
```

Там будут записи вида:
```json
{"name":"MuKeLaNGlo","uuid":"cd1a6f5f-9040-3c24-a6d5-69a51f31ff84","expiresOn":"..."}
```

Игрок может иметь **две записи** — с онлайн и оффлайн UUID. Нужен тот, который создан **после** переключения на `online-mode=false`.

## Перенос данных

### Предварительные условия

- Игрок **не должен быть на сервере** в момент переноса
- Проверить: `docker exec mc-server rcon-cli list`

### Команды

```bash
OLD="<онлайн-uuid>"    # лицензионный UUID (из Mojang API)
NEW="<оффлайн-uuid>"   # оффлайн UUID (из usercache.json)
BASE="/root/minecraft-server/server/data/World 1"

# Копируем данные
cp -fv "$BASE/playerdata/$OLD.dat"     "$BASE/playerdata/$NEW.dat"
cp -fv "$BASE/playerdata/$OLD.dat_old" "$BASE/playerdata/$NEW.dat_old"
cp -fv "$BASE/advancements/$OLD.json"  "$BASE/advancements/$NEW.json"
cp -fv "$BASE/stats/$OLD.json"         "$BASE/stats/$NEW.json"
```

### Проверка

После копирования игрок заходит на сервер — прогресс, инвентарь и позиция должны восстановиться.

## Выполненные переносы

| Игрок       | Онлайн UUID                            | Оффлайн UUID                           | Дата       |
|-------------|----------------------------------------|----------------------------------------|------------|
| MuKeLaNGlo  | `c78b1051-b8cd-45b8-8675-57d4c038f5f0` | `cd1a6f5f-9040-3c24-a6d5-69a51f31ff84` | 2026-02-14 |
| Mysty0      | `d2e9f46a-399c-4649-847f-b436bce2f39e` | `11aa8e5a-95dc-32d8-8183-9b5ab078b32d` | 2026-02-14 |

## Примечания

- Скин в оффлайн-режиме не загружается с серверов Mojang. Для скинов нужен мод (например SkinsRestorer).
- Старые файлы (с онлайн UUID) не удаляются — если вернуть `online-mode=true`, они снова будут использоваться.
