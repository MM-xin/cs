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

export async function inlineUpdateItem(id, payload) {
  const { data } = await http.patch(`/items/${id}/inline`, payload)
  return data
}
