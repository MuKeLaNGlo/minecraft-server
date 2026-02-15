import { api } from './client'

export interface ServerStatus {
  running: boolean
  status?: string
  health?: string
  started_at?: string
  cpu_percent?: number
  memory_mb?: number
  memory_limit_mb?: number
  tps?: number
  players?: {
    count: number
    max: number
    list: string[]
  }
}

export interface MonitoringData {
  running: boolean
  tps?: number | null
  cpu_percent?: number
  memory_mb?: number
  memory_limit_mb?: number
  players_online?: number
  players?: string[]
}

export interface AuthResponse {
  token: string
  role: string
  telegram_id: number
  first_name: string
}

// Stats
export interface StatsOverview {
  period: string
  unique_players: number
  total_sessions: number
  total_hours: number
}

export interface TopPlayer {
  name: string
  total_seconds: number
  total_hours: number
  sessions: number
  last_seen: string
  online: boolean
  first_seen: string
}

export interface HourlyActivity {
  hour: number
  minutes: number
  sessions: number
}

export interface DailyActivity {
  date: string
  hours: number
  sessions: number
  unique_players: number
}

export interface PlayerStats {
  found: boolean
  name?: string
  session_count?: number
  total_hours?: number
  total_seconds?: number
  last_seen?: string
  online?: boolean
  first_seen?: string
  recent_sessions?: { joined: string; left: string; duration_seconds: number }[]
}

// Player live data
export interface PlayerLiveData {
  online: boolean
  xp_level?: number
  health?: number
  food_level?: number
  pos?: { x: number; y: number; z: number }
  dimension?: string
  gamemode?: string
}

// Backups
export interface Backup {
  id: number
  filename: string
  size: number
  size_str: string
  world: string
  created_at: string
}

// Worlds
export interface World {
  name: string
  size_mb: number
  last_modified: string
  generated: boolean
  dimensions: number
  active: boolean
}

export interface WorldsResponse {
  current: string
  worlds: World[]
}

// Mods
export interface InstalledMod {
  id: number
  slug: string
  name: string
  version_id: string
  filename: string
  game_version?: string
  loader?: string
  installed_at?: string
}

export interface ModSearchHit {
  slug: string
  title: string
  description: string
  downloads: number
  icon_url: string
}

export interface ModProject {
  slug: string
  title: string
  description: string
  body: string
  icon_url: string
  downloads: number
  followers: number
  updated: string | null
  published: string | null
  categories: string[]
  license: string | null
  source_url: string
  wiki_url: string
  issues_url: string
  server_side: string
  server_side_label: string
  client_side: string
  client_side_label: string
  is_client_only: boolean
  latest_version: string | null
  loader: string
  game_version: string
  installed: boolean
  modrinth_url: string
  gallery: string[]
}

// Scheduler
export interface ScheduledTask {
  id: number
  type: string
  cron: string
  enabled: boolean
  extra_data: string
  created_at: string
}

export const endpoints = {
  auth: (initData: string) =>
    api.post<AuthResponse>('/api/auth', { init_data: initData }),

  // Server
  serverStatus: () => api.get<ServerStatus>('/api/server/status'),
  serverStart: () => api.post<{ success: boolean }>('/api/server/start'),
  serverStop: () => api.post<{ success: boolean }>('/api/server/stop'),
  serverRestart: () => api.post<{ success: boolean }>('/api/server/restart'),

  // Monitoring
  monitoring: () => api.get<MonitoringData>('/api/monitoring'),

  // Players
  playersOnline: () =>
    api.get<{ count: number; max: number; players: string[] }>('/api/players/online'),
  playerKick: (name: string, reason = '') =>
    api.post<{ success: boolean; response: string }>(`/api/players/${name}/kick`, { reason }),
  playerBan: (name: string, reason = '') =>
    api.post<{ success: boolean; response: string }>(`/api/players/${name}/ban`, { reason }),
  playerPardon: (name: string) =>
    api.post<{ success: boolean; response: string }>(`/api/players/${name}/pardon`),
  playerOp: (name: string) =>
    api.post<{ success: boolean; response: string }>(`/api/players/${name}/op`),
  playerDeop: (name: string) =>
    api.post<{ success: boolean; response: string }>(`/api/players/${name}/deop`),
  playerGamemode: (name: string, mode: string) =>
    api.post<{ success: boolean; response: string }>(`/api/players/${name}/gamemode`, { mode }),
  playerWhitelistAdd: (name: string) =>
    api.post<{ success: boolean; response: string }>(`/api/players/${name}/whitelist/add`),
  playerWhitelistRemove: (name: string) =>
    api.post<{ success: boolean; response: string }>(`/api/players/${name}/whitelist/remove`),
  playerLive: (name: string) =>
    api.get<PlayerLiveData>(`/api/players/${name}/live`),
  playerRcon: (name: string, command: string) =>
    api.post<{ success: boolean; response: string }>(`/api/players/${name}/rcon`, { command }),

  // Stats
  statsOverview: (period = '7d') =>
    api.get<StatsOverview>(`/api/stats/overview?period=${period}`),
  statsTop: (period = '7d', limit = 10) =>
    api.get<TopPlayer[]>(`/api/stats/top?period=${period}&limit=${limit}`),
  statsHourly: (period = '7d', player = '') =>
    api.get<HourlyActivity[]>(`/api/stats/activity/hourly?period=${period}&player=${player}`),
  statsDaily: (period = '30d', player = '') =>
    api.get<DailyActivity[]>(`/api/stats/activity/daily?period=${period}&player=${player}`),
  statsPlayer: (name: string) => api.get<PlayerStats>(`/api/stats/player/${name}`),

  // Backups
  backupsList: () => api.get<Backup[]>('/api/backups'),
  backupCreate: () => api.post<{ success: boolean }>('/api/backups'),
  backupRestore: (id: number) =>
    api.post<{ success: boolean; error?: string }>(`/api/backups/${id}/restore`),
  backupDelete: (id: number) =>
    api.del<{ success: boolean }>(`/api/backups/${id}`),

  // Worlds
  worldsList: () => api.get<WorldsResponse>('/api/worlds'),
  worldCreate: (name: string) =>
    api.post<{ success: boolean }>('/api/worlds', { name }),
  worldSwitch: (name: string) =>
    api.post<{ success: boolean }>(`/api/worlds/${name}/switch`),
  worldRename: (name: string, newName: string) =>
    api.put<{ success: boolean }>(`/api/worlds/${name}`, { new_name: newName }),
  worldClone: (name: string, cloneName: string) =>
    api.post<{ success: boolean }>(`/api/worlds/${name}/clone`, { clone_name: cloneName }),
  worldDelete: (name: string) =>
    api.del<{ success: boolean }>(`/api/worlds/${name}`),

  // Mods
  modsList: () => api.get<InstalledMod[]>('/api/mods'),
  modsSearch: (q: string, limit = 10) =>
    api.get<{ hits: ModSearchHit[]; total: number }>(`/api/mods/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  modInstall: (slug: string) =>
    api.post<{ success: boolean }>(`/api/mods/${slug}/install`),
  modRemove: (slug: string) =>
    api.del<{ success: boolean }>(`/api/mods/${slug}`),
  modProject: (slug: string) =>
    api.get<ModProject>(`/api/mods/project/${slug}`),
  modsCheckUpdates: () =>
    api.post<{ updates: any[] }>('/api/mods/check-updates'),

  // Logs
  logsHistory: (lines = 500) =>
    api.get<{ lines: string[] }>(`/api/logs/history?lines=${lines}`),

  // Console
  consoleExecute: (command: string) =>
    api.post<{ success: boolean; response?: string; error?: string }>('/api/console/execute', { command }),

  // Scheduler
  schedulerList: () => api.get<ScheduledTask[]>('/api/scheduler/tasks'),
  schedulerCreate: (taskType: string, cron: string, extraData = '') =>
    api.post<{ success: boolean; id?: number }>('/api/scheduler/tasks', {
      task_type: taskType, cron, extra_data: extraData,
    }),
  schedulerToggle: (id: number) =>
    api.post<{ success: boolean; enabled?: boolean }>(`/api/scheduler/tasks/${id}/toggle`),
  schedulerDelete: (id: number) =>
    api.del<{ success: boolean }>(`/api/scheduler/tasks/${id}`),
}
