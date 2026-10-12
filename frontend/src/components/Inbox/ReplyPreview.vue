<template>
  <div
    class="flex min-w-0 items-stretch gap-2 overflow-hidden rounded-3 border-l-[3px] bg-surface-alpha-gray-2"
    :class="mine ? 'border-outline-green-5' : 'border-outline-blue-5'"
  >
    <div class="min-w-0 flex-1 px-2 py-1.5">
      <TruncatedText
        as="p"
        class="truncate text-xs font-semibold"
        :class="mine ? 'text-ink-green-7' : 'text-ink-blue-7'"
        :text="mine ? __('You') : contactName"
      />
      <p class="mt-0.5 flex items-center gap-1 text-sm text-ink-gray-6">
        <span v-if="icon" :class="icon" class="size-3.5 shrink-0" aria-hidden="true" />
        <TruncatedText class="line-clamp-2 break-words" :text="text" />
      </p>
    </div>

    <img v-if="thumbnail" :src="thumbnail" alt="" class="size-12 shrink-0 object-cover" />

    <div v-if="removable" class="flex items-start p-1">
      <Button variant="ghost" size="sm" icon="lucide-x" :label="__('Cancel reply')" @click="emit('cancel')" />
    </div>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed } from 'vue'
import { Button } from 'frappe-ui'
import { previewText } from '@/data/inbox'
import { translate as __ } from '@/translation'

const ICONS = {
  image: 'lucide-image',
  video: 'lucide-video',
  audio: 'lucide-mic',
  document: 'lucide-file-text',
  location: 'lucide-map-pin',
  contact: 'lucide-contact',
}

const props = defineProps({
  message: { type: Object, required: true },
  contactName: { type: String, default: '' },
  removable: { type: Boolean, default: false },
})

const emit = defineEmits(['cancel'])

const mine = computed(() => props.message.type === 'Outgoing')
const text = computed(() => previewText(props.message))
const icon = computed(() => ICONS[props.message.content_type] || '')
const thumbnail = computed(() => (props.message.content_type === 'image' && props.message.attach) || '')
</script>
