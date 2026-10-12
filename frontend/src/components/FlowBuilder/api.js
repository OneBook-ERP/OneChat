import { call } from 'frappe-ui'

const fieldCache = new Map()
const templateCache = new Map()

export function doctypeFields(doctype) {
  if (!doctype) return Promise.resolve([])
  if (!fieldCache.has(doctype)) {
    const request = call('onechat.automation.flow_helpers.get_doctype_fields', { doctype }).catch((error) => {
      fieldCache.delete(doctype)
      throw error
    })
    fieldCache.set(doctype, request)
  }

  return fieldCache.get(doctype)
}

export function templateDetails(name) {
  if (!name) return Promise.resolve(null)
  if (!templateCache.has(name)) {
    const request = call('frappe.client.get', { doctype: 'WhatsApp Templates', name }).catch((error) => {
      templateCache.delete(name)
      throw error
    })
    templateCache.set(name, request)
  }

  return templateCache.get(name)
}

export function placeholderCount(text) {
  const matches = String(text || '').match(/\{\{\s*(\d+)\s*\}\}/g) || []

  return matches.reduce((max, match) => Math.max(max, Number(match.replace(/\D/g, ''))), 0)
}

export const NO_VALUE_TYPES = [
  'Section Break',
  'Column Break',
  'Tab Break',
  'HTML',
  'Button',
  'Image',
  'Fold',
  'Heading',
  'Table',
  'Table MultiSelect',
]

export function formatDuration(seconds) {
  const value = Number(seconds)
  if (!value) return ''
  if (value < 1) return `${Math.round(value * 1000)} ms`
  if (value < 60) return `${value.toFixed(1)} s`

  return `${Math.floor(value / 60)} m ${Math.round(value % 60)} s`
}
