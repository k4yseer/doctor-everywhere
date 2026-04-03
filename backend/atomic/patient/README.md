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

   This will start the patient service on port 5003 and the MySQL database on port 3306.

3. The application will be accessible at `http://localhost:5003`.

## Accessing API Documentation

Access the Swagger documentation and test the endpoints at

`http://localhost:5003/apidocs`

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

## API Endpoints

### `POST /patient/check-allergies`

Check a patient's allergies against a list of prescribed drugs.

**Request body:**
```json
{ "patient_id": 1, "prescription": ["Aspirin", "Ibuprofen"] }
```

**Response `200` — no allergies:**
```json
{ "code": 200, "data": { "check": "PASSED" } }
```

**Response `200` — allergies found:**
```json
{ "code": 200, "data": { "check": "FAILED", "allergic_drugs": ["Aspirin"] } }
```

**Response `404`:** Patient not found.

---

### `GET /patient/<patient_id>/details`

Retrieve full details for a single patient.

**Response `200`:**
```json
{ "code": 200, "data": { "patient_id": 1, "patient_name": "Jane Doe", "email": "jane@example.com" } }
```

**Response `404`:** Patient not found.

---

### `GET /patients/<patient_id>/allergies`

Retrieve all allergy records for a patient.

**Response `200`:**
```json
{ "code": 200, "data": [{ "allergy": "Penicillin" }, { "allergy": "Aspirin" }] }
```

**Response `404`:** Patient not found.
