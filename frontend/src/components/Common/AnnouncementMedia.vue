<template>
  <div v-if="item.type === 'image' && item.media?.src" class="overflow-hidden bg-surface-gray-2" :class="large ? 'rounded-5' : ''">
    <button type="button" class="block w-full" :aria-label="item.title || __('Open')" @click="emit('open')">
      <img
        :src="item.media.src"
        :alt="item.media.alt || item.title || ''"
        class="w-full object-cover"
        :style="{ aspectRatio: item.media.aspect || '16/9' }"
        loading="lazy"
      />
    </button>
  </div>

  <div
    v-else-if="item.type === 'video' && item.media?.src"
    class="relative overflow-hidden bg-black"
    :class="large ? 'rounded-5' : ''"
    :style="{ aspectRatio: item.media.aspect || '16/9' }"
  >
    <iframe
      v-if="embed && (large || playing)"
      :src="embed.url(true)"
      class="absolute inset-0 size-full"
      :title="item.title || __('Video')"
      allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
      allowfullscreen
      referrerpolicy="strict-origin-when-cross-origin"
    />
    <button v-else-if="embed" type="button" class="group absolute inset-0 size-full" :aria-label="__('Play video')" @click="play">
      <img v-if="embed.thumb || item.media.poster" :src="item.media.poster || embed.thumb" alt="" class="size-full object-cover" />
      <span class="absolute inset-0 flex items-center justify-center bg-black/20 transition-colors group-hover:bg-black/30">
        <span class="flex size-12 items-center justify-center rounded-full bg-white/90 text-ink-gray-9 shadow-lg">
          <span class="lucide-play ml-0.5 size-5" aria-hidden="true" />
        </span>
      </span>
    </button>
    <video
      v-else
      :src="item.media.src"
      :poster="item.media.poster"
      class="absolute inset-0 size-full object-cover"
      :autoplay="autoplayFile"
      :muted="!large"
      :controls="large"
      loop
      playsinline
      preload="metadata"
      @click="!large && emit('open')"
    />
  </div>

  <div
    v-else-if="item.type === 'html' && item.html"
    class="overflow-hidden bg-surface-base"
    :class="large ? 'rounded-5 border border-outline-gray-1' : ''"
  >
    <iframe
      :srcdoc="documentHtml"
      sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox"
      referrerpolicy="no-referrer"
      loading="lazy"
      class="block w-full border-0"
      :style="{ height: `${frameHeight}px` }"
      :title="item.title || __('Announcement')"
    />
  </div>

  <div v-else-if="item.type === 'card' && item.media?.src" class="bg-surface-gray-2">
    <img :src="item.media.src" alt="" class="w-full object-cover" :style="{ aspectRatio: item.media.aspect || '2/1' }" loading="lazy" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { embedOf, htmlDocument } from '@/data/announcements'
import { translate as __ } from '@/translation'

const props = defineProps({
  item: { type: Object, required: true },
  large: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  autoplay: { type: Boolean, default: false },
})
const emit = defineEmits(['open'])

const playing = ref(false)
const reducedMotion = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

const embed = computed(() => (props.item.type === 'video' ? embedOf(props.item.media?.src) : null))
const autoplayFile = computed(() => !reducedMotion && (props.large ? props.autoplay : props.item.media?.autoplay !== false))
const documentHtml = computed(() => htmlDocument(props.item.html))
const frameHeight = computed(() => {
  if (props.large) return Number(props.item.expanded_height) || Math.max(Number(props.item.height) || 0, 420)
  const height = Number(props.item.height) || 140
  return Math.min(height, props.compact ? 120 : 260)
})

function play() {
  playing.value = true
}
</script>
