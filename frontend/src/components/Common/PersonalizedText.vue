<template>
  <div class="flex flex-col gap-1.5">
    <div v-if="label || variables.length" class="flex items-center justify-between gap-2">
      <FormLabel v-if="label" :label="label" :required="required" />
      <span v-else />
      <Dropdown v-if="variables.length" :options="menu" align="end">
        <Button size="sm" variant="ghost" icon-left="lucide-user-round-plus" :label="__('Add personal detail')" />
      </Dropdown>
    </div>

    <div class="relative">
      <div
        ref="editor"
        contenteditable="true"
        role="textbox"
        :aria-multiline="!singleLine"
        :aria-label="label || placeholder"
        class="personalized w-full overflow-y-auto rounded-4 border border-[--surface-gray-2] bg-surface-gray-2 px-2 py-1.5 text-base leading-6 text-ink-gray-8 outline-none transition-colors hover:border-outline-elevation-2 hover:bg-surface-gray-3 focus:border-outline-gray-4 focus:bg-surface-base focus:shadow-sm focus:ring-0"
        :class="singleLine ? 'whitespace-nowrap' : 'whitespace-pre-wrap break-words'"
        :style="{ minHeight: `${singleLine ? 2 : rows * 1.5 + 0.75}rem` }"
        @input="sync"
        @keydown="onKeydown"
        @paste="onPaste"
        @drop="onDrop"
        @blur="refresh"
        @keyup="remember"
        @mouseup="remember"
      />
      <span v-if="empty && placeholder" class="pointer-events-none absolute left-2.5 top-1.5 text-base leading-6 text-ink-gray-4">
        {{ shown(placeholder) }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { Button, Dropdown, FormLabel } from 'frappe-ui'
import { translate as __ } from '@/translation'

const props = defineProps({
  modelValue: { type: String, default: '' },
  variables: { type: Array, default: () => [] },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  required: { type: Boolean, default: false },
  rows: { type: Number, default: 4 },
  singleLine: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const TOKEN = /\{\{\s*([\w.]+)\s*\}\}/g

const editor = ref(null)
const empty = ref(!props.modelValue)
let last = null
let range = null

const labels = computed(() => Object.fromEntries(props.variables.map((row) => [normalize(row.token), __(row.label)])))

const menu = computed(() => {
  const groups = []
  for (const variable of props.variables) {
    const name = variable.group ? __(variable.group) : __('Details')
    let group = groups.find((row) => row.group === name)
    if (!group) {
      group = { group: name, options: [] }
      groups.push(group)
    }
    group.options.push({ label: __(variable.label), onClick: () => insert(variable.token) })
  }
  return groups
})

function normalize(token) {
  return token.replace(/^\{\{\s*/, '{{').replace(/\s*\}\}$/, '}}')
}

function labelOf(token) {
  const known = labels.value[normalize(token)]
  if (known) return known
  const inner = token.replace(/[{}\s]/g, '')
  const part =
    inner
      .split('.')
      .filter((piece) => piece !== 'name')
      .pop() || inner
  const text = part.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function shown(text) {
  return String(text || '').replace(TOKEN, (token) => labelOf(token))
}

function pill(token) {
  const node = document.createElement('span')
  node.contentEditable = 'false'
  node.dataset.token = normalize(token)
  node.className = 'personalized-pill'
  node.textContent = labelOf(token)
  return node
}

function nodesOf(text) {
  const nodes = []
  let index = 0
  for (const match of text.matchAll(TOKEN)) {
    if (match.index > index) nodes.push(document.createTextNode(text.slice(index, match.index)))
    nodes.push(pill(match[0]))
    index = match.index + match[0].length
  }
  if (index < text.length) nodes.push(document.createTextNode(text.slice(index)))
  return nodes
}

function render(value) {
  const element = editor.value
  if (!element) return
  const text = String(value || '')
  element.replaceChildren(...nodesOf(text))
  if (!props.singleLine) element.append(endMarker())
  last = text
  empty.value = !text
}

function endMarker() {
  const node = document.createElement('br')
  node.dataset.end = '1'
  return node
}

function serialize(node) {
  let out = ''
  for (const child of node.childNodes) {
    if (child.nodeType === Node.TEXT_NODE) out += child.textContent
    else if (child.dataset?.token) out += child.dataset.token
    else if (child.nodeName === 'BR') out += child.dataset?.end ? '' : '\n'
    else {
      const inner = serialize(child)
      out += child.nodeName === 'DIV' || child.nodeName === 'P' ? `\n${inner}` : inner
    }
  }
  return out.replace(/ /g, ' ')
}

function sync() {
  if (!props.singleLine && !editor.value.querySelector('br[data-end]')) editor.value.append(endMarker())
  let value = serialize(editor.value)
  if (!value.trim() && !editor.value.querySelector('[data-token]')) value = ''
  last = value
  empty.value = !value
  emit('update:modelValue', value)
  remember()
}

function refresh() {
  const typed = [...editor.value.childNodes].some(
    (child) => child.nodeType === Node.TEXT_NODE && /\{\{\s*[\w.]+\s*\}\}/.test(child.textContent),
  )
  if (typed) render(serialize(editor.value))
}

function remember() {
  const selection = window.getSelection()
  if (selection?.rangeCount && editor.value?.contains(selection.anchorNode)) range = selection.getRangeAt(0).cloneRange()
}

function place(node) {
  const selection = window.getSelection()
  const target = range && editor.value.contains(range.startContainer) ? range : null
  if (target) {
    target.deleteContents()
    target.insertNode(node)
  } else {
    const end = editor.value.querySelector('br[data-end]')
    editor.value.insertBefore(node, end)
  }
  const after = document.createRange()
  after.setStartAfter(node)
  after.collapse(true)
  selection.removeAllRanges()
  selection.addRange(after)
  range = after.cloneRange()
}

function insert(token) {
  editor.value.focus()
  place(pill(token))
  sync()
}

function insertText(text) {
  editor.value.focus()
  remember()
  place(document.createTextNode(text))
  sync()
}

function onKeydown(event) {
  if (event.key !== 'Enter' || event.isComposing) return
  event.preventDefault()
  if (!props.singleLine) insertText('\n')
}

function onPaste(event) {
  event.preventDefault()
  insertPlain(event.clipboardData?.getData('text/plain') || '')
}

function onDrop(event) {
  event.preventDefault()
  const point = document.caretRangeFromPoint?.(event.clientX, event.clientY)
  if (point && editor.value.contains(point.startContainer)) range = point
  insertPlain(event.dataTransfer?.getData('text/plain') || '')
}

function insertPlain(value) {
  let text = value
  if (props.singleLine) text = text.replace(/\s*\n\s*/g, ' ')
  if (!text) return
  editor.value.focus()
  if (!range) remember()
  nodesOf(text).forEach(place)
  sync()
}

watch(
  () => props.modelValue,
  (value) => {
    if ((value || '') !== (last || '')) render(value)
  },
)

function relabel() {
  for (const node of editor.value?.querySelectorAll('[data-token]') || []) {
    const text = labelOf(node.dataset.token)
    if (node.textContent !== text) node.textContent = text
  }
}

watch(labels, relabel)

onMounted(() => render(props.modelValue))
</script>

<style scoped>
.personalized :deep(.personalized-pill) {
  display: inline-block;
  margin: 0 1px;
  padding: 0 6px;
  border-radius: 9999px;
  background: var(--surface-blue-2, #e6f0ff);
  color: var(--ink-blue-3, #0a5bd3);
  font-size: 0.85em;
  line-height: 1.5;
  white-space: nowrap;
  user-select: all;
  cursor: default;
}
</style>
