import { onBeforeUnmount, ref } from 'vue'

const query = window.matchMedia('(min-width: 640px)')

export function useBreakpoint() {
  const isDesktop = ref(query.matches)

  const update = (event) => (isDesktop.value = event.matches)
  query.addEventListener('change', update)
  onBeforeUnmount(() => query.removeEventListener('change', update))

  return { isDesktop }
}
