<template>
  <Transition
    enter-active-class="transition duration-300 ease-out motion-reduce:transition-none"
    enter-from-class="translate-y-3 opacity-0"
    leave-active-class="transition duration-200 ease-in motion-reduce:transition-none"
    leave-to-class="translate-y-3 opacity-0"
  >
    <aside
      v-if="current && !minimized && ready && !inChat"
      class="fixed z-40 flex max-h-[min(34rem,calc(100dvh-7rem))] flex-col overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-elevation-2 shadow-xl"
      :class="isDesktop ? 'bottom-4 right-4 w-[21rem]' : 'inset-x-3 bottom-[calc(4.25rem+env(safe-area-inset-bottom))]'"
      :aria-label="current.title || __('Announcement')"
      aria-live="polite"
    >
      <ScrollArea class="min-h-0">
        <AnnouncementMedia :key="current.id" :item="current" :compact="!isDesktop" @open="expand" />

        <div class="flex flex-col gap-3 p-4">
          <div class="flex items-start gap-3">
            <div class="min-w-0 flex-1">
              <p class="flex items-center gap-1.5 text-xs font-medium text-ink-gray-5">
                <span class="size-1.5 shrink-0 rounded-full" :class="dot" aria-hidden="true" />
                <TruncatedText class="truncate" :text="current.label || __(DEFAULT_LABELS[current.theme] || 'Announcement')" />
              </p>
              <TruncatedText
                v-if="current.title"
                as="p"
                class="mt-1.5 line-clamp-2 text-base font-semibold leading-5 text-ink-gray-9"
                :text="current.title"
              />
              <TruncatedText
                v-if="current.body"
                as="p"
                class="mt-1 text-sm leading-5 text-ink-gray-6"
                :class="isDesktop ? 'line-clamp-4' : 'line-clamp-3'"
                :text="current.body"
              />
            </div>
            <Button
              v-if="current.dismissible !== false"
              class="-mr-1.5 -mt-1 shrink-0"
              variant="ghost"
              size="sm"
              icon="lucide-x"
              :label="__('Dismiss')"
              @click="dismissAnnouncement(current.id)"
            />
          </div>

          <div class="flex items-center gap-2">
            <Button v-if="current.action" variant="solid" size="sm" :label="current.action.label" @click="act(current)" />
            <Button variant="ghost" size="sm" :label="__('Later')" @click="minimized = true" />
            <div v-if="items.length > 1" class="ml-auto flex items-center">
              <Button variant="ghost" size="sm" icon="lucide-chevron-left" :label="__('Previous')" @click="step(-1)" />
              <span class="px-1 text-xs tabular-nums text-ink-gray-5">{{ __('{0} of {1}').format(index + 1, items.length) }}</span>
              <Button variant="ghost" size="sm" icon="lucide-chevron-right" :label="__('Next')" @click="step(1)" />
            </div>
          </div>
        </div>
      </ScrollArea>
    </aside>
  </Transition>

  <Transition
    enter-active-class="transition duration-200 ease-out motion-reduce:transition-none"
    enter-from-class="translate-y-2 opacity-0"
    leave-active-class="transition duration-150 ease-in motion-reduce:transition-none"
    leave-to-class="translate-y-2 opacity-0"
  >
    <button
      v-if="current && minimized && !inChat"
      type="button"
      class="fixed z-40 flex items-center gap-2 whitespace-nowrap rounded-full border border-outline-gray-2 bg-surface-elevation-2 px-3 py-1.5 text-sm text-ink-gray-7 shadow-md transition-colors hover:bg-surface-gray-1"
      :class="isDesktop ? 'bottom-4 right-4' : 'bottom-[calc(4.25rem+env(safe-area-inset-bottom))] right-3'"
      @click="minimized = false"
    >
      <span class="size-1.5 shrink-0 rounded-full" :class="dot" aria-hidden="true" />
      {{ items.length > 1 ? __('{0} announcements').format(items.length) : current.label || __('Announcement') }}
    </button>
  </Transition>

  <ResponsiveDialog v-model:open="expanded" :title="current?.title || current?.label || __('Announcement')" size="3xl">
    <template #default>
      <AnnouncementMedia v-if="current && expanded" :item="current" large autoplay @open="() => {}" />
      <p v-if="current?.body" class="mt-3 text-base leading-6 text-ink-gray-7">{{ current.body }}</p>
    </template>
    <template v-if="current?.action" #actions>
      <div class="flex w-full justify-end">
        <Button variant="solid" :label="current.action.label" @click="act(current)" />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, ScrollArea } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import AnnouncementMedia from '@/components/Common/AnnouncementMedia.vue'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { dismissAnnouncement, visibleAnnouncements } from '@/data/announcements'
import { translate as __ } from '@/translation'

const SHOW_AFTER = 1500
const MINIMIZED_KEY = 'onechat-announcements-minimized'

const router = useRouter()
const route = useRoute()
const inChat = computed(() => route.name === 'Inbox' && !!route.params.contact)
const { isDesktop } = useBreakpoint()

const index = ref(0)
const expanded = ref(false)
const ready = ref(false)
const minimized = ref(readMinimized())
let timer = null

const items = computed(() => visibleAnnouncements.value)
const current = computed(() => items.value[Math.min(index.value, items.value.length - 1)] || null)
const DOTS = {
  new: 'bg-surface-blue-6',
  info: 'bg-surface-gray-5',
  success: 'bg-surface-green-6',
  warning: 'bg-surface-amber-5',
  ad: 'bg-surface-gray-5',
}
const DEFAULT_LABELS = { new: 'New', warning: 'Notice', success: 'Update', ad: 'Sponsored' }
const dot = computed(() => DOTS[current.value?.theme] || DOTS.info)

function readMinimized() {
  try {
    return sessionStorage.getItem(MINIMIZED_KEY) === '1'
  } catch {
    return false
  }
}

function step(offset) {
  index.value = (index.value + offset + items.value.length) % items.value.length
}

function expand() {
  expanded.value = true
}

function act(item) {
  const action = item.action
  if (!action) return
  if (action.route) router.push(action.route)
  else if (action.url) window.open(action.url, '_blank', 'noopener')
  expanded.value = false
}

watch(
  () => items.value.length,
  (length) => {
    if (index.value >= length) index.value = Math.max(0, length - 1)
  },
)

watch(minimized, (value) => {
  try {
    sessionStorage.setItem(MINIMIZED_KEY, value ? '1' : '0')
  } catch {
    return
  }
})

onMounted(() => {
  timer = setTimeout(() => (ready.value = true), SHOW_AFTER)
})

onBeforeUnmount(() => clearTimeout(timer))
</script>
