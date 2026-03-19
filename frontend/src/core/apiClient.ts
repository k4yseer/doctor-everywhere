import axios from 'axios'

// connect to api gateway
const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_GATEWAY_URL,
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
    (error) => {
        return Promise.reject(error);
    }
);

// axios response interceptor
apiClient.interceptors.response.use(
    (response) => { // if succeed
        return response; // pass data
    },
    (error) => {
        if (error.response && error.response.status === 401) { // if unauthorised
            console.log("Unauthorised access. Token may have expired.")
            // TODO: trigger silent token refresh or redirect to /login route here
        }
        return Promise.reject(error);
    }
);

export default apiClient;