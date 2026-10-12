<template>
  <div
    class="flex flex-col overflow-hidden rounded-8 border border-outline-gray-2 bg-surface-base shadow-sm"
    :class="{ 'h-full min-h-0': stretch }"
  >
    <div class="flex shrink-0 items-center gap-2.5 border-b border-outline-gray-1 px-3 py-2.5">
      <span class="lucide-chevron-left size-4 text-ink-gray-5" aria-hidden="true" />
      <span class="grid size-8 shrink-0 place-content-center rounded-full bg-surface-gray-3">
        <span class="lucide-store size-4 text-ink-gray-6" aria-hidden="true" />
      </span>
      <div class="min-w-0 flex-1">
        <p class="flex items-center gap-1 truncate text-base font-medium text-ink-gray-9">
          <TruncatedText class="truncate" :text="business || __('Your business')" />
          <span class="lucide-badge-check size-3.5 shrink-0 text-ink-green-3" aria-hidden="true" />
        </p>
        <p class="text-xs text-ink-gray-5">{{ __('Business account') }}</p>
      </div>
    </div>

    <ScrollArea
      class="chat-wallpaper min-h-0 bg-surface-gray-1"
      :class="stretch ? 'flex-1' : full ? '' : 'max-h-[460px]'"
      viewport-class="px-3 py-4"
    >
      <p class="mx-auto mb-3 w-fit rounded-3 bg-surface-base px-2 py-0.5 text-xs text-ink-gray-5 shadow-sm">{{ __('Today') }}</p>

      <div class="relative w-[88%] max-w-[300px]">
        <span class="bubble-tail absolute -left-1.5 top-0 size-3 bg-surface-base" aria-hidden="true" />
        <div class="relative overflow-hidden rounded-4 rounded-tl-none bg-surface-base shadow-sm">
          <div v-if="media" class="p-1 pb-0">
            <img v-if="media.image" :src="media.image" class="aspect-[1.91/1] w-full rounded-3 object-cover" alt="" />
            <div v-else-if="media.document" class="flex items-center gap-2.5 rounded-3 bg-surface-gray-2 px-2.5 py-2.5">
              <span class="lucide-file-text size-7 shrink-0 text-ink-red-3" aria-hidden="true" />
              <div class="min-w-0">
                <TruncatedText as="p" class="truncate text-sm text-ink-gray-8" :text="media.document" />
                <p class="text-xs uppercase text-ink-gray-5">{{ media.extension }}</p>
              </div>
            </div>
            <div v-else class="flex aspect-[1.91/1] w-full items-center justify-center rounded-3 bg-surface-gray-3">
              <span :class="media.icon" class="size-7 text-ink-gray-5" aria-hidden="true" />
            </div>
          </div>

          <div class="px-2.5 pb-1.5 pt-2">
            <p v-if="template.header_type === 'TEXT' && template.header" class="mb-1 text-base font-semibold text-ink-gray-9">
              {{ fill(template.header, headerSamples) }}
            </p>
            <p
              class="whitespace-pre-wrap break-words text-base leading-snug text-ink-gray-8"
              v-html="body || `<span class='text-ink-gray-4'>${__('Your message appears here')}</span>`"
            />
            <div class="mt-1 flex items-end justify-between gap-3">
              <p class="min-w-0 text-sm text-ink-gray-5">{{ template.footer }}</p>
              <p class="shrink-0 text-xs text-ink-gray-4">{{ time }}</p>
            </div>
          </div>

          <div v-if="buttons.length" class="divide-y divide-outline-gray-1 border-t border-outline-gray-1">
            <div
              v-for="(button, index) in shownButtons"
              :key="index"
              class="flex items-center justify-center gap-1.5 px-3 py-2 text-base text-ink-blue-link"
            >
              <span :class="ICONS[button.button_type] || 'lucide-reply'" class="size-4 shrink-0" aria-hidden="true" />
              <TruncatedText class="truncate" :text="button.button_label || __('Button')" />
            </div>
            <div v-if="buttons.length > 3" class="flex items-center justify-center gap-1.5 px-3 py-2 text-base text-ink-blue-link">
              <span class="lucide-list size-4 shrink-0" aria-hidden="true" />
              <span>{{ __('See all options') }}</span>
            </div>
          </div>
        </div>
      </div>
    </ScrollArea>

    <div class="flex shrink-0 items-center gap-2 border-t border-outline-gray-1 px-3 py-2">
      <span class="lucide-smile size-4 text-ink-gray-4" aria-hidden="true" />
      <TruncatedText class="flex-1 truncate rounded-full bg-surface-gray-2 px-3 py-1.5 text-sm text-ink-gray-4" :text="__('Message')" />
      <span class="lucide-mic size-4 text-ink-gray-4" aria-hidden="true" />
    </div>
  </div>
</template>

<script>
export function variableCount(text) {
  const numbers = [...String(text || '').matchAll(/{{\s*(\d+)\s*}}/g)].map((match) => Number(match[1]))

  return numbers.length ? Math.max(...numbers) : 0
}

export function splitList(value) {
  return String(value || '')
    .split(',')
    .map((item) => item.trim())
}

export function fill(text, values) {
  return String(text || '').replace(/{{\s*(\d+)\s*}}/g, (match, number) => values?.[number - 1] || match)
}
</script>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed } from 'vue'
import { ScrollArea, dayjs } from 'frappe-ui'
import { translate as __ } from '@/translation'

const props = defineProps({
  template: { type: Object, required: true },
  samples: { type: Array, default: null },
  business: { type: String, default: '' },
  stretch: { type: Boolean, default: false },
  full: { type: Boolean, default: false },
})

const ICONS = {
  'Quick Reply': 'lucide-reply',
  'Call Phone': 'lucide-phone',
  'Visit Website': 'lucide-external-link',
  'Copy Code': 'lucide-copy',
  Flow: 'lucide-square-arrow-out-up-right',
}

const time = dayjs().format('h:mm a')

const values = computed(() => props.samples || splitList(props.template.sample_values))

const headerSamples = computed(() => splitList(props.template.sample))

const buttons = computed(() => (props.template.buttons || []).filter((button) => button.is_active !== 0))

const shownButtons = computed(() => (buttons.value.length > 3 ? buttons.value.slice(0, 2) : buttons.value))

const media = computed(() => {
  const type = props.template.header_type
  const sample = props.template.sample
  if (type === 'IMAGE') return sample ? { image: sample } : { icon: 'lucide-image' }
  if (type === 'VIDEO') return { icon: 'lucide-circle-play' }
  if (type === 'DOCUMENT') {
    const name = fileName(sample) || __('Document')
    return { document: name, extension: name.includes('.') ? name.split('.').pop() : 'pdf' }
  }

  return null
})

function escape(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

const body = computed(() =>
  escape(fill(props.template.template, values.value))
    .replace(/\*([^*\n]+)\*/g, '<strong>$1</strong>')
    .replace(/(^|\s)_([^_\n]+)_/g, '$1<em>$2</em>')
    .replace(/~([^~\n]+)~/g, '<s>$1</s>')
    .replace(/```([^`]+)```/g, '<code>$1</code>'),
)

function fileName(url) {
  return url ? decodeURIComponent(String(url).split('/').pop()) : ''
}
</script>

<style scoped>
.chat-wallpaper {
  --dot: rgb(0 0 0 / 0.06);
  background-image: radial-gradient(var(--dot) 0.6px, transparent 0.6px);
  background-size: 14px 14px;
}

:global([data-theme='dark']) .chat-wallpaper {
  --dot: rgb(255 255 255 / 0.05);
}

.bubble-tail {
  clip-path: polygon(0 0, 100% 0, 100% 100%);
}
</style>
