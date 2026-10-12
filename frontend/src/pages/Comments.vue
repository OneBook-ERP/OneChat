<template>
  <AppHeader>
    <template #actions>
      <Button icon-left="lucide-refresh-cw" :label="__('Refresh')" :loading="loading" @click="load(true)" />
    </template>
  </AppHeader>

  <div class="mx-auto flex min-h-0 w-full max-w-[1100px] flex-1 flex-col gap-3 px-3 pb-3 pt-5 sm:px-5">
    <div v-if="isDesktop" class="flex flex-wrap items-center gap-2">
      <TabButtons v-model="filters.status" :buttons="statusTabs" />
      <div class="flex flex-1 flex-wrap items-center justify-end gap-2">
        <FormControl v-model="filters.search" class="w-56" :placeholder="__('Search comments or people')">
          <template #prefix><span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" /></template>
        </FormControl>
        <Select v-if="accounts.length > 1" v-model="filters.account" class="w-40" :options="accountOptions" />
        <Select v-model="filters.post" class="w-48" :options="postOptions" />
        <Select v-model="filters.days" class="w-36" :options="dayOptions" />
      </div>
    </div>

    <template v-else>
      <div class="flex items-center gap-2">
        <FormControl v-model="filters.search" class="min-w-0 flex-1" size="lg" type="search" :placeholder="__('Search comments')">
          <template #prefix><span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" /></template>
        </FormControl>
        <div class="relative shrink-0">
          <Button size="lg" variant="subtle" icon="lucide-sliders-horizontal" :label="__('Filters')" @click="filterSheet = true" />
          <Badge
            v-if="filterCount"
            class="pointer-events-none absolute -right-1.5 -top-1.5 tabular-nums"
            variant="solid"
            theme="blue"
            size="sm"
            :label="String(filterCount)"
          />
        </div>
      </div>
      <div class="-mx-3 overflow-x-auto px-3">
        <TabButtons v-model="filters.status" :buttons="statusTabs" class="w-max" />
      </div>
    </template>

    <ResponsiveDialog v-model:open="filterSheet" :title="__('Filters')" size="sm">
      <template #default="{ close }">
        <FilterChips v-if="accounts.length > 1" v-model="filters.account" :label="__('Account')" :options="accountOptions" />
        <FilterChips v-model="filters.days" :label="__('When')" :options="dayOptions" />
        <Select v-model="filters.post" :label="__('Post')" :options="postOptions" />
        <Button class="mt-2 w-full" variant="solid" size="lg" :label="__('Show comments')" @click="close" />
      </template>
    </ResponsiveDialog>

    <div
      v-if="job"
      class="flex flex-col gap-1.5 rounded bg-surface-gray-2 px-3 py-2 text-sm text-ink-gray-7"
      :class="isDesktop ? '' : 'sticky top-0 z-10'"
      aria-live="polite"
    >
      <span>{{ __(job.label).format(job.done + job.failed, job.total) }}</span>
      <Progress :value="Math.round(((job.done + job.failed) * 100) / job.total)" size="sm" />
    </div>

    <div
      v-else-if="selected.size"
      class="flex flex-wrap items-center gap-2 rounded bg-surface-gray-2 px-3 py-2 text-sm text-ink-gray-7"
      :class="isDesktop ? '' : 'sticky top-0 z-10'"
    >
      <span class="mr-auto sm:mr-0">{{ __('{0} selected').format(selected.size) }}</span>
      <Button size="sm" icon-left="lucide-send" :label="__('Reply privately')" @click="openReply('private')" />
      <Button size="sm" variant="ghost" icon-left="lucide-reply" :label="__('Reply publicly')" @click="openReply('public')" />
      <Button size="sm" icon-left="lucide-eye-off" :label="__('Hide')" :loading="bulk" @click="hideSelected(1)" />
      <Button size="sm" variant="ghost" icon-left="lucide-eye" :label="__('Unhide')" :loading="bulk" @click="hideSelected(0)" />
      <Button size="sm" variant="ghost" :label="__('Clear')" @click="selected = new Set()" />
    </div>

    <ErrorMessage :message="error" />

    <ResponsiveDialog v-model:open="replyDialog" :title="__(replyCopy.title)" size="lg">
      <template #default>
        <p class="mb-3 text-sm text-ink-gray-6">{{ __(replyCopy.bulkHelp).format(replyDays) }}</p>
        <PersonalizedText v-model="replyText" :rows="4" :variables="CONTACT_DETAILS" :placeholder="__(replyCopy.placeholder)" />
      </template>
      <template #actions>
        <Button
          variant="solid"
          class="w-full"
          size="lg"
          :loading="replying"
          :disabled="!replyText.trim()"
          :label="__('Send to {0}').format(selected.size)"
          @click="sendReplies"
        />
      </template>
    </ResponsiveDialog>

    <div class="min-h-0 flex-1 overflow-y-auto" :class="rows.length ? 'rounded border border-outline-gray-1' : ''">
      <div v-if="loading && !rows.length" class="flex flex-col gap-3 p-4">
        <Skeleton v-for="row in 6" :key="row" class="h-16 w-full" />
      </div>

      <EmptyState
        v-else-if="!rows.length"
        icon="lucide-message-square-text"
        :title="__('No comments here')"
        :description="__('Comments on your Instagram posts and reels show up here as they come in.')"
      />

      <div v-else class="divide-y divide-outline-gray-1">
        <div v-for="row in rows" :key="row.name" class="flex gap-3 px-3 py-3" :class="row.comment_hidden ? 'opacity-70' : ''">
          <Checkbox class="mt-1" :model-value="selected.has(row.name)" @update:model-value="toggle(row.name)" />

          <a
            v-if="row.link_url"
            :href="row.link_url"
            target="_blank"
            class="size-10 shrink-0 overflow-hidden rounded bg-surface-gray-2 sm:size-12"
            :title="__('Open post')"
          >
            <img v-if="thumbnailOf(row)" :src="thumbnailOf(row)" class="h-full w-full object-cover" loading="lazy" />
            <span v-else class="lucide-image flex h-full w-full items-center justify-center text-ink-gray-4" />
          </a>

          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <Avatar :image="row.profile_image" :label="nameOf(row)" size="sm" />
              <span class="truncate text-base font-medium text-ink-gray-8">{{ nameOf(row) }}</span>
              <span v-if="row.instagram_username" class="hidden truncate text-sm text-ink-gray-5 sm:inline"
                >@{{ row.instagram_username }}</span
              >
              <span class="ml-auto shrink-0 text-sm text-ink-gray-5" :title="row.creation">{{ timeAgo(row.creation) }}</span>
            </div>

            <p class="mt-1 whitespace-pre-wrap break-words text-base text-ink-gray-8">{{ row.message }}</p>

            <div
              v-for="(reply, index) in row.replies"
              :key="index"
              class="mt-1.5 flex gap-1.5 border-l-2 border-outline-gray-2 pl-2 text-sm text-ink-gray-6"
            >
              <span class="lucide-reply mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              <span class="break-words">{{ reply.message }}</span>
            </div>

            <div class="flex flex-wrap items-center">
              <CommentActions :message="row" @changed="load(true)" />
              <Button
                class="mt-1.5"
                size="sm"
                variant="ghost"
                icon-left="lucide-message-circle"
                :label="__('Open chat')"
                @click="openChat(row)"
              />
            </div>
          </div>
        </div>

        <div v-if="hasMore" class="flex justify-center p-3">
          <Button :label="__('Load more')" :loading="loading" @click="load(false)" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Avatar,
  Badge,
  Button,
  Checkbox,
  ErrorMessage,
  FormControl,
  Progress,
  Select,
  Skeleton,
  TabButtons,
  call,
  debounce,
  toast,
} from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import FilterChips from '@/components/Common/FilterChips.vue'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import PersonalizedText from '@/components/Common/PersonalizedText.vue'
import { CONTACT_DETAILS } from '@/data/personalization'
import { REPLY_DAYS, REPLY_MODES, postImage } from '@/data/instagram'
import { toggled } from '@/utils/collections'
import CommentActions from '@/components/Inbox/CommentActions.vue'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { useSocket } from '@/data/socket'
import { errorMessage, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

const PAGE = 50
const STATUSES = [
  { value: 'unreplied', label: 'Needs reply' },
  { value: 'replied', label: 'Replied' },
  { value: 'hidden', label: 'Hidden' },
  { value: 'all', label: 'All' },
]

const router = useRouter()
const { isDesktop } = useBreakpoint()
const filterSheet = ref(false)

const filters = reactive({ status: 'unreplied', search: '', account: '', post: '', days: '30' })
const rows = ref([])
const totals = ref({})
const posts = ref([])
const hasMore = ref(false)
const loading = ref(false)
const bulk = ref(false)
const job = ref(null)
const replyDialog = ref(false)
const replyMode = ref('private')
const replyText = ref('')
const bulkLimit = ref(100)
const replyDays = ref(REPLY_DAYS)
const replyCopy = computed(() => REPLY_MODES[replyMode.value])
const replying = ref(false)
const error = ref('')
const selected = ref(new Set())

const statusTabs = computed(() =>
  STATUSES.map((row) => ({
    value: row.value,
    label: totals.value[row.value] !== undefined ? `${__(row.label)} · ${totals.value[row.value]}` : __(row.label),
  })),
)

const accounts = computed(() => [...new Set(posts.value.map((post) => post.account))])
const accountOptions = computed(() => [
  { label: __('All accounts'), value: '' },
  ...accounts.value.map((name) => ({ label: name, value: name })),
])

const postOptions = computed(() => [
  { label: __('All posts'), value: '' },
  ...posts.value
    .filter((post) => !filters.account || post.account === filters.account)
    .map((post) => ({ label: caption(post), value: post.id })),
])

const filterCount = computed(() => [filters.account, filters.post, filters.days !== '30' ? 1 : ''].filter(Boolean).length)

const dayOptions = [
  { label: __('Last 7 days'), value: '7' },
  { label: __('Last 30 days'), value: '30' },
  { label: __('Last 90 days'), value: '90' },
  { label: __('Any time'), value: '' },
]

const images = computed(() => Object.fromEntries(posts.value.map((post) => [post.id, postImage(post)])))

function caption(post) {
  const text = (post.caption || '').replace(/\s+/g, ' ').trim()
  const date = post.timestamp ? new Date(post.timestamp).toLocaleDateString() : ''
  return [date, text.length > 32 ? `${text.slice(0, 32)}…` : text || __('No caption')].filter(Boolean).join(' · ')
}

function thumbnailOf(row) {
  return images.value[row.media_id]
}

function nameOf(row) {
  return row.contact_name || row.profile_name || row.instagram_username || __('Instagram user')
}

let request = 0

async function load(reset = true) {
  const current = ++request
  loading.value = true
  error.value = ''
  try {
    const result = await call('onechat.instagram.comments.moderation', {
      account: filters.account || null,
      post: filters.post || null,
      status: filters.status,
      search: filters.search || null,
      days: filters.days || null,
      start: reset ? 0 : rows.value.length,
      page_length: PAGE,
    })
    if (current !== request) return
    rows.value = reset ? result.comments : [...rows.value, ...result.comments]
    totals.value = result.totals
    bulkLimit.value = result.bulk_limit || bulkLimit.value
    replyDays.value = result.reply_days || replyDays.value
    hasMore.value = result.has_more
    if (reset) selected.value = new Set()
  } catch (err) {
    if (current === request) error.value = errorMessage(err)
  } finally {
    if (current === request) loading.value = false
  }
}

async function loadPosts() {
  try {
    posts.value = await call('onechat.instagram.comments.recent_posts')
  } catch {
    posts.value = []
  }
}

function toggle(name) {
  if (!selected.value.has(name) && selected.value.size >= bulkLimit.value) {
    toast.warning(__('You can act on up to {0} comments at a time.').format(bulkLimit.value))
    return
  }
  selected.value = toggled(selected.value, name)
}

function openReply(mode) {
  replyMode.value = mode
  replyText.value = ''
  replyDialog.value = true
}

const JOB_COPY = {
  reply: { label: 'Replying… {0} of {1}', success: 'Sent {0} replies', partial: 'Sent {0}, skipped {1}' },
  hide: { label: 'Hiding… {0} of {1}', success: 'Hid {0} comments', partial: 'Hid {0}, {1} could not be hidden' },
  show: { label: 'Showing… {0} of {1}', success: 'Showed {0} comments', partial: 'Showed {0}, {1} could not be shown' },
}

function startJob(kind, result) {
  job.value = { ...JOB_COPY[kind], id: result.job, total: result.total, done: 0, failed: 0 }
  selected.value = new Set()
}

function onJobProgress(data) {
  if (!job.value || data.job !== job.value.id) return
  Object.assign(job.value, { done: data.done, failed: data.failed })
  if (!data.finished) return
  const { success, partial } = job.value
  if (data.failed) toast.warning(__(partial).format(data.done, data.failed))
  else toast.success(__(success).format(data.done))
  job.value = null
  load(true)
}

async function sendReplies() {
  replying.value = true
  try {
    const result = await call('onechat.instagram.comments.reply_many', {
      messages: [...selected.value],
      mode: replyMode.value,
      text: replyText.value,
    })
    replyDialog.value = false
    startJob('reply', result)
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    replying.value = false
  }
}

async function hideSelected(hidden) {
  bulk.value = true
  try {
    startJob(hidden ? 'hide' : 'show', await call('onechat.instagram.comments.hide_many', { messages: [...selected.value], hidden }))
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    bulk.value = false
  }
}

function openChat(row) {
  router.push({ name: 'Inbox', params: { contact: row.contact } })
}

const search = debounce(() => load(true), 300)

watch(() => filters.search, search)
watch(
  () => filters.account,
  () => {
    if (filters.post) filters.post = ''
    else load(true)
  },
)
watch(
  () => [filters.status, filters.post, filters.days],
  () => load(true),
)

onMounted(() => {
  useSocket().on('onechat_comment_bulk', onJobProgress)
  load(true)
  loadPosts()
})

onBeforeUnmount(() => useSocket().off('onechat_comment_bulk', onJobProgress))
</script>
