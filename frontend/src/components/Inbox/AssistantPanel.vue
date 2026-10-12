<template>
  <section
    v-if="status.ready"
    class="flex flex-col gap-3"
    :class="{ 'rounded-5 border border-outline-gray-1 p-3': !bare, 'h-full min-h-0': fill }"
  >
    <header v-if="!bare" class="flex items-center justify-between gap-2">
      <div class="flex min-w-0 items-center gap-2">
        <AssistantIcon class="size-5 shrink-0 text-ink-green-6" />
        <h3 class="text-sm font-medium text-ink-gray-8">{{ __('Assistant') }}</h3>
        <span class="text-xs text-ink-gray-4">{{ status.provider }}</span>
      </div>
      <Button
        v-if="turns.length"
        variant="ghost"
        icon="lucide-message-square-plus"
        :label="__('New chat')"
        :tooltip="__('New chat')"
        @click="reset"
      />
    </header>

    <div v-if="pendingSignIns.length" class="flex flex-col gap-1.5 rounded-4 bg-surface-amber-1 px-3 py-2.5">
      <p class="text-sm text-ink-amber-8">
        {{
          __('Sign in to {0} with your own account so the Assistant can use your access there.').format(
            pendingSignIns.map((row) => row.label).join(', '),
          )
        }}
      </p>
      <div class="flex flex-wrap gap-1.5">
        <Button
          v-for="row in pendingSignIns"
          :key="row.integration"
          size="sm"
          variant="solid"
          icon-left="lucide-log-in"
          :loading="busy === `signin-${row.integration}`"
          :label="__('Sign in to {0}').format(row.label)"
          @click="signIn(row.integration)"
        />
      </div>
    </div>
    <p v-if="signedIn.length" class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-gray-5">
      <span v-for="row in signedIn" :key="row.integration" class="inline-flex items-center gap-1">
        <span class="lucide-user-check size-3" aria-hidden="true" />{{ __('{0} as {1}').format(row.label, row.signed_in_as) }}
        <button type="button" class="underline hover:text-ink-gray-8" @click="signOut(row.integration)">{{ __('Sign out') }}</button>
      </span>
    </p>

    <div
      v-if="!turns.length && status.usable"
      class="flex flex-col items-center gap-4 py-3 text-center"
      :class="{ 'flex-1 justify-center': fill }"
    >
      <AssistantIcon class="size-12 text-ink-green-6" />
      <div>
        <p class="text-base font-medium text-ink-gray-9">{{ heading || __('How can I help with this customer?') }}</p>
        <p class="mt-0.5 text-sm text-ink-gray-5">{{ subheading || __('I look up their orders, invoices and this chat for you.') }}</p>
      </div>
      <div class="grid w-full grid-cols-1 gap-2 sm:grid-cols-2">
        <button
          v-for="item in prompts"
          :key="item.text"
          type="button"
          class="flex items-center gap-2.5 rounded-4 border border-outline-gray-2 px-3 py-2.5 text-left text-sm text-ink-gray-8 transition-colors hover:bg-surface-gray-1 focus-visible:focus-ring disabled:opacity-50"
          :disabled="!!busy"
          @click="send(item.text)"
        >
          <span :class="item.icon" class="size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
          {{ item.text }}
        </button>
      </div>
    </div>

    <ScrollArea
      v-if="turns.length"
      :class="{ 'min-h-0 flex-1': fill }"
      :viewport-class="fill ? 'h-full pr-2' : bare ? 'max-h-[min(55vh,30rem)] pr-2' : 'max-h-96 pr-2'"
    >
      <div class="flex flex-col gap-4 py-1">
        <div v-for="(turn, index) in turns" :key="index" class="flex flex-col gap-3">
          <p
            class="max-w-[85%] self-end whitespace-pre-wrap break-words rounded-5 rounded-br-1 bg-surface-gray-3 px-3 py-2 text-sm leading-5 text-ink-gray-9"
          >
            {{ turn.question }}
          </p>

          <div v-if="turn.reply || turn.draft || turn.steps?.length || turn.pending?.length" class="flex items-start gap-2.5">
            <AssistantIcon class="mt-0.5 size-6 shrink-0 text-ink-green-6" />
            <div class="flex min-w-0 flex-1 flex-col gap-2.5">
              <p v-if="turn.steps?.length" class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-gray-5">
                <span v-for="(step, position) in turn.steps" :key="position" class="inline-flex items-center gap-1">
                  <span :class="step.ok ? 'lucide-check text-ink-green-6' : 'lucide-x text-ink-red-6'" class="size-3" aria-hidden="true" />
                  {{ toolLabel(step.tool) }}
                </span>
              </p>

              <p v-if="turn.reply" class="whitespace-pre-wrap break-words text-sm leading-6 text-ink-gray-8">{{ plain(turn.reply) }}</p>

              <div v-if="turn.draft" class="flex flex-col gap-2 rounded-4 border border-outline-gray-2 p-3">
                <p class="flex items-center gap-1.5 text-xs font-medium text-ink-gray-5">
                  <span class="lucide-message-square-text size-3.5" aria-hidden="true" />
                  {{ __('Suggested reply') }}
                </p>
                <p class="whitespace-pre-wrap break-words text-sm leading-6 text-ink-gray-9">{{ plain(turn.draft) }}</p>
                <div class="flex gap-1.5">
                  <Button
                    v-if="target"
                    size="sm"
                    variant="solid"
                    icon-left="lucide-corner-down-left"
                    :label="__('Insert into reply')"
                    @click="insert(plain(turn.draft))"
                  />
                  <Button size="sm" variant="subtle" icon-left="lucide-copy" :label="__('Copy')" @click="copy(plain(turn.draft))" />
                </div>
              </div>

              <div
                v-if="turn.pending?.length && index === turns.length - 1"
                class="flex flex-col gap-3 rounded-4 border border-outline-amber-2 bg-surface-amber-1 p-3"
              >
                <div v-for="(action, position) in turn.pending" :key="position" class="flex flex-col gap-2">
                  <p class="flex items-start gap-1.5 text-base font-medium text-ink-gray-9">
                    <span
                      :class="[KIND_ICON[action.card?.kind] || 'lucide-shield-alert', 'mt-0.5 size-4 shrink-0 text-ink-amber-7']"
                      aria-hidden="true"
                    />
                    {{ action.card?.title || toolLabel(action.tool) }}
                  </p>
                  <dl v-if="action.card?.fields?.length" class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
                    <template v-for="field in action.card.fields" :key="field.label">
                      <dt class="text-ink-gray-5">{{ field.label }}</dt>
                      <dd class="min-w-0 break-words text-ink-gray-8">{{ field.value }}</dd>
                    </template>
                  </dl>
                  <p v-if="action.card?.more_fields" class="text-xs text-ink-gray-5">
                    {{ __('+ {0} more fields').format(action.card.more_fields) }}
                  </p>
                  <div
                    v-if="action.card?.lines?.length"
                    class="flex flex-col divide-y divide-outline-gray-1 rounded-3 bg-surface-base text-sm"
                  >
                    <div v-for="(line, row) in action.card.lines" :key="row" class="flex items-center gap-2 px-2.5 py-1.5">
                      <TruncatedText class="min-w-0 flex-1 truncate text-ink-gray-8" :text="line.item" />
                      <span v-if="line.qty" class="shrink-0 tabular-nums text-ink-gray-5">× {{ formatNumber(line.qty) }}</span>
                      <span v-if="line.amount" class="w-20 shrink-0 text-right tabular-nums text-ink-gray-8">{{
                        formatNumber(line.amount)
                      }}</span>
                    </div>
                    <p v-if="action.card.more_lines" class="px-2.5 py-1.5 text-xs text-ink-gray-5">
                      {{ __('+ {0} more rows').format(action.card.more_lines) }}
                    </p>
                    <div v-if="action.card.total" class="flex items-center justify-between px-2.5 py-1.5 font-medium text-ink-gray-9">
                      <span>{{ __('Total') }}</span>
                      <span class="tabular-nums">{{ formatNumber(action.card.total) }}</span>
                    </div>
                  </div>
                  <p v-if="action.card?.warning" class="flex items-start gap-1.5 text-sm text-ink-amber-8">
                    <span class="lucide-triangle-alert mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                    {{ action.card.warning }}
                  </p>
                  <details class="text-xs text-ink-gray-5">
                    <summary class="cursor-pointer select-none hover:text-ink-gray-7">{{ __('Show exact details') }}</summary>
                    <ScrollArea class="mt-1 rounded-3 bg-surface-base" viewport-class="max-h-40">
                      <pre class="whitespace-pre-wrap px-2 py-1.5 font-mono text-xs text-ink-gray-7">{{ pretty(action.input) }}</pre>
                    </ScrollArea>
                  </details>
                </div>
                <div class="flex gap-1.5">
                  <Button
                    size="sm"
                    variant="solid"
                    :theme="turn.pending.some((action) => action.card?.warning) ? 'red' : 'gray'"
                    :label="turn.pending.length > 1 ? __('Do all {0}').format(turn.pending.length) : __('Yes, do it')"
                    :loading="busy === 'confirm'"
                    :disabled="!!busy"
                    @click="decide(true)"
                  />
                  <Button size="sm" variant="subtle" :label="__('Cancel')" :disabled="!!busy" @click="decide(false)" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="busy === 'ask'" class="flex items-center gap-2.5">
          <AssistantIcon thinking class="size-6 shrink-0 text-ink-green-6" />
          <span class="text-sm text-ink-gray-5">{{ __('Looking it up…') }}</span>
        </div>
        <div ref="end" />
      </div>
    </ScrollArea>

    <ErrorMessage :message="error" />

    <div v-if="page && pageLabel" class="-mb-1 flex items-center gap-1.5">
      <button
        type="button"
        class="inline-flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs transition-colors focus-visible:focus-ring"
        :class="
          usePage
            ? 'border-outline-gray-3 bg-surface-gray-2 text-ink-gray-8'
            : 'border-dashed border-outline-gray-2 text-ink-gray-5 line-through'
        "
        :aria-pressed="usePage"
        @click="usePage = !usePage"
      >
        <span class="lucide-map-pin size-3 shrink-0" aria-hidden="true" />
        <span class="truncate">{{ pageLabel }}</span>
      </button>
      <span class="text-xs text-ink-gray-4">{{ usePage ? __('included') : __('not included') }}</span>
    </div>

    <form
      v-if="status.usable"
      class="flex items-end gap-2 rounded-5 border border-outline-gray-2 bg-surface-base p-1.5 transition-colors focus-within:border-outline-gray-4 focus-within:shadow-sm"
      @submit.prevent="send()"
    >
      <Textarea
        v-model="question"
        class="min-w-0 flex-1"
        variant="ghost"
        :rows="2"
        :placeholder="turns.length ? __('Ask a follow-up…') : __('Ask about this customer…')"
        :disabled="!!busy || waiting"
        @keydown.enter.exact.prevent="send()"
      />
      <Button
        type="submit"
        variant="solid"
        icon="lucide-arrow-up"
        :label="__('Send')"
        :tooltip="__('Send (Enter)')"
        :loading="busy === 'ask'"
        :disabled="!question.trim() || !!busy || waiting"
      />
    </form>
  </section>

  <p
    v-else-if="session.user.is_admin && status.enabled && !status.ready"
    class="flex items-center justify-between gap-2 rounded-4 bg-surface-gray-1 px-3 py-2 text-sm text-ink-gray-6"
  >
    {{ __('The assistant needs setup.') }}
    <Button size="sm" variant="ghost" :label="__('Open settings')" @click="ui.openSettings('integrations')" />
  </p>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { Button, ErrorMessage, ScrollArea, Textarea, toast } from 'frappe-ui'
import AssistantIcon from './AssistantIcon.vue'
import TruncatedText from '@/components/Common/TruncatedText.vue'
import {
  askAssistant,
  assistantStatus,
  assistantThread,
  confirmAssistant,
  forgetAssistant,
  loadAssistantHistory,
  signInToSite,
  signOutOfSite,
  toolLabel,
} from '@/data/assistant'
import { insertIntoComposer } from '@/data/inbox'
import { session } from '@/data/session'
import { useUI } from '@/stores/ui'
import { errorMessage, formatNumber } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  contact: { type: String, default: '' },
  bare: { type: Boolean, default: false },
  fill: { type: Boolean, default: false },
  page: { type: Object, default: null },
  pageLabel: { type: String, default: '' },
  suggestions: { type: Array, default: null },
  heading: { type: String, default: '' },
  subheading: { type: String, default: '' },
})

const emit = defineEmits(['inserted'])

const ui = useUI()
const question = ref('')
const end = ref(null)
const usePage = ref(true)
const scope = computed(() => props.contact || 'global')
const target = computed(() => props.contact || props.page?.contact || '')
const turns = computed({
  get: () => assistantThread(scope.value).turns,
  set: (value) => (assistantThread(scope.value).turns = value),
})
const chat = computed({
  get: () => assistantThread(scope.value).chat,
  set: (value) => (assistantThread(scope.value).chat = value),
})
const busy = ref('')
const error = ref('')

const status = computed(() => assistantStatus.data || {})
const waiting = computed(() => !!turns.value.at(-1)?.pending?.length)
const pendingSignIns = computed(() => (status.value.sign_ins || []).filter((row) => !row.signed_in_as))
const signedIn = computed(() => (status.value.sign_ins || []).filter((row) => row.signed_in_as))

const KIND_ICON = {
  create: 'lucide-file-plus-2',
  update: 'lucide-file-pen-line',
  submit: 'lucide-file-check-2',
  workflow: 'lucide-workflow',
  send: 'lucide-send',
}

const CUSTOMER_PROMPTS = [
  { text: __('What does this customer owe?'), icon: 'lucide-receipt-indian-rupee' },
  { text: __('Show their recent orders'), icon: 'lucide-package' },
  { text: __('Draft a reply with their order status'), icon: 'lucide-message-square-text' },
  { text: __('Summarise this chat'), icon: 'lucide-list' },
]
const prompts = computed(() => props.suggestions || CUSTOMER_PROMPTS)

function plain(text) {
  return String(text || '')
    .replace(/\r/g, '')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/__(.+?)__/g, '$1')
    .replace(/(^|[\s(])\*(?!\s)(.+?)\*(?=[\s).,!?:;]|$)/gm, '$1$2')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '$1 ($2)')
    .replace(/^\s*[-*+]\s+/gm, '• ')
    .replace(/^\s*\|?\s*:?-{3,}.*$/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function insert(text) {
  insertIntoComposer(target.value, text)
  emit('inserted')
}

function scrollToEnd() {
  nextTick(() => end.value?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }))
}

async function signIn(integration) {
  busy.value = `signin-${integration}`
  try {
    await signInToSite(integration)
  } catch (err) {
    toast.error(errorMessage(err))
    busy.value = ''
  }
}

async function signOut(integration) {
  try {
    await signOutOfSite(integration)
    toast.success(__('Signed out'))
  } catch (err) {
    toast.error(errorMessage(err))
  }
}

function reset() {
  if (turns.value.length) forgetAssistant(props.contact).catch(() => {})
  turns.value = []
  chat.value = null
  error.value = ''
  question.value = ''
}

async function send(text) {
  const value = (text ?? question.value).trim()
  if (!value || busy.value || waiting.value) return
  const turn = { question: value, reply: '', draft: '', pending: null, steps: [] }
  turns.value.push(turn)
  question.value = ''
  busy.value = 'ask'
  error.value = ''
  scrollToEnd()
  try {
    const result = await askAssistant(props.contact, value, chat.value, !props.contact && usePage.value ? props.page : null)
    Object.assign(turns.value.at(-1), { reply: result.reply, draft: result.draft, pending: result.pending, steps: result.steps || [] })
    chat.value = result.session
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    busy.value = ''
    scrollToEnd()
  }
}

async function decide(approve) {
  if (!chat.value || busy.value) return
  busy.value = approve ? 'confirm' : 'cancel'
  error.value = ''
  const turn = turns.value.at(-1)
  try {
    const result = await confirmAssistant(chat.value, approve)
    turn.reply = [turn.reply, result.reply].filter(Boolean).join('\n\n')
    turn.draft = result.draft || turn.draft
    turn.pending = result.pending
    turn.steps = [...turn.steps, ...(result.steps || [])]
    chat.value = result.session
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    busy.value = ''
    scrollToEnd()
  }
}

function pretty(value) {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(__('Copied'))
  } catch {
    toast.error(__('Could not copy'))
  }
}

watch(
  () => props.contact,
  () => {
    error.value = ''
    question.value = ''
  },
)

watch(
  scope,
  () =>
    loadAssistantHistory(scope.value, props.contact)
      .then(scrollToEnd)
      .catch(() => {}),
  { immediate: true },
)

defineExpose({ reset, hasTurns: computed(() => turns.value.length > 0), provider: computed(() => status.value.provider || '') })

watch(
  () => props.page?.path,
  () => (usePage.value = true),
)
</script>
