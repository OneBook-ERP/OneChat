import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUI = defineStore('ui', () => {
  const settingsDialog = ref(false)
  const searchDialog = ref(false)
  const settingsTab = ref('preferences')
  const settingsDirect = ref(false)
  const sidebarCollapsed = ref(false)
  const fullScreen = ref(false)
  const confirmation = ref({ open: false, title: '', message: '', action: '', theme: 'gray', onConfirm: null })

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function toggleFullScreen() {
    fullScreen.value = !fullScreen.value
  }

  function openSettings(tab) {
    settingsTab.value = tab || 'preferences'
    settingsDirect.value = Boolean(tab)
    settingsDialog.value = true
  }

  function openSearch() {
    searchDialog.value = true
  }

  function confirm({ title, message = '', action = 'Confirm', theme = 'gray', onConfirm }) {
    confirmation.value = { open: true, title, message, action, theme, onConfirm }
  }

  return {
    settingsDialog,
    searchDialog,
    settingsTab,
    settingsDirect,
    sidebarCollapsed,
    fullScreen,
    confirmation,
    toggleSidebar,
    toggleFullScreen,
    openSettings,
    openSearch,
    confirm,
  }
})
