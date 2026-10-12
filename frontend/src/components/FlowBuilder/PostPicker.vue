<template>
  <div class="flex flex-col gap-1.5">
    <span class="block text-xs text-ink-gray-5">{{ label }}</span>

    <div v-if="selected.length" class="grid grid-cols-4 gap-1.5">
      <div v-for="post in selected" :key="post.value" class="group relative aspect-square overflow-hidden rounded bg-surface-gray-2">
        <img v-if="post.image" :src="post.image" class="h-full w-full object-cover" loading="lazy" />
        <a
          v-else
          :href="post.value"
          target="_blank"
          class="flex h-full w-full items-center justify-center p-1 text-center text-xs text-ink-gray-6 break-all"
        >
          {{ shortLink(post.value) }}
        </a>
        <button
          class="absolute right-0.5 top-0.5 hidden rounded-full bg-surface-white/90 p-0.5 text-ink-gray-7 shadow group-hover:block"
          @click="remove(post.value)"
        >
          <span class="lucide-x h-3 w-3" />
        </button>
      </div>
    </div>
    <p v-else class="text-sm text-ink-gray-6">{{ __('Every post and reel') }}</p>

    <div class="flex gap-1.5">
      <Button size="sm" icon-left="lucide-images" :label="__('Pick posts')" @click="openPicker" />
      <Button v-if="selected.length" size="sm" variant="ghost" :label="__('Clear')" @click="emit('update:modelValue', [])" />
    </div>
    <p v-if="description" class="text-xs text-ink-gray-5">{{ description }}</p>

    <ResponsiveDialog v-model:open="dialog" :title="__('Pick posts')" size="xl">
      <template #default>
        <ErrorMessage :message="error" class="mb-2" />
        <div v-if="loading" class="grid grid-cols-4 gap-2">
          <Skeleton v-for="cell in 8" :key="cell" class="aspect-square w-full" />
        </div>
        <p v-else-if="!posts.length && !error" class="py-6 text-center text-sm text-ink-gray-6">
          {{ __('No posts found on your connected Instagram accounts.') }}
        </p>
        <div v-else class="grid max-h-[60vh] grid-cols-3 gap-1.5 overflow-y-auto sm:grid-cols-4 sm:gap-2">
          <button
            v-for="post in posts"
            :key="post.id"
            class="relative aspect-square overflow-hidden rounded border-2"
            :class="draft.has(post.permalink) ? 'border-outline-gray-5' : 'border-transparent'"
            :title="post.caption || ''"
            @click="toggle(post.permalink)"
          >
            <img :src="imageOf(post)" class="h-full w-full object-cover" loading="lazy" />
            <span v-if="post.media_type === 'VIDEO'" class="absolute left-1 top-1 rounded bg-black/60 px-1 text-xs text-white">
              {{ __('Reel') }}
            </span>
            <span
              v-if="draft.has(post.permalink)"
              class="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-surface-gray-7 text-white"
            >
              <span class="lucide-check h-3 w-3" />
            </span>
            <span class="absolute inset-x-0 bottom-0 truncate bg-black/50 px-1 py-0.5 text-left text-xs text-white">
              {{ dayjs(post.timestamp).format('D MMM') }} · {{ post.caption || __('No caption') }}
            </span>
          </button>
        </div>

        <div class="mt-3 flex gap-1.5">
          <FormControl v-model="link" class="flex-1" :placeholder="__('Or paste a post or reel link')" @keydown.enter="addLink" />
          <Button :label="__('Add')" :disabled="!link.trim()" @click="addLink" />
        </div>
      </template>
      <template #actions>
        <Button variant="solid" class="w-full" :label="__('Use {0} posts').format(draft.size)" @click="apply" />
      </template>
    </ResponsiveDialog>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, ErrorMessage, FormControl, Skeleton, call, dayjs } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { postImage as imageOf } from '@/data/instagram'
import { toggled } from '@/utils/collections'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  label: { type: String, default: '' },
  description: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const posts = ref([])
const loaded = ref(false)
const loading = ref(false)
const error = ref('')
const dialog = ref(false)
const draft = ref(new Set())
const link = ref('')

const images = computed(() => Object.fromEntries(posts.value.map((post) => [post.permalink, imageOf(post)])))
const ids = computed(() => ({
  ...Object.fromEntries((props.modelValue || []).filter((row) => row?.id && row?.value).map((row) => [row.value, row.id])),
  ...Object.fromEntries(posts.value.map((post) => [post.permalink, post.id])),
}))

function rowFor(value) {
  return ids.value[value] ? { value, id: ids.value[value] } : { value }
}

const selected = computed(() =>
  (props.modelValue || [])
    .map((row) => String((row && typeof row === 'object' ? row.value : row) || '').trim())
    .filter(Boolean)
    .map((value) => ({ value, image: images.value[value] })),
)

function shortLink(value) {
  return value.replace(/^https?:\/\/(www\.)?instagram\.com\//, '').replace(/\/$/, '')
}

async function load() {
  if (loaded.value) return
  loading.value = true
  error.value = ''
  try {
    posts.value = await call('onechat.instagram.comments.recent_posts')
    loaded.value = true
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

function openPicker() {
  draft.value = new Set(selected.value.map((post) => post.value))
  link.value = ''
  dialog.value = true
  load()
}

function toggle(value) {
  draft.value = toggled(draft.value, value)
}

function addLink() {
  const value = link.value.trim()
  if (!value) return
  draft.value = new Set([...draft.value, value])
  link.value = ''
}

function remove(value) {
  emit(
    'update:modelValue',
    selected.value.filter((post) => post.value !== value).map((post) => rowFor(post.value)),
  )
}

function apply() {
  emit('update:modelValue', [...draft.value].map(rowFor))
  dialog.value = false
}

if (selected.value.length) load()
</script>
