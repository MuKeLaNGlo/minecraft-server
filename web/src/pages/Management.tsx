import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { endpoints, type Backup, type World } from '../api/endpoints'
import { useAuthStore } from '../stores/authStore'

function BackupsTab() {
  const queryClient = useQueryClient()
  const { data: backups, isLoading } = useQuery({
    queryKey: ['backups'],
    queryFn: endpoints.backupsList,
  })

  const createMut = useMutation({
    mutationFn: endpoints.backupCreate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['backups'] }),
  })
  const restoreMut = useMutation({
    mutationFn: (id: number) => endpoints.backupRestore(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['backups'] }),
  })
  const deleteMut = useMutation({
    mutationFn: (id: number) => endpoints.backupDelete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['backups'] }),
  })

  const acting = createMut.isPending || restoreMut.isPending || deleteMut.isPending

  if (isLoading) return <div className="skeleton h-32 rounded-xl" />

  return (
    <div className="space-y-3">
      <button
        className="btn btn-primary w-full"
        onClick={() => createMut.mutate()}
        disabled={acting}
      >
        {createMut.isPending ? 'Создание...' : 'Создать бэкап'}
      </button>

      {restoreMut.isError && (
        <p className="text-[var(--color-danger)] text-xs">{(restoreMut.error as Error).message}</p>
      )}

      {(!backups || backups.length === 0) ? (
        <div className="text-center py-6">
          <div className="text-2xl mb-1.5 opacity-40">💾</div>
          <p className="text-hint text-sm">Нет бэкапов</p>
        </div>
      ) : (
        <div className="space-y-2">
          {backups.map((b: Backup) => (
            <div key={b.id} className="card">
              <div className="flex items-start justify-between mb-1">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{b.filename}</div>
                  <div className="text-hint text-xs">
                    {b.size_str} · {b.world} · {b.created_at?.split(' ')[0]}
                  </div>
                </div>
              </div>
              <div className="flex gap-2 mt-2">
                <button
                  className="btn btn-yellow text-xs flex-1 py-1.5"
                  onClick={() => {
                    if (confirm('Восстановить этот бэкап? Сервер должен быть остановлен.'))
                      restoreMut.mutate(b.id)
                  }}
                  disabled={acting}
                >
                  Восстановить
                </button>
                <button
                  className="btn btn-red text-xs py-1.5 px-3"
                  onClick={() => {
                    if (confirm('Удалить бэкап?')) deleteMut.mutate(b.id)
                  }}
                  disabled={acting}
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function WorldsTab() {
  const queryClient = useQueryClient()
  const [newName, setNewName] = useState('')
  const [renamingWorld, setRenamingWorld] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [cloneTarget, setCloneTarget] = useState<string | null>(null)
  const [cloneValue, setCloneValue] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['worlds'],
    queryFn: endpoints.worldsList,
  })

  const createMut = useMutation({
    mutationFn: (name: string) => endpoints.worldCreate(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worlds'] })
      setNewName('')
    },
  })
  const switchMut = useMutation({
    mutationFn: (name: string) => endpoints.worldSwitch(name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['worlds'] }),
  })
  const renameMut = useMutation({
    mutationFn: ({ name, newName }: { name: string; newName: string }) =>
      endpoints.worldRename(name, newName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worlds'] })
      setRenamingWorld(null)
    },
  })
  const cloneMut = useMutation({
    mutationFn: ({ name, cloneName }: { name: string; cloneName: string }) =>
      endpoints.worldClone(name, cloneName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worlds'] })
      setCloneTarget(null)
    },
  })
  const deleteMut = useMutation({
    mutationFn: (name: string) => endpoints.worldDelete(name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['worlds'] }),
  })

  const acting = createMut.isPending || switchMut.isPending || renameMut.isPending || cloneMut.isPending || deleteMut.isPending

  if (isLoading) return <div className="skeleton h-32 rounded-xl" />

  const worlds = data?.worlds ?? []

  return (
    <div className="space-y-3">
      {/* Create world */}
      <div className="flex gap-2">
        <input
          className="input flex-1"
          placeholder="Название нового мира"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
        />
        <button
          className="btn btn-primary text-sm px-4"
          onClick={() => newName.trim() && createMut.mutate(newName.trim())}
          disabled={acting || !newName.trim()}
        >
          +
        </button>
      </div>

      {worlds.length === 0 ? (
        <div className="text-center py-6">
          <div className="text-2xl mb-1.5 opacity-40">🌍</div>
          <p className="text-hint text-sm">Нет миров</p>
        </div>
      ) : (
        <div className="space-y-2">
          {worlds.map((w: World) => (
            <div key={w.name} className="card">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${w.active ? 'bg-[var(--color-success)]' : 'bg-white/20'}`}
                    style={w.active ? { boxShadow: '0 0 6px rgba(52,211,153,0.4)' } : undefined}
                  />
                  <span className="text-sm font-medium">{w.name}</span>
                  {w.active && <span className="badge badge-green">Активный</span>}
                </div>
                <span className="text-hint text-xs font-mono">{w.size_mb} МБ</span>
              </div>
              <div className="text-hint text-xs mb-2">
                {w.dimensions} {w.dimensions === 1 ? 'измерение' : w.dimensions < 5 ? 'измерения' : 'измерений'}
              </div>

              {/* Rename form */}
              {renamingWorld === w.name && (
                <div className="flex gap-2 mb-2">
                  <input
                    className="input flex-1 py-1.5 text-xs"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    placeholder="Новое имя"
                    autoFocus
                  />
                  <button className="btn btn-primary text-xs py-1 px-3"
                    onClick={() => renameValue.trim() && renameMut.mutate({ name: w.name, newName: renameValue.trim() })}>
                    OK
                  </button>
                  <button className="btn btn-ghost text-xs py-1 px-2" onClick={() => setRenamingWorld(null)}>✕</button>
                </div>
              )}

              {/* Clone form */}
              {cloneTarget === w.name && (
                <div className="flex gap-2 mb-2">
                  <input
                    className="input flex-1 py-1.5 text-xs"
                    value={cloneValue}
                    onChange={(e) => setCloneValue(e.target.value)}
                    placeholder="Имя клона"
                    autoFocus
                  />
                  <button className="btn btn-primary text-xs py-1 px-3"
                    onClick={() => cloneValue.trim() && cloneMut.mutate({ name: w.name, cloneName: cloneValue.trim() })}>
                    OK
                  </button>
                  <button className="btn btn-ghost text-xs py-1 px-2" onClick={() => setCloneTarget(null)}>✕</button>
                </div>
              )}

              <div className="flex gap-1.5 flex-wrap">
                {!w.active && (
                  <button className="btn btn-green text-xs py-1.5 px-2.5" onClick={() => switchMut.mutate(w.name)} disabled={acting}>
                    Активировать
                  </button>
                )}
                <button className="btn btn-ghost text-xs py-1.5 px-2.5"
                  onClick={() => { setRenamingWorld(w.name); setRenameValue(w.name) }}>
                  Переименовать
                </button>
                <button className="btn btn-ghost text-xs py-1.5 px-2.5"
                  onClick={() => { setCloneTarget(w.name); setCloneValue(`${w.name}-copy`) }}>
                  Клон
                </button>
                {!w.active && (
                  <button className="btn btn-red text-xs py-1.5 px-2.5"
                    onClick={() => {
                      if (confirm(`Удалить мир "${w.name}"? Это действие нельзя отменить!`))
                        deleteMut.mutate(w.name)
                    }}
                    disabled={acting}>
                    Удалить
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function Management() {
  const [tab, setTab] = useState<'backups' | 'worlds'>('backups')
  const role = useAuthStore((s) => s.role)
  const isAdmin = role === 'admin' || role === 'super_admin'

  if (!isAdmin) {
    return <p className="text-hint text-sm text-center py-8">Доступ только для админов</p>
  }

  return (
    <div className="space-y-3">
      <div className="segment-control">
        <button
          onClick={() => setTab('backups')}
          className={`segment-btn ${tab === 'backups' ? 'active' : ''}`}
        >
          Бэкапы
        </button>
        <button
          onClick={() => setTab('worlds')}
          className={`segment-btn ${tab === 'worlds' ? 'active' : ''}`}
        >
          Миры
        </button>
      </div>

      {tab === 'backups' ? <BackupsTab /> : <WorldsTab />}
    </div>
  )
}
