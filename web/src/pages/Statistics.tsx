import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid,
} from 'recharts'
import { endpoints, type TopPlayer } from '../api/endpoints'
import { usePlayerStore } from '../stores/playerStore'

const PERIODS = [
  { value: 'today', label: 'Сегодня' },
  { value: '7d', label: '7 дней' },
  { value: '30d', label: '30 дней' },
  { value: 'all', label: 'Всё время' },
] as const

function formatHour(h: number) {
  return `${h.toString().padStart(2, '0')}:00`
}

function formatDate(d: string) {
  const parts = d.split('-')
  return `${parts[2]}.${parts[1]}`
}

const tooltipStyle = {
  contentStyle: {
    backgroundColor: 'var(--tg-theme-secondary-bg-color)',
    border: 'none',
    borderRadius: '8px',
    color: 'var(--tg-theme-text-color)',
    fontSize: '12px',
  },
}

export function Statistics() {
  const [period, setPeriod] = useState('7d')
  const openProfile = usePlayerStore((s) => s.openProfile)

  const { data: overview } = useQuery({
    queryKey: ['statsOverview', period],
    queryFn: () => endpoints.statsOverview(period),
  })

  const { data: topPlayers } = useQuery({
    queryKey: ['statsTop', period],
    queryFn: () => endpoints.statsTop(period),
  })

  const { data: hourly } = useQuery({
    queryKey: ['statsHourly', period],
    queryFn: () => endpoints.statsHourly(period),
  })

  const { data: daily } = useQuery({
    queryKey: ['statsDaily', period],
    queryFn: () => endpoints.statsDaily(period === 'today' ? '7d' : period),
    enabled: period !== 'today',
  })

  return (
    <div className="space-y-4">
      {/* Period selector */}
      <div className="flex gap-1.5 flex-wrap">
        {PERIODS.map((p) => (
          <button
            key={p.value}
            onClick={() => setPeriod(p.value)}
            className={`period-chip ${period === p.value ? 'active' : ''}`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Overview cards */}
      {overview && (
        <div className="grid grid-cols-3 gap-2">
          <div className="card text-center py-3">
            <div className="stat-value">{overview.unique_players}</div>
            <div className="stat-label">Игроков</div>
          </div>
          <div className="card text-center py-3">
            <div className="stat-value">{overview.total_sessions}</div>
            <div className="stat-label">Сессий</div>
          </div>
          <div className="card text-center py-3">
            <div className="stat-value">{overview.total_hours}</div>
            <div className="stat-label">Часов</div>
          </div>
        </div>
      )}

      {/* Hourly activity chart */}
      {hourly && hourly.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold mb-3">Активность по часам</h3>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={hourly}>
              <XAxis
                dataKey="hour"
                tickFormatter={formatHour}
                tick={{ fontSize: 10, fill: 'var(--tg-theme-hint-color)' }}
                interval={5}
              />
              <YAxis tick={{ fontSize: 10, fill: 'var(--tg-theme-hint-color)' }} width={30} />
              <Tooltip
                {...tooltipStyle}
                labelFormatter={(v) => formatHour(v as number)}
                formatter={(v: number) => [`${v} мин`, 'Время']}
              />
              <Bar dataKey="minutes" fill="var(--color-info)" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Daily activity chart */}
      {daily && daily.length > 0 && period !== 'today' && (
        <div className="card">
          <h3 className="text-sm font-semibold mb-3">Активность по дням</h3>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={daily}>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" />
              <XAxis
                dataKey="date"
                tickFormatter={formatDate}
                tick={{ fontSize: 10, fill: 'var(--tg-theme-hint-color)' }}
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 10, fill: 'var(--tg-theme-hint-color)' }} width={30} />
              <Tooltip
                {...tooltipStyle}
                labelFormatter={formatDate}
                formatter={(v: number, name: string) => [
                  v,
                  name === 'hours' ? 'Часов' : name === 'unique_players' ? 'Игроков' : name,
                ]}
              />
              <Line type="monotone" dataKey="hours" stroke="var(--color-success)" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="unique_players" stroke="var(--color-purple)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-4 mt-2 text-xs text-hint">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 rounded bg-[var(--color-success)] inline-block" /> Часы
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 rounded bg-[var(--color-purple)] inline-block" /> Игроки
            </span>
          </div>
        </div>
      )}

      {/* Top players */}
      {topPlayers && topPlayers.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold mb-3">Топ игроков</h3>
          <div className="space-y-1">
            {topPlayers.map((p: TopPlayer, i: number) => (
              <button
                key={p.name}
                onClick={() => openProfile(p.name)}
                className="w-full flex items-center gap-2 text-left rounded-lg p-2 -mx-1 active:bg-white/5 transition-colors"
              >
                <span className="text-hint text-xs w-5 text-right font-mono">{i + 1}</span>
                <img
                  src={`https://mc-heads.net/avatar/${p.name}/24`}
                  alt={p.name}
                  className="w-6 h-6 rounded"
                  loading="lazy"
                />
                <span className="flex-1 text-sm font-medium truncate">
                  {p.name}
                  {p.online && (
                    <span className="ml-1.5 inline-block w-1.5 h-1.5 bg-[var(--color-success)] rounded-full align-middle" />
                  )}
                </span>
                <span className="text-hint text-xs font-mono">{p.total_hours}ч</span>
                <span className="text-hint text-xs font-mono w-6 text-right">{p.sessions}с</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
