<template>
  <div
    v-if="!isDesktop"
    ref="root"
    class="flex items-center gap-1 border-t border-outline-gray-1"
    :class="
      inline ? 'pt-2' : ['sticky bottom-0 z-10 bg-surface-base py-2', { 'pb-[calc(0.5rem+env(safe-area-inset-bottom))]': ui.fullScreen }]
    "
  >
    <Button
      size="lg"
      variant="ghost"
      icon="lucide-chevron-left"
      :label="__('Previous page')"
      :disabled="page === 1"
      @click="go(page - 1)"
    />
    <span class="min-w-14 text-center text-base tabular-nums text-ink-gray-7" aria-live="polite"> {{ page }} / {{ totalPages }} </span>
    <Button
      size="lg"
      variant="ghost"
      icon="lucide-chevron-right"
      :label="__('Next page')"
      :disabled="page === totalPages"
      @click="go(page + 1)"
    />
  </div>

  <div
    v-else
    ref="root"
    class="flex flex-col gap-3 border-t border-outline-gray-1 sm:flex-row sm:items-center sm:justify-between"
    :class="inline ? 'pt-2.5' : 'sticky bottom-0 z-10 bg-surface-base px-2 py-2.5'"
  >
    <div class="flex items-center gap-3">
      <div class="flex items-center gap-2">
        <span class="whitespace-nowrap text-sm text-ink-gray-5">{{ __('Rows per page') }}</span>
        <Select v-model="size" class="w-20" :options="sizes" :aria-label="__('Rows per page')" />
      </div>
      <span class="whitespace-nowrap text-sm text-ink-gray-5">
        {{ __('Page {0} of {1}').format(page, totalPages) }}
      </span>
      <span class="hidden whitespace-nowrap text-sm text-ink-gray-5 sm:inline">
        {{ __('{0}–{1} of {2}').format(first, last, total) }}
      </span>
    </div>

    <div class="flex items-center gap-1">
      <Button variant="ghost" icon="lucide-chevrons-left" :label="__('First page')" :disabled="page === 1" @click="go(1)" />
      <Button variant="ghost" icon="lucide-chevron-left" :label="__('Previous page')" :disabled="page === 1" @click="go(page - 1)" />

      <div class="hidden items-center gap-1 sm:flex">
        <template v-for="entry in pages" :key="entry">
          <span v-if="typeof entry === 'string'" class="grid size-7 place-content-center text-sm text-ink-gray-4">…</span>
          <Button v-else :variant="entry === page ? 'subtle' : 'ghost'" :label="String(entry)" @click="go(entry)" />
        </template>
      </div>

      <Button variant="ghost" icon="lucide-chevron-right" :label="__('Next page')" :disabled="page === totalPages" @click="go(page + 1)" />
      <Button
        variant="ghost"
        icon="lucide-chevrons-right"
        :label="__('Last page')"
        :disabled="page === totalPages"
        @click="go(totalPages)"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, Select } from 'frappe-ui'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { useUI } from '@/stores/ui'
import { PAGE_SIZES, pageLength } from '@/utils/paging'
import { translate as __ } from '@/translation'

const props = defineProps({
  total: { type: Number, default: 0 },
  spread: { type: Number, default: 1 },
  inline: { type: Boolean, default: false },
})

const page = defineModel('page', { type: Number, default: 1 })

const ui = useUI()
const { isDesktop } = useBreakpoint()

const sizes = PAGE_SIZES.map((value) => ({ label: String(value), value }))

const size = computed({
  get: () => pageLength.value,
  set: (value) => (pageLength.value = Number(value)),
})

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / pageLength.value)))
const first = computed(() => (props.total ? (page.value - 1) * pageLength.value + 1 : 0))
const last = computed(() => Math.min(page.value * pageLength.value, props.total))

const pages = computed(() => {
  const count = totalPages.value
  const current = page.value
  const out = []
  let previous = 0

  for (let i = 1; i <= count; i++) {
    const near = Math.abs(i - current) <= props.spread
    const edge = i === 1 || i === count
    if (!near && !edge) continue

    if (previous && i - previous > 1) out.push('gap-' + i)
    out.push(i)
    previous = i
  }

  return out
})

const root = ref(null)

function go(to) {
  const next = Math.min(Math.max(1, to), totalPages.value)
  if (next === page.value) return
  page.value = next
  scrollBack()
}

// The rows scroll in a container the pager sits beside, not inside, so reset
// whatever is actually scrolled in the nearest block around the pager.
function scrollBack() {
  let node = root.value?.parentElement
  while (node && node !== document.body) {
    const scrolled = [node, ...node.querySelectorAll('*')].filter((el) => el.scrollTop > 0)
    if (scrolled.length) {
      scrolled.forEach((el) => el.scrollTo({ top: 0 }))
      return
    }
    node = node.parentElement
  }
  if (window.scrollY > 0) window.scrollTo({ top: 0 })
}
</script>
