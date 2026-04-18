import http from './http'

export async function login(payload) {
  const { data } = await http.post('/login', payload)
  return data
}

export async function logout() {
  const { data } = await http.post('/logout')
  return data
}

export async function getMe() {
  const { data } = await http.get('/me')
  return data
}
