import { useRef, useCallback, type RefObject } from 'react'

const THRESHOLD = 120
const VELOCITY_THRESHOLD = 0.5

interface SwipeHandlers {
  onTouchStart: (e: React.TouchEvent) => void
  onTouchMove: (e: React.TouchEvent) => void
  onTouchEnd: () => void
}

export function useSwipeToDismiss(
  sheetRef: RefObject<HTMLDivElement | null>,
  onDismiss: () => void,
): SwipeHandlers {
  const startY = useRef(0)
  const startTime = useRef(0)
  const currentY = useRef(0)
  const dragging = useRef(false)

  const onTouchStart = useCallback((e: React.TouchEvent) => {
    const el = sheetRef.current
    if (!el) return

    // Only start swipe if the scrollable content is at the top
    // or if the touch is on the handle area (top 40px)
    const touch = e.touches[0]
    const rect = el.getBoundingClientRect()
    const touchRelY = touch.clientY - rect.top
    const isOnHandle = touchRelY < 40

    if (!isOnHandle && el.scrollTop > 0) return

    startY.current = touch.clientY
    startTime.current = Date.now()
    currentY.current = 0
    dragging.current = true
  }, [sheetRef])

  const onTouchMove = useCallback((e: React.TouchEvent) => {
    if (!dragging.current) return
    const el = sheetRef.current
    if (!el) return

    const deltaY = e.touches[0].clientY - startY.current

    // Only allow downward drag
    if (deltaY < 0) {
      currentY.current = 0
      el.style.transform = ''
      el.style.transition = 'none'
      return
    }

    // Prevent browser scroll while dragging
    if (deltaY > 10 && el.scrollTop <= 0) {
      e.preventDefault()
    }

    currentY.current = deltaY

    // Apply rubber-band transform with diminishing returns
    const dampened = deltaY * 0.6
    el.style.transform = `translateY(${dampened}px)`
    el.style.transition = 'none'

    // Adjust overlay opacity
    const overlay = el.previousElementSibling as HTMLElement | null
    if (overlay) {
      const opacity = Math.max(0, 1 - dampened / 400)
      overlay.style.opacity = String(opacity)
    }
  }, [sheetRef])

  const onTouchEnd = useCallback(() => {
    if (!dragging.current) return
    dragging.current = false

    const el = sheetRef.current
    if (!el) return

    const elapsed = Date.now() - startTime.current
    const velocity = currentY.current / Math.max(elapsed, 1)
    const shouldDismiss = currentY.current > THRESHOLD || velocity > VELOCITY_THRESHOLD

    if (shouldDismiss) {
      el.style.transform = `translateY(100%)`
      el.style.transition = 'transform 250ms ease-out'
      const overlay = el.previousElementSibling as HTMLElement | null
      if (overlay) {
        overlay.style.opacity = '0'
        overlay.style.transition = 'opacity 250ms ease-out'
      }
      setTimeout(onDismiss, 250)
    } else {
      el.style.transform = ''
      el.style.transition = 'transform 300ms cubic-bezier(0.34, 1.56, 0.64, 1)'
      const overlay = el.previousElementSibling as HTMLElement | null
      if (overlay) {
        overlay.style.opacity = ''
        overlay.style.transition = 'opacity 300ms ease'
      }
    }
  }, [sheetRef, onDismiss])

  return { onTouchStart, onTouchMove, onTouchEnd }
}
