import { create } from 'zustand'

interface SafetyUIState {
  drawerOpen: boolean
  setDrawerOpen: (open: boolean) => void
}

export const useSafetyUI = create<SafetyUIState>((set) => ({
  drawerOpen: false,
  setDrawerOpen: (drawerOpen) => set({ drawerOpen }),
}))
