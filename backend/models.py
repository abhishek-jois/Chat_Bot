"""
Data Models for Drone Operations Coordinator
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
from enum import Enum


class PilotStatus(str, Enum):
    AVAILABLE = "Available"
    ASSIGNED = "Assigned"
    ON_LEAVE = "On Leave"
    UNAVAILABLE = "Unavailable"


class DroneStatus(str, Enum):
    AVAILABLE = "Available"
    DEPLOYED = "Deployed"
    MAINTENANCE = "Maintenance"


class MissionPriority(str, Enum):
    URGENT = "Urgent"
    HIGH = "High"
    STANDARD = "Standard"


class WeatherCondition(str, Enum):
    SUNNY = "Sunny"
    CLOUDY = "Cloudy"
    RAINY = "Rainy"


class Pilot(BaseModel):
    pilot_id: str
    name: str
    skills: List[str]
    certifications: List[str]
    location: str
    status: PilotStatus
    current_assignment: Optional[str] = None
    available_from: date
    daily_rate_inr: int

    @classmethod
    def from_csv_row(cls, row: dict) -> "Pilot":
        skills = [s.strip() for s in row["skills"].split(",")]
        certifications = [c.strip() for c in row["certifications"].split(",")]
        assignment = row["current_assignment"] if row["current_assignment"] != "-" else None
        
        return cls(
            pilot_id=row["pilot_id"],
            name=row["name"],
            skills=skills,
            certifications=certifications,
            location=row["location"],
            status=PilotStatus(row["status"]),
            current_assignment=assignment,
            available_from=date.fromisoformat(row["available_from"]),
            daily_rate_inr=int(row["daily_rate_inr"])
        )

    def to_csv_row(self) -> dict:
        return {
            "pilot_id": self.pilot_id,
            "name": self.name,
            "skills": ", ".join(self.skills),
            "certifications": ", ".join(self.certifications),
            "location": self.location,
            "status": self.status.value,
            "current_assignment": self.current_assignment or "-",
            "available_from": self.available_from.isoformat(),
            "daily_rate_inr": str(self.daily_rate_inr)
        }


class Drone(BaseModel):
    drone_id: str
    model: str
    capabilities: List[str]
    status: DroneStatus
    location: str
    current_assignment: Optional[str] = None
    maintenance_due: date
    weather_resistance: str

    @classmethod
    def from_csv_row(cls, row: dict) -> "Drone":
        capabilities = [c.strip() for c in row["capabilities"].split(",")]
        assignment = row["current_assignment"] if row["current_assignment"] != "-" else None
        
        return cls(
            drone_id=row["drone_id"],
            model=row["model"],
            capabilities=capabilities,
            status=DroneStatus(row["status"]),
            location=row["location"],
            current_assignment=assignment,
            maintenance_due=date.fromisoformat(row["maintenance_due"]),
            weather_resistance=row["weather_resistance"]
        )

    def to_csv_row(self) -> dict:
        return {
            "drone_id": self.drone_id,
            "model": self.model,
            "capabilities": ", ".join(self.capabilities),
            "status": self.status.value,
            "location": self.location,
            "current_assignment": self.current_assignment or "-",
            "maintenance_due": self.maintenance_due.isoformat(),
            "weather_resistance": self.weather_resistance
        }

    def can_fly_in_weather(self, weather: str) -> bool:
        """Check if drone can fly in given weather condition"""
        weather_lower = weather.lower()
        if weather_lower == "rainy":
            return "IP43" in self.weather_resistance or "Rain" in self.weather_resistance
        return True  # Can fly in Sunny or Cloudy


class Mission(BaseModel):
    project_id: str
    client: str
    location: str
    required_skills: List[str]
    required_certs: List[str]
    start_date: date
    end_date: date
    priority: MissionPriority
    mission_budget_inr: int
    weather_forecast: str
    assigned_pilot: Optional[str] = None
    assigned_drone: Optional[str] = None

    @classmethod
    def from_csv_row(cls, row: dict) -> "Mission":
        required_skills = [s.strip() for s in row["required_skills"].split(",")]
        required_certs = [c.strip() for c in row["required_certs"].split(",")]
        
        return cls(
            project_id=row["project_id"],
            client=row["client"],
            location=row["location"],
            required_skills=required_skills,
            required_certs=required_certs,
            start_date=date.fromisoformat(row["start_date"]),
            end_date=date.fromisoformat(row["end_date"]),
            priority=MissionPriority(row["priority"]),
            mission_budget_inr=int(row["mission_budget_inr"]),
            weather_forecast=row["weather_forecast"],
            assigned_pilot=row.get("assigned_pilot"),
            assigned_drone=row.get("assigned_drone")
        )

    def to_csv_row(self) -> dict:
        return {
            "project_id": self.project_id,
            "client": self.client,
            "location": self.location,
            "required_skills": ", ".join(self.required_skills),
            "required_certs": ", ".join(self.required_certs),
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "priority": self.priority.value,
            "mission_budget_inr": str(self.mission_budget_inr),
            "weather_forecast": self.weather_forecast,
            "assigned_pilot": self.assigned_pilot or "",
            "assigned_drone": self.assigned_drone or ""
        }

    def get_duration_days(self) -> int:
        """Calculate mission duration in days"""
        return (self.end_date - self.start_date).days + 1


# API Request/Response Models
class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    actions_taken: Optional[List[str]] = None


class PilotStatusUpdate(BaseModel):
    pilot_id: str
    new_status: PilotStatus


class DroneStatusUpdate(BaseModel):
    drone_id: str
    new_status: DroneStatus


class AssignmentRequest(BaseModel):
    mission_id: str
    pilot_id: Optional[str] = None
    drone_id: Optional[str] = None


class ConflictWarning(BaseModel):
    type: str
    severity: str  # "error", "warning", "info"
    message: str
    affected_entities: List[str]


class ReassignmentRequest(BaseModel):
    mission_id: str
    reason: str
    urgency: str = "normal"  # "urgent", "normal"
