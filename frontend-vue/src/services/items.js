import http from './http'

export async function getMeta() {
  const { data } = await http.get('/meta')
  return data
}

export async function getItems(params) {
  const { data } = await http.get('/items', { params })
  return data.items || []
}

export async function createItem(payload) {
  const { data } = await http.post('/items', payload)
  return data
}

export async function updateItem(id, payload) {
  const { data } = await http.put(`/items/${id}`, payload)
  return data
}

export async function deleteItem(id) {
  const { data } = await http.delete(`/items/${id}`)
  return data
}

export async function cloneItem(id) {
  const { data } = await http.post(`/items/${id}/clone`)
  return data
}

export async function bulkCreateItems(payload) {
  const { data } = await http.post('/items/bulk', payload)
  return data
}

export async function bulkSellItems(payload) {
  const { data } = await http.post('/items/bulk-sell', payload)
  return data
}

export async function inlineUpdateItem(id, payload) {
  const { data } = await http.patch(`/items/${id}/inline`, payload)
  return data
}

export async function getItemTrades(id) {
  const { data } = await http.get(`/items/${id}/trades`)
  return data.trades || []
}

export async function getDashboard() {
  const { data } = await http.get('/dashboard')
  return data
}

export async function recalculateAll() {
  const { data } = await http.post('/items/recalculate')
  return data
}

export async function getAuditLogs(limit = 200) {
  const { data } = await http.get('/audit-logs', { params: { limit } })
  return data.logs || []
}

export async function refreshPrices(itemIds = null) {
  const body = itemIds ? { item_ids: itemIds } : {}
  const { data } = await http.post('/prices/refresh', body)
  return data
}

export async function refreshPriceForItem(id) {
  const { data } = await http.post(`/items/${id}/refresh-price`)
  return data
}

export async function getPricesConfig() {
  const { data } = await http.get('/prices/config')
  return data
}

export function buildExportUrl(params = {}) {
  const usp = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      usp.append(key, value)
    }
  })
  const query = usp.toString()
  return query ? `/api/items/export?${query}` : '/api/items/export'
}
