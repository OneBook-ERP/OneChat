<template>
  <ResponsiveDialog v-model:open="open" :title="__('Choose from media library')" size="3xl">
    <template #default>
      <div class="flex flex-col gap-3">
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
          <ScrollArea orientation="horizontal" class="max-w-full shrink-0">
            <TabButtons v-model="mediaType" :options="tabs" />
          </ScrollArea>
          <FormControl v-model="search" class="w-full sm:ml-auto sm:w-56" type="search" :placeholder="__('Search media')">
            <template #prefix>
              <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
            </template>
          </FormControl>
        </div>

        <ErrorMessage :message="error" />

        <ScrollArea viewport-class="max-h-[55vh]">
          <div v-if="loading && !items.length" class="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Skeleton v-for="card in 8" :key="card" class="aspect-[4/3] w-full rounded-5" />
          </div>

          <EmptyState
            v-else-if="!items.length"
            icon="lucide-images"
            :title="filtered ? __('No matching media') : __('The media library is empty')"
            :description="
              filtered
                ? __('Try another search or type.')
                : __('Admins can upload images, videos and files under Campaigns → Media library.')
            "
          />

          <div v-else class="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MediaCard v-for="item in items" :key="item.name" :item="item" @click="pick(item)" />
          </div>
        </ScrollArea>

        <Pagination v-if="total > PAGE_SIZES[0]" v-model:page="page" :total="total" inline />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ErrorMessage, FormControl, ScrollArea, Skeleton, TabButtons, call, debounce } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import Pagination from '@/components/Common/Pagination.vue'
import MediaCard from './MediaCard.vue'
import { fileName, mediaTabs } from './media'
import { PAGE_SIZES, pageLength } from '@/utils/paging'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const open = defineModel('open', { type: Boolean, default: false })

const emit = defineEmits(['pick'])

const tabs = mediaTabs()

const mediaType = ref('all')
const search = ref('')
const page = ref(1)
const items = ref([])
const total = ref(0)
const loading = ref(false)
const error = ref('')

const filtered = computed(() => Boolean(search.value.trim()) || mediaType.value !== 'all')

let ticket = 0

async function load() {
  const id = ++ticket
  loading.value = true
  error.value = ''

  try {
    const data = await call('onechat.campaigns.media.library', {
      search: search.value.trim() || null,
      media_type: mediaType.value === 'all' ? null : mediaType.value,
      start: (page.value - 1) * pageLength.value,
      limit: pageLength.value,
    })
    if (id !== ticket) return

    items.value = data.items || []
    total.value = data.total || 0
  } catch (err) {
    if (id === ticket) error.value = errorMessage(err)
  } finally {
    if (id === ticket) loading.value = false
  }
}

function reload() {
  if (page.value === 1) load()
  else page.value = 1
}

const reloadSoon = debounce(reload, 300)

watch(
  open,
  (value) => {
    if (value) load()
  },
  { immediate: true },
)

watch(search, () => open.value && reloadSoon())
watch(mediaType, () => open.value && reload())
watch(page, () => open.value && load())
watch(pageLength, () => open.value && reload())

function pick(item) {
  emit('pick', {
    file_url: item.file,
    file_name: fileName(item.file),
    media_type: item.media_type,
    title: item.title,
  })
  open.value = false
}
</script>
