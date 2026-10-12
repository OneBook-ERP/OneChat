<template>
  <svg
    viewBox="6 2.5 19.5 19.5"
    fill="none"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="assistant-icon"
    :class="{ 'assistant-icon--still': still }"
    aria-hidden="true"
  >
    <path d="M8 19.5l1-3.2A6.5 6.5 0 1 1 11.7 19z" stroke="currentColor" :stroke-width="stroke" />
    <g v-if="thinking" fill="currentColor">
      <circle class="assistant-icon__dot" cx="11.9" cy="13.3" r="1.05" />
      <circle class="assistant-icon__dot" cx="14.6" cy="13.3" r="1.05" />
      <circle class="assistant-icon__dot" cx="17.3" cy="13.3" r="1.05" />
    </g>
    <g v-else fill="currentColor">
      <rect class="assistant-icon__eye" x="11.85" y="11.6" width="1.6" height="3.2" rx=".8" />
      <rect class="assistant-icon__eye" x="15.75" y="11.6" width="1.6" height="3.2" rx=".8" />
    </g>
    <path
      class="assistant-icon__spark"
      d="M21.6 4c.22 1.5.75 2.03 2.25 2.25-1.5.22-2.03.75-2.25 2.25-.22-1.5-.75-2.03-2.25-2.25 1.5-.22 2.03-.75 2.25-2.25Z"
      fill="#e0a800"
    />
  </svg>
</template>

<script setup>
defineOptions({ name: 'AssistantIcon' })
defineProps({
  stroke: { type: Number, default: 1.7 },
  thinking: { type: Boolean, default: false },
  still: { type: Boolean, default: false },
})
</script>

<style scoped>
.assistant-icon__eye,
.assistant-icon__spark,
.assistant-icon__dot {
  transform-box: fill-box;
  transform-origin: center;
}
.assistant-icon__eye {
  animation: assistant-blink 5s infinite;
}
.assistant-icon__spark {
  animation: assistant-twinkle 3s ease-in-out infinite;
}
.assistant-icon__dot {
  animation: assistant-dot 1.2s ease-in-out infinite;
}
.assistant-icon__dot:nth-child(2) {
  animation-delay: 0.15s;
}
.assistant-icon__dot:nth-child(3) {
  animation-delay: 0.3s;
}
.assistant-icon--still .assistant-icon__eye,
.assistant-icon--still .assistant-icon__spark {
  animation: none;
}
@keyframes assistant-blink {
  0%,
  94%,
  100% {
    transform: scaleY(1);
  }
  97% {
    transform: scaleY(0.15);
  }
}
@keyframes assistant-twinkle {
  50% {
    transform: scale(0.6) rotate(45deg);
    opacity: 0.65;
  }
}
@keyframes assistant-dot {
  0%,
  100% {
    opacity: 0.35;
  }
  40% {
    opacity: 1;
  }
}
@media (prefers-reduced-motion: reduce) {
  .assistant-icon__eye,
  .assistant-icon__spark,
  .assistant-icon__dot {
    animation: none;
  }
}
</style>
