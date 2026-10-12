<template>
  <MobileShell>
    <slot />
  </MobileShell>
</template>

<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { MobileShell } from 'frappe-ui'

const router = useRouter()

function onMessage(event) {
  if (event.origin !== window.location.origin) return
  if (event.data?.type !== 'onechat:open' || typeof event.data.path !== 'string') return

  router.push(event.data.path)
}

function followDeskTheme() {
  try {
    const theme = window.parent.document.documentElement.getAttribute('data-theme')
    if (theme === 'dark' || theme === 'light') document.documentElement.setAttribute('data-theme', theme)
  } catch {
    return
  }
}

onMounted(() => {
  followDeskTheme()
  window.addEventListener('message', onMessage)
})
onBeforeUnmount(() => window.removeEventListener('message', onMessage))
</script>
