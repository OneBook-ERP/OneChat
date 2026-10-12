<template>
  <AppHeader>
    <template #actions>
      <Button variant="ghost" icon="lucide-refresh-cw" :label="__('Refresh')" :loading="loading" @click="load" />
    </template>
  </AppHeader>

  <ScrollArea class="min-h-0 flex-1">
    <div class="mx-auto flex w-full max-w-[1000px] flex-col gap-4 px-3 pb-10 pt-5 sm:px-5">
      <p class="text-sm text-ink-gray-6">
        {{
          mode === 'Automatic'
            ? __(
                'Contacts with the same phone number are merged automatically every night and when a new contact arrives. Matches on email or a linked record wait here for review.',
              )
            : __(
                'Contacts that look like the same person. Merging keeps every chat, note, reminder and link on one contact, and messages from either number reach it.',
              )
        }}
        <button
          v-if="session.user.is_admin"
          type="button"
          class="ml-1 text-ink-gray-8 underline underline-offset-2 hover:text-ink-gray-9"
          @click="ui.openSettings('defaults')"
        >
          {{ mode === 'Automatic' ? __('Merging automatically. Change in Settings') : __('Merge automatically? Turn it on in Settings') }}
        </button>
      </p>
      <ErrorMessage :message="error" />

      <div v-if="loading && !loaded" class="flex flex-col gap-3">
        <Skeleton v-for="index in 3" :key="index" class="h-36 w-full rounded-5" />
      </div>

      <EmptyState
        v-else-if="!pairs.length"
        icon="lucide-users-round"
        :title="__('No duplicates found')"
        :description="__('Contacts are matched on phone number, email or linked record. A matching name only adds confidence.')"
      />

      <template v-else>
        <p class="text-sm text-ink-gray-5">{{ __('{0} possible duplicates').format(formatNumber(total)) }}</p>
        <article v-for="pair in pairs" :key="pair.key" class="flex flex-col gap-3 rounded-5 border border-outline-gray-1 p-3">
          <div class="flex flex-wrap items-center gap-1.5">
            <Badge
              v-for="reason in pair.reasons"
              :key="reason.kind"
              :theme="['phone', 'record'].includes(reason.kind) ? 'blue' : 'gray'"
              :label="reason.label"
            />
            <Badge v-if="!pair.confident" theme="amber" variant="outline" :label="__('Check carefully')" />
          </div>

          <div class="grid gap-2 md:grid-cols-2">
            <button
              v-for="side in sides(pair)"
              :key="side.row.name"
              type="button"
              class="flex min-w-0 items-start gap-3 rounded-4 border p-3 text-left transition-colors"
              :class="
                choice[pair.key] === side.row.name
                  ? 'border-outline-gray-4 bg-surface-gray-1'
                  : 'border-outline-gray-1 hover:bg-surface-gray-1'
              "
              @click="choice[pair.key] = side.row.name"
            >
              <Avatar size="lg" :image="side.row.profile_image" :label="side.row.contact_name || side.row.mobile_no" />
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-1.5">
                  <TruncatedText
                    as="p"
                    class="truncate text-base font-medium text-ink-gray-9"
                    :text="side.row.contact_name || side.row.mobile_no"
                  />
                  <Badge v-if="choice[pair.key] === side.row.name" size="sm" theme="green" :label="__('Keep')" />
                </div>
                <TruncatedText as="p" class="truncate text-sm tabular-nums text-ink-gray-6" :text="side.row.mobile_no" />
                <TruncatedText as="p" v-if="side.row.email" class="truncate text-sm text-ink-gray-5" :text="side.row.email" />
                <p v-if="side.row.reference_docname" class="truncate text-sm text-ink-gray-5">
                  {{ __(side.row.reference_doctype) }} · {{ side.row.reference_docname }}
                </p>
                <p class="mt-1 text-xs text-ink-gray-5">
                  {{ __('{0} messages').format(formatNumber(side.row.messages)) }}
                  <template v-if="side.row.last_message_at"> · {{ __('last {0}').format(timeAgo(side.row.last_message_at)) }}</template>
                </p>
              </div>
            </button>
          </div>

          <div class="flex flex-wrap items-center justify-end gap-2">
            <Button variant="ghost" :label="__('Open both')" icon-left="lucide-external-link" @click="openBoth(pair)" />
            <Button v-if="session.user.is_admin" variant="subtle" :label="__('Not the same person')" @click="dismiss(pair)" />
            <Button
              v-if="session.user.is_admin"
              variant="solid"
              icon-left="lucide-merge"
              :loading="busy[pair.key]"
              :label="__('Merge into {0}').format(kept(pair).contact_name || kept(pair).mobile_no)"
              @click="confirmMerge(pair)"
            />
          </div>
        </article>
      </template>
    </div>
  </ScrollArea>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Avatar, Badge, Button, ErrorMessage, ScrollArea, Skeleton, call, toast } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import { session } from '@/data/session'
import { useUI } from '@/stores/ui'
import { errorMessage, formatNumber, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({ compact: { type: Boolean, default: false } })

const METHOD = 'onechat.inbox.duplicates.'

const router = useRouter()
const ui = useUI()

const pairs = ref([])
const total = ref(0)
const mode = ref('Manual')
const loading = ref(false)
const loaded = ref(false)
const error = ref('')
const choice = reactive({})
const busy = reactive({})

function sides(pair) {
  return [{ row: pair.keep }, { row: pair.merge }]
}

function kept(pair) {
  return choice[pair.key] === pair.merge.name ? pair.merge : pair.keep
}

function dropped(pair) {
  return choice[pair.key] === pair.merge.name ? pair.keep : pair.merge
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await call(`${METHOD}suggestions`)
    pairs.value = data.pairs
    total.value = data.total
    mode.value = data.mode
    for (const pair of data.pairs) choice[pair.key] = choice[pair.key] || pair.keep.name
    loaded.value = true
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

function openBoth(pair) {
  for (const row of [pair.keep, pair.merge]) {
    window.open(router.resolve({ name: 'CustomerProfile', params: { contact: row.name } }).href, '_blank', 'noopener')
  }
}

async function dismiss(pair) {
  try {
    await call(`${METHOD}ignore`, { key: pair.key })
    pairs.value = pairs.value.filter((row) => row.key !== pair.key)
    total.value -= 1
  } catch (err) {
    toast.error(errorMessage(err))
  }
}

function confirmMerge(pair) {
  const keep = kept(pair)
  const drop = dropped(pair)
  ui.confirm({
    title: __('Merge into {0}?').format(keep.contact_name || keep.mobile_no),
    message: __(
      '{0} is removed. Its chats, notes, reminders, labels and links move to {1}, and messages from {2} will reach {1}. This cannot be undone.',
    ).format(drop.contact_name || drop.mobile_no, keep.contact_name || keep.mobile_no, drop.mobile_no),
    action: __('Merge'),
    onConfirm: async () => {
      busy[pair.key] = true
      try {
        await call(`${METHOD}merge`, { keep: keep.name, duplicate: drop.name })
        toast.success(__('Contacts merged'))
        pairs.value = pairs.value.filter((row) => row.key !== pair.key && !row.key.split('|').includes(drop.name))
        total.value = pairs.value.length
      } catch (err) {
        toast.error(errorMessage(err))
      } finally {
        busy[pair.key] = false
      }
    },
  })
}

onMounted(load)
</script>
