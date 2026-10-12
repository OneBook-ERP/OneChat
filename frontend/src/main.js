import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { FrappeUI, frappeRequest, setConfig } from 'frappe-ui'
import './data/install'
import translationPlugin from './translation'
import { autosizeTextareas } from './utils/autosize'
import { syncThemeColor } from './utils/themeColor'
import { withFeedback } from './utils/feedback'
import './index.css'

setConfig('resourceFetcher', withFeedback(frappeRequest))

async function hydrate() {
  if (window.csrf_token && window.site_name) return

  const response = await fetch('/api/method/onechat.workspace.session.boot', {
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) return

  const { message } = await response.json()
  Object.assign(window, message)
}

async function start() {
  await hydrate().catch(() => {})

  const { default: App } = await import('./App.vue')
  const { default: router } = await import('./router')

  const app = createApp(App)
  app.use(createPinia())
  app.use(router)
  app.use(FrappeUI)
  app.use(translationPlugin)
  document.documentElement.lang = window.onechat_user?.language || 'en'
  document.documentElement.dir = window.onechat_user?.rtl ? 'rtl' : 'ltr'
  app.mount('#app')
  autosizeTextareas()
  syncThemeColor()
}

start()
