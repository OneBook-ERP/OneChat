import { computed, reactive } from 'vue'
import { call } from 'frappe-ui'

export const install = reactive({
  prompt: null,
  installed: standalone(),
  ios: /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream,
  settings: { app_name: 'OneChat', app_install_button: 1, ...remembered() },
})

const CACHE_KEY = 'onechat-app-settings'

function remembered() {
  try {
    return JSON.parse(localStorage.getItem(CACHE_KEY) || '{}')
  } catch {
    return {}
  }
}

function standalone() {
  return window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone === true
}

window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault()
  install.prompt = event
})

window.addEventListener('appinstalled', () => {
  install.prompt = null
  install.installed = true
})

export const canInstall = computed(
  () => Boolean(install.settings.app_install_button) && !install.installed && (Boolean(install.prompt) || install.ios),
)

export async function promptInstall() {
  const event = install.prompt
  if (!event) return 'manual'
  event.prompt()
  const choice = await event.userChoice.catch(() => ({ outcome: 'dismissed' }))
  if (choice.outcome === 'accepted') install.prompt = null
  return choice.outcome
}

function setLink(rel, href) {
  if (!href) return
  let link = document.querySelector(`link[rel="${rel}"]`)
  if (!link) {
    link = document.createElement('link')
    link.rel = rel
    document.head.appendChild(link)
  }
  if (link.getAttribute('href') !== href) link.setAttribute('href', href)
}

export const appName = computed(() => install.settings.app_name || 'OneChat')
export const appLogo = computed(() => install.settings.app_icon || '/assets/onechat/frontend/onechat-mark.svg')

export function setAppTitle(name) {
  const count = document.title.match(/^\(\d+\+?\) /)?.[0] || ''
  const next = `${count}${name}`
  if (document.title !== next) document.title = next
}

export function applyAppSettings(settings) {
  Object.assign(install.settings, settings)
  setLink('apple-touch-icon', settings.apple_icon)
  setLink('icon', settings.favicon)
  const title = document.querySelector('meta[name="apple-mobile-web-app-title"]')
  if (title && settings.app_short_name) title.setAttribute('content', settings.app_short_name)
  if (settings.app_name) setAppTitle(settings.app_name)
  try {
    localStorage.setItem(
      CACHE_KEY,
      JSON.stringify({
        app_name: settings.app_name,
        app_icon: settings.app_icon,
        favicon: settings.favicon,
        apple_icon: settings.apple_icon,
      }),
    )
  } catch {
    return
  }
}

if (install.settings.favicon || install.settings.app_name !== 'OneChat') applyAppSettings({ ...install.settings })

export async function loadAppSettings() {
  try {
    applyAppSettings(await call('onechat.pwa.settings'))
  } catch {
    return
  }
}

export async function saveAppSettings(values) {
  const saved = await call('onechat.pwa.save_settings', values)
  applyAppSettings(saved)
  return saved
}
