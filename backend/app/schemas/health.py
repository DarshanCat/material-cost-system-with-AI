from datetime import datetime
from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    connected: bool
    status: str
    message: str


class HealthResponse(BaseModel):
    status: str = Field(..., description="Application operational status: 'healthy' or 'degraded'")
    app_name: str
    environment: str
    version: str = "0.1.0"
    costing_start_date: str
    database: DatabaseHealth
    timestamp: datetime
