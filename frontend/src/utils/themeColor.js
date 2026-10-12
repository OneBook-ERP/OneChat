const SYSTEM = { light: '#ffffff', dark: '#171717' }

function toRgb(color) {
  try {
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 1
    const context = canvas.getContext('2d', { willReadFrequently: true })
    context.fillStyle = color
    context.fillRect(0, 0, 1, 1)
    const [red, green, blue] = context.getImageData(0, 0, 1, 1).data
    return `rgb(${red}, ${green}, ${blue})`
  } catch {
    return color
  }
}

function background() {
  for (const element of [document.body, document.querySelector('#app > *'), document.documentElement]) {
    const color = element && getComputedStyle(element).backgroundColor
    if (color && color !== 'transparent' && color !== 'rgba(0, 0, 0, 0)') return color
  }
  return null
}

function systemDark() {
  return !!window.matchMedia?.('(prefers-color-scheme: dark)').matches
}

function appDark() {
  const theme = document.documentElement.getAttribute('data-theme')
  return theme ? theme === 'dark' : systemDark()
}

function apply() {
  let value = systemDark() ? SYSTEM.dark : SYSTEM.light
  if (appDark() === systemDark()) {
    const color = background()
    if (color) value = toRgb(color)
  }
  document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
    meta.removeAttribute('media')
    meta.setAttribute('content', value)
  })
}

export function syncThemeColor() {
  if (typeof document === 'undefined') return
  requestAnimationFrame(apply)
  new MutationObserver(() => requestAnimationFrame(apply)).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme', 'class', 'style'],
  })
  window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', () => requestAnimationFrame(apply))
}
