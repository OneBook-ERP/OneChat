<template>
  <AppHeader>
    <template #actions>
      <Button variant="solid" icon-left="lucide-plus" :label="__('New note')" @click="openNote(null)" />
    </template>
  </AppHeader>

  <div class="mx-auto flex min-h-0 w-full max-w-[1100px] flex-1 flex-col px-3 pb-3 pt-5 sm:px-5">
    <DocListView
      :list="list"
      :columns="columns"
      :search-placeholder="__('Search notes')"
      empty-icon="lucide-notebook-pen"
      :empty-title="__('No notes yet')"
      :empty-description="__('Keep context about customers and conversations in one place.')"
      export-name="onechat-notes"
      @open="(row) => openNote(row.name)"
    >
      <template #cell-title="{ row }">
        <div class="min-w-0 py-0.5">
          <TruncatedText as="p" class="truncate text-base font-medium text-ink-gray-8" :text="row.title || __('Untitled note')" />
          <TruncatedText as="p" class="truncate text-sm text-ink-gray-5" :text="plainText(row.content)" />
        </div>
      </template>

      <template #cell-reference_docname="{ row }">
        <span v-if="row.reference_docname" class="inline-flex min-w-0 items-center gap-1.5 text-base text-ink-gray-7">
          <span
            :class="row.reference_doctype === 'OneChat Contact' ? 'lucide-contact' : 'lucide-link'"
            class="size-3.5 shrink-0 text-ink-gray-5"
            aria-hidden="true"
          />
          <TruncatedText class="truncate" :text="linkLabel(row)" />
        </span>
        <span v-else class="text-base text-ink-gray-4">—</span>
      </template>
    </DocListView>
  </div>

  <NoteDialog v-model:open="dialog" :name="editing" @saved="list.refresh" @deleted="list.refresh" />
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { reactive, ref, watch } from 'vue'
import { Button, call } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import DocListView from '@/components/Common/DocListView.vue'
import NoteDialog from '@/components/Contacts/NoteDialog.vue'
import { useDocList } from '@/composables/useDocList'
import { session } from '@/data/session'
import { plainText, timeAgo } from '@/utils/format'
import { translate as __ } from '@/translation'

defineProps({ compact: { type: Boolean, default: false } })

const dialog = ref(false)
const editing = ref(null)
const contactNames = reactive({})

const list = useDocList({
  doctype: 'OneChat Note',
  fields: ['name', 'title', 'content', 'reference_doctype', 'reference_docname', 'owner', 'modified'],
  searchFields: ['title', 'content', 'reference_docname'],
  quickFilters: [
    {
      key: 'owner',
      label: 'Author',
      options: [{ label: __('Written by me'), value: session.user.name }],
    },
  ],
  sortOptions: [
    { label: 'Recently updated', value: 'modified desc' },
    { label: 'Newest first', value: 'creation desc' },
    { label: 'Title', value: 'title asc' },
  ],
})

const columns = [
  { key: 'title', label: 'Note', width: 'minmax(0,3fr)' },
  { key: 'reference_docname', label: 'Linked to', hideOnMobile: true, format: (value, row) => linkLabel(row) },
  { key: 'owner', label: 'Author', hideOnMobile: true },
  { key: 'modified', label: 'Updated', width: '120px', format: timeAgo },
]

function linkLabel(row) {
  if (!row.reference_docname) return ''
  if (row.reference_doctype === 'OneChat Contact') return contactNames[row.reference_docname] || row.reference_docname

  return `${__(row.reference_doctype)} · ${row.reference_docname}`
}

function openNote(name) {
  editing.value = name
  dialog.value = true
}

watch(list.rows, async (rows) => {
  const missing = [
    ...new Set(
      rows
        .filter((row) => row.reference_doctype === 'OneChat Contact' && row.reference_docname)
        .map((row) => row.reference_docname)
        .filter((name) => !(name in contactNames)),
    ),
  ]
  if (!missing.length) return

  const contacts = await call('frappe.client.get_list', {
    doctype: 'OneChat Contact',
    fields: ['name', 'contact_name', 'mobile_no'],
    filters: { name: ['in', missing] },
    limit_page_length: missing.length,
  }).catch(() => [])

  for (const name of missing) contactNames[name] = name
  for (const contact of contacts) contactNames[contact.name] = contact.contact_name || contact.mobile_no || contact.name
})
</script>
