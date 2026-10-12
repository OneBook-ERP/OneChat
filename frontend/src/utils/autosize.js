const SKIP = '[data-fixed-size]'
const native = typeof CSS !== 'undefined' && CSS.supports?.('field-sizing', 'content')

function fit(element) {
  if (!(element instanceof HTMLTextAreaElement) || element.closest(SKIP)) return
  element.style.height = 'auto'
  element.style.height = `${element.scrollHeight + element.offsetHeight - element.clientHeight}px`
}

function fitAll(root) {
  if (root instanceof HTMLTextAreaElement) fit(root)
  root.querySelectorAll?.('textarea').forEach(fit)
}

export function autosizeTextareas() {
  if (native || typeof document === 'undefined') return

  document.addEventListener('input', (event) => fit(event.target), true)
  document.addEventListener('focusin', (event) => fit(event.target), true)
  new MutationObserver((changes) => {
    for (const change of changes) change.addedNodes.forEach((node) => requestAnimationFrame(() => fitAll(node)))
  }).observe(document.body, { childList: true, subtree: true })
}
