import { useRef, useEffect, type ReactNode } from 'react'
import { useSwipeToDismiss } from '../hooks/useSwipeToDismiss'

export function BottomSheet({
  onClose,
  children,
}: {
  onClose: () => void
  children: ReactNode
}) {
  const sheetRef = useRef<HTMLDivElement>(null)
  const { onTouchStart, onTouchMove, onTouchEnd } = useSwipeToDismiss(sheetRef, onClose)

  // Lock body scroll
  useEffect(() => {
    const scrollY = window.scrollY
    document.body.style.position = 'fixed'
    document.body.style.top = `-${scrollY}px`
    document.body.style.left = '0'
    document.body.style.right = '0'
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.position = ''
      document.body.style.top = ''
      document.body.style.left = ''
      document.body.style.right = ''
      document.body.style.overflow = ''
      window.scrollTo(0, scrollY)
    }
  }, [])

  return (
    <div className="sheet-backdrop">
      <div className="sheet-overlay" onClick={onClose} />
      <div
        ref={sheetRef}
        className="sheet-content"
        onClick={(e) => e.stopPropagation()}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
      >
        <div className="sheet-handle" />
        <div className="px-4 pb-[calc(env(safe-area-inset-bottom,0px)+16px)]">
          {children}
        </div>
      </div>
    </div>
  )
}
