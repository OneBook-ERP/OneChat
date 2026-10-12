<template>
  <AppHeader>
    <template #actions>
      <Button variant="solid" icon-left="lucide-upload" :loading="uploading.active" :label="__('Upload')" @click="input?.click()" />
    </template>
  </AppHeader>

  <input ref="input" type="file" multiple class="hidden" @change="onFiles" />

  <div class="mx-auto w-full max-w-[1100px] px-3 pb-10 pt-5 sm:px-5">
    <div class="flex flex-col gap-3">
      <MobileListToolbar
        v-if="!isDesktop"
        :list="list"
        :placeholder="__('Search media')"
        :active-count="mediaType === 'all' ? 0 : 1"
        @clear="mediaType = 'all'"
      >
        <FilterChips v-model="mediaType" :label="__('Type')" :options="tabs" />
      </MobileListToolbar>

      <div v-else class="flex flex-col gap-2 sm:flex-row sm:items-center">
        <ScrollArea orientation="horizontal" class="max-w-full shrink-0">
          <TabButtons v-model="mediaType" :options="tabs" />
        </ScrollArea>
        <FormControl v-model="list.search.value" class="w-full sm:ml-auto sm:w-60" type="search" :placeholder="__('Search media')">
          <template #prefix>
            <span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
          </template>
        </FormControl>
      </div>

      <div v-if="uploading.active" class="flex flex-col gap-2 rounded-5 border border-outline-gray-1 bg-surface-gray-1 px-3 py-2.5">
        <div class="flex items-center justify-between gap-3 text-sm">
          <TruncatedText
            class="min-w-0 truncate text-ink-gray-7"
            :text="__('Uploading {0} of {1}: {2}').format(uploading.index, uploading.count, uploading.name)"
          />
          <span class="shrink-0 tabular-nums text-ink-gray-5">{{ uploader.state.progress }}%</span>
        </div>
        <Progress :value="uploader.state.progress" size="sm" />
      </div>

      <div v-if="list.loading.value && !list.rows.value.length" class="grid grid-cols-1 gap-4 sm:grid-cols-3 sm:gap-3 lg:grid-cols-5">
        <Skeleton v-for="card in 10" :key="card" class="aspect-[4/5] w-full rounded-5" />
      </div>

      <EmptyState
        v-else-if="!list.rows.value.length"
        icon="lucide-images"
        :title="filtered ? __('No matching media') : __('No media yet')"
        :description="
          filtered
            ? __('Try another search or type.')
            : __('Upload images, videos, audio and documents once, then reuse them in chats and templates.')
        "
      />

      <div
        v-else
        class="grid grid-cols-1 gap-4 sm:grid-cols-3 sm:gap-3 lg:grid-cols-5"
        :class="{ 'mb-16': !isDesktop && list.total.value <= PAGE_SIZES[0] }"
      >
        <MediaCard v-for="row in list.rows.value" :key="row.name" :item="row" @click="openDetail(row.name)" />
      </div>

      <Pagination v-if="list.total.value > PAGE_SIZES[0]" v-model:page="list.page.value" :total="list.total.value" />
    </div>
  </div>

  <MediaDetail v-model:open="detailOpen" :name="selected" @saved="list.refresh" @deleted="list.refresh" />
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, reactive, ref } from 'vue'
import { Button, FormControl, Progress, ScrollArea, Skeleton, TabButtons, call, toast, useFileUpload } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import FilterChips from '@/components/Common/FilterChips.vue'
import MobileListToolbar from '@/components/Common/MobileListToolbar.vue'
import Pagination from '@/components/Common/Pagination.vue'
import MediaCard from '@/components/Media/MediaCard.vue'
import MediaDetail from '@/components/Media/MediaDetail.vue'
import { mediaTabs, titleFromFile } from '@/components/Media/media'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { useDocList } from '@/composables/useDocList'
import { PAGE_SIZES } from '@/utils/paging'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({ compact: { type: Boolean, default: false } })

const DOCTYPE = 'OneChat Media'

const tabs = mediaTabs()
const input = ref(null)
const mediaType = ref('all')
const detailOpen = ref(false)
const selected = ref(null)
const uploader = useFileUpload()
const uploading = reactive({ active: false, index: 0, count: 0, name: '' })
const { isDesktop } = useBreakpoint()

const list = useDocList({
  doctype: DOCTYPE,
  fields: ['name', 'title', 'file', 'media_type', 'file_size', 'tags', 'modified'],
  searchFields: ['title', 'tags', 'description'],
  filters: () => (mediaType.value === 'all' ? {} : { media_type: mediaType.value }),
  orderBy: 'modified desc',
})

const filtered = computed(() => Boolean(list.search.value.trim()) || mediaType.value !== 'all')

function openDetail(name) {
  selected.value = name
  detailOpen.value = true
}

async function onFiles(event) {
  const files = [...(event.target.files || [])]
  event.target.value = ''
  if (!files.length) return

  Object.assign(uploading, { active: true, index: 0, count: files.length, name: '' })
  let added = 0

  for (const file of files) {
    uploading.index += 1
    uploading.name = file.name

    try {
      const uploaded = await uploader.upload(file, { private: false, folder: 'Home' })
      await call('frappe.client.insert', {
        doc: { doctype: DOCTYPE, title: titleFromFile(file.name), file: uploaded.file_url },
      })
      added += 1
    } catch (err) {
      toast.error(__('{0}: {1}').format(file.name, errorMessage(err)))
    }
  }

  uploading.active = false
  if (added) toast.success(added === 1 ? __('1 file uploaded') : __('{0} files uploaded').format(added))
  list.reload()
}
</script>
