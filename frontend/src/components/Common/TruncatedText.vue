<template>
  <Tooltip :text="shown">
    <component :is="as" ref="node" v-bind="$attrs" @pointerenter="measure" @focusin="measure">
      <slot>{{ text }}</slot>
    </component>
  </Tooltip>
</template>

<script setup>
import { ref } from 'vue'
import { Tooltip } from 'frappe-ui'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  text: { type: [String, Number], default: '' },
  tip: { type: [String, Number], default: '' },
  as: { type: String, default: 'span' },
})

const node = ref(null)
const shown = ref('')

function measure() {
  const element = node.value?.$el || node.value
  if (!element) return
  const cut = element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1
  const full = String(props.tip || props.text || element.innerText || '').trim()
  shown.value = cut && full ? full : ''
}
</script>
