import http from './http'

export async function searchCatalog({ q = '', page = 1, size = 20 } = {}) {
  const { data } = await http.get('/catalog/search', {
    params: { q, page, size },
  })
  return data
}

export async function getCatalogStats() {
  const { data } = await http.get('/catalog/stats')
  return data
}

export async function syncCatalog() {
  const { data } = await http.post('/catalog/sync')
  return data
}
