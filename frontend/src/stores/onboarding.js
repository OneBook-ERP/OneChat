import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { call, toast } from 'frappe-ui'
import { GROUPS, STEPS } from '@/data/onboardingSteps'
import { session } from '@/data/session'
import { translate as __ } from '@/translation'

export { GROUPS, STEPS }

const SEEN_KEY = 'onechat-onboarding-seen'
const WATCH_DELAYS = [3000, 10000, 30000, 90000]

export const useOnboarding = defineStore('onboarding', () => {
  const status = ref(null)
  const loading = ref(false)
  const open = ref(false)
  const tour = ref(null)
  const result = ref(null)

  const steps = computed(() =>
    STEPS.filter((step) => status.value && step.key in status.value.steps).map((step) => ({
      ...step,
      done: Boolean(status.value.steps[step.key]),
    })),
  )
  const groups = computed(() =>
    GROUPS.map((group) => ({ ...group, steps: steps.value.filter((step) => step.group === group.key) })).filter(
      (group) => group.steps.length,
    ),
  )
  const doneCount = computed(() => steps.value.filter((step) => step.done).length)
  const remaining = computed(() => steps.value.filter((step) => !step.done && !step.optional).length)
  const complete = computed(() => Boolean(status.value) && remaining.value === 0)
  const dismissed = computed(() => Boolean(status.value?.dismissed))
  const marked = computed(() => new Set(status.value?.marked || []))
  let lastLoad = 0

  const current = computed(() => {
    if (!tour.value) return null
    const step = STEPS.find((row) => row.key === tour.value.key)
    return step ? { step, index: tour.value.index, total: step.tour.length, stop: step.tour[tour.value.index] } : null
  })

  async function load() {
    if (!session.user.is_admin) return
    loading.value = true
    lastLoad = Date.now()
    try {
      status.value = await call('onechat.workspace.onboarding.status')
    } finally {
      loading.value = false
    }
  }

  function refresh() {
    if (!status.value || complete.value || dismissed.value) return
    if (Date.now() - lastLoad < 5000) return
    load()
  }

  async function mark(key, done = true) {
    status.value = await call('onechat.workspace.onboarding.mark', { step: key, done: done ? 1 : 0 })
  }

  async function welcome() {
    await load()
    if (!status.value || dismissed.value || doneCount.value) return
    let seen = false
    try {
      seen = Boolean(sessionStorage.getItem(SEEN_KEY))
      sessionStorage.setItem(SEEN_KEY, '1')
    } catch {
      seen = false
    }
    if (!seen) open.value = true
  }

  function show() {
    open.value = true
    load()
  }

  function start(key) {
    open.value = false
    result.value = null
    tour.value = { key, index: 0 }
  }

  function next() {
    if (!current.value) return
    if (current.value.index + 1 < current.value.total) tour.value = { ...tour.value, index: tour.value.index + 1 }
    else finish()
  }

  async function check(key) {
    await load()
    result.value = key ? { key, done: Boolean(status.value?.steps?.[key]) } : null
  }

  function back() {
    if (tour.value?.index) tour.value = { ...tour.value, index: tour.value.index - 1 }
  }

  function stop() {
    tour.value = null
  }

  function finish() {
    const key = tour.value?.key
    tour.value = null
    if (key && !status.value?.steps?.[key]) watchStep(key)
  }

  function watchStep(key, attempt = 0) {
    setTimeout(async () => {
      if (tour.value || open.value) return
      await load()
      if (status.value?.steps?.[key]) celebrate(key)
      else if (attempt + 1 < WATCH_DELAYS.length) watchStep(key, attempt + 1)
    }, WATCH_DELAYS[attempt])
  }

  function celebrate(key) {
    const step = STEPS.find((row) => row.key === key)
    const upcoming = steps.value.find((row) => !row.done && !row.optional)
    result.value = { key, done: true }
    toast.success(__('{0} is done').format(__(step?.title || key)), {
      description: upcoming ? __('Next up: {0}').format(__(upcoming.title)) : __('Your setup is complete'),
      duration: 8000,
      action: { label: __('Open setup'), onClick: show },
    })
  }

  async function dismiss(value = true) {
    status.value = await call('onechat.workspace.onboarding.dismiss', { value: value ? 1 : 0 })
    if (value) open.value = false
  }

  return {
    status,
    loading,
    open,
    tour,
    result,
    steps,
    groups,
    doneCount,
    remaining,
    complete,
    dismissed,
    marked,
    current,
    load,
    refresh,
    mark,
    welcome,
    show,
    start,
    next,
    back,
    stop,
    finish,
    check,
    dismiss,
  }
})
