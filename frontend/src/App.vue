<template>
  <FrappeUIProvider>
    <div class="h-screen w-full bg-surface-base text-ink-gray-9">
      <component :is="Layout">
        <router-view v-slot="{ Component }">
          <component :is="Component" :key="numbers.version" :compact="embedded || !isDesktop" />
        </router-view>
      </component>

      <AppDialogs />
      <template v-if="!embedded && session.user.is_admin">
        <OnboardingChecklist />
        <TourSpotlight />
      </template>
      <AnnouncementPopup v-if="!embedded && session.user.name !== 'Guest' && !(ui.fullScreen && !isDesktop)" />
      <AssistantLauncher v-if="!embedded && isDesktop && session.user.name !== 'Guest'" />
    </div>
  </FrappeUIProvider>
</template>

<script setup>
import { loadAnnouncements } from '@/data/announcements'
import { useFlags } from '@/stores/flags'
import { useOnboarding } from '@/stores/onboarding'
import { loadAppSettings } from '@/data/install'
import { computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { FrappeUIProvider, toast } from 'frappe-ui'
import { integrations, oauthReturn } from '@/data/integrations'
import { assistantStatus } from '@/data/assistant'
import { translate as __ } from '@/translation'
import AnnouncementPopup from '@/components/Common/AnnouncementPopup.vue'
import AssistantLauncher from '@/components/Common/AssistantLauncher.vue'
import AppDialogs from '@/components/Layouts/AppDialogs.vue'
import OnboardingChecklist from '@/components/Onboarding/OnboardingChecklist.vue'
import TourSpotlight from '@/components/Onboarding/TourSpotlight.vue'
import DesktopLayout from '@/components/Layouts/DesktopLayout.vue'
import EmbedLayout from '@/components/Layouts/EmbedLayout.vue'
import MobileLayout from '@/components/Layouts/MobileLayout.vue'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { useShortcuts } from '@/composables/useShortcuts'
import { embedded } from '@/data/embed'
import { startInbox } from '@/data/inbox'
import { session } from '@/data/session'
import { useSocket } from '@/data/socket'
import { useUI } from '@/stores/ui'
import { useNumbers } from '@/stores/numbers'
import { useDeskTheme } from '@/data/theme'

const instagramReturn = (() => {
  try {
    const query = new URLSearchParams(window.location.search)
    const status = query.get('instagram')
    return status && query.get('settings') === 'accounts' ? { status, message: query.get('message') || '' } : null
  } catch {
    return null
  }
})()

const { isDesktop } = useBreakpoint()
const ui = useUI()
const router = useRouter()
const onboarding = useOnboarding()
const numbers = useNumbers()
if (session.user.name !== 'Guest') numbers.load()
const deskTheme = useDeskTheme()
if (session.user.name !== 'Guest' && !embedded) deskTheme.apply(session.user.theme)

const Layout = computed(() => {
  if (embedded) return EmbedLayout

  return isDesktop.value ? DesktopLayout : MobileLayout
})

useShortcuts()

onMounted(() => {
  if (session.user.name !== 'Guest') {
    useSocket().on('onechat_access', (data) => {
      if (data?.active) return
      toast.error(__('Your OneChat access was turned off. Ask an admin if this is a mistake.'), { duration: 6000 })
      setTimeout(() => window.location.replace('/app'), 3000)
    })
    startInbox()
    loadAppSettings()
    loadAnnouncements()
    useFlags().warm()
    if (!embedded && session.user.is_admin) useOnboarding().welcome()
    if (instagramReturn && session.user.is_admin) {
      ui.openSettings('accounts')
      if (instagramReturn.status === 'error') toast.error(instagramReturn.message || __('Could not connect Instagram.'), { duration: 10000 })
      else toast.success(__('Instagram connected.'))
      window.history.replaceState(null, '', window.location.pathname)
    }
    if (oauthReturn && session.user.is_admin) {
      ui.openSettings('integrations')
      if (oauthReturn.error) toast.error(oauthReturn.error, { duration: 10000 })
      else toast.success(__('Signed in. The connection is ready.'))
      integrations.reload()
      window.history.replaceState(null, '', window.location.pathname)
    }
    assistantReturn()
  }
})

router.afterEach(() => onboarding.refresh())
watch(
  () => ui.settingsDialog,
  (open) => !open && onboarding.refresh(),
)
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState !== 'visible') return
  onboarding.refresh()
  if (session.user.name !== 'Guest' && !embedded) deskTheme.pull()
})

function assistantReturn() {
  const query = new URLSearchParams(window.location.search)
  const signedIn = query.get('assistant_signed_in')
  const failed = query.get('assistant_error')
  if (!signedIn && !failed) return
  if (failed) toast.error(failed, { duration: 10000 })
  else toast.success(__('Signed in. The Assistant now uses your own access.'))
  assistantStatus.reload()
  query.delete('assistant_signed_in')
  query.delete('assistant_error')
  const rest = query.toString()
  window.history.replaceState(null, '', `${window.location.pathname}${rest ? `?${rest}` : ''}`)
}
</script>
