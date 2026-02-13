from aiogram.fsm.state import State, StatesGroup


class AdminState(StatesGroup):
    add_admin = State()
    command_add = State()
    command_remove = State()


class RconState(StatesGroup):
    waiting_command = State()
    waiting_preset_params = State()


class BackupState(StatesGroup):
    confirm_restore = State()
    waiting_clone_name = State()


class ModState(StatesGroup):
    waiting_search_query = State()
    waiting_mod_files = State()
    waiting_upload_confirm = State()


class ConfigState(StatesGroup):
    waiting_value = State()


class SchedulerState(StatesGroup):
    waiting_cron = State()
    waiting_extra = State()
    waiting_time = State()


class PlayerState(StatesGroup):
    waiting_player_name = State()
    waiting_gamemode = State()
    waiting_say_text = State()


class WorldState(StatesGroup):
    waiting_world_name = State()
    waiting_new_name = State()
    waiting_clone_name = State()


class ServerState(StatesGroup):
    waiting_password = State()


class BotSettingsState(StatesGroup):
    waiting_chat_id = State()
