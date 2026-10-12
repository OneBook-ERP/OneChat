<template>
  <Settings v-model:open="ui.settingsDialog" />
  <ConfirmDialog />
  <SearchPalette v-model:open="ui.searchDialog" />
</template>

<script setup>
import Settings from '@/components/Settings/Settings.vue'
import ConfirmDialog from '@/components/Common/ConfirmDialog.vue'
import SearchPalette from '@/components/Search/SearchPalette.vue'
import { useUI } from '@/stores/ui'

const ui = useUI()
</script>
