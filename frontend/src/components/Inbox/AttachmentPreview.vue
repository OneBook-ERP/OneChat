<template>
  <div class="flex items-center gap-3 rounded-4 border border-outline-gray-2 bg-surface-base p-2">
    <img v-if="thumbnail" :src="thumbnail" alt="" class="size-11 shrink-0 rounded-3 object-cover" />
    <span v-else class="grid size-11 shrink-0 place-content-center rounded-3 bg-surface-gray-2 text-ink-gray-6" aria-hidden="true">
      <span :class="icon" class="size-5" />
    </span>

    <div class="min-w-0 flex-1">
      <TruncatedText as="p" class="truncate text-sm font-medium text-ink-gray-8" :text="file.name" />
      <TruncatedText as="p" v-if="error" class="truncate text-xs text-ink-red-7" :text="error" />
      <div v-else-if="uploading" class="mt-1.5 flex items-center gap-2">
        <div class="h-1 flex-1 overflow-hidden rounded-full bg-surface-gray-3">
          <div class="h-full rounded-full bg-surface-gray-7 transition-[width]" :style="{ width: `${progress}%` }" />
        </div>
        <span class="text-xs tabular-nums text-ink-gray-5">{{ progress }}%</span>
      </div>
      <p v-else class="text-xs text-ink-gray-5">{{ [size, label].filter(Boolean).join(' · ') }}</p>
    </div>

    <Button variant="ghost" icon="lucide-x" :label="__('Remove attachment')" @click="emit('remove')" />
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onBeforeUnmount, watch, ref } from 'vue'
import { Button } from 'frappe-ui'
import { contentLabel, contentTypeFor } from '@/data/inbox'
import { translate as __ } from '@/translation'

const ICONS = {
  image: 'lucide-image',
  video: 'lucide-video',
  audio: 'lucide-music',
  document: 'lucide-file-text',
}

const props = defineProps({
  file: { type: Object, required: true },
  progress: { type: Number, default: 0 },
  uploading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['remove'])

const thumbnail = ref('')

const kind = computed(() => contentTypeFor(props.file))
const icon = computed(() => ICONS[kind.value])
const label = computed(() => contentLabel(kind.value))

const size = computed(() => {
  const bytes = props.file.size || 0
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
})

watch(
  () => props.file,
  (file) => {
    revoke()
    if (contentTypeFor(file) !== 'image') thumbnail.value = ''
    else thumbnail.value = file.url || URL.createObjectURL(file)
  },
  { immediate: true },
)

function revoke() {
  if (thumbnail.value.startsWith('blob:')) URL.revokeObjectURL(thumbnail.value)
}

onBeforeUnmount(revoke)
</script>
