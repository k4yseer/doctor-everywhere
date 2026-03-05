# Patient Microservice

## Running the Application

1. Ensure you have a `.env` file configured with the following environment variables:
  ```
  DB_SERVER=db
  DB_PASSWORD=your_mysql_root_password
  DATABASE=your_database_name
  DB_PORT=3306
  DB_USER=your_db_user
  ```

2. Build and start the services using Docker Compose:
   ```bash
   docker compose up --build
   ```

   This will start the patient service on port 5000 and the MySQL database on port 3306.

3. The application will be accessible at `http://localhost:5000`.

## Accessing API Documentation

Access and Swagger documentation and test the endpoints at

`http://localhost:5000/apidocs`

## Seeding the Database

To populate the database with sample data, run the seed command inside the running container:

1. First, find the container ID or name:
   ```bash
   docker ps
   ```

2. Execute the seed command in the patient-service container:
   ```bash
   docker exec -it <container_name_or_id> flask seed
   ```

   Replace `<container_name_or_id>` with the actual container name (e.g., `patient-patient-service-1`).

This will insert dummy patient records and allergies into the database.