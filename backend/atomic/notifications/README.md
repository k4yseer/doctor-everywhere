# Notification Microservice

## Running the Application

1. Ensure you have a `.env` file configured with the following environment variables:
  ```
  RESEND_API_KEY=your_api_key
  DOMAIN_NAME=your_domain_name
  ```

2. Build and start the services using Docker Compose:
   ```bash
   docker compose up --build
   ```

   This will start the notification service on port 5000.

3. The application will be accessible at `http://localhost:5000`.

## Accessing API Documentation

Access and Swagger documentation and test the endpoints at

`http://localhost:5000/apidocs`