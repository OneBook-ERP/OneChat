<template>
  <svg
    :width="size"
    :height="size"
    :viewBox="art?.viewBox || '0 0 130 122'"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="oc-empty-art mx-auto select-none"
    aria-hidden="true"
    v-html="art?.body || ''"
  />
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  name: { type: String, default: 'result' },
  size: { type: [Number, String], default: 160 },
})

const FILES = import.meta.glob('./illustrations/*.js')

const cache = {}
const art = ref(null)

function fileFor(name) {
  const key = `./illustrations/${name}.js`
  return FILES[key] ? key : './illustrations/product.js'
}

watch(
  () => props.name,
  async (name) => {
    const key = fileFor(name)
    if (!cache[key]) {
      cache[key] = FILES[key]()
        .then((module) => module.default)
        .catch(() => {
          delete cache[key]
          return null
        })
    }
    const loaded = await cache[key]
    if (fileFor(props.name) === key) art.value = loaded
  },
  { immediate: true },
)
</script>

<style>
.oc-empty-art {
  --oc-es-bg: var(--surface-gray-2);
  --oc-es-soft: var(--surface-gray-4, #d2d2d2);
  --oc-es-card: var(--surface-elevation-1, #fff);
  --oc-es-line: var(--ink-gray-4);
  --oc-es-spark: var(--ink-gray-3, #cfcfcf);
  stroke-linecap: round;
  stroke-linejoin: round;
}
.oc-empty-art .oc-es-f-bg {
  fill: var(--oc-es-bg);
}
.oc-empty-art .oc-es-f-soft {
  fill: var(--oc-es-soft);
}
.oc-empty-art .oc-es-f-card {
  fill: var(--oc-es-card);
}
.oc-empty-art .oc-es-f-line {
  fill: var(--oc-es-line);
}
.oc-empty-art .oc-es-f-spark {
  fill: var(--oc-es-spark);
}
.oc-empty-art .oc-es-s-bg {
  stroke: var(--oc-es-bg);
}
.oc-empty-art .oc-es-s-soft {
  stroke: var(--oc-es-soft);
}
.oc-empty-art .oc-es-s-card {
  stroke: var(--oc-es-card);
}
.oc-empty-art .oc-es-s-line {
  stroke: var(--oc-es-line);
}
.oc-empty-art .oc-es-s-spark {
  stroke: var(--oc-es-spark);
}
</style>
