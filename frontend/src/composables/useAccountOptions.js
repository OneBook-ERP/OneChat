import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'frappe-ui'
import { canInstall, install, promptInstall } from '@/data/install'
import { session } from '@/data/session'
import { useOnboarding } from '@/stores/onboarding'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

export function useAccountOptions({ settings = true } = {}) {
  const ui = useUI()
  const onboarding = useOnboarding()
  const router = useRouter()

  async function toggleAvailability() {
    const away = session.user.availability === 'Away'

    try {
      await session.setAvailability(away ? 'Available' : 'Away')
      toast.success(away ? __('You are available') : __('You are away'))
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  async function installApp() {
    const outcome = await promptInstall()
    if (outcome === 'accepted') toast.success(__('{0} is installed').format(install.settings.app_name))
    if (outcome === 'manual') {
      toast(__('Install {0}').format(install.settings.app_name), {
        description: install.ios
          ? __('Tap the Share button, then Add to Home Screen.')
          : __('Use the install icon in the address bar, or the browser menu → Install app.'),
        duration: 10000,
      })
    }
  }

  return computed(() => [
    {
      label: session.user.availability === 'Away' ? __('Set yourself available') : __('Set yourself away'),
      icon: session.user.availability === 'Away' ? 'lucide-circle-check' : 'lucide-moon',
      onClick: toggleAvailability,
    },
    { label: __('Settings'), icon: 'lucide-settings', onClick: () => ui.openSettings(), condition: () => settings },
    { label: __('Setup guide'), icon: 'lucide-rocket', onClick: () => onboarding.show(), condition: () => session.user.is_admin },
    { label: __('Install app'), icon: 'lucide-download', onClick: installApp, condition: () => canInstall.value },
    {
      label: __('Audit log'),
      icon: 'lucide-shield-check',
      onClick: () => router.push({ name: 'AuditLog' }),
      condition: () => settings && session.user.is_system_manager,
    },
    {
      label: __('Open the desk'),
      icon: 'lucide-external-link',
      onClick: () => window.open('/app', '_blank'),
      condition: () => session.user.is_admin,
    },
    { label: __('Log out'), icon: 'lucide-log-out', onClick: () => session.logout() },
  ])
}
