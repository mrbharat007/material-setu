import { useEffect, useRef, useState } from 'react'

const reduced =
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** Hash router: returns the current path, e.g. "/materials". */
export function useRoute() {
  const read = () => window.location.hash.replace(/^#/, '') || '/'
  const [route, setRoute] = useState(read)
  useEffect(() => {
    const on = () => setRoute(read())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return route
}

export const go = (path) => {
  window.location.hash = path
}

/** Ease a number from its previous value to `target`. Always lands on `target`. */
export function useCountUp(target, ms = 700) {
  const [display, setDisplay] = useState(target)
  const prevRef = useRef(target)

  useEffect(() => {
    const from = prevRef.current
    prevRef.current = target
    if (reduced || from === target || typeof target !== 'number') {
      setDisplay(target)
      return
    }
    const steps = 24
    let i = 0
    const id = setInterval(() => {
      i += 1
      const t = i / steps
      const eased = 1 - Math.pow(1 - t, 3)
      setDisplay(Math.round(from + (target - from) * eased))
      if (i >= steps) {
        clearInterval(id)
        setDisplay(target)
      }
    }, ms / steps)
    return () => clearInterval(id)
  }, [target, ms])

  return display
}

/** false on first paint, then true — drives a CSS transition on an inline style. */
export function useReveal(delay = 60) {
  const [shown, setShown] = useState(false)
  useEffect(() => {
    if (reduced) {
      setShown(true)
      return
    }
    const id = setTimeout(() => setShown(true), delay)
    return () => clearTimeout(id)
  }, [delay])
  return shown
}

/** Ref + boolean that flips true once the element scrolls into view (stays true after). */
export function useInView(threshold = 0.18) {
  const ref = useRef(null)
  const [inView, setInView] = useState(reduced)

  useEffect(() => {
    if (reduced) return
    const el = ref.current
    if (!el || typeof IntersectionObserver === 'undefined') {
      setInView(true)
      return
    }
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true)
          obs.disconnect()
        }
      },
      { threshold, rootMargin: '0px 0px -8% 0px' },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold])

  return [ref, inView]
}

/** True once the page has scrolled past `past` pixels — drives a sticky nav's "scrolled" look. */
export function useScrolled(past = 8) {
  const [scrolled, setScrolled] = useState(
    typeof window !== 'undefined' && window.scrollY > past,
  )
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > past)
    window.addEventListener('scroll', on, { passive: true })
    on()
    return () => window.removeEventListener('scroll', on)
  }, [past])
  return scrolled
}

/** Debounce a value. */
export function useDebounced(value, ms = 350) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setV(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return v
}
