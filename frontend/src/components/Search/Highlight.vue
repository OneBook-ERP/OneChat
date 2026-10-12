<template>
  <template v-for="(part, index) in parts" :key="index">
    <mark v-if="part.match" class="bg-transparent font-semibold text-ink-gray-9">{{ part.text }}</mark>
    <template v-else>{{ part.text }}</template>
  </template>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  text: { type: String, default: '' },
  query: { type: String, default: '' },
})

const parts = computed(() => {
  const source = props.text || ''
  const needle = props.query.trim().toLowerCase()
  if (!needle) return [{ text: source, match: false }]

  const lower = source.toLowerCase()
  const out = []
  let from = 0
  let at = lower.indexOf(needle)

  while (at > -1) {
    if (at > from) out.push({ text: source.slice(from, at), match: false })
    out.push({ text: source.slice(at, at + needle.length), match: true })
    from = at + needle.length
    at = lower.indexOf(needle, from)
  }

  if (from < source.length) out.push({ text: source.slice(from), match: false })

  return out
})
</script>
