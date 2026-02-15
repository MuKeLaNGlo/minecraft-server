import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { endpoints } from '../api/endpoints'
import { useAuthStore } from '../stores/authStore'
import { BottomSheet } from './BottomSheet'

const GAMEMODES = [
  { value: 'survival', label: 'Survival' },
  { value: 'creative', label: 'Creative' },
  { value: 'adventure', label: 'Adventure' },
  { value: 'spectator', label: 'Spectator' },
]

const DIM_LABELS: Record<string, string> = {
  overworld: 'Обычный мир',
  the_nether: 'Незер',
  the_end: 'Край',
}

const GM_LABELS: Record<string, string> = {
  survival: 'Выживание',
  creative: 'Творческий',
  adventure: 'Приключение',
  spectator: 'Наблюдатель',
}

const RCON_PRESETS = [
  {
    label: 'Телепорт',
    items: [
      { label: 'На спавн', cmd: 'tp {player} 0 ~ 0' },
      { label: 'Ко мне', cmd: 'tp {player} ~0 ~0 ~0' },
    ],
  },
  {
    label: 'Выдать',
    items: [
      { label: 'Алмазы x64', cmd: 'give {player} diamond 64' },
      { label: 'Незерит x16', cmd: 'give {player} netherite_ingot 16' },
      { label: 'Стейк x64', cmd: 'give {player} cooked_beef 64' },
      { label: 'Элитры', cmd: 'give {player} elytra 1' },
      { label: 'Фейерверки x64', cmd: 'give {player} firework_rocket 64' },
      { label: 'Тотем', cmd: 'give {player} totem_of_undying 1' },
      { label: 'Опыт x64', cmd: 'give {player} experience_bottle 64' },
    ],
  },
  {
    label: 'Эффекты',
    items: [
      { label: 'Регенерация', cmd: 'effect give {player} regeneration 120 1' },
      { label: 'Сила', cmd: 'effect give {player} strength 300 1' },
      { label: 'Скорость', cmd: 'effect give {player} speed 300 1' },
      { label: 'Сопротивление', cmd: 'effect give {player} resistance 300 1' },
      { label: 'Невидимость', cmd: 'effect give {player} invisibility 300' },
      { label: 'Снять все', cmd: 'effect clear {player}' },
    ],
  },
]

function HealthBar({ health }: { health: number }) {
  const full = Math.floor(health / 2)
  const half = health % 2 >= 1
  const empty = 10 - full - (half ? 1 : 0)
  return (
    <span className="font-mono text-xs">
      {'❤️'.repeat(full)}{half ? '💔' : ''}{'🖤'.repeat(Math.max(0, empty))}
    </span>
  )
}

function FoodBar({ food }: { food: number }) {
  const full = Math.floor(food / 2)
  const half = food % 2 >= 1
  return (
    <span className="font-mono text-xs">
      {'🍗'.repeat(full)}{half ? '🦴' : ''}{'🖤'.repeat(Math.max(0, 10 - full - (half ? 1 : 0)))}
    </span>
  )
}

function formatHour(h: number) {
  return `${h.toString().padStart(2, '0')}:00`
}

export function PlayerProfile({ name, onClose }: { name: string; onClose: () => void }) {
  const role = useAuthStore((s) => s.role)
  const isAdmin = role === 'admin' || role === 'super_admin'
  const queryClient = useQueryClient()
  const [lastResult, setLastResult] = useState<string | null>(null)
  const [openPreset, setOpenPreset] = useState<string | null>(null)

  const { data: stats, isLoading } = useQuery({
    queryKey: ['statsPlayer', name],
    queryFn: () => endpoints.statsPlayer(name),
  })

  const { data: liveData } = useQuery({
    queryKey: ['playerLive', name],
    queryFn: () => endpoints.playerLive(name),
    refetchInterval: 10000,
  })

  const { data: hourly } = useQuery({
    queryKey: ['statsHourly', '30d', name],
    queryFn: () => endpoints.statsHourly('30d', name),
  })

  function onAction(result: { success: boolean; response: string }) {
    setLastResult(result.response || 'OK')
    queryClient.invalidateQueries({ queryKey: ['playersOnline'] })
    queryClient.invalidateQueries({ queryKey: ['playerLive', name] })
  }

  const kickMut = useMutation({ mutationFn: () => endpoints.playerKick(name), onSuccess: onAction })
  const banMut = useMutation({ mutationFn: () => endpoints.playerBan(name), onSuccess: onAction })
  const pardonMut = useMutation({ mutationFn: () => endpoints.playerPardon(name), onSuccess: onAction })
  const opMut = useMutation({ mutationFn: () => endpoints.playerOp(name), onSuccess: onAction })
  const deopMut = useMutation({ mutationFn: () => endpoints.playerDeop(name), onSuccess: onAction })
  const gamemodeMut = useMutation({ mutationFn: (mode: string) => endpoints.playerGamemode(name, mode), onSuccess: onAction })
  const wlAddMut = useMutation({ mutationFn: () => endpoints.playerWhitelistAdd(name), onSuccess: onAction })
  const wlRemoveMut = useMutation({ mutationFn: () => endpoints.playerWhitelistRemove(name), onSuccess: onAction })
  const rconMut = useMutation({ mutationFn: (cmd: string) => endpoints.playerRcon(name, cmd), onSuccess: onAction })

  const acting = kickMut.isPending || banMut.isPending || pardonMut.isPending
    || opMut.isPending || deopMut.isPending || gamemodeMut.isPending
    || wlAddMut.isPending || wlRemoveMut.isPending || rconMut.isPending

  const isOnline = liveData?.online || stats?.online

  return (
    <BottomSheet onClose={onClose}>
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <img
              src={`https://mc-heads.net/avatar/${name}/48`}
              alt={name}
              className="w-12 h-12 rounded-lg"
            />
            {liveData?.xp_level != null && (
              <div className="absolute -bottom-1 -right-1 bg-green-600 text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center border-2 border-[var(--tg-theme-bg-color)]">
                {liveData.xp_level}
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-lg font-bold flex items-center gap-2">
              {name}
              {isOnline && (
                <span className="w-2 h-2 bg-[var(--color-success)] rounded-full" style={{ boxShadow: '0 0 6px rgba(52,211,153,0.5)' }} />
              )}
            </div>
            <div className="text-hint text-xs">
              {isOnline ? (
                <span className="text-[var(--color-success)]">Онлайн</span>
              ) : (
                stats?.found && <>Был {stats.last_seen?.split(' ')[0].split('-').reverse().join('.')}</>
              )}
              {liveData?.gamemode && <> · {GM_LABELS[liveData.gamemode] || liveData.gamemode}</>}
              {liveData?.dimension && <> · {DIM_LABELS[liveData.dimension] || liveData.dimension}</>}
            </div>
          </div>
          <button onClick={onClose} className="text-hint text-xl px-1 active:opacity-50">✕</button>
        </div>

        {/* Live info */}
        {liveData?.online && (
          <div className="card space-y-2">
            {liveData.health != null && (
              <div className="flex items-center justify-between">
                <span className="text-hint text-xs">HP</span>
                <HealthBar health={liveData.health} />
              </div>
            )}
            {liveData.food_level != null && (
              <div className="flex items-center justify-between">
                <span className="text-hint text-xs">Еда</span>
                <FoodBar food={liveData.food_level} />
              </div>
            )}
            {liveData.pos && (
              <div className="flex items-center justify-between">
                <span className="text-hint text-xs">Позиция</span>
                <span className="font-mono text-xs">
                  {liveData.pos.x} / {liveData.pos.y} / {liveData.pos.z}
                </span>
              </div>
            )}
            {liveData.xp_level != null && (
              <div className="flex items-center justify-between">
                <span className="text-hint text-xs">Уровень</span>
                <span className="font-mono text-xs text-[var(--color-success)]">{liveData.xp_level} LVL</span>
              </div>
            )}
          </div>
        )}

        {/* Stats summary */}
        {isLoading && <div className="skeleton h-16 rounded-xl" />}
        {stats?.found && (
          <div className="grid grid-cols-3 gap-2">
            <div className="card text-center py-2">
              <div className="text-xl font-bold">{stats.total_hours}</div>
              <div className="text-hint text-[10px]">Часов</div>
            </div>
            <div className="card text-center py-2">
              <div className="text-xl font-bold">{stats.session_count}</div>
              <div className="text-hint text-[10px]">Сессий</div>
            </div>
            <div className="card text-center py-2">
              <div className="text-sm font-bold">
                {stats.first_seen?.split(' ')[0].split('-').reverse().join('.')}
              </div>
              <div className="text-hint text-[10px]">Первый вход</div>
            </div>
          </div>
        )}

        {/* Activity chart */}
        {hourly && hourly.some((h) => h.minutes > 0) && (
          <div className="card">
            <div className="text-xs font-semibold mb-2">Активность по часам (30д)</div>
            <ResponsiveContainer width="100%" height={100}>
              <BarChart data={hourly}>
                <XAxis
                  dataKey="hour"
                  tickFormatter={formatHour}
                  tick={{ fontSize: 8, fill: 'var(--tg-theme-hint-color)' }}
                  interval={5}
                />
                <YAxis tick={{ fontSize: 8, fill: 'var(--tg-theme-hint-color)' }} width={25} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--tg-theme-secondary-bg-color)',
                    border: 'none', borderRadius: '8px',
                    color: 'var(--tg-theme-text-color)', fontSize: '11px',
                  }}
                  labelFormatter={(v) => formatHour(v as number)}
                  formatter={(v: number) => [`${v} мин`, 'Время']}
                />
                <Bar dataKey="minutes" fill="var(--color-info)" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Recent sessions */}
        {stats?.found && stats.recent_sessions && stats.recent_sessions.length > 0 && (
          <div className="card">
            <div className="text-xs font-semibold mb-2">Последние сессии</div>
            <div className="space-y-1 max-h-28 overflow-y-auto overscroll-contain">
              {stats.recent_sessions.slice(0, 10).map((s, i) => (
                <div key={i} className="flex justify-between text-xs">
                  <span className="text-hint">
                    {s.joined?.split(' ')[0].split('-').reverse().join('.')}
                    {' '}{s.joined?.split(' ')[1]?.slice(0, 5)}
                  </span>
                  <span className="font-mono">
                    {s.duration_seconds >= 3600
                      ? `${Math.floor(s.duration_seconds / 3600)}ч ${Math.round((s.duration_seconds % 3600) / 60)}м`
                      : `${Math.round(s.duration_seconds / 60)} мин`
                    }
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Admin actions */}
        {isAdmin && (
          <div className="space-y-3">
            <div className="section-title">Управление</div>

            <div className="card space-y-3">
              {/* Moderation */}
              <div>
                <div className="text-[10px] text-hint uppercase tracking-wider mb-1.5">Модерация</div>
                <div className="grid grid-cols-4 gap-1.5">
                  {isOnline && (
                    <button className="btn btn-red text-xs py-2" disabled={acting}
                      onClick={() => { if (confirm(`Кикнуть ${name}?`)) kickMut.mutate() }}>
                      Кик
                    </button>
                  )}
                  <button className="btn btn-red text-xs py-2" disabled={acting}
                    onClick={() => { if (confirm(`Забанить ${name}?`)) banMut.mutate() }}>
                    Бан
                  </button>
                  <button className="btn btn-ghost text-xs py-2" disabled={acting}
                    onClick={() => pardonMut.mutate()}>Разбан</button>
                </div>
              </div>

              {/* Permissions */}
              <div>
                <div className="text-[10px] text-hint uppercase tracking-wider mb-1.5">Права</div>
                <div className="grid grid-cols-4 gap-1.5">
                  <button className="btn btn-ghost text-xs py-2" disabled={acting}
                    onClick={() => opMut.mutate()}>OP</button>
                  <button className="btn btn-ghost text-xs py-2" disabled={acting}
                    onClick={() => deopMut.mutate()}>Deop</button>
                  <button className="btn btn-ghost text-xs py-2" disabled={acting}
                    onClick={() => wlAddMut.mutate()}>+WL</button>
                  <button className="btn btn-ghost text-xs py-2" disabled={acting}
                    onClick={() => wlRemoveMut.mutate()}>-WL</button>
                </div>
              </div>

              {/* Gamemode */}
              <div>
                <div className="text-[10px] text-hint uppercase tracking-wider mb-1.5">Режим игры</div>
                <div className="grid grid-cols-4 gap-1.5">
                  {GAMEMODES.map((gm) => (
                    <button
                      key={gm.value}
                      className={`btn text-xs py-2 ${liveData?.gamemode === gm.value ? 'btn-primary' : 'btn-ghost'}`}
                      onClick={() => gamemodeMut.mutate(gm.value)}
                      disabled={acting}
                    >{gm.label}</button>
                  ))}
                </div>
              </div>
            </div>

            {/* RCON presets */}
            {isOnline && (
              <div className="card space-y-1">
                <div className="text-[10px] text-hint uppercase tracking-wider mb-1">Команды</div>
                {RCON_PRESETS.map((cat) => (
                  <div key={cat.label}>
                    <button
                      className="w-full text-left text-xs font-medium py-2 flex items-center justify-between border-b border-white/5 last:border-0"
                      onClick={() => setOpenPreset(openPreset === cat.label ? null : cat.label)}
                    >
                      <span>{cat.label}</span>
                      <span className="text-hint text-[10px]">{openPreset === cat.label ? '▲' : '▼'}</span>
                    </button>
                    {openPreset === cat.label && (
                      <div className="grid grid-cols-3 gap-1.5 py-2">
                        {cat.items.map((item) => (
                          <button
                            key={item.cmd}
                            className="btn btn-ghost text-xs py-1.5"
                            onClick={() => rconMut.mutate(item.cmd)}
                            disabled={acting}
                          >{item.label}</button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Result */}
            {lastResult && (
              <div className="bg-black/30 rounded-lg px-3 py-2 text-xs font-mono text-[var(--color-success)]">
                {lastResult}
              </div>
            )}
          </div>
        )}
      </div>
    </BottomSheet>
  )
}
