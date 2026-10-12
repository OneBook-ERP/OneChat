function cell(value) {
  const text = value === null || value === undefined ? '' : String(value)

  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

export function downloadCsv(filename, columns, rows) {
  const lines = [columns.map((column) => cell(column.label)).join(',')]

  for (const row of rows) {
    lines.push(columns.map((column) => cell(row[column.key])).join(','))
  }

  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename.endsWith('.csv') ? filename : `${filename}.csv`
  link.click()
  URL.revokeObjectURL(url)
}
