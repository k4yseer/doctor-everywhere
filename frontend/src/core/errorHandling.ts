import { AxiosError } from 'axios'

export const handleApiError = (error: unknown) => {
    if (error instanceof AxiosError) { // check if error is from axios
        const status = error.response?.status;
        const message = error.response?.data?.message || error.message;

        switch (status) {
            case 400:
              console.error('Bad Request: Please check your input.');
              break;
            case 401:
              console.error('Session expired or unauthorised. Redirecting to login.');
              // TODO: trigger logout action or router push to login
              break;
            case 403:
              console.error('Forbidden: You do not have permission to access this.');
              break;
            case 404:
              console.error('Resource not found.');
              break;
            case 500:
              console.error('Internal Server Error: Something went wrong on the microservice.');
              break;
            default:
              console.error(`Unhandled API Error [${status}]: ${message}`);
          }

          // TODO: add primevue toast to show global error notifs

          return Promise.reject(error);
    }
    
    // if error is non-HTTP
    console.error('Unexpected error:', error);
    return Promise.reject(error);
}