import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Telegram Mini App setup
const tg = (window as any).Telegram?.WebApp
if (tg) {
  tg.ready()
  tg.expand()
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
