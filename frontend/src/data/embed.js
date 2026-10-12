function framedByDesk() {
  try {
    if (window.self === window.top) return false

    const parent = window.parent
    return !!parent.frappe && parent.location.pathname.startsWith('/app')
  } catch {
    return false
  }
}

export const embedded = framedByDesk()
