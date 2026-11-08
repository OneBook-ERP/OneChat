<template>
  <Transition
    enter-active-class="transition duration-300 ease-out motion-reduce:transition-none"
    enter-from-class="translate-y-3 opacity-0"
    leave-active-class="transition duration-200 ease-in motion-reduce:transition-none"
    leave-to-class="translate-y-3 opacity-0"
    mode="out-in"
  >
    <aside
      v-if="current && ready && !inChat && open"
      key="card"
      class="fixed z-40 flex max-h-[min(34rem,calc(100dvh-7rem))] flex-col overflow-hidden rounded-[14px] border border-outline-gray-2 bg-surface-elevation-2 shadow-xl"
      :class="placement"
      :aria-label="headline"
      aria-live="polite"
      @keydown.esc="open = false"
    >
      <ScrollArea class="min-h-0">
        <div v-if="hasMedia" class="relative">
          <AnnouncementMedia :key="current.id" :item="current" :compact="!isDesktop" @open="expanded = true" />
          <div class="absolute right-2.5 top-2.5 flex gap-1.5">
            <button type="button" :class="CHIP" :aria-label="__('Collapse')" @click="open = false">
              <span class="lucide-chevron-down size-4" aria-hidden="true" />
            </button>
            <button v-if="current.dismissible !== false" type="button" :class="CHIP" :aria-label="__('Don\'t show again')" @click="dismiss">
              <span class="lucide-x size-4" aria-hidden="true" />
            </button>
          </div>
        </div>

        <div v-else class="flex items-center gap-2.5 pl-2.5 pr-2 pt-2.5">
          <span class="flex size-[34px] shrink-0 items-center justify-center rounded-[10px] bg-surface-gray-2 text-ink-gray-9">
            <span :class="[icon, 'size-[17px]']" aria-hidden="true" />
          </span>
          <div class="min-w-0 flex-1">
            <TruncatedText as="p" class="truncate text-sm font-semibold leading-[18px] text-ink-gray-9" :text="headline" />
            <TruncatedText v-if="meta" as="p" class="truncate text-xs leading-4 text-ink-gray-6" :text="meta" />
          </div>
          <Button variant="ghost" icon="lucide-chevron-down" :label="__('Collapse')" @click="open = false" />
          <Button v-if="current.dismissible !== false" variant="ghost" icon="lucide-x" :label="__('Don\'t show again')" @click="dismiss" />
        </div>

        <div class="flex flex-col gap-1 px-4 pt-3.5">
          <TruncatedText
            v-if="hasMedia && current.title"
            as="p"
            class="line-clamp-2 text-[15px] font-semibold leading-5 text-ink-gray-9"
            :text="current.title"
          />
          <TruncatedText
            v-if="current.body"
            as="p"
            class="text-sm leading-[21px] text-ink-gray-7"
            :class="isDesktop ? 'line-clamp-4' : 'line-clamp-3'"
            :text="current.body"
          />
          <TruncatedText v-if="hasMedia && meta" as="p" class="truncate text-xs leading-4 text-ink-gray-6" :text="meta" />
        </div>

        <div class="flex min-h-8 items-center gap-2 pb-3 pl-4 pr-2 pt-3.5">
          <Button v-if="current.action" variant="solid" :label="current.action.label" @click="act(current)">
            <template v-if="current.action.url" #suffix>
              <span class="lucide-arrow-up-right size-3.5" aria-hidden="true" />
            </template>
          </Button>
          <div v-if="items.length > 1" class="ml-auto flex items-center">
            <Button variant="ghost" icon="lucide-chevron-left" :label="__('Previous')" @click="step(-1)" />
            <span class="min-w-8 text-center text-xs tabular-nums text-ink-gray-6">{{
              __('{0} / {1}').format(index + 1, items.length)
            }}</span>
            <Button variant="ghost" icon="lucide-chevron-right" :label="__('Next')" @click="step(1)" />
          </div>
        </div>
      </ScrollArea>
    </aside>

    <div v-else-if="current && ready && !inChat" key="bar" class="fixed z-40" :class="[placement, items.length > 1 ? 'pt-3' : '']">
      <template v-if="items.length > 1">
        <span
          class="absolute inset-x-4 top-0 h-14 rounded-[14px] border border-outline-gray-2 bg-surface-elevation-2 opacity-50"
          aria-hidden="true"
        />
        <span
          class="absolute inset-x-2 top-1.5 h-14 rounded-[14px] border border-outline-gray-2 bg-surface-elevation-2 opacity-80"
          aria-hidden="true"
        />
      </template>
      <button
        type="button"
        class="relative flex h-14 w-full items-center gap-2.5 rounded-[14px] border border-outline-gray-2 bg-surface-elevation-2 pl-2.5 pr-2 text-left shadow-lg transition-transform duration-150 hover:-translate-y-0.5 motion-reduce:transition-none"
        :aria-label="items.length > 1 ? __('Open {0} announcements').format(items.length) : __('Open announcement: {0}').format(headline)"
        @click="open = true"
      >
        <span v-if="thumb" class="size-[34px] shrink-0 overflow-hidden rounded-[10px] bg-surface-gray-2">
          <img :src="thumb" alt="" class="size-full object-cover" />
        </span>
        <span v-else class="flex size-[34px] shrink-0 items-center justify-center rounded-[10px] bg-surface-gray-2 text-ink-gray-9">
          <span :class="[icon, 'size-[17px]']" aria-hidden="true" />
        </span>
        <span class="flex min-w-0 flex-1 flex-col">
          <span class="truncate text-sm font-semibold leading-[18px] text-ink-gray-9">{{ headline }}</span>
          <span v-if="meta" class="truncate text-xs leading-4 text-ink-gray-6">{{ meta }}</span>
        </span>
        <span
          v-if="items.length > 1"
          class="flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-surface-gray-9 px-1.5 text-2xs font-semibold tabular-nums text-ink-white"
        >
          {{ items.length }}
        </span>
        <span class="flex size-7 shrink-0 items-center justify-center text-ink-gray-6" aria-hidden="true">
          <span class="lucide-chevron-up size-4" />
        </span>
      </button>
    </div>
  </Transition>

  <ResponsiveDialog v-model:open="expanded" :title="headline" size="3xl">
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
import { dismissAnnouncement, embedOf, visibleAnnouncements } from '@/data/announcements'
import { translate as __ } from '@/translation'

const SHOW_AFTER = 1500
const CHIP =
  'flex size-[30px] items-center justify-center rounded-full bg-black/50 text-white transition-colors hover:bg-black/70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-outline-gray-4'
const ICONS = {
  sparkles: 'lucide-sparkles',
  wrench: 'lucide-wrench',
  alert: 'lucide-circle-alert',
  check: 'lucide-circle-check',
  megaphone: 'lucide-megaphone',
  tag: 'lucide-tag',
  update: 'lucide-circle-arrow-up',
  gift: 'lucide-gift',
  calendar: 'lucide-calendar',
  party: 'lucide-party-popper',
  bell: 'lucide-bell',
  rocket: 'lucide-rocket',
}
const THEME_ICONS = { new: 'sparkles', warning: 'alert', success: 'check', ad: 'tag', info: 'megaphone' }
const THEME_LABELS = { new: 'New feature', warning: 'Notice', success: 'Update', ad: 'Sponsored' }

const router = useRouter()
const route = useRoute()
const inChat = computed(() => route.name === 'Inbox' && !!route.params.contact)
const { isDesktop } = useBreakpoint()

const index = ref(0)
const open = ref(false)
const expanded = ref(false)
const ready = ref(false)
let timer = null

const items = computed(() => visibleAnnouncements.value)
const current = computed(() => items.value[Math.min(index.value, items.value.length - 1)] || null)
const placement = computed(() =>
  isDesktop.value ? 'bottom-4 right-4 w-[21rem]' : 'inset-x-3 bottom-[calc(4.25rem+env(safe-area-inset-bottom))]',
)
const hasMedia = computed(() => {
  const item = current.value
  if (!item) return false
  if (item.type === 'html') return !!item.html
  return ['image', 'video', 'card'].includes(item.type) && !!item.media?.src
})
const headline = computed(() => current.value?.title || current.value?.label || __('Announcement'))
const meta = computed(() => {
  const item = current.value
  if (!item) return ''
  const label = item.label || (THEME_LABELS[item.theme] ? __(THEME_LABELS[item.theme]) : '')
  return label && !repeats(label, headline.value) ? label : ''
})

function words(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '')
}

function repeats(label, title) {
  const short = words(label)
  const long = words(title)
  return !short || long.includes(short) || short.includes(long)
}
const icon = computed(() => {
  const item = current.value
  return ICONS[item?.icon] || ICONS[THEME_ICONS[item?.theme]] || ICONS.megaphone
})
const thumb = computed(() => {
  const item = current.value
  if (!item?.media?.src) return ''
  if (item.type === 'video') return item.media.poster || embedOf(item.media.src)?.thumb || ''
  return ['image', 'card'].includes(item.type) ? item.media.src : ''
})

function step(offset) {
  index.value = (index.value + offset + items.value.length) % items.value.length
}

function dismiss() {
  dismissAnnouncement(current.value.id)
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

onMounted(() => {
  timer = setTimeout(() => (ready.value = true), SHOW_AFTER)
})

onBeforeUnmount(() => clearTimeout(timer))
</script>
