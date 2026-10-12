<template>
  <AppHeader :title="__('Page not found')" />

  <div class="mx-auto w-full max-w-[940px] px-3 pb-10 pt-5 sm:px-5">
    <EmptyState illustration="result" :title="__('Nothing lives here')" :description="__('The link may be old, or the page has moved.')">
      <Button class="mt-2" variant="subtle" icon-left="lucide-inbox" :label="__('Go to inbox')" @click="router.push('/inbox')" />
    </EmptyState>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { Button } from 'frappe-ui'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import EmptyState from '@/components/Common/EmptyState.vue'
import { translate as __ } from '@/translation'

const router = useRouter()
</script>
