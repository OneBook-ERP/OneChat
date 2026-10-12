import { ref, watch } from 'vue'

const STORAGE_KEY = 'onechat-page-length'

export const PAGE_SIZES = [20, 50, 100]
export const DEFAULT_PAGE_LENGTH = 20

function stored() {
  try {
    const value = Number(localStorage.getItem(STORAGE_KEY))
    return PAGE_SIZES.includes(value) ? value : DEFAULT_PAGE_LENGTH
  } catch {
    return DEFAULT_PAGE_LENGTH
  }
}

export const pageLength = ref(stored())

watch(pageLength, (value) => {
  try {
    localStorage.setItem(STORAGE_KEY, String(value))
  } catch {
    return
  }
})

export function pageOf(rows, page) {
  return rows.slice((page - 1) * pageLength.value, page * pageLength.value)
}
