<template>
  <AppHeader>
    <template #actions>
      <Button variant="solid" icon-left="lucide-plus" :label="__('New contact')" @click="openNew" />
    </template>
  </AppHeader>

  <div class="mx-auto flex min-h-0 w-full max-w-[1100px] flex-1 flex-col px-3 pb-3 pt-5 sm:px-5">
    <div v-if="band" class="mb-3 flex items-center gap-2 text-sm text-ink-gray-6">
      <span class="lucide-filter size-3.5" aria-hidden="true" />
      <span>{{ __('Showing {0} contacts (engagement {1}–{2})').format(__(band.label).toLowerCase(), band.min, band.max) }}</span>
      <Button
        size="sm"
        variant="ghost"
        :label="__('Clear')"
        @click="router.replace({ query: { ...route.query, engagement: undefined } })"
      />
    </div>
    <DocListView
      :list="list"
      :columns="columns"
      :search-placeholder="__('Search name, number, email or @username')"
      empty-icon="lucide-contact"
      :empty-title="__('No contacts yet')"
      :empty-description="__('Contacts appear here when someone messages you, or when you add them.')"
      export-name="whatsapp-contacts"
      importable
      @open="openDetail"
    >
      <template #cell-contact_name="{ row }">
        <div class="flex min-w-0 items-center gap-2.5">
          <Avatar :image="row.profile_image" :label="title(row)" size="lg" />
          <div class="min-w-0">
            <div class="flex min-w-0 items-center gap-1.5">
              <TruncatedText
                as="p"
                class="truncate text-base font-medium text-ink-gray-9"
                :class="{ 'text-ink-gray-5 line-through': row.disable }"
                :text="title(row)"
                :tip="row.contact_name || ''"
              />
              <ChannelIcon :channel="row.channel" show-whatsapp class="size-3.5 shrink-0" />
              <Badge v-if="row.opted_out" theme="red" size="sm" :label="__('Opted out')" />
            </div>
            <TruncatedText as="p" class="truncate text-sm tabular-nums text-ink-gray-5" :text="subtitle(row)" />
          </div>
        </div>
      </template>

      <template #cell-assigned_to="{ value }">
        <div v-if="value" class="flex min-w-0 items-center gap-1.5" :title="agentName(value)">
          <Avatar :label="agentName(value)" size="sm" />
          <TruncatedText class="truncate text-base text-ink-gray-7" :text="agentName(value).split(' ')[0]" />
        </div>
        <span v-else class="text-base text-ink-gray-4">{{ __('Unassigned') }}</span>
      </template>

      <template #cell-value_group="{ value }">
        <Badge v-if="value" :theme="groupMeta(value).theme" :label="__(value)" />
        <span v-else class="text-base text-ink-gray-4">—</span>
      </template>

      <template #cell-engagement_score="{ value }">
        <div class="flex w-full items-center justify-end gap-2" :title="__('Engagement score {0}/100').format(value || 0)">
          <div class="h-1.5 w-10 overflow-hidden rounded-full bg-surface-gray-3">
            <div class="h-full rounded-full" :class="engagementColor(value)" :style="{ width: `${Math.min(value || 0, 100)}%` }" />
          </div>
          <span class="w-6 text-right text-sm tabular-nums text-ink-gray-7">{{ value || 0 }}</span>
        </div>
      </template>

      <template #cell-reference_doctype="{ row, value }">
        <div v-if="value" class="flex min-w-0 items-center gap-1.5" :title="`${__(value)} · ${row.reference_docname}`">
          <Badge :theme="linkMeta(value).theme" :label="__(value)" class="shrink-0" />
          <TruncatedText v-if="row.reference_docname" class="truncate text-sm text-ink-gray-5" :text="row.reference_docname" />
        </div>
        <span v-else class="text-base text-ink-gray-4">—</span>
      </template>

      <template #cell-last_message_at="{ row, value }">
        <div class="flex items-center gap-1.5">
          <TruncatedText class="truncate text-base text-ink-gray-7" :text="shortTime(value)" />
          <Badge v-if="row.unread_count" theme="green" variant="solid" size="sm" :label="countLabel(row.unread_count)" />
        </div>
      </template>
    </DocListView>
  </div>

  <ContactFormDialog v-model:open="formOpen" :name="editing" :defaults="defaults" @saved="saved" @deleted="list.refresh" />
</template>

<script setup>
import ChannelIcon from '@/components/Common/ChannelIcon.vue'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Avatar, Badge, Button } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import DocListView from '@/components/Common/DocListView.vue'
import ContactFormDialog from '@/components/Contacts/ContactFormDialog.vue'
import { useDocList } from '@/composables/useDocList'
import { agents } from '@/data/inbox'
import { hasPurchases, linkMeta } from '@/data/integrations'
import { engagementBand, groupMeta } from '@/data/segments'
import { countLabel, shortTime } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({ compact: { type: Boolean, default: false } })

const route = useRoute()
const router = useRouter()

const referenceType = computed(() => route.query.link || null)
const valueGroup = computed(() => route.query.group || null)
const band = computed(() => engagementBand(route.query.engagement))

const list = useDocList({
  doctype: 'OneChat Contact',
  fields: [
    'name',
    'contact_name',
    'mobile_no',
    'email',
    'channel',
    'instagram_username',
    'profile_image',
    'disable',
    'reference_doctype',
    'reference_docname',
    'last_message_at',
    'unread_count',
    'assigned_to',
    'opted_out',
    'value_group',
    'engagement_score',
  ],
  searchFields: ['contact_name', 'mobile_no', 'email', 'instagram_username', 'reference_docname'],
  filters: () => ({
    ...(referenceType.value ? { reference_doctype: referenceType.value } : {}),
    ...(valueGroup.value ? { value_group: valueGroup.value } : {}),
    ...(band.value ? { engagement_score: ['between', [band.value.min, band.value.max]] } : {}),
  }),
  quickFilters: [
    {
      key: 'channel',
      label: 'Channel',
      options: [
        { label: __('WhatsApp'), value: 'WhatsApp' },
        { label: __('Instagram'), value: 'Instagram' },
      ],
    },
    {
      key: 'disable',
      label: 'Status',
      options: [
        { label: __('Active'), value: '0' },
        { label: __('Disabled'), value: '1' },
      ],
      toFilter: Number,
    },
    {
      key: 'opted_out',
      label: 'Consent',
      options: [
        { label: __('Opted out'), value: '1' },
        { label: __('Subscribed'), value: '0' },
      ],
      toFilter: Number,
    },
  ],
  sortOptions: [
    { label: 'Recently updated', value: 'modified desc' },
    { label: 'Latest message', value: 'last_message_at desc' },
    { label: 'Name', value: 'contact_name asc' },
    { label: 'Newest first', value: 'creation desc' },
    { label: 'Most engaged', value: 'engagement_score desc' },
  ],
})

function title(row) {
  return row.contact_name || row.mobile_no || (row.instagram_username && `@${row.instagram_username}`) || row.name
}

function subtitle(row) {
  const handle = row.instagram_username ? `@${row.instagram_username}` : ''
  return [row.channel === 'Instagram' ? handle : phone(row.mobile_no), row.email].filter(Boolean).join(' · ') || '—'
}

const columns = computed(() => [
  { key: 'contact_name', label: 'Contact', width: 'minmax(0,2.4fr)' },
  { key: 'reference_doctype', label: 'Linked to', width: 'minmax(0,1.3fr)' },
  ...(hasPurchases.value ? [{ key: 'value_group', label: 'Value group', width: '130px', hideOnMobile: true }] : []),
  { key: 'engagement_score', label: 'Engagement', width: '110px', align: 'right', hideOnMobile: true },
  { key: 'last_message_at', label: 'Last message', width: '120px', hideOnMobile: true, format: shortTime },
  {
    key: 'assigned_to',
    label: 'Assigned to',
    width: 'minmax(0,1fr)',
    hideOnMobile: true,
    format: (value) => (value ? agentName(value) : ''),
  },
  { key: 'channel', label: 'Channel', exportOnly: true },
  { key: 'mobile_no', label: 'Mobile', exportOnly: true },
  { key: 'instagram_username', label: 'Instagram username', exportOnly: true },
  { key: 'email', label: 'Email', exportOnly: true },
  { key: 'reference_docname', label: 'Linked record', exportOnly: true },
])

if (!agents.fetched && !agents.loading) agents.fetch()

function agentName(user) {
  return (agents.data || []).find((row) => row.name === user)?.full_name || user
}

function phone(value) {
  const digits = String(value || '').replace(/\D/g, '')
  if (digits.length <= 10) return value || ''
  return `+${digits.slice(0, -10)} ${digits.slice(-10, -5)} ${digits.slice(-5)}`
}

function engagementColor(value) {
  if (value >= 70) return 'bg-surface-green-6'
  if (value >= 40) return 'bg-surface-blue-5'
  if (value >= 15) return 'bg-surface-amber-5'
  return 'bg-surface-gray-5'
}

const formOpen = ref(false)
const editing = ref(null)

const defaults = computed(() => ({ reference_doctype: referenceType.value || '', disable: 0 }))

function openNew() {
  editing.value = null
  formOpen.value = true
}

function openEdit(name) {
  editing.value = name
  formOpen.value = true
}

function openDetail(row) {
  router.push({ name: 'CustomerProfile', params: { contact: row.name } })
}

function saved(doc) {
  list.refresh()
  if (!editing.value && doc?.name) openDetail(doc)
  else if (editing.value && route.query.edit) router.push({ name: 'CustomerProfile', params: { contact: editing.value } })
}

function editFromRoute() {
  if (route.query.edit) openEdit(route.query.edit)
}

watch(() => route.query.edit, editFromRoute)
onMounted(editFromRoute)
</script>
