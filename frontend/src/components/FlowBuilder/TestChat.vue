<template>
  <div class="flex h-full flex-col">
    <div class="flex items-center gap-2 border-b border-outline-gray-1 p-3">
      <span class="flex size-8 shrink-0 items-center justify-center rounded-4 bg-surface-green-2 text-ink-green-7">
        <span class="lucide-smartphone size-4" aria-hidden="true" />
      </span>
      <div class="min-w-0 flex-1">
        <p class="text-base font-medium text-ink-gray-8">{{ __('Test chat') }}</p>
        <TruncatedText as="p" class="truncate text-xs text-ink-gray-5" :text="__('You are the customer. Nothing is sent.')" />
      </div>
      <Button variant="ghost" icon="lucide-rotate-ccw" :label="__('Restart')" :disabled="busy" @click="restart" />
      <Button variant="ghost" icon="lucide-x" :label="__('Close')" @click="emit('close')" />
    </div>

    <ScrollArea ref="scroller" class="chat-wallpaper min-h-0 flex-1 bg-surface-gray-1" viewport-class="px-3 py-4">
      <div class="flex flex-col gap-2">
        <template v-for="(message, index) in messages" :key="index">
          <p
            v-if="message.from === 'system'"
            class="mx-auto max-w-[90%] rounded-4 bg-surface-base px-2.5 py-1 text-center text-xs text-ink-gray-6 shadow-sm"
          >
            <span class="lucide-info mr-1 inline-block size-3 align-[-1px]" aria-hidden="true" />{{ message.text }}
          </p>

          <div v-else-if="message.from === 'error'" class="flex gap-2 rounded-4 bg-surface-red-1 p-2.5 text-sm text-ink-red-6">
            <span class="lucide-circle-x mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span class="break-words">{{ message.text }}</span>
          </div>

          <div
            v-else-if="message.from === 'customer'"
            class="ml-auto max-w-[85%] rounded-4 rounded-tr-none bg-surface-green-2 px-2.5 py-1.5 text-sm text-ink-gray-9 shadow-sm"
          >
            {{ message.text }}
          </div>

          <div v-else class="max-w-[88%]">
            <div class="rounded-4 rounded-tl-none bg-surface-base px-2.5 py-1.5 shadow-sm">
              <p v-if="message.type === 'template'" class="text-sm italic text-ink-gray-6">{{ message.text }}</p>
              <p v-else class="whitespace-pre-wrap break-words text-sm text-ink-gray-9" v-html="format(message.text)" />
              <p v-if="message.attach" class="mt-1 flex items-center gap-1 text-xs text-ink-gray-5">
                <span class="lucide-paperclip size-3" aria-hidden="true" />{{ fileName(message.attach) }}
              </p>
            </div>

            <div v-if="message.kind === 'button'" class="mt-1 flex flex-col gap-1">
              <button
                v-for="option in message.options"
                :key="option.id"
                type="button"
                class="rounded-4 bg-surface-base px-2.5 py-1.5 text-sm font-medium text-ink-blue-link shadow-sm hover:bg-surface-gray-2 disabled:opacity-60"
                :disabled="!canAnswer(index)"
                @click="choose(option)"
              >
                {{ option.title }}
              </button>
            </div>

            <div v-else-if="message.kind === 'list'" class="mt-1 rounded-4 bg-surface-base shadow-sm">
              <button
                v-for="option in message.options"
                :key="option.id"
                type="button"
                class="flex w-full flex-col border-b border-outline-gray-1 px-2.5 py-1.5 text-left last:border-0 hover:bg-surface-gray-2 disabled:opacity-60"
                :disabled="!canAnswer(index)"
                @click="choose(option)"
              >
                <span class="text-sm text-ink-gray-9">{{ option.title }}</span>
                <span v-if="option.description" class="text-xs text-ink-gray-5">{{ option.description }}</span>
              </button>
            </div>

            <button
              v-else-if="message.type === 'form'"
              type="button"
              class="mt-1 w-full rounded-4 bg-surface-base px-2.5 py-1.5 text-sm font-medium text-ink-blue-link shadow-sm hover:bg-surface-gray-2 disabled:opacity-60"
              :disabled="!canAnswer(index)"
              @click="submitForm"
            >
              {{ __('Submit the form') }}
            </button>
          </div>
        </template>

        <div v-if="busy" class="flex items-center gap-2 text-xs text-ink-gray-5">
          <LoadingIndicator class="size-3.5" />{{ __('Running…') }}
        </div>
        <p v-if="done && messages.length" class="mx-auto mt-2 rounded-full bg-surface-gray-3 px-3 py-1 text-xs text-ink-gray-6">
          {{ __('The flow ended') }}
        </p>
      </div>
    </ScrollArea>

    <div class="flex flex-col gap-2 border-t border-outline-gray-1 p-3">
      <template v-if="!done && waiting?.kind === 'Timer'">
        <p class="text-sm text-ink-gray-6">{{ __('The flow is waiting.') }}</p>
        <Button
          variant="subtle"
          icon-left="lucide-fast-forward"
          :disabled="busy"
          :label="__('Skip the wait')"
          @click="send({ event: 'timer' })"
        />
      </template>
      <template v-else-if="!done">
        <form class="flex items-center gap-2" @submit.prevent="type">
          <FormControl type="text" v-model="draft" class="min-w-0 flex-1" :placeholder="__('Type a reply')" :disabled="busy || !waiting" />
          <Button variant="solid" icon="lucide-send-horizontal" :label="__('Send')" :disabled="busy || !draft.trim()" type="submit" />
        </form>
        <button
          v-if="waiting"
          type="button"
          class="self-start text-xs text-ink-gray-5 underline underline-offset-2 hover:text-ink-gray-7"
          :disabled="busy"
          @click="send({ event: 'timeout' })"
        >
          {{ __('Pretend they never reply') }}
        </button>
      </template>
      <Button v-else variant="subtle" icon-left="lucide-rotate-ccw" :label="__('Start again')" @click="restart" />
    </div>
  </div>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { nextTick, onMounted, ref } from 'vue'
import { Button, FormControl, LoadingIndicator, ScrollArea, call } from 'frappe-ui'
import { fileName } from '@/data/inbox'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const props = defineProps({
  graph: { type: Function, required: true },
})

const emit = defineEmits(['close', 'path'])

const messages = ref([])
const state = ref(null)
const waiting = ref(null)
const done = ref(false)
const busy = ref(false)
const draft = ref('')
const scroller = ref(null)
const visited = ref([])
let lastBot = -1

function escape(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function format(text) {
  return escape(text)
    .replace(/\*([^*\n]+)\*/g, '<strong>$1</strong>')
    .replace(/(^|\s)_([^_\n]+)_/g, '$1<em>$2</em>')
    .replace(/~([^~\n]+)~/g, '<s>$1</s>')
}

function canAnswer(index) {
  return !busy.value && !done.value && index === lastBot
}

async function scrollDown() {
  await nextTick()
  const viewport = scroller.value?.viewportElement
  if (viewport) viewport.scrollTop = viewport.scrollHeight
}

async function send(reply = null) {
  busy.value = true
  try {
    const result = await call('onechat.automation.flows.simulate', {
      graph_json: JSON.stringify(props.graph()),
      state: state.value ? JSON.stringify(state.value) : undefined,
      reply: reply ? JSON.stringify(reply) : undefined,
    })
    messages.value.push(...(result.messages || []))
    lastBot = messages.value.findLastIndex((message) => message.from === 'bot')
    state.value = result.state
    waiting.value = result.waiting || null
    done.value = !!result.done
    visited.value = [...new Set([...visited.value, ...(result.path || [])])]
    emit('path', {
      visited: visited.value,
      waiting: waiting.value?.node || null,
      failed: (result.messages || []).some((row) => row.from === 'error'),
    })
  } catch (err) {
    messages.value.push({ from: 'error', text: errorMessage(err) })
    done.value = true
  } finally {
    busy.value = false
    scrollDown()
  }
}

function choose(option) {
  messages.value.push({ from: 'customer', text: option.title })
  send({ type: 'button', text: option.title, reply_id: option.id })
}

function type() {
  const text = draft.value.trim()
  if (!text) return
  draft.value = ''
  messages.value.push({ from: 'customer', text })
  send({ type: 'text', text })
}

function submitForm() {
  messages.value.push({ from: 'customer', text: __('Submitted the form') })
  send({ type: 'flow', text: '', form: {} })
}

function restart() {
  messages.value = []
  state.value = null
  waiting.value = null
  done.value = false
  visited.value = []
  lastBot = -1
  emit('path', { visited: [], waiting: null, failed: false })
  send()
}

onMounted(restart)
</script>

<style scoped>
.chat-wallpaper {
  background-image: radial-gradient(var(--dot, rgb(0 0 0 / 0.05)) 0.6px, transparent 0.6px);
  background-size: 14px 14px;
}
</style>
