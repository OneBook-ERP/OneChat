<template>
  <Teleport v-if="stop" to="body">
    <div
      ref="layer"
      class="onechat-tour"
      :style="{ position: 'fixed', left: '0px', top: '0px', width: '0px', height: '0px', zIndex: 2147483000 }"
    >
      <div
        v-if="hole"
        class="onechat-tour-hole"
        :style="{
          position: 'absolute',
          left: `${hole.left}px`,
          top: `${hole.top}px`,
          width: `${hole.width}px`,
          height: `${hole.height}px`,
        }"
      />
      <div
        v-else
        :style="{
          position: 'absolute',
          left: `${-origin.x}px`,
          top: `${-origin.y}px`,
          width: '100vw',
          height: '100dvh',
          background: 'rgba(15, 15, 15, 0.55)',
          pointerEvents: 'none',
        }"
      />

      <div
        ref="card"
        role="region"
        aria-live="polite"
        :aria-label="__(stop.title)"
        class="flex flex-col gap-3 rounded-6 border border-outline-gray-2 bg-surface-base p-4 shadow-2xl"
        :style="{ position: 'absolute', left: `${place.left}px`, top: `${place.top}px`, width: `${place.width}px`, pointerEvents: 'auto' }"
        @pointerdown.stop
        @mousedown.prevent
        @focusin.stop
      >
        <div class="flex items-start justify-between gap-2">
          <div class="flex min-w-0 items-center gap-2">
            <span class="grid size-7 shrink-0 place-content-center rounded-full bg-surface-gray-2 text-ink-gray-7">
              <span :class="current.step.icon" class="size-3.5" aria-hidden="true" />
            </span>
            <TruncatedText as="p" class="truncate text-sm text-ink-gray-5" :text="__(current.step.title)" />
          </div>
          <Button variant="ghost" icon="lucide-x" :label="__('Close guide')" @click="onboarding.stop()" />
        </div>

        <div>
          <p class="text-lg font-semibold text-ink-gray-9">{{ __(stop.title) }}</p>
          <p class="mt-1 text-base leading-6 text-ink-gray-7">{{ __(stop.text) }}</p>
        </div>

        <div v-if="missing" class="flex flex-col items-start gap-2">
          <p class="flex items-start gap-1.5 text-sm text-ink-amber-7">
            <span class="lucide-search mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            {{ __('It is not on this screen right now. On a phone, look under More actions.') }}
          </p>
          <Button
            v-if="stop.route || stop.settings"
            size="sm"
            variant="subtle"
            icon-left="lucide-navigation"
            :label="__('Take me there')"
            @click="retry"
          />
        </div>
        <p v-else-if="stop.advance === 'click'" class="flex items-center gap-1.5 text-sm text-ink-blue-7">
          <span class="lucide-mouse-pointer-click size-3.5 shrink-0" aria-hidden="true" />
          {{ __('Click the highlighted spot to continue.') }}
        </p>

        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-1" :aria-label="__('Step {0} of {1}').format(current.index + 1, current.total)">
            <span
              v-for="dot in current.total"
              :key="dot"
              class="h-1.5 rounded-full transition-all"
              :class="dot - 1 === current.index ? 'w-4 bg-surface-gray-7' : 'w-1.5 bg-surface-gray-4'"
            />
          </div>
          <div class="flex items-center gap-2">
            <Button v-if="current.index" variant="ghost" :label="__('Back')" @click="onboarding.back()" />
            <Button
              :variant="stop.advance === 'click' && !missing ? 'subtle' : 'solid'"
              :label="last ? __('Done') : stop.advance === 'click' && !missing ? __('Skip') : __('Next')"
              @click="onboarding.next()"
            />
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import TruncatedText from '@/components/Common/TruncatedText.vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Button } from 'frappe-ui'
import { useOnboarding } from '@/stores/onboarding'
import { useUI } from '@/stores/ui'
import { translate as __ } from '@/translation'

const PAD = 6
const GAP = 12
const EDGE = 12
const WAIT_MS = 5000

const onboarding = useOnboarding()
const ui = useUI()
const router = useRouter()

const layer = ref(null)
const card = ref(null)
const rect = ref(null)
const origin = ref({ x: 0, y: 0 })
const bounds = ref({ left: 0, top: 0, right: window.innerWidth, bottom: window.innerHeight })
const cardHeight = ref(180)
const missing = ref(false)

const current = computed(() => onboarding.current)
const stop = computed(() => current.value?.stop || null)
const last = computed(() => current.value && current.value.index + 1 === current.value.total)

let element = null
let enteredAt = 0
let frame = 0
let advancing = false

function visible(node) {
  if (!node?.isConnected) return false
  const box = node.getBoundingClientRect()
  return box.width > 0 && box.height > 0
}

function find(keys) {
  for (const key of [].concat(keys || [])) {
    const node = [...document.querySelectorAll(`[data-tour="${key}"]`)].find(visible)
    if (node) return node
  }
  return null
}

function go(value) {
  if (!value) return
  if (value.settings && (!ui.settingsDialog || ui.settingsTab !== value.settings)) ui.openSettings(value.settings)
  if (value.route) {
    ui.settingsDialog = false
    if (router.currentRoute.value.name !== value.route) router.push({ name: value.route })
  }
}

function same(a, b) {
  return a && b && Object.keys(a).every((key) => Math.round(a[key]) === Math.round(b[key]))
}

function tick() {
  frame = requestAnimationFrame(tick)
  if (!stop.value) return

  if (!visible(element)) {
    element = find(stop.value.target)
    if (element) {
      missing.value = false
      element.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' })
    } else if (stop.value.skip && find(stop.value.skip)) {
      onboarding.next()
      return
    } else if (Date.now() - enteredAt > WAIT_MS) {
      missing.value = true
    }
  }

  const box = element ? element.getBoundingClientRect() : null
  const next = box ? { left: box.left, top: box.top, width: box.width, height: box.height } : null
  if (!same(next, rect.value)) rect.value = next

  if (layer.value) {
    const probe = layer.value.getBoundingClientRect()
    const nextOrigin = { x: probe.left, y: probe.top }
    if (!same(nextOrigin, origin.value)) origin.value = nextOrigin
  }

  const nextBounds = { left: 0, top: 0, right: window.innerWidth, bottom: window.innerHeight }
  if (!same(nextBounds, bounds.value)) bounds.value = nextBounds

  if (card.value && Math.round(card.value.offsetHeight) !== cardHeight.value) cardHeight.value = Math.round(card.value.offsetHeight)
}

const hole = computed(() => {
  if (!rect.value) return null
  return {
    left: rect.value.left - PAD - origin.value.x,
    top: rect.value.top - PAD - origin.value.y,
    width: rect.value.width + PAD * 2,
    height: rect.value.height + PAD * 2,
  }
})

const place = computed(() => {
  const area = bounds.value
  const width = Math.min(360, area.right - area.left - EDGE * 2)
  const height = cardHeight.value
  let left
  let top

  if (rect.value) {
    const below = rect.value.top + rect.value.height + PAD + GAP
    const above = rect.value.top - PAD - GAP - height
    const right = rect.value.left + rect.value.width + PAD + GAP
    const leftSide = rect.value.left - PAD - GAP - width
    left = rect.value.left
    if (below + height <= area.bottom - EDGE) top = below
    else if (above >= area.top + EDGE) top = above
    else {
      top = rect.value.top
      if (right + width <= area.right - EDGE) left = right
      else if (leftSide >= area.left + EDGE) left = leftSide
      else top = area.bottom - EDGE - height
    }
  } else {
    top = (area.top + area.bottom - height) / 2
    left = (area.left + area.right - width) / 2
  }

  left = Math.min(Math.max(left, area.left + EDGE), area.right - EDGE - width)
  top = Math.min(Math.max(top, area.top + EDGE), area.bottom - EDGE - height)
  return { left: left - origin.value.x, top: top - origin.value.y, width }
})

function onClick(event) {
  if (!stop.value || stop.value.advance !== 'click' || advancing) return
  const marked = event.target.closest?.('[data-tour]')?.getAttribute('data-tour')
  if (!element?.contains(event.target) && !stop.value.target.includes(marked)) return
  advancing = true
  setTimeout(() => {
    advancing = false
    onboarding.next()
  }, 400)
}

function retry() {
  element = null
  missing.value = false
  enteredAt = Date.now()
  go(stop.value)
}

function onKey(event) {
  if (event.key === 'Escape' && stop.value) onboarding.stop()
}

watch(
  stop,
  (value) => {
    element = null
    rect.value = null
    missing.value = false
    enteredAt = Date.now()
    go(value)
  },
  { immediate: true },
)

onMounted(() => {
  frame = requestAnimationFrame(tick)
  document.addEventListener('click', onClick, true)
  document.addEventListener('keydown', onKey)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  document.removeEventListener('click', onClick, true)
  document.removeEventListener('keydown', onKey)
})
</script>
