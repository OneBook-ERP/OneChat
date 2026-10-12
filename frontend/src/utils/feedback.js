import { toast } from 'frappe-ui'
import { translate as __ } from '@/translation'

const FEEDBACK = {}

function method(options) {
  return String(options?.url || '').replace(/^\/api\/method\//, '')
}

function plain(text) {
  return String(text || '')
    .replace(/<[^>]*>/g, '')
    .trim()
}

export function withFeedback(fetcher) {
  return async (options) => {
    const rule = FEEDBACK[method(options)]
    if (!rule) return fetcher(options)

    const params = options.params || {}

    try {
      const data = await fetcher(options)
      const message = typeof rule.done === 'function' ? rule.done(params, data) : rule.done
      if (message) toast.success(__(message))
      return data
    } catch (error) {
      if (!rule.inline) {
        toast.error(plain(error?.messages?.[0] || error?.message) || __('Something went wrong. Please try again.'))
      }
      throw error
    }
  }
}
