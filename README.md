# Node Dash Ingest Service

## Overview

This service handles the ingestion of device data for the device management platform and processes any related flows.

## Features

- Fast and efficient data ingestion via REST API
- Flow-based data processing engine
- Function and integration processors for customizable data handling
- Robust authentication with API key validation
- Health check endpoint for monitoring

## Project Structure

```
app/
├── api/             # API routes and endpoints
├── core/            # Core functionality (auth, config)
├── crud/            # Database CRUD operations
├── db/              # Database connection and session management
├── models/          # SQLAlchemy ORM models
├── redis/           # Redis client configuration
├── schemas/         # Pydantic schemas for data validation
└── services/        # Business logic services
    ├── flow_processor/    # Flow processing engine
    └── integrations/      # External service integrations
```

## Prerequisites

- Python 3.11 or higher
- PostgreSQL database
- Redis (for setting the device status)

## Installation

### Using a Virtual Environment

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd device-manager-ingest
   ```

2. Create a virtual environment:

   ```bash
   python -m venv venv
   ```

3. Activate the virtual environment:

   ```bash
   # On macOS/Linux
   source venv/bin/activate

   # On Windows
   venv\Scripts\activate
   ```

4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

Start the FastAPI application:

```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000

## API Documentation

Once the application is running, you can access:

- Interactive API documentation: http://localhost:8000/docs
- Alternative API documentation: http://localhost:8000/redoc

## Key Components

### Ingest

The service handles device ingest and then calls any flows this device is part of to be run.

### Flow Processing Engine

A flexible flow-based processing engine that applies user-defined functions and integrations to process incoming device data.

### Integrations

Built-in support for various integration types:

- HTTP clients for REST API communication
- MQTT clients for message broker communication

## Troubleshooting

### Database Connection Issues

- Verify PostgreSQL is running: `pg_isready`
- Check database URL configuration
- Ensure database user has proper permissions

### Redis Connection Issues

- Verify Redis is running: `redis-cli ping`
- Check Redis URL configuration

## License

See the [LICENSE](LICENSE) file for details.
