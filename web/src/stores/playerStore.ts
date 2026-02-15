import { create } from 'zustand'

interface PlayerStore {
  selectedPlayer: string | null
  openProfile: (name: string) => void
  closeProfile: () => void
}

export const usePlayerStore = create<PlayerStore>((set) => ({
  selectedPlayer: null,
  openProfile: (name) => set({ selectedPlayer: name }),
  closeProfile: () => set({ selectedPlayer: null }),
}))
