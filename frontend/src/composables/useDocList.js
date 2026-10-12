import { computed, reactive, ref, toValue, watch } from 'vue'
import { call, createResource, debounce } from 'frappe-ui'
import { field, refField, useQueryState } from '@/composables/useQueryState'
import { pageLength } from '@/utils/paging'
import { recall, remember } from '@/utils/swr'

export const EXPORT_LIMIT = 10000

export function useDocList(options) {
  const search = ref('')
  const values = reactive({ ...(options.initialFilters || {}) })
  const orderBy = ref(options.orderBy || 'modified desc')
  const selection = ref([])
  const rows = ref([])
  const page = ref(1)

  function filters() {
    const out = { ...(toValue(options.filters) || {}) }

    for (const filter of options.quickFilters || []) {
      const value = values[filter.key]
      if (value === '' || value === null || value === undefined) continue

      out[filter.field || filter.key] = filter.toFilter ? filter.toFilter(value) : value
    }

    return Object.entries(out).flatMap(([key, value]) => {
      if (!Array.isArray(value)) return [[key, '=', value]]
      const [op, arg] = value
      if (op === 'between' && Array.isArray(arg) && arg.every((bound) => typeof bound === 'number')) {
        return [
          [key, '>=', arg[0]],
          [key, '<=', arg[1]],
        ]
      }
      return [[key, op, arg]]
    })
  }

  function orFilters() {
    const text = search.value.trim()
    if (!text || !options.searchFields?.length) return null

    return Object.fromEntries(options.searchFields.map((field) => [field, ['like', `%${text}%`]]))
  }

  const list = createResource({
    url: 'frappe.client.get_list',
    makeParams: () => ({
      doctype: options.doctype,
      fields: options.fields || ['name'],
      filters: filters(),
      or_filters: orFilters(),
      order_by: orderBy.value,
      limit_start: (page.value - 1) * pageLength.value,
      limit_page_length: pageLength.value,
    }),
    onSuccess(data) {
      rows.value = data
      remember(listKey, data)
      if (!data.length && page.value > 1) page.value -= 1
    },
  })

  const count = createResource({
    url: 'frappe.desk.reportview.get_count',
    makeParams: () => ({
      doctype: options.doctype,
      filters: filters(),
      or_filters: orFilters(),
    }),
    onSuccess(data) {
      remember(countKey, data)
    },
  })

  let listKey = ''
  let countKey = ''
  const knownTotal = ref(null)

  function keys() {
    const scope = JSON.stringify([filters(), orFilters()])
    return {
      list: `list:${options.doctype}:${JSON.stringify([scope, orderBy.value, page.value, pageLength.value, options.fields || []])}`,
      count: `count:${options.doctype}:${scope}`,
    }
  }

  function refresh() {
    selection.value = []
    const next = keys()
    listKey = next.list
    countKey = next.count
    const cachedRows = recall(listKey)
    if (cachedRows) rows.value = cachedRows
    knownTotal.value = recall(countKey)
    list.reload()
    count.reload()
  }

  function reload() {
    if (page.value === 1) refresh()
    else page.value = 1
  }

  function patch(name, changes) {
    rows.value = rows.value.map((row) => (row.name === name ? { ...row, ...changes } : row))
  }

  async function remove(names) {
    if (names.length === 1) {
      await call('frappe.client.delete', { doctype: options.doctype, name: names[0] })
    } else {
      await call('frappe.desk.reportview.delete_items', {
        doctype: options.doctype,
        items: JSON.stringify(names),
      })
    }

    refresh()
  }

  const reloadSoon = debounce(reload, 300)

  const filtered = computed(() => filters().length > 0 || Boolean(search.value.trim()))

  function exportRows(scope) {
    const narrow = scope === 'filtered'
    return call('frappe.client.get_list', {
      doctype: options.doctype,
      fields: options.fields || ['name'],
      filters: narrow ? filters() : [],
      or_filters: narrow ? orFilters() : null,
      order_by: orderBy.value,
      limit_page_length: EXPORT_LIMIT,
    })
  }

  function countAll() {
    return call('frappe.desk.reportview.get_count', { doctype: options.doctype })
  }

  const state =
    options.url === false
      ? { restoring: () => false }
      : useQueryState(
          [
            refField('q', search, ''),
            refField('sort', orderBy, options.orderBy || 'modified desc'),
            refField('page', page, 1),
            ...(options.quickFilters || []).map((filter) =>
              field(filter.key, values, filter.key, (options.initialFilters || {})[filter.key] ?? ''),
            ),
          ],
          { size: true },
        )

  function changed() {
    if (state.restoring()) refresh()
    else reload()
  }

  watch(search, () => (state.restoring() ? refresh() : reloadSoon()))
  watch([values, orderBy], changed, { deep: true })
  watch(page, refresh)
  watch(pageLength, changed)
  if (options.filters && typeof options.filters !== 'object') watch(options.filters, reload, { deep: true })

  if (options.auto !== false) refresh()

  return {
    doctype: options.doctype,
    search,
    values,
    orderBy,
    selection,
    rows,
    page,
    loading: computed(() => list.loading),
    error: computed(() => list.error),
    total: computed(() => (count.loading ? null : count.data) ?? knownTotal.value ?? count.data ?? null),
    filtered,
    exportRows,
    countAll,
    quickFilters: options.quickFilters || [],
    sortOptions: options.sortOptions || [],
    reload,
    refresh,
    patch,
    remove,
  }
}
