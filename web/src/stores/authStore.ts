import { create } from 'zustand'

interface AuthState {
  token: string | null
  role: string | null
  telegramId: number | null
  firstName: string | null
  setAuth: (token: string, role: string, telegramId: number, firstName: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  role: null,
  telegramId: null,
  firstName: null,
  setAuth: (token, role, telegramId, firstName) =>
    set({ token, role, telegramId, firstName }),
  logout: () =>
    set({ token: null, role: null, telegramId: null, firstName: null }),
}))
