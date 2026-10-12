<template>
  <ResponsiveDialog v-if="ui.confirmation.open" v-model:open="ui.confirmation.open" :title="ui.confirmation.title" size="sm">
    <template #default>
      <p class="text-base text-ink-gray-7">{{ ui.confirmation.message }}</p>
      <ErrorMessage :message="error" class="mt-3" />
    </template>

    <template #actions>
      <div class="flex w-full justify-end gap-2">
        <Button variant="subtle" :label="__('Cancel')" @click="ui.confirmation.open = false" />
        <Button variant="solid" :theme="ui.confirmation.theme" :loading="busy" :label="ui.confirmation.action" @click="confirm" />
      </div>
    </template>
  </ResponsiveDialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Button, ErrorMessage } from 'frappe-ui'
import ResponsiveDialog from '@/components/Common/ResponsiveDialog.vue'
import { useUI } from '@/stores/ui'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const ui = useUI()
const busy = ref(false)
const error = ref('')

watch(
  () => ui.confirmation.open,
  () => (error.value = ''),
)

async function confirm() {
  busy.value = true
  error.value = ''

  try {
    await ui.confirmation.onConfirm?.()
    ui.confirmation.open = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    busy.value = false
  }
}
</script>
