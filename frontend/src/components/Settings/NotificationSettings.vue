<template>
  <div class="mt-8 flex flex-col">
    <p class="text-base font-semibold text-ink-gray-9">{{ __('Notifications') }}</p>
    <p class="mt-1 text-sm text-ink-gray-5">{{ __('Saved to your account, so they follow you to every device.') }}</p>

    <div class="mt-2 divide-y divide-outline-gray-1">
      <SettingsRow
        :title="__('Show in the bell')"
        :description="__('OneChat only hides notifications from other apps on this site, like email failures or course replies.')"
      >
        <TabButtons
          :model-value="settings.feed_scope || 'onechat'"
          :options="[
            { label: __('OneChat only'), value: 'onechat' },
            { label: __('All apps'), value: 'all' },
          ]"
          @update:model-value="setScope"
        />
      </SettingsRow>

      <SettingsRow :title="__('Desktop notifications')" :description="desktopHint">
        <div class="flex items-center gap-2">
          <Button v-if="notifications.permission === 'default'" size="sm" variant="subtle" :label="__('Allow in browser')" @click="allow" />
          <Switch
            :model-value="Boolean(settings.desktop)"
            :disabled="notifications.permission === 'unsupported' || notifications.permission === 'denied'"
            @update:model-value="(value) => update({ desktop: value ? 1 : 0 })"
          />
        </div>
      </SettingsRow>

      <div class="py-3.5">
        <p class="text-base-medium text-ink-gray-8">{{ __('Notify me for') }}</p>
        <div class="mt-3 flex flex-col gap-3">
          <div v-for="event in events" :key="event.key" class="flex items-start gap-3">
            <Checkbox
              :model-value="Boolean(settings.events[event.key])"
              @update:model-value="(value) => update({ events: { ...settings.events, [event.key]: value ? 1 : 0 } })"
            />
            <div class="min-w-0">
              <p class="text-base text-ink-gray-8">{{ __(event.label) }}</p>
              <p class="text-sm text-ink-gray-5">{{ __(event.description) }}</p>
            </div>
          </div>
        </div>
      </div>

      <SettingsRow :title="__('Sound')" :description="__('Play a short tone when a notification arrives')">
        <Switch :model-value="Boolean(settings.sound)" @update:model-value="(value) => update({ sound: value ? 1 : 0 })" />
      </SettingsRow>

      <div v-if="settings.sound" class="flex flex-wrap items-end gap-3 py-3.5">
        <Select
          class="w-36"
          :label="__('Tone')"
          :model-value="settings.tone"
          :options="tones"
          @update:model-value="(value) => update({ tone: value }, true)"
        />
        <div class="flex min-w-40 flex-1 flex-col gap-1.5">
          <FormLabel :label="__('Volume')" />
          <Slider
            :model-value="[volume ?? settings.volume]"
            :min="0"
            :max="100"
            :step="5"
            @update:model-value="(value) => (volume = toNumber(value))"
            @value-commit="commitVolume"
          />
        </div>
        <Button variant="subtle" icon-left="lucide-volume-2" :label="__('Preview')" @click="playTone(settings.tone, settings.volume)" />
      </div>

      <SettingsRow :title="__('Quiet hours')" :description="quietHint">
        <Switch :model-value="Boolean(settings.quiet)" @update:model-value="(value) => update({ quiet: value ? 1 : 0 })" />
      </SettingsRow>

      <div v-if="settings.quiet" class="flex flex-wrap items-end gap-3 py-3.5">
        <TimePicker
          class="w-32"
          :label="__('From')"
          :model-value="settings.quiet_from"
          @update:model-value="(value) => value && update({ quiet_from: value.slice(0, 5) })"
        />
        <TimePicker
          class="w-32"
          :label="__('To')"
          :model-value="settings.quiet_to"
          @update:model-value="(value) => value && update({ quiet_to: value.slice(0, 5) })"
        />
        <Badge v-if="quietNow" theme="amber" :label="__('Quiet now')" class="mb-1.5" />
      </div>

      <SettingsRow :title="__('Unread count in tab')" :description="__('Show the number of unread chats in the browser tab title')">
        <Switch :model-value="Boolean(settings.tab_badge)" @update:model-value="(value) => update({ tab_badge: value ? 1 : 0 })" />
      </SettingsRow>

      <SettingsRow :title="__('Try it')" :description="__('Plays your tone and shows a desktop notification if they are allowed')">
        <Button variant="subtle" icon-left="lucide-bell-ring" :label="__('Send test')" @click="sendTest" />
      </SettingsRow>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Badge, Button, Checkbox, FormLabel, Select, SettingsRow, Slider, Switch, TabButtons, TimePicker, toast } from 'frappe-ui'
import { useNotificationFeed } from '@/stores/notificationFeed'
import {
  EVENTS,
  TONES,
  inQuietHours,
  loadNotificationSettings,
  notifications,
  playTone,
  requestPermission,
  saveNotificationSettings,
  sendTest,
} from '@/data/notifications'
import { session } from '@/data/session'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const volume = ref(null)

const settings = computed(() => notifications.settings)
const events = computed(() => EVENTS.filter((event) => !event.admin || session.user.is_admin))
const tones = computed(() => TONES.map((tone) => ({ label: __(tone.label), value: tone.value })))
const quietNow = computed(() => inQuietHours(settings.value))

const desktopHint = computed(() => {
  const permission = notifications.permission
  if (permission === 'unsupported') return __('This browser does not support desktop notifications.')
  if (permission === 'denied') return __('Blocked in this browser. Allow notifications for this site in the browser settings, then reload.')
  if (permission === 'default') return __('Your browser needs permission before OneChat can show them.')
  return __('Pop up a notification when OneChat is in the background')
})

const quietHint = computed(() =>
  settings.value.quiet
    ? __('No sounds or pop-ups from {0} to {1}. Unread counts still update.').format(settings.value.quiet_from, settings.value.quiet_to)
    : __('Mute sounds and pop-ups at set times. Unread counts still update.'),
)

function toNumber(value) {
  return Number(Array.isArray(value) ? value[0] : value) || 0
}

async function setScope(value) {
  await update({ feed_scope: value })
  const feed = useNotificationFeed()
  feed.load()
  feed.refreshCount()
}

async function update(patch, preview = false) {
  try {
    await saveNotificationSettings(patch)
    if (preview && settings.value.sound) playTone(settings.value.tone, settings.value.volume)
  } catch (err) {
    toast.error(errorMessage(err))
  }
}

async function commitVolume(value) {
  await update({ volume: toNumber(value) }, true)
  volume.value = null
}

async function allow() {
  const result = await requestPermission()
  if (result === 'granted') {
    await update({ desktop: 1 })
    toast.success(__('Desktop notifications allowed'))
  } else if (result === 'denied') {
    toast.error(__('Notifications were blocked. You can allow them in the browser settings.'))
  }
}

onMounted(() => {
  if (!notifications.loaded) loadNotificationSettings()
})
</script>
