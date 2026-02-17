"""
FastAPI Backend for Drone Operations Coordinator AI Agent
"""
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv

from models import (
    ChatMessage, ChatResponse, PilotStatusUpdate, DroneStatusUpdate,
    AssignmentRequest, ConflictWarning
)
from data_manager import DataManager
from conflict_detector import ConflictDetector
from agent import DroneOperationsAgent

# Load environment variables
load_dotenv()


# Global instances
data_manager: Optional[DataManager] = None
conflict_detector: Optional[ConflictDetector] = None
agent: Optional[DroneOperationsAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize components on startup"""
    global data_manager, conflict_detector, agent
    
    # Get data directory - use relative path from project root
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_data_dir = os.path.join(base_dir, "data")
    data_dir = os.environ.get("DATA_DIR", default_data_dir)
    if not os.path.isabs(data_dir):
        data_dir = os.path.join(base_dir, data_dir)
    use_google_sheets = os.environ.get("USE_GOOGLE_SHEETS", "false").lower() == "true"
    
    # Initialize data manager
    data_manager = DataManager(data_dir=data_dir, use_google_sheets=use_google_sheets)
    
    # Initialize conflict detector
    conflict_detector = ConflictDetector(data_manager)
    
    # Initialize agent
    openai_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_api_key:
        agent = DroneOperationsAgent(data_manager, openai_api_key)
        print("✅ AI Agent initialized successfully")
    else:
        print("⚠️ OPENAI_API_KEY not set. Chat functionality will be limited.")
    
    print(f"✅ Data Manager initialized (Google Sheets: {use_google_sheets})")
    
    yield
    
    # Cleanup
    print("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Drone Operations Coordinator AI Agent",
    description="AI-powered drone operations management system for Skylark Drones",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ==================== ENDPOINTS ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend"""
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return HTMLResponse("<h1>Drone Operations Coordinator API</h1><p>Frontend not found. Use /docs for API documentation.</p>")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "data_manager": data_manager is not None,
        "agent": agent is not None
    }


# ==================== CHAT ENDPOINT ====================

@app.post("/api/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """
    Main chat endpoint for conversational interaction with the agent.
    Send natural language queries about pilots, drones, missions, and assignments.
    """
    if not agent:
        # Fallback to basic responses if agent not initialized
        return await handle_basic_query(message.message)
    
    try:
        response = agent.chat(message.message)
        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


async def handle_basic_query(query: str) -> ChatResponse:
    """Handle queries when agent is not available"""
    query_lower = query.lower()
    
    if "pilot" in query_lower:
        pilots = data_manager.get_all_pilots()
        response = "📋 Pilots:\n"
        for p in pilots:
            response += f"- {p.name} ({p.pilot_id}): {p.status.value}, {p.location}, Skills: {', '.join(p.skills)}\n"
        return ChatResponse(response=response)
    
    elif "drone" in query_lower:
        drones = data_manager.get_all_drones()
        response = "🚁 Drones:\n"
        for d in drones:
            response += f"- {d.drone_id} ({d.model}): {d.status.value}, {d.location}, Weather: {d.weather_resistance}\n"
        return ChatResponse(response=response)
    
    elif "mission" in query_lower or "project" in query_lower:
        missions = data_manager.get_all_missions()
        response = "📋 Missions:\n"
        for m in missions:
            response += f"- {m.project_id}: {m.client}, {m.location}, {m.priority.value}, {m.start_date} to {m.end_date}\n"
        return ChatResponse(response=response)
    
    elif "summary" in query_lower or "overview" in query_lower:
        summary = data_manager.get_summary()
        response = f"📊 Summary:\n"
        response += f"- Pilots: {summary['total_pilots']} total, {summary['available_pilots']} available\n"
        response += f"- Drones: {summary['total_drones']} total, {summary['available_drones']} available\n"
        response += f"- Missions: {summary['total_missions']} total, {summary['urgent_missions']} urgent\n"
        return ChatResponse(response=response)
    
    return ChatResponse(
        response="I understand you're asking about drone operations. Please set the OPENAI_API_KEY environment variable for full conversational capability. For now, try asking about 'pilots', 'drones', 'missions', or 'summary'."
    )


# ==================== PILOT ENDPOINTS ====================

@app.get("/api/pilots")
async def get_pilots(skill: str = None, certification: str = None, 
                     location: str = None, status: str = None):
    """Get pilots with optional filters"""
    pilots = data_manager.get_all_pilots()
    
    if skill:
        pilots = [p for p in pilots if any(skill.lower() in s.lower() for s in p.skills)]
    if certification:
        pilots = [p for p in pilots if any(certification.lower() in c.lower() for c in p.certifications)]
    if location:
        pilots = [p for p in pilots if location.lower() in p.location.lower()]
    if status:
        pilots = [p for p in pilots if p.status.value.lower() == status.lower()]
    
    return {"pilots": [p.model_dump() for p in pilots]}


@app.get("/api/pilots/{pilot_id}")
async def get_pilot(pilot_id: str):
    """Get a specific pilot by ID"""
    pilot = data_manager.get_pilot_by_id(pilot_id)
    if not pilot:
        raise HTTPException(status_code=404, detail=f"Pilot {pilot_id} not found")
    return pilot.model_dump()


@app.put("/api/pilots/{pilot_id}/status")
async def update_pilot_status(pilot_id: str, update: PilotStatusUpdate):
    """Update pilot status - syncs to Google Sheets"""
    pilot = data_manager.update_pilot_status(pilot_id, update.new_status)
    if not pilot:
        raise HTTPException(status_code=404, detail=f"Pilot {pilot_id} not found")
    return {"message": f"Pilot {pilot_id} status updated to {update.new_status.value}", "pilot": pilot.model_dump()}


@app.get("/api/pilots/{pilot_id}/cost/{mission_id}")
async def calculate_pilot_cost(pilot_id: str, mission_id: str):
    """Calculate pilot cost for a mission"""
    result = data_manager.calculate_pilot_cost(pilot_id, mission_id)
    if not result:
        raise HTTPException(status_code=404, detail="Pilot or mission not found")
    return result


# ==================== DRONE ENDPOINTS ====================

@app.get("/api/drones")
async def get_drones(capability: str = None, location: str = None, 
                     status: str = None, weather: str = None):
    """Get drones with optional filters"""
    drones = data_manager.get_all_drones()
    
    if capability:
        drones = [d for d in drones if any(capability.lower() in c.lower() for c in d.capabilities)]
    if location:
        drones = [d for d in drones if location.lower() in d.location.lower()]
    if status:
        drones = [d for d in drones if d.status.value.lower() == status.lower()]
    if weather:
        drones = [d for d in drones if d.can_fly_in_weather(weather)]
    
    return {"drones": [d.model_dump() for d in drones]}


@app.get("/api/drones/{drone_id}")
async def get_drone(drone_id: str):
    """Get a specific drone by ID"""
    drone = data_manager.get_drone_by_id(drone_id)
    if not drone:
        raise HTTPException(status_code=404, detail=f"Drone {drone_id} not found")
    return drone.model_dump()


@app.put("/api/drones/{drone_id}/status")
async def update_drone_status(drone_id: str, update: DroneStatusUpdate):
    """Update drone status - syncs to Google Sheets"""
    drone = data_manager.update_drone_status(drone_id, update.new_status)
    if not drone:
        raise HTTPException(status_code=404, detail=f"Drone {drone_id} not found")
    return {"message": f"Drone {drone_id} status updated to {update.new_status.value}", "drone": drone.model_dump()}


@app.get("/api/drones/maintenance/upcoming")
async def get_upcoming_maintenance(days: int = 7):
    """Get drones with upcoming maintenance"""
    drones = data_manager.get_drones_needing_maintenance(days)
    return {"drones": [d.model_dump() for d in drones]}


# ==================== MISSION ENDPOINTS ====================

@app.get("/api/missions")
async def get_missions(priority: str = None, location: str = None):
    """Get missions with optional filters"""
    missions = data_manager.get_all_missions()
    
    if priority:
        missions = [m for m in missions if m.priority.value.lower() == priority.lower()]
    if location:
        missions = [m for m in missions if location.lower() in m.location.lower()]
    
    return {"missions": [m.model_dump() for m in missions]}


@app.get("/api/missions/{mission_id}")
async def get_mission(mission_id: str):
    """Get a specific mission by ID"""
    mission = data_manager.get_mission_by_id(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")
    return mission.model_dump()


@app.get("/api/missions/{mission_id}/suitable-pilots")
async def get_suitable_pilots(mission_id: str):
    """Find suitable pilots for a mission"""
    suitable = data_manager.find_suitable_pilots_for_mission(mission_id)
    return {"suitable_pilots": suitable}


@app.get("/api/missions/{mission_id}/suitable-drones")
async def get_suitable_drones(mission_id: str):
    """Find suitable drones for a mission"""
    suitable = data_manager.find_suitable_drones_for_mission(mission_id)
    return {"suitable_drones": suitable}


# ==================== ASSIGNMENT ENDPOINTS ====================

@app.post("/api/assignments")
async def create_assignment(request: AssignmentRequest):
    """Assign pilot/drone to a mission with conflict validation"""
    # Validate first
    warnings = conflict_detector.validate_assignment(
        request.mission_id, request.pilot_id, request.drone_id
    )
    
    errors = [w for w in warnings if w.severity == "error"]
    if errors:
        return {
            "success": False,
            "message": "Assignment blocked due to conflicts",
            "errors": [w.model_dump() for w in errors]
        }
    
    # Make assignment
    mission = data_manager.assign_to_mission(
        request.mission_id, request.pilot_id, request.drone_id
    )
    
    if mission:
        return {
            "success": True,
            "message": "Assignment successful",
            "mission": mission.model_dump(),
            "warnings": [w.model_dump() for w in warnings if w.severity == "warning"]
        }
    
    raise HTTPException(status_code=400, detail="Failed to create assignment")


@app.delete("/api/assignments/{mission_id}")
async def remove_assignment(mission_id: str, unassign_pilot: bool = True, 
                           unassign_drone: bool = True):
    """Remove assignment from a mission"""
    mission = data_manager.unassign_from_mission(mission_id, unassign_pilot, unassign_drone)
    if mission:
        return {"message": "Assignment removed", "mission": mission.model_dump()}
    raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")


# ==================== CONFLICT ENDPOINTS ====================

@app.get("/api/conflicts")
async def check_conflicts():
    """Check all conflicts in the system"""
    return conflict_detector.get_conflict_summary()


@app.post("/api/conflicts/validate")
async def validate_assignment(request: AssignmentRequest):
    """Validate an assignment without making it"""
    warnings = conflict_detector.validate_assignment(
        request.mission_id, request.pilot_id, request.drone_id
    )
    
    return {
        "is_valid": not any(w.severity == "error" for w in warnings),
        "warnings": [w.model_dump() for w in warnings]
    }


# ==================== SUMMARY ENDPOINTS ====================

@app.get("/api/summary")
async def get_summary():
    """Get operational summary"""
    return data_manager.get_summary()


@app.post("/api/refresh")
async def refresh_data():
    """Refresh data from Google Sheets"""
    data_manager.reload_data()
    return {"message": "Data refreshed successfully"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
