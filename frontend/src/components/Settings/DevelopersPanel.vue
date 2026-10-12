<template>
  <SettingsHeader :title="__('Developers')" :description="__('Connect your own systems to OneChat')" />
  <SettingsBody>
    <div class="flex flex-col gap-8 pb-8 pt-6">
      <WebhooksSection />

      <ApiReference />
    </div>
  </SettingsBody>
</template>

<script setup>
import { SettingsBody, SettingsHeader } from 'frappe-ui'
import ApiReference from './ApiReference.vue'
import WebhooksSection from './WebhooksSection.vue'
import { translate as __ } from '@/translation'
</script>
