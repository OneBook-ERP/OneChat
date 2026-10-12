<template>
  <p v-if="!mayReply && !mayNote" class="flex shrink-0 items-center gap-1.5 border-t px-4 py-3 text-sm text-ink-gray-5">
    <span class="lucide-lock size-4 shrink-0" aria-hidden="true" />
    {{ __('Your role can only read this chat. Ask an admin to allow sending in Role Permission Manager.') }}
  </p>
  <div
    v-else
    class="shrink-0 border-t px-2 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] transition-colors sm:px-3"
    :class="noteMode ? 'border-outline-amber-2 bg-surface-amber-1' : 'bg-surface-base'"
    @dragover.prevent
    @drop.prevent="onDrop"
  >
    <div class="flex flex-col gap-2">
      <div class="flex items-center gap-2">
        <TabButtons v-if="modes.length > 1" v-model="mode" :options="modes" />
        <span v-if="noteMode" class="flex min-w-0 items-center gap-1 truncate text-xs text-ink-amber-7">
          <span class="lucide-lock size-3.5 shrink-0" aria-hidden="true" />
          <TruncatedText class="truncate" :text="noteHint" />
        </span>
        <span
          v-else-if="instagram && !humanWindowOpen"
          class="flex min-w-0 flex-1 items-center gap-1.5 text-sm text-ink-amber-8"
          role="status"
        >
          <span class="lucide-clock-alert size-3.5 shrink-0" aria-hidden="true" />
          <Tooltip :text="__('Instagram only allows replies within 7 days of the customer’s last message.')">
            <span class="min-w-0 truncate">{{ __('Reply window closed until they message again') }}</span>
          </Tooltip>
        </span>
        <span v-else-if="instagram && !windowOpen" class="flex min-w-0 flex-1 items-center gap-1.5 text-sm text-ink-gray-6" role="status">
          <span class="lucide-user-round-check size-3.5 shrink-0" aria-hidden="true" />
          <Tooltip
            :text="
              __(
                'More than 24 hours since their last message. Your reply is sent with Instagram’s Human Agent tag, allowed for 7 days. Bots and auto-replies stop at 24 hours.',
              )
            "
          >
            <span class="min-w-0 truncate">{{ __('Replying as a human agent') }}</span>
          </Tooltip>
        </span>
        <span v-else-if="!windowOpen && !instagram" class="flex min-w-0 flex-1 items-center gap-1.5 text-sm text-ink-amber-8" role="status">
          <span class="lucide-clock-alert size-3.5 shrink-0" aria-hidden="true" />
          <Tooltip
            :text="__('The 24-hour reply window is closed. WhatsApp only delivers template messages until this contact writes back.')"
          >
            <span class="min-w-0 truncate">{{ __('Reply window closed') }}</span>
          </Tooltip>
          <button type="button" class="shrink-0 font-medium underline underline-offset-2" @click="emit('templates')">
            {{ __('Send a template') }}
          </button>
        </span>
      </div>

      <div
        v-if="!noteMode && collision"
        class="flex items-center gap-2 rounded-4 px-3 py-1.5 text-sm"
        :class="collision.urgent ? 'bg-surface-amber-1 text-ink-amber-8' : 'bg-surface-gray-2 text-ink-gray-7'"
        role="status"
        aria-live="polite"
      >
        <span :class="collision.icon" class="size-3.5 shrink-0" aria-hidden="true" />
        <TruncatedText class="min-w-0 flex-1 truncate" :text="collision.text" />
        <Button v-if="collision.claim" size="sm" variant="subtle" :label="__('Assign to me')" @click="claim" />
      </div>

      <ReplyPreview v-if="reply && !noteMode" :message="reply" :contact-name="contactName" removable @cancel="reply = null" />

      <AttachmentPreview
        v-if="file && !noteMode"
        :file="file"
        :progress="progress"
        :uploading="uploading"
        :error="uploadError"
        @remove="removeFile"
      />

      <div class="relative flex items-end gap-1">
        <div
          v-if="suggest.open"
          class="absolute inset-x-0 bottom-full z-10 mb-2 overflow-hidden rounded-4 border border-outline-gray-2 bg-surface-elevation-2 shadow-lg"
        >
          <p v-if="suggest.kind === 'mention'" class="border-b border-outline-gray-1 px-3 py-1.5 text-xs text-ink-gray-5">
            {{ __('Mention a teammate') }}
            <span v-if="!touch" class="ml-1 text-ink-gray-4">{{ __('↑ ↓ to move · Enter to pick · Esc to close') }}</span>
          </p>
          <p v-else class="border-b border-outline-gray-1 px-3 py-1.5 text-xs text-ink-gray-5">
            {{ __('Quick replies') }}
            <span v-if="!touch" class="ml-1 text-ink-gray-4">{{ __('↑ ↓ to move · Enter to insert · Esc to close') }}</span>
          </p>
          <ScrollArea viewport-class="max-h-64 p-1">
            <div v-if="suggest.kind === 'mention'" :id="`quick-replies-${contact}`" role="listbox" :aria-label="__('Teammates')">
              <button
                v-for="(item, index) in suggestions"
                :id="`quick-reply-${contact}-${index}`"
                :key="item.name"
                type="button"
                role="option"
                :aria-selected="index === suggest.index"
                class="flex w-full items-center gap-2 rounded-3 px-2 py-1.5 text-left"
                :class="index === suggest.index ? 'bg-surface-gray-3' : 'hover:bg-surface-gray-2'"
                @mousedown.prevent
                @mouseenter="suggest.index = index"
                @click="choose(item)"
              >
                <Avatar size="sm" :image="item.image" :label="item.full_name || item.name" />
                <TruncatedText class="min-w-0 flex-1 truncate text-sm text-ink-gray-8" :text="item.full_name || item.name" />
              </button>
              <p v-if="!suggestions.length" class="px-2 py-3 text-sm text-ink-gray-5">
                {{ __('No teammate matches @{0}').format(suggest.query) }}
              </p>
            </div>
            <div v-else-if="suggestions.length" :id="`quick-replies-${contact}`" role="listbox" :aria-label="__('Quick replies')">
              <button
                v-for="(item, index) in suggestions"
                :id="`quick-reply-${contact}-${index}`"
                :key="item.name"
                type="button"
                role="option"
                :aria-selected="index === suggest.index"
                class="flex w-full items-start gap-2 rounded-3 px-2 py-1.5 text-left"
                :class="index === suggest.index ? 'bg-surface-gray-3' : 'hover:bg-surface-gray-2'"
                @mousedown.prevent
                @mouseenter="suggest.index = index"
                @click="insertReply(item)"
              >
                <span class="shrink-0 rounded-3 bg-surface-gray-2 px-1.5 py-0.5 font-mono text-xs text-ink-gray-7">
                  /{{ item.shortcut }}
                </span>
                <span class="min-w-0 flex-1">
                  <span class="flex items-center gap-1.5">
                    <TruncatedText class="truncate text-sm font-medium text-ink-gray-8" :text="item.title" />
                    <span v-if="item.attach" class="lucide-paperclip size-3.5 shrink-0 text-ink-gray-5" aria-hidden="true" />
                  </span>
                  <TruncatedText class="block truncate text-xs text-ink-gray-5" :text="item.message || fileName(item.attach)" />
                </span>
                <img v-if="isImage(item.attach)" :src="item.attach" alt="" class="size-9 shrink-0 rounded-3 object-cover" loading="lazy" />
              </button>
            </div>
            <p v-else-if="quickReplies.loading && !quickReplies.data?.length" class="px-2 py-3 text-sm text-ink-gray-5">
              {{ __('Loading…') }}
            </p>
            <p v-else-if="!quickReplies.data?.length" class="px-2 py-3 text-sm text-ink-gray-5">
              {{ __('No quick replies yet. Add them under Settings → Quick replies.') }}
            </p>
            <p v-else class="px-2 py-3 text-sm text-ink-gray-5">
              {{ __('No quick reply matches /{0}').format(suggest.query) }}
            </p>
          </ScrollArea>
        </div>

        <Button
          v-if="!noteMode && compact"
          variant="ghost"
          size="lg"
          icon="lucide-plus"
          :label="__('Attach, template or quick reply')"
          :disabled="uploading"
          @click="more = true"
        />

        <template v-else-if="!noteMode">
          <Dropdown :options="attachOptions" side="top" align="start" :disabled="uploading">
            <Button
              variant="ghost"
              icon="lucide-paperclip"
              :tooltip="__('Attach a file')"
              :label="__('Attach a file')"
              :disabled="uploading"
            />
          </Dropdown>
          <Button
            v-if="!instagram"
            :variant="windowOpen ? 'ghost' : 'solid'"
            icon="lucide-layout-template"
            :tooltip="__('Send a template')"
            :label="__('Send a template')"
            @click="emit('templates')"
          />
          <Button
            variant="ghost"
            icon="lucide-message-square-quote"
            :tooltip="__('Quick replies (/)')"
            :label="__('Quick replies')"
            :class="{ 'bg-surface-gray-3': suggest.open }"
            @mousedown.prevent
            @click="openSuggestions"
          />
        </template>

        <input ref="picker" type="file" class="hidden" :accept="ACCEPT" @change="onPick" />

        <ScrollArea
          class="min-w-0 flex-1 border transition-colors focus-within:shadow-sm"
          :class="[
            compact ? 'rounded-5' : 'rounded-4',
            noteMode
              ? 'border-outline-amber-2 bg-surface-base focus-within:border-outline-amber-4'
              : 'border-transparent bg-surface-gray-2 focus-within:border-outline-gray-4 focus-within:bg-surface-base',
          ]"
          :viewport-class="compact ? 'max-h-[9.5rem]' : 'max-h-40'"
        >
          <Textarea
            ref="field"
            v-model="text"
            :rows="1"
            variant="ghost"
            :size="compact ? 'lg' : 'sm'"
            class="w-full resize-none"
            :class="compact ? '!min-h-10 !py-2 !text-lg !leading-snug' : '!min-h-8 !text-base'"
            :placeholder="placeholder"
            :aria-label="noteMode ? __('Internal note') : __('Message')"
            :aria-expanded="suggest.open"
            :aria-controls="suggest.open ? `quick-replies-${contact}` : undefined"
            :aria-activedescendant="suggest.open && suggestions.length ? `quick-reply-${contact}-${suggest.index}` : undefined"
            @input="onInput"
            @keydown="onKeydown"
            @keyup="onCaret"
            @click="onCaret"
            @blur="closeSuggestions"
            @paste="onPaste"
          />
        </ScrollArea>

        <Button
          variant="solid"
          :size="compact ? 'lg' : 'sm'"
          :class="{ '!size-11 !rounded-full': compact }"
          :icon="noteMode ? 'lucide-lock' : 'lucide-send-horizontal'"
          :tooltip="noteMode ? __('Save note') : __('Send')"
          :label="noteMode ? __('Save note') : __('Send')"
          :disabled="!canSend"
          :loading="uploading || savingNote"
          @click="send"
        />
      </div>
    </div>

    <MediaPicker v-model:open="library" @pick="pickFromLibrary" />

    <ResponsiveDialog v-if="compact" v-model:open="more" :title="__('Add to message')" size="sm">
      <template #default>
        <div class="-mx-2 flex flex-col">
          <button
            v-for="item in moreOptions"
            :key="item.label"
            type="button"
            class="flex h-11 items-center gap-3 rounded-4 px-2 text-left text-base text-ink-gray-8 active:bg-surface-gray-2"
            @click="item.onClick"
          >
            <span :class="item.icon" class="size-4 shrink-0 text-ink-gray-6" aria-hidden="true" />
            {{ item.label }}
          </button>
        </div>
      </template>
    </ResponsiveDialog>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { Avatar, Button, Dropdown, ScrollArea, TabButtons, Textarea, Tooltip, toast } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import MediaPicker from '@/components/Media/MediaPicker.vue'
import { embedded } from '@/data/embed'
import { notifyTyping, stopTyping, useTypers, useViewers } from '@/data/typing'
import AttachmentPreview from './AttachmentPreview.vue'
import ReplyPreview from './ReplyPreview.vue'
import {
  agents,
  assign,
  composerRequest,
  contentTypeFor,
  fileName,
  fillQuickReply,
  findRow,
  inbox,
  quickReplies,
  saveNote,
  sendMessage,
  uploadFile,
} from '@/data/inbox'
import { can, session } from '@/data/session'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const MIME = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp',
  mp4: 'video/mp4',
  '3gp': 'video/3gpp',
  mp3: 'audio/mpeg',
  ogg: 'audio/ogg',
  aac: 'audio/aac',
  amr: 'audio/amr',
  m4a: 'audio/mp4',
  opus: 'audio/opus',
}

const TOKEN = /(^|\s)\/([a-z0-9-]*)$/i
const MENTION = /(^|\s)@([^\s@]*)$/
const IMAGE = /\.(jpe?g|png|webp|gif)$/i

const ACCEPT = 'image/jpeg,image/png,video/mp4,video/3gpp,audio/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip'

const props = defineProps({
  contact: { type: String, required: true },
  contactName: { type: String, default: '' },
  windowOpen: { type: Boolean, default: true },
  humanWindowOpen: { type: Boolean, default: true },
  channel: { type: String, default: 'WhatsApp' },
  compact: { type: Boolean, default: false },
})

const instagram = computed(() => props.channel === 'Instagram')
const noteHint = computed(() =>
  instagram.value
    ? __('Only your team sees notes. Nothing is sent on Instagram.')
    : __('Only your team sees notes. Nothing is sent on WhatsApp.'),
)

const emit = defineEmits(['templates', 'sent'])

const reply = defineModel('reply', { type: Object, default: null })

const text = ref('')
const mayReply = can('OneChat Message', 'create')
const mayNote = can('OneChat Note', 'create')
const mode = ref(mayReply ? 'reply' : 'note')
const savingNote = ref(false)
const file = ref(null)
const uploading = ref(false)
const progress = ref(0)
const uploadError = ref('')
const touch = computed(() => props.compact && !embedded)
const picker = ref(null)
const library = ref(false)
const more = ref(false)

const attachOptions = computed(() => [
  { label: __('Upload from this device'), icon: 'lucide-upload', onClick: () => picker.value?.click() },
  { label: __('Choose from media library'), icon: 'lucide-images', onClick: () => (library.value = true) },
])
const moreOptions = computed(() => allMoreOptions.value.filter((item) => !(instagram.value && item.template)))
const allMoreOptions = computed(() => [
  {
    label: __('Upload from this device'),
    icon: 'lucide-upload',
    onClick: () => {
      picker.value?.click()
      more.value = false
    },
  },
  {
    label: __('Choose from media library'),
    icon: 'lucide-images',
    onClick: () => {
      more.value = false
      library.value = true
    },
  },
  {
    label: __('Send a template'),
    icon: 'lucide-layout-template',
    template: true,
    onClick: () => {
      more.value = false
      emit('templates')
    },
  },
  {
    label: __('Quick replies'),
    icon: 'lucide-message-square-quote',
    onClick: () => {
      more.value = false
      setTimeout(openSuggestions, 300)
    },
  },
])

const field = ref(null)
const input = computed(() => field.value?.inputElement || null)

const suggest = reactive({ open: false, kind: 'reply', start: 0, query: '', index: 0 })
const mentioned = new Map()
const ui = useUI()
const typers = useTypers(() => props.contact)
const viewers = useViewers(() => props.contact)
let seen = null

let upload = null
let refreshed = false

function isImage(url) {
  return IMAGE.test(String(url || '').split('?')[0])
}

function personName(user) {
  const agent = (agents.data || []).find((row) => row.name === user)
  return agent?.full_name || user
}

function namesOf(users) {
  const names = users.map(personName)
  if (names.length <= 2) return names.join(__(' and '))
  return __('{0} and {1} others').format(names[0], names.length - 1)
}

const collision = computed(() => {
  const detail = inbox.details[props.contact] || findRow(props.contact) || {}
  const owner = detail.assigned_to
  const claimable = owner && owner !== session.user.name
  if (typers.value.length) {
    return {
      urgent: true,
      icon: 'lucide-pencil-line',
      text: __('{0} is replying to this customer right now').format(namesOf(typers.value)),
      claim: claimable,
    }
  }
  if (claimable) {
    return { urgent: false, icon: 'lucide-user-check', text: __('Assigned to {0}').format(personName(owner)), claim: true }
  }
  if (viewers.value.length) {
    return { urgent: false, icon: 'lucide-eye', text: __('{0} is also viewing this chat').format(namesOf(viewers.value)) }
  }
  return null
})

async function claim() {
  try {
    await assign(props.contact, session.user.name)
  } catch (error) {
    toast.error(errorMessage(error))
  }
}

function teammateReplies() {
  if (!seen) return []
  const messages = inbox.threads[props.contact]?.messages || []
  const team = new Set((agents.data || []).map((row) => row.name))
  return messages.filter(
    (message) =>
      message.type === 'Outgoing' &&
      !message.pending &&
      message.owner !== session.user.name &&
      team.has(message.owner) &&
      !seen.has(message.name),
  )
}

function markSeen() {
  seen = new Set((inbox.threads[props.contact]?.messages || []).map((message) => message.name))
}

const suggestions = computed(() => {
  const query = suggest.query.toLowerCase()
  if (suggest.kind === 'mention') {
    return (agents.data || [])
      .filter((row) => row.name !== session.user.name && `${row.full_name || ''} ${row.name}`.toLowerCase().includes(query))
      .slice(0, 8)
  }
  const rows = quickReplies.data || []
  if (!query) return rows

  const starts = rows.filter((row) => row.shortcut.startsWith(query))
  const rest = rows.filter(
    (row) => !row.shortcut.startsWith(query) && `${row.shortcut} ${row.title} ${row.message}`.toLowerCase().includes(query),
  )

  return [...starts, ...rest]
})

const noteMode = computed(() => mode.value === 'note')

const modes = computed(() =>
  [
    mayReply && { label: __('Reply'), value: 'reply', iconLeft: props.compact ? undefined : 'lucide-message-circle' },
    mayNote && { label: __('Internal note'), value: 'note', iconLeft: props.compact ? undefined : 'lucide-lock' },
  ].filter(Boolean),
)

const drafts = { reply: '', note: '' }

const canSend = computed(() => {
  if (noteMode.value) return !savingNote.value && !!text.value.trim()
  if (instagram.value && !props.humanWindowOpen) return false
  return !uploading.value && (!!text.value.trim() || !!file.value)
})

const placeholder = computed(() => {
  if (noteMode.value) return __('Write a note only your team sees. Type @ to mention someone')
  if (instagram.value) return props.humanWindowOpen ? __('Type a message') : __('Waiting for the customer to message again')
  return props.windowOpen ? __('Type a message') : __('Free-form messages may not be delivered')
})

function grow() {
  const element = input.value
  if (!element) return

  element.style.height = 'auto'
  element.style.height = `${element.scrollHeight}px`
}

function focus() {
  if (!touch.value) input.value?.focus()
}

function setFile(selected) {
  if (!selected || noteMode.value) return

  file.value = selected
  progress.value = 0
  uploadError.value = ''
}

function onPick(event) {
  setFile(event.target.files?.[0])
  event.target.value = ''
}

function onDrop(event) {
  setFile(event.dataTransfer?.files?.[0])
}

function onPaste(event) {
  const pasted = event.clipboardData?.files?.[0]
  if (!pasted) return

  event.preventDefault()
  setFile(pasted)
}

function detect() {
  const element = input.value
  if (!element) return closeSuggestions()

  const caret = element.selectionStart
  if (caret !== element.selectionEnd) return closeSuggestions()

  const kind = noteMode.value ? 'mention' : 'reply'
  const match = text.value.slice(0, caret).match(kind === 'mention' ? MENTION : TOKEN)
  if (!match) return closeSuggestions()

  if (!suggest.open || suggest.query !== match[2] || suggest.kind !== kind) suggest.index = 0
  suggest.kind = kind
  suggest.start = caret - match[2].length - 1
  suggest.query = match[2]
  if (suggest.open) return

  suggest.open = true
  if (kind === 'mention') {
    if (!agents.data && !agents.loading) agents.fetch()
    return
  }
  if (!refreshed) {
    refreshed = true
    quickReplies.reload().catch(() => {})
  }
}

function closeSuggestions() {
  suggest.open = false
  suggest.query = ''
  suggest.index = 0
}

function onInput() {
  grow()
  detect()
  if (!noteMode.value && text.value.trim()) {
    if (!seen) markSeen()
    notifyTyping(props.contact)
  }
  if (!text.value.trim()) seen = null
}

function choose(item) {
  if (suggest.kind === 'mention') insertMention(item)
  else insertReply(item)
}

function insertMention(agent) {
  const end = input.value ? input.value.selectionStart : text.value.length
  const start = suggest.start
  const tag = `@${agent.full_name || agent.name} `

  text.value = `${text.value.slice(0, start)}${tag}${text.value.slice(end)}`
  mentioned.set(agent.name, agent.full_name || agent.name)
  closeSuggestions()

  nextTick(() => {
    const position = start + tag.length
    input.value?.focus()
    input.value?.setSelectionRange(position, position)
    grow()
  })
}

function onCaret(event) {
  if (event.type === 'keyup' && !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  detect()
}

function openSuggestions() {
  if (suggest.open) {
    closeSuggestions()
    input.value?.focus()
    return
  }

  const caret = input.value ? input.value.selectionEnd : text.value.length
  const before = text.value.slice(0, caret)
  const token = !before || /\s$/.test(before) ? '/' : ' /'

  text.value = `${before}${token}${text.value.slice(caret)}`
  nextTick(() => {
    const position = before.length + token.length
    input.value?.focus()
    input.value?.setSelectionRange(position, position)
    grow()
    detect()
  })
}

function attachmentFromUrl(url) {
  const name = fileName(url)
  const extension = name.split('.').pop().toLowerCase()

  return { name, url, size: 0, type: MIME[extension] || 'application/octet-stream' }
}

function pickFromLibrary(item) {
  removeFile()
  setFile(attachmentFromUrl(item.file_url))
  nextTick(() => input.value?.focus())
}

function insertReply(item) {
  const end = input.value ? input.value.selectionStart : text.value.length
  const start = suggest.start
  const contact = { ...findRow(props.contact), ...inbox.details[props.contact] }
  const body = fillQuickReply(item.message, contact)

  text.value = `${text.value.slice(0, start)}${body}${text.value.slice(end)}`
  if (item.attach) {
    removeFile()
    setFile(attachmentFromUrl(item.attach))
  }
  closeSuggestions()

  nextTick(() => {
    const position = start + body.length
    input.value?.focus()
    input.value?.setSelectionRange(position, position)
    grow()
  })
}

function scrollToSuggestion() {
  document.getElementById(`quick-reply-${props.contact}-${suggest.index}`)?.scrollIntoView({ block: 'nearest' })
}

function onSuggestionKey(event) {
  const count = suggestions.value.length

  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    closeSuggestions()
    return true
  }

  if (!count) return false

  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    suggest.index = (suggest.index + (event.key === 'ArrowDown' ? 1 : -1) + count) % count
    nextTick(scrollToSuggestion)
    return true
  }

  if ((event.key === 'Enter' && !event.shiftKey && !event.isComposing) || event.key === 'Tab') {
    event.preventDefault()
    choose(suggestions.value[suggest.index] || suggestions.value[0])
    return true
  }

  return false
}

function removeFile() {
  upload?.abort()
  upload = null
  file.value = null
  uploadError.value = ''
  uploading.value = false
}

function onKeydown(event) {
  if (suggest.open && onSuggestionKey(event)) return

  if (event.key === 'Escape' && reply.value && !noteMode.value) {
    event.preventDefault()
    event.stopPropagation()
    reply.value = null
    return
  }

  if (event.key !== 'Enter' || event.shiftKey || event.isComposing || touch.value) return

  event.preventDefault()
  send()
}

async function addNote() {
  const content = text.value.trim()
  savingNote.value = true
  text.value = ''
  nextTick(grow)

  const mentions = [...mentioned].filter(([, name]) => content.includes(`@${name}`)).map(([user]) => user)

  try {
    await saveNote(props.contact, content, null, mentions)
    mentioned.clear()
    emit('sent')
  } catch (error) {
    if (!text.value) text.value = content
    nextTick(grow)
    toast.error(errorMessage(error))
  } finally {
    savingNote.value = false
    focus()
  }
}

async function send() {
  if (!canSend.value) return
  if (noteMode.value) return addNote()

  const overlap = teammateReplies()
  if (overlap.length) {
    const latest = overlap[overlap.length - 1]
    ui.confirm({
      title: __('{0} already replied').format(personName(latest.owner)),
      message: __('While you were typing, they sent: "{0}". Send your message too?').format(String(latest.message || '').slice(0, 140)),
      action: __('Send anyway'),
      onConfirm: () => {
        markSeen()
        send()
      },
    })
    return
  }
  seen = null
  stopTyping()

  const message = text.value.trim()
  let attach = null
  let contentType = 'text'

  if (file.value?.url) {
    attach = file.value.url
    contentType = contentTypeFor(file.value)
  } else if (file.value) {
    uploading.value = true
    uploadError.value = ''
    progress.value = 0

    try {
      upload = uploadFile(file.value, { contact: props.contact, onProgress: (value) => (progress.value = value) })
      const result = await upload
      attach = result.file_url
      contentType = contentTypeFor(file.value)
    } catch (error) {
      if (!error.aborted) uploadError.value = error.message
      return
    } finally {
      uploading.value = false
      upload = null
    }
  }

  const quoted = reply.value
  text.value = ''
  file.value = null
  reply.value = null
  closeSuggestions()
  nextTick(grow)

  sendMessage(props.contact, {
    message: contentType === 'audio' ? '' : message,
    attach,
    content_type: contentType,
    reply: quoted,
  })
  if (contentType === 'audio' && message) sendMessage(props.contact, { message, content_type: 'text' })

  emit('sent')
  focus()
}

watch(reply, (value) => {
  if (!value || !mayReply) return
  mode.value = 'reply'
  nextTick(() => input.value?.focus())
})

watch(
  () => composerRequest.stamp,
  () => {
    if (composerRequest.contact !== props.contact) return
    drafts.reply = composerRequest.text
    if (mode.value === 'reply') {
      text.value = composerRequest.text
      nextTick(() => {
        grow()
        input.value?.focus()
      })
    } else {
      mode.value = 'reply'
    }
  },
)

watch(mode, (value, previous) => {
  drafts[previous] = text.value
  text.value = drafts[value] || ''
  closeSuggestions()
  nextTick(() => {
    grow()
    input.value?.focus()
  })
})

watch(
  () => props.contact,
  () => {
    removeFile()
    closeSuggestions()
    drafts.reply = ''
    drafts.note = ''
    mode.value = 'reply'
    text.value = ''
    nextTick(grow)
  },
)

onMounted(focus)

defineExpose({ focus })
</script>
