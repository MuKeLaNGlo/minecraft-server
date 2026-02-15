import { useQuery } from '@tanstack/react-query'
import { endpoints } from '../api/endpoints'
import { usePlayerStore } from '../stores/playerStore'

export function PlayerList() {
  const openProfile = usePlayerStore((s) => s.openProfile)
  const { data } = useQuery({
    queryKey: ['playersOnline'],
    queryFn: endpoints.playersOnline,
    refetchInterval: 10000,
  })

  const players = data?.players ?? []

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-base font-bold tracking-tight">Игроки</h2>
        {data && (
          <span className="badge badge-blue">
            {data.count}/{data.max}
          </span>
        )}
      </div>

      {players.length === 0 ? (
        <div className="text-center py-4">
          <div className="text-2xl mb-1.5 opacity-40">👻</div>
          <p className="text-hint text-sm">Никого нет онлайн</p>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {players.map((name) => (
            <button
              key={name}
              onClick={() => openProfile(name)}
              className="flex items-center gap-2 bg-white/5 border border-white/6 rounded-lg px-3 py-2 active:scale-[0.97] transition-transform"
            >
              <img
                src={`https://mc-heads.net/avatar/${name}/24`}
                alt={name}
                className="w-6 h-6 rounded"
                loading="lazy"
              />
              <span className="text-sm font-medium">{name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
