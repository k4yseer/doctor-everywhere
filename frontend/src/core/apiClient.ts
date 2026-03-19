import axios from 'axios'
import { handleApiError } from './errorHandling'

// connect to api gateway
const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_GATEWAY_URL || 'http://localhost:8080/api',
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 10000, // drop request if BE hangs after 10 sec
})

// axios request interceptor
apiClient.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('accessToken') // get auth token

        if (token && config.headers) { // if token exists
            config.headers.Authorization = `Bearer ${token}` // add token to auth header
        }

        return config;
    },
    (error) => handleApiError(error)
);

// axios response interceptor
apiClient.interceptors.response.use(
    (response) => response, // if succeed, pass data
    (error) => handleApiError(error)
);

export default apiClient;