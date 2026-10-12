import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { call, toast } from 'frappe-ui'
import { counts, inbox, loadConversations } from '@/data/inbox'
import { errorMessage } from '@/utils/format'
import { translate as __ } from '@/translation'

const METHOD = 'onechat.workspace.numbers.'

export const useNumbers = defineStore('numbers', () => {
  const rows = ref([])
  const teamRows = ref([])
  const loaded = ref(false)
  const saving = ref(false)
  const version = ref(0)

  const hidden = computed(() => rows.value.filter((row) => !row.shown).map((row) => row.name))
  const hiddenTeams = computed(() => teamRows.value.filter((row) => !row.shown).map((row) => row.name))
  const scoped = computed(() => hidden.value.length > 0 || hiddenTeams.value.length > 0)
  const hasMenu = computed(() => rows.value.length > 1 || teamRows.value.length > 1)

  function sync() {
    inbox.hiddenNumbers = hidden.value
    inbox.hiddenTeams = hiddenTeams.value
  }

  async function load() {
    const [accounts, teams] = await Promise.allSettled([call(`${METHOD}options`), call(`${METHOD}team_options`)])
    rows.value = (accounts.status === 'fulfilled' && accounts.value) || []
    teamRows.value = (teams.status === 'fulfilled' && teams.value) || []
    sync()
    loaded.value = true
  }

  async function saveAccounts(names) {
    rows.value = await call(`${METHOD}save`, { hidden_numbers: JSON.stringify(names) })
  }

  async function saveTeams(names) {
    teamRows.value = await call(`${METHOD}save_teams`, { hidden: JSON.stringify(names) })
  }

  async function persist(...requests) {
    saving.value = true
    try {
      await Promise.all(requests)
      sync()
      version.value += 1
      loadConversations(true)
      counts.reload()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      saving.value = false
    }
  }

  function hideIn(current, total, name, shown, message, saveNames) {
    const next = new Set(current)
    if (shown) next.delete(name)
    else next.add(name)
    if (next.size >= total) {
      toast.error(message)
      return
    }
    return persist(saveNames([...next]))
  }

  function toggle(name, shown) {
    return hideIn(hidden.value, rows.value.length, name, shown, __('Keep at least one account shown.'), saveAccounts)
  }

  function toggleTeam(name, shown) {
    return hideIn(hiddenTeams.value, teamRows.value.length, name, shown, __('Keep at least one team shown.'), saveTeams)
  }

  function showAll() {
    return persist(...(hidden.value.length ? [saveAccounts([])] : []), ...(hiddenTeams.value.length ? [saveTeams([])] : []))
  }

  function isHidden(account) {
    return Boolean(account) && hidden.value.includes(account)
  }

  return {
    rows,
    teamRows,
    loaded,
    saving,
    version,
    hidden,
    hiddenTeams,
    scoped,
    hasMenu,
    load,
    toggle,
    toggleTeam,
    showAll,
    isHidden,
  }
})
