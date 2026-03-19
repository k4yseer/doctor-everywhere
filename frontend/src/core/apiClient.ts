import axios from 'axios'

// connect to api gateway
const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_GATEWAY_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 10000, // drop request if BE hangs after 10 sec
})