import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  withCredentials: true,
  timeout: 10000,
})

export default http
