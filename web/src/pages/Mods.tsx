import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { endpoints, type InstalledMod, type ModSearchHit, type ModProject } from '../api/endpoints'
import { useAuthStore } from '../stores/authStore'
import { BottomSheet } from '../components/BottomSheet'

function formatDownloads(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

// ─── Mod Detail Bottom Sheet ──────────────────────────────────────────

function ModDetail({ slug, onClose }: { slug: string; onClose: () => void }) {
  const queryClient = useQueryClient()

  const { data: mod, isLoading, error } = useQuery({
    queryKey: ['modProject', slug],
    queryFn: () => endpoints.modProject(slug),
  })

  const installMut = useMutation({
    mutationFn: () => endpoints.modInstall(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['modsInstalled'] })
      queryClient.invalidateQueries({ queryKey: ['modProject', slug] })
    },
  })

  const removeMut = useMutation({
    mutationFn: () => endpoints.modRemove(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['modsInstalled'] })
      queryClient.invalidateQueries({ queryKey: ['modProject', slug] })
    },
  })

  const acting = installMut.isPending || removeMut.isPending

  return (
    <BottomSheet onClose={onClose}>
      {isLoading && (
        <div className="text-center text-hint text-sm py-12">Загрузка...</div>
      )}

      {error && (
        <div className="text-center text-[var(--color-danger)] text-sm py-12">
          Ошибка загрузки мода
        </div>
      )}

      {mod && <ModDetailContent mod={mod} acting={acting} installMut={installMut} removeMut={removeMut} />}
    </BottomSheet>
  )
}

function ModDetailContent({
  mod, acting, installMut, removeMut,
}: {
  mod: ModProject
  acting: boolean
  installMut: { mutate: () => void; isPending: boolean }
  removeMut: { mutate: () => void; isPending: boolean }
}) {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start gap-3">
        {mod.icon_url && (
          <img src={mod.icon_url} alt="" className="w-16 h-16 rounded-xl flex-shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-bold leading-tight">{mod.title}</h2>
          <p className="text-hint text-xs mt-0.5 line-clamp-2">{mod.description}</p>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-2">
        <div className="card text-center py-2">
          <div className="text-sm font-bold">{formatDownloads(mod.downloads)}</div>
          <div className="text-hint text-[10px]">Скачиваний</div>
        </div>
        <div className="card text-center py-2">
          <div className="text-sm font-bold">{formatDownloads(mod.followers)}</div>
          <div className="text-hint text-[10px]">Подписчиков</div>
        </div>
        <div className="card text-center py-2">
          <div className="text-sm font-bold">{mod.latest_version || '—'}</div>
          <div className="text-hint text-[10px]">Версия</div>
        </div>
      </div>

      {/* Client-only warning */}
      {mod.is_client_only && (
        <div className="bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30 rounded-lg px-3 py-2 text-xs text-[var(--color-warning)]">
          Это клиентский мод — на сервер ставить не нужно
        </div>
      )}

      {/* Install / Remove */}
      {mod.installed ? (
        <button
          className="btn btn-red w-full text-sm"
          disabled={acting}
          onClick={() => {
            if (confirm(`Удалить ${mod.title}?`)) removeMut.mutate()
          }}
        >
          {removeMut.isPending ? 'Удаление...' : 'Удалить мод'}
        </button>
      ) : (
        <button
          className="btn btn-green w-full text-sm"
          disabled={acting}
          onClick={() => installMut.mutate()}
        >
          {installMut.isPending ? 'Установка...' : 'Установить'}
        </button>
      )}

      {/* Info card */}
      <div className="card space-y-2">
        <InfoRow label="Сервер" value={mod.server_side_label} />
        <InfoRow label="Клиент" value={mod.client_side_label} />
        <InfoRow label="Категории" value={mod.categories.join(', ') || '—'} />
        <InfoRow label="Лицензия" value={mod.license || '—'} />
        <InfoRow label="Лоадер" value={mod.loader} />
        <InfoRow label="Версия MC" value={mod.game_version} />
        {mod.updated && <InfoRow label="Обновлён" value={mod.updated} />}
        {mod.published && <InfoRow label="Опубликован" value={mod.published} />}
      </div>

      {/* Gallery */}
      {mod.gallery.length > 0 && (
        <div>
          <div className="text-xs font-semibold mb-2">Галерея</div>
          <div className="flex gap-2 overflow-x-auto pb-2 -mx-4 px-4">
            {mod.gallery.map((url, i) => (
              <img
                key={i}
                src={url}
                alt=""
                className="h-32 rounded-lg flex-shrink-0"
                loading="lazy"
              />
            ))}
          </div>
        </div>
      )}

      {/* Links */}
      <div className="flex flex-wrap gap-2">
        <a href={mod.modrinth_url} target="_blank" rel="noopener noreferrer"
          className="btn btn-primary text-xs py-2 px-3">Modrinth</a>
        {mod.source_url && (
          <a href={mod.source_url} target="_blank" rel="noopener noreferrer"
            className="btn btn-ghost text-xs py-2 px-3">Исходный код</a>
        )}
        {mod.wiki_url && (
          <a href={mod.wiki_url} target="_blank" rel="noopener noreferrer"
            className="btn btn-ghost text-xs py-2 px-3">Wiki</a>
        )}
        {mod.issues_url && (
          <a href={mod.issues_url} target="_blank" rel="noopener noreferrer"
            className="btn btn-ghost text-xs py-2 px-3">Баг-трекер</a>
        )}
      </div>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-hint">{label}</span>
      <span className="font-medium text-right">{value}</span>
    </div>
  )
}

// ─── Search Mods ──────────────────────────────────────────────────────

function SearchMods({ onSelect }: { onSelect: (slug: string) => void }) {
  const [query, setQuery] = useState('')
  const [searchTerm, setSearchTerm] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['modsSearch', searchTerm],
    queryFn: () => endpoints.modsSearch(searchTerm),
    enabled: searchTerm.length > 0,
  })

  return (
    <div className="space-y-3">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (query.trim()) setSearchTerm(query.trim())
        }}
        className="flex gap-2"
      >
        <input
          className="input flex-1"
          placeholder="Поиск модов на Modrinth..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn btn-primary text-sm" type="submit">Найти</button>
      </form>

      {isLoading && <div className="skeleton h-20 rounded-xl" />}

      {data?.hits?.map((mod: ModSearchHit) => (
        <button
          key={mod.slug}
          className="card flex gap-3 w-full text-left active:scale-[0.98] transition-transform"
          onClick={() => onSelect(mod.slug)}
        >
          {mod.icon_url && (
            <img src={mod.icon_url} alt="" className="w-10 h-10 rounded-lg flex-shrink-0" loading="lazy" />
          )}
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold truncate">{mod.title}</div>
            <div className="text-hint text-xs line-clamp-2">{mod.description}</div>
            <div className="text-hint text-xs mt-1">
              {formatDownloads(mod.downloads)} скачиваний
            </div>
          </div>
          <span className="text-hint text-sm self-center">›</span>
        </button>
      ))}
    </div>
  )
}

// ─── Installed Mods ───────────────────────────────────────────────────

function InstalledMods({ onSelect }: { onSelect: (slug: string) => void }) {
  const queryClient = useQueryClient()

  const { data: mods, isLoading } = useQuery({
    queryKey: ['modsInstalled'],
    queryFn: endpoints.modsList,
  })

  const removeMut = useMutation({
    mutationFn: (slug: string) => endpoints.modRemove(slug),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['modsInstalled'] }),
  })

  const updatesMut = useMutation({
    mutationFn: endpoints.modsCheckUpdates,
  })

  if (isLoading) return <div className="skeleton h-32 rounded-xl" />

  return (
    <div className="space-y-3">
      <button
        className="btn btn-ghost w-full text-sm"
        onClick={() => updatesMut.mutate()}
        disabled={updatesMut.isPending}
      >
        {updatesMut.isPending ? 'Проверка...' : 'Проверить обновления'}
      </button>

      {updatesMut.data?.updates && updatesMut.data.updates.length > 0 && (
        <div className="card border border-[var(--color-warning)]/30">
          <div className="text-sm font-semibold text-[var(--color-warning)] mb-1">
            Доступны обновления: {updatesMut.data.updates.length}
          </div>
        </div>
      )}

      {(!mods || mods.length === 0) ? (
        <div className="text-center py-6">
          <div className="text-2xl mb-1.5 opacity-40">📦</div>
          <p className="text-hint text-sm">Нет установленных модов</p>
        </div>
      ) : (
        mods.map((m: InstalledMod) => (
          <div key={m.id} className="card flex items-center gap-3">
            <button
              className="flex-1 min-w-0 text-left active:opacity-70 transition-opacity"
              onClick={() => onSelect(m.slug)}
            >
              <div className="text-sm font-medium truncate">{m.name || m.slug}</div>
              <div className="text-hint text-xs truncate">{m.filename}</div>
              {m.game_version && (
                <div className="text-hint text-xs">{m.loader} · {m.game_version}</div>
              )}
            </button>
            <button
              className="btn btn-red text-xs py-1.5 px-3"
              onClick={() => {
                if (confirm(`Удалить ${m.name || m.slug}?`)) removeMut.mutate(m.slug)
              }}
              disabled={removeMut.isPending}
            >
              ✕
            </button>
          </div>
        ))
      )}
    </div>
  )
}

// ─── Main Mods Page ───────────────────────────────────────────────────

export function Mods() {
  const [tab, setTab] = useState<'installed' | 'search'>('installed')
  const [selectedMod, setSelectedMod] = useState<string | null>(null)
  const role = useAuthStore((s) => s.role)
  const isAdmin = role === 'admin' || role === 'super_admin'

  if (!isAdmin) {
    return <p className="text-hint text-sm text-center py-8">Доступ только для админов</p>
  }

  return (
    <div className="space-y-3">
      {selectedMod && (
        <ModDetail slug={selectedMod} onClose={() => setSelectedMod(null)} />
      )}

      <div className="segment-control">
        <button
          onClick={() => setTab('installed')}
          className={`segment-btn ${tab === 'installed' ? 'active' : ''}`}
        >
          Установленные
        </button>
        <button
          onClick={() => setTab('search')}
          className={`segment-btn ${tab === 'search' ? 'active' : ''}`}
        >
          Поиск
        </button>
      </div>

      {tab === 'installed'
        ? <InstalledMods onSelect={setSelectedMod} />
        : <SearchMods onSelect={setSelectedMod} />
      }
    </div>
  )
}
