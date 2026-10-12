<template>
  <SettingsDialog v-model:open="open" v-model:tab="ui.settingsTab" size="5xl">
    <div v-if="!isDesktop" class="onechat-settings-bar flex h-14 shrink-0 items-center gap-1 border-b border-outline-gray-1 px-2">
      <Button v-if="showing" variant="ghost" size="lg" icon="lucide-arrow-left" :label="__('Back')" @click="showing = false" />
      <TruncatedText
        as="p"
        class="min-w-0 flex-1 truncate px-2 text-lg font-semibold text-ink-gray-9"
        :text="showing ? __(TAB_LABELS[ui.settingsTab] || 'Settings') : __('Settings')"
      />
      <Button variant="ghost" size="lg" icon="lucide-x" :label="__('Close')" @click="open = false" />
    </div>

    <SettingsSidebar
      v-show="isDesktop || !showing"
      :class="{ 'onechat-settings-nav !max-h-none flex-1 !border-b-0 !bg-surface-base': !isDesktop }"
      @click="openPanel"
    >
      <SettingsNavGroup :label="__('My settings')">
        <SettingsNavItem value="profile">
          <template #prefix>
            <span class="lucide-circle-user size-4 shrink-0 text-ink-gray-6" />
          </template>
          {{ __('Profile') }}
        </SettingsNavItem>
        <SettingsNavItem value="preferences">
          <template #prefix>
            <span class="lucide-sliders-horizontal size-4 shrink-0 text-ink-gray-6" />
          </template>
          {{ __('Preferences') }}
        </SettingsNavItem>
        <SettingsNavItem value="shortcuts">
          <template #prefix>
            <span class="lucide-keyboard size-4 shrink-0 text-ink-gray-6" />
          </template>
          {{ __('Shortcuts') }}
        </SettingsNavItem>
      </SettingsNavGroup>

      <SettingsNavGroup :label="__('Inbox')">
        <SettingsNavItem value="quick-replies">
          <template #prefix>
            <span class="lucide-message-square-quote size-4 shrink-0 text-ink-gray-6" />
          </template>
          {{ __('Quick replies') }}
        </SettingsNavItem>
      </SettingsNavGroup>

      <SettingsNavGroup v-if="session.user.is_admin" :label="__('Administration')">
        <SettingsNavItem value="accounts">
          <template #prefix>
            <span class="lucide-smartphone size-4 shrink-0 text-ink-gray-6" />
          </template>
          {{ __('Accounts') }}
        </SettingsNavItem>
        <SettingsNavItem value="defaults">
          <template #prefix>
            <span class="lucide-settings-2 size-4 shrink-0 text-ink-gray-6" />
          </template>
          {{ __('Defaults') }}
        </SettingsNavItem>
        <SettingsNavItem value="team">
          <template #prefix>
            <span class="lucide-users size-4 shrink-0 text-ink-gray-6" />
          </template>
          {{ __('Team') }}
        </SettingsNavItem>
        <SettingsNavItem value="teams">
          <template #prefix>
            <span class="lucide-users-round size-4 shrink-0 text-ink-gray-6" />
          </template>
          {{ __('Teams') }}
        </SettingsNavItem>
        <SettingsNavItem value="labels">
          <template #prefix>
            <span class="lucide-tags size-4 shrink-0 text-ink-gray-6" />
          </template>
          {{ __('Labels') }}
        </SettingsNavItem>
        <SettingsNavItem value="inbox-rules">
          <template #prefix>
            <span class="lucide-route size-4 shrink-0 text-ink-gray-6" />
          </template>
          {{ __('Inbox rules') }}
        </SettingsNavItem>
        <SettingsNavItem value="whatsapp">
          <template #prefix>
            <ChannelIcon channel="WhatsApp" show-whatsapp class="size-4 shrink-0" />
          </template>
          {{ __('WhatsApp') }}
        </SettingsNavItem>
        <SettingsNavItem value="instagram">
          <template #prefix>
            <ChannelIcon channel="Instagram" class="size-4 shrink-0" />
          </template>
          {{ __('Instagram') }}
          <template #suffix>
            <Badge theme="amber" variant="subtle" size="sm" :label="__('Beta')" />
          </template>
        </SettingsNavItem>
        <SettingsNavItem value="retention">
          <template #prefix>
            <span class="lucide-archive size-4 shrink-0 text-ink-gray-6" />
          </template>
          {{ __('Data retention') }}
        </SettingsNavItem>
        <SettingsNavItem value="integrations">
          <template #prefix>
            <span class="lucide-blocks size-4 shrink-0 text-ink-gray-6" />
          </template>
          {{ __('Integrations') }}
        </SettingsNavItem>
        <SettingsNavItem value="developers">
          <template #prefix>
            <span class="lucide-code-xml size-4 shrink-0 text-ink-gray-6" />
          </template>
          {{ __('Developers') }}
        </SettingsNavItem>
        <SettingsNavItem value="health">
          <template #prefix>
            <span class="lucide-heart-pulse size-4 shrink-0 text-ink-gray-6" />
          </template>
          {{ __('Health') }}
        </SettingsNavItem>
        <SettingsNavItem value="app">
          <template #prefix>
            <span class="lucide-smartphone size-4 shrink-0 text-ink-gray-6" />
          </template>
          {{ __('App') }}
        </SettingsNavItem>
      </SettingsNavGroup>
    </SettingsSidebar>

    <SettingsContent v-show="isDesktop || showing" :class="{ 'onechat-settings-page': !isDesktop }">
      <SettingsPanel value="profile">
        <ProfilePanel />
      </SettingsPanel>

      <SettingsPanel value="preferences">
        <SettingsHeader :title="__('Preferences')" />
        <SettingsBody>
          <div class="divide-y divide-outline-gray-1 pt-6">
            <SettingsRow :title="__('Appearance')" :description="__('Choose a light, dark, or system-matched interface')">
              <TabButtons
                :options="[
                  { label: __('Light'), value: 'light' },
                  { label: __('Dark'), value: 'dark' },
                  { label: __('System'), value: 'system' },
                ]"
                :model-value="colorScheme"
                @update:model-value="changeTheme"
              />
            </SettingsRow>
            <SettingsRow :title="__('Language')" :description="__('Used for OneChat and the desk. The page reloads to apply it.')">
              <TabButtons
                :options="languageOptions"
                :model-value="language"
                :class="{ 'pointer-events-none opacity-60': savingLanguage }"
                @update:model-value="changeLanguage"
              />
            </SettingsRow>
          </div>

          <NotificationSettings />
        </SettingsBody>
      </SettingsPanel>

      <SettingsPanel value="quick-replies">
        <QuickRepliesPanel />
      </SettingsPanel>

      <SettingsPanel value="shortcuts">
        <SettingsHeader :title="__('Shortcuts')" :description="__('Press Ctrl and / anywhere to bring this list up')" />
        <SettingsBody>
          <div class="mt-6 flex flex-col gap-5">
            <div v-for="group in groups" :key="group.name">
              <p class="mb-2 text-sm text-ink-gray-5">{{ __(group.name) }}</p>

              <div class="divide-y divide-outline-gray-1 rounded-4 border border-outline-gray-2">
                <div v-for="row in group.rows" :key="row.label" class="flex items-center justify-between gap-4 px-3 py-2">
                  <TruncatedText class="min-w-0 truncate text-base text-ink-gray-7" :text="__(row.label)" />

                  <span class="flex shrink-0 items-center gap-1">
                    <kbd
                      v-for="key in row.keys"
                      :key="key"
                      class="rounded-3 bg-surface-gray-2 px-1.5 py-0.5 font-mono text-xs text-ink-gray-7"
                    >
                      {{ KEYS[key] || key }}
                    </kbd>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </SettingsBody>
      </SettingsPanel>

      <template v-if="session.user.is_admin">
        <SettingsPanel value="accounts">
          <AccountsPanel />
        </SettingsPanel>

        <SettingsPanel value="defaults">
          <DefaultsPanel />
        </SettingsPanel>

        <SettingsPanel value="team">
          <TeamPanel />
        </SettingsPanel>

        <SettingsPanel value="teams">
          <TeamsPanel />
        </SettingsPanel>

        <SettingsPanel value="labels">
          <LabelsPanel />
        </SettingsPanel>

        <SettingsPanel value="inbox-rules">
          <InboxRulesPanel />
        </SettingsPanel>

        <SettingsPanel value="whatsapp">
          <WhatsAppPanel />
        </SettingsPanel>

        <SettingsPanel value="instagram">
          <InstagramPanel />
        </SettingsPanel>

        <SettingsPanel value="retention">
          <RetentionPanel />
        </SettingsPanel>

        <SettingsPanel value="integrations">
          <IntegrationsPanel />
        </SettingsPanel>

        <SettingsPanel value="developers">
          <DevelopersPanel />
        </SettingsPanel>

        <SettingsPanel value="health">
          <HealthPanel />
        </SettingsPanel>

        <SettingsPanel value="app">
          <AppPanel />
        </SettingsPanel>
      </template>
    </SettingsContent>
  </SettingsDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, ref, watch } from 'vue'
import {
  Badge,
  Button,
  SettingsBody,
  SettingsContent,
  SettingsDialog,
  SettingsHeader,
  SettingsNavGroup,
  SettingsNavItem,
  SettingsPanel,
  SettingsRow,
  SettingsSidebar,
  TabButtons,
  call,
  toast,
} from 'frappe-ui'
import AccountsPanel from './AccountsPanel.vue'
import AppPanel from './AppPanel.vue'
import DefaultsPanel from './DefaultsPanel.vue'
import DevelopersPanel from './DevelopersPanel.vue'
import HealthPanel from './HealthPanel.vue'
import InboxRulesPanel from './InboxRulesPanel.vue'
import IntegrationsPanel from './IntegrationsPanel.vue'
import LabelsPanel from './LabelsPanel.vue'
import NotificationSettings from './NotificationSettings.vue'
import ProfilePanel from './ProfilePanel.vue'
import RetentionPanel from './RetentionPanel.vue'
import InstagramPanel from './InstagramPanel.vue'
import WhatsAppPanel from './WhatsAppPanel.vue'
import ChannelIcon from '@/components/Common/ChannelIcon.vue'
import QuickRepliesPanel from './QuickRepliesPanel.vue'
import TeamPanel from './TeamPanel.vue'
import TeamsPanel from './TeamsPanel.vue'
import { SHORTCUTS } from '@/composables/useShortcuts'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { session } from '@/data/session'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { useDeskTheme } from '@/data/theme'
import { translate as __ } from '@/translation'

const open = defineModel('open', { type: Boolean, default: false })

const languages = ref([])
const language = ref(session.user.language || 'en')
const savingLanguage = ref(false)
const languageOptions = computed(() => languages.value.map((row) => ({ label: row.language_name, value: row.name })))

async function loadLanguages() {
  if (languages.value.length) return
  try {
    languages.value = await call('onechat.workspace.session.languages')
  } catch {
    languages.value = [{ name: 'en', language_name: 'English' }]
  }
}

async function changeLanguage(value) {
  if (!value || value === language.value) return
  savingLanguage.value = true
  try {
    await call('onechat.workspace.session.set_language', { language: value })
    language.value = value
    toast.success(__('Language changed. Reloading…'))
    setTimeout(() => window.location.reload(), 600)
  } catch (err) {
    savingLanguage.value = false
    toast.error(errorMessage(err))
  }
}

watch(open, (value) => value && loadLanguages(), { immediate: true })
const ui = useUI()

const ADMIN_TABS = [
  'accounts',
  'defaults',
  'team',
  'teams',
  'integrations',
  'labels',
  'inbox-rules',
  'whatsapp',
  'instagram',
  'retention',
  'app',
  'developers',
  'health',
]

const TAB_LABELS = {
  profile: 'Profile',
  preferences: 'Preferences',
  shortcuts: 'Shortcuts',
  'quick-replies': 'Quick replies',
  accounts: 'Accounts',
  defaults: 'Defaults',
  team: 'Team',
  teams: 'Teams',
  labels: 'Labels',
  'inbox-rules': 'Inbox rules',
  whatsapp: 'WhatsApp',
  instagram: 'Instagram',
  retention: 'Data retention',
  integrations: 'Integrations',
  app: 'App',
  developers: 'Developers',
  health: 'Health',
}

const { isDesktop } = useBreakpoint()
const showing = ref(false)

function openPanel(event) {
  if (!isDesktop.value && event.target.closest('[role="tab"]')) showing.value = true
}

watch(open, (value) => {
  if (value) showing.value = ui.settingsDirect
})

watch(
  () => ui.settingsTab,
  (tab) => {
    if (ADMIN_TABS.includes(tab) && !session.user.is_admin) ui.settingsTab = 'preferences'
  },
  { immediate: true },
)

const { colorScheme, change: changeDeskTheme } = useDeskTheme()

async function changeTheme(value) {
  try {
    await changeDeskTheme(value)
  } catch (err) {
    toast.error(errorMessage(err))
  }
}

const isMac = /Mac|iPhone|iPad/.test(navigator.platform)
const KEYS = { mod: isMac ? '⌘' : 'Ctrl', alt: isMac ? '⌥' : 'Alt', shift: isMac ? '⇧' : 'Shift' }

const groups = computed(() => {
  const rows = SHORTCUTS.filter((row) => !row.admin || session.user.is_admin)
  const names = [...new Set(rows.map((row) => row.group))]

  return names.map((name) => ({ name, rows: rows.filter((row) => row.group === name) }))
})
</script>

<style scoped>
.onechat-settings-nav :deep([role='tab']) {
  height: 2.75rem;
  font-size: 1rem;
}

.onechat-settings-page :deep(.px-\[4\.4rem\]) {
  padding-left: 1rem;
  padding-right: 1rem;
}

.onechat-settings-page :deep(.shrink-0.pt-10) {
  padding-top: 1rem;
}

.onechat-settings-page :deep(.gap-8.py-3\.5) {
  flex-direction: column;
  align-items: stretch;
  gap: 0.75rem;
}

.onechat-settings-page :deep(.gap-8.py-3\.5 > .justify-end) {
  justify-content: flex-start;
}
</style>
