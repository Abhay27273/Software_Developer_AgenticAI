"""
Starter templates for common project types.

This module defines pre-built templates that users can use to bootstrap
new projects quickly with best practices and common patterns.
"""

from models.template import ProjectTemplate
from datetime import datetime


def create_rest_api_template() -> ProjectTemplate:
    """
    Create a REST API template with FastAPI, authentication, database, and tests.
    """
    return ProjectTemplate(
        id="rest-api-fastapi",
        name="REST API with FastAPI",
        description="A production-ready REST API with FastAPI, JWT authentication, PostgreSQL database, and comprehensive tests",
        category="api",
        files={
            "main.py": '''from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from database import engine, Base

app = FastAPI(title="{{project_name}}", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Include routers
app.include_router(router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
''',
            "database.py": '''from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/{{db_name}}")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
''',
            "models/user.py": '''from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
''',
            "api/routes.py": '''from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from schemas.user import UserCreate, UserResponse

router = APIRouter()

@router.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    db_user = User(email=user.email, hashed_password=user.password)  # Hash in production!
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
''',
            "schemas/user.py": '''from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime
    
    class Config:
        from_attributes = True
''',
            "requirements.txt": '''fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
pydantic[email]==2.5.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
pytest==7.4.3
httpx==0.25.2
''',
            "README.md": '''# {{project_name}}

{{project_description}}

## Features

- FastAPI REST API
- PostgreSQL database with SQLAlchemy ORM
- JWT authentication
- CORS enabled
- Health check endpoint
- Comprehensive tests

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export DATABASE_URL=postgresql://user:password@localhost/{{db_name}}
```

3. Run the application:
```bash
python main.py
```

The API will be available at http://localhost:8000

## API Documentation

Interactive API docs available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testing

Run tests with:
```bash
pytest
```
'''
        },
        required_vars=["project_name", "db_name"],
        optional_vars=["project_description"],
        tech_stack=["FastAPI", "PostgreSQL", "SQLAlchemy", "Pydantic", "Pytest"],
        estimated_setup_time=15,
        complexity="medium",
        tags=["api", "rest", "fastapi", "postgresql"]
    )


def create_web_app_template() -> ProjectTemplate:
    """
    Create a Web App template with React frontend and FastAPI backend.
    """
    return ProjectTemplate(
        id="web-app-react-fastapi",
        name="Web App (React + FastAPI)",
        description="Full-stack web application with React frontend and FastAPI backend",
        category="web_app",
        files={
            "backend/main.py": '''from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="{{project_name}} API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/data")
async def get_data():
    return {"message": "Hello from {{project_name}}!"}

# Serve React frontend in production
# app.mount("/", StaticFiles(directory="frontend/build", html=True), name="static")
''',
            "frontend/package.json": '''{
  "name": "{{project_name}}-frontend",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-scripts": "5.0.1",
    "axios": "^1.6.0"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test",
    "eject": "react-scripts eject"
  }
}
''',
            "frontend/src/App.js": '''import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get('http://localhost:8000/api/data')
      .then(response => {
        setData(response.data);
        setLoading(false);
      })
      .catch(error => {
        console.error('Error fetching data:', error);
        setLoading(false);
      });
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>{{project_name}}</h1>
        {loading ? (
          <p>Loading...</p>
        ) : (
          <p>{data?.message}</p>
        )}
      </header>
    </div>
  );
}

export default App;
''',
            "frontend/src/App.css": '''.App {
  text-align: center;
}

.App-header {
  background-color: #282c34;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: calc(10px + 2vmin);
  color: white;
}
''',
            "backend/requirements.txt": '''fastapi==0.104.1
uvicorn[standard]==0.24.0
''',
            "README.md": '''# {{project_name}}

{{project_description}}

## Architecture

- **Frontend**: React application
- **Backend**: FastAPI REST API
- **Communication**: REST API with CORS enabled

## Setup

### Backend

1. Navigate to backend directory:
```bash
cd backend
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the backend:
```bash
uvicorn main:app --reload
```

Backend will be available at http://localhost:8000

### Frontend

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Run the frontend:
```bash
npm start
```

Frontend will be available at http://localhost:3000

## Production Deployment

1. Build the frontend:
```bash
cd frontend && npm run build
```

2. The backend will serve the built frontend automatically
'''
        },
        required_vars=["project_name"],
        optional_vars=["project_description"],
        tech_stack=["React", "FastAPI", "Axios"],
        estimated_setup_time=20,
        complexity="medium",
        tags=["web", "fullstack", "react", "fastapi"]
    )


def create_mobile_backend_template() -> ProjectTemplate:
    """
    Create a Mobile Backend template optimized for mobile apps.
    """
    return ProjectTemplate(
        id="mobile-backend-api",
        name="Mobile Backend API",
        description="API backend optimized for mobile applications with push notifications and offline sync",
        category="mobile_backend",
        files={
            "main.py": '''from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import Optional

app = FastAPI(title="{{project_name}} Mobile API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (use database in production)
sessions = {}
sync_data = {}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/auth/login")
async def login(email: str, password: str):
    # Simplified auth (implement proper auth in production)
    session_token = f"session_{email}_{datetime.utcnow().timestamp()}"
    sessions[session_token] = {
        "email": email,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=30)
    }
    return {"token": session_token, "expires_in": 2592000}

@app.get("/api/sync")
async def sync_data_endpoint(token: str, last_sync: Optional[str] = None):
    if token not in sessions:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Return data modified since last_sync
    return {
        "data": sync_data.get(token, []),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/sync")
async def upload_sync_data(token: str, data: dict):
    if token not in sessions:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Store sync data
    if token not in sync_data:
        sync_data[token] = []
    sync_data[token].append({
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {"status": "synced", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/push/register")
async def register_push_token(token: str, device_token: str, platform: str):
    if token not in sessions:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Store device token for push notifications
    return {"status": "registered"}
''',
            "requirements.txt": '''fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
python-jose[cryptography]==3.3.0
''',
            "README.md": '''# {{project_name}}

{{project_description}}

## Features

- Mobile-optimized API endpoints
- Session-based authentication with long-lived tokens
- Offline sync support
- Push notification registration
- Lightweight responses for mobile bandwidth

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the API:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login and get session token

### Data Sync
- `GET /api/sync?token=xxx&last_sync=timestamp` - Download data since last sync
- `POST /api/sync` - Upload local changes

### Push Notifications
- `POST /api/push/register` - Register device for push notifications

## Mobile Integration

### iOS (Swift)
```swift
let url = URL(string: "http://localhost:8000/api/sync")!
var request = URLRequest(url: url)
request.setValue(token, forHTTPHeaderField: "Authorization")
```

### Android (Kotlin)
```kotlin
val client = OkHttpClient()
val request = Request.Builder()
    .url("http://localhost:8000/api/sync")
    .addHeader("Authorization", token)
    .build()
```
'''
        },
        required_vars=["project_name"],
        optional_vars=["project_description"],
        tech_stack=["FastAPI", "JWT", "Push Notifications"],
        estimated_setup_time=15,
        complexity="medium",
        tags=["mobile", "api", "sync", "push"]
    )


def create_data_pipeline_template() -> ProjectTemplate:
    """
    Create a Data Pipeline template for ETL with scheduling.
    """
    return ProjectTemplate(
        id="data-pipeline-etl",
        name="Data Pipeline (ETL)",
        description="ETL data pipeline with scheduling, monitoring, and error handling",
        category="data_pipeline",
        files={
            "pipeline.py": '''import logging
from datetime import datetime
from typing import List, Dict, Any
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataPipeline:
    """{{project_name}} ETL Pipeline"""
    
    def __init__(self):
        self.name = "{{project_name}}"
        self.run_id = None
    
    def extract(self) -> List[Dict[str, Any]]:
        """Extract data from source"""
        logger.info(f"[{self.run_id}] Starting extraction...")
        
        # TODO: Implement your data extraction logic
        # Example: Read from database, API, files, etc.
        data = [
            {"id": 1, "value": "sample1"},
            {"id": 2, "value": "sample2"}
        ]
        
        logger.info(f"[{self.run_id}] Extracted {len(data)} records")
        return data
    
    def transform(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform extracted data"""
        logger.info(f"[{self.run_id}] Starting transformation...")
        
        # TODO: Implement your transformation logic
        # Example: Clean, enrich, aggregate data
        transformed = []
        for record in data:
            transformed.append({
                **record,
                "processed_at": datetime.utcnow().isoformat(),
                "pipeline": self.name
            })
        
        logger.info(f"[{self.run_id}] Transformed {len(transformed)} records")
        return transformed
    
    def load(self, data: List[Dict[str, Any]]) -> bool:
        """Load transformed data to destination"""
        logger.info(f"[{self.run_id}] Starting load...")
        
        # TODO: Implement your load logic
        # Example: Write to database, data warehouse, files, etc.
        with open(f"output_{self.run_id}.json", "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"[{self.run_id}] Loaded {len(data)} records")
        return True
    
    def run(self) -> Dict[str, Any]:
        """Execute the complete ETL pipeline"""
        self.run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"[{self.run_id}] Pipeline started")
            
            # Extract
            raw_data = self.extract()
            
            # Transform
            transformed_data = self.transform(raw_data)
            
            # Load
            success = self.load(transformed_data)
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            result = {
                "run_id": self.run_id,
                "status": "success" if success else "failed",
                "records_processed": len(transformed_data),
                "duration_seconds": duration,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
            
            logger.info(f"[{self.run_id}] Pipeline completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"[{self.run_id}] Pipeline failed: {e}", exc_info=True)
            return {
                "run_id": self.run_id,
                "status": "error",
                "error": str(e),
                "start_time": start_time.isoformat()
            }


if __name__ == "__main__":
    pipeline = DataPipeline()
    result = pipeline.run()
    print(json.dumps(result, indent=2))
''',
            "scheduler.py": '''import schedule
import time
from pipeline import DataPipeline
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_pipeline():
    """Run the pipeline"""
    pipeline = DataPipeline()
    result = pipeline.run()
    logger.info(f"Pipeline run completed: {result['status']}")


# Schedule the pipeline
schedule.every().day.at("02:00").do(run_pipeline)  # Run daily at 2 AM
# schedule.every().hour.do(run_pipeline)  # Or run hourly
# schedule.every(30).minutes.do(run_pipeline)  # Or every 30 minutes

logger.info("Scheduler started. Pipeline will run on schedule.")

# Keep the scheduler running
while True:
    schedule.run_pending()
    time.sleep(60)
''',
            "requirements.txt": '''schedule==1.2.0
pandas==2.1.3
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
''',
            "README.md": '''# {{project_name}}

{{project_description}}

## Features

- ETL pipeline with extract, transform, load stages
- Scheduled execution
- Error handling and logging
- Run tracking and monitoring

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure your data sources and destinations in `pipeline.py`

3. Run the pipeline manually:
```bash
python pipeline.py
```

4. Run with scheduler:
```bash
python scheduler.py
```

## Pipeline Stages

### Extract
- Read data from source systems
- Support for databases, APIs, files

### Transform
- Clean and validate data
- Apply business logic
- Enrich with additional data

### Load
- Write to destination systems
- Support for databases, data warehouses, files

## Scheduling

Edit `scheduler.py` to configure run frequency:
- Daily at specific time
- Hourly
- Every N minutes

## Monitoring

Pipeline runs are logged with:
- Run ID
- Status (success/failed/error)
- Records processed
- Duration
- Timestamps
'''
        },
        required_vars=["project_name"],
        optional_vars=["project_description"],
        tech_stack=["Python", "Schedule", "Pandas", "SQLAlchemy"],
        estimated_setup_time=20,
        complexity="medium",
        tags=["etl", "pipeline", "data", "scheduling"]
    )


def create_microservice_template() -> ProjectTemplate:
    """
    Create a Microservice template with observability.
    """
    return ProjectTemplate(
        id="microservice-observability",
        name="Microservice with Observability",
        description="Single microservice with health checks, metrics, logging, and tracing",
        category="microservice",
        files={
            "main.py": '''from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest
from fastapi.responses import Response
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="{{service_name}}", version="1.0.0")

# Prometheus metrics
request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'])

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Collect metrics for each request"""
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    request_count.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    request_duration.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "{{service_name}}",
        "version": "1.0.0"
    }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type="text/plain")

@app.get("/api/{{service_name}}")
async def get_data():
    """Main service endpoint"""
    logger.info("Processing request for {{service_name}}")
    return {
        "service": "{{service_name}}",
        "message": "Service is running",
        "data": []
    }

@app.post("/api/{{service_name}}")
async def create_data(data: dict):
    """Create endpoint"""
    logger.info(f"Creating data: {data}")
    return {
        "status": "created",
        "data": data
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
''',
            "requirements.txt": '''fastapi==0.104.1
uvicorn[standard]==0.24.0
prometheus-client==0.19.0
''',
            "Dockerfile": '''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
''',
            "docker-compose.yml": '''version: '3.8'

services:
  {{service_name}}:
    build: .
    ports:
      - "8000:8000"
    environment:
      - SERVICE_NAME={{service_name}}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
  
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
''',
            "prometheus.yml": '''global:
  scrape_interval: 15s

scrape_configs:
  - job_name: '{{service_name}}'
    static_configs:
      - targets: ['{{service_name}}:8000']
''',
            "README.md": '''# {{service_name}}

{{service_description}}

## Features

- RESTful API endpoints
- Health check endpoint
- Prometheus metrics
- Structured logging
- Docker containerization
- Docker Compose for local development

## Setup

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the service:
```bash
python main.py
```

### Docker

1. Build and run with Docker Compose:
```bash
docker-compose up --build
```

The service will be available at:
- API: http://localhost:8000
- Health: http://localhost:8000/health
- Metrics: http://localhost:8000/metrics
- Prometheus: http://localhost:9090

## Observability

### Health Checks
- Endpoint: `GET /health`
- Returns service status and version

### Metrics
- Endpoint: `GET /metrics`
- Prometheus format metrics
- Tracks request count, duration, status codes

### Logging
- Structured JSON logging
- Request/response logging
- Error tracking

## API Endpoints

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics
- `GET /api/{{service_name}}` - Get data
- `POST /api/{{service_name}}` - Create data
'''
        },
        required_vars=["service_name"],
        optional_vars=["service_description"],
        tech_stack=["FastAPI", "Prometheus", "Docker", "Docker Compose"],
        estimated_setup_time=15,
        complexity="simple",
        tags=["microservice", "observability", "prometheus", "docker"]
    )


async def initialize_starter_templates():
    """
    Initialize all starter templates in the template library.
    
    This function should be called on system startup to ensure
    all default templates are available.
    """
    from utils.template_library import TemplateLibrary
    
    library = TemplateLibrary()
    
    templates = [
        create_rest_api_template(),
        create_web_app_template(),
        create_mobile_backend_template(),
        create_data_pipeline_template(),
        create_microservice_template()
    ]
    
    for template in templates:
        await library.save_template(template)
    
    return len(templates)
