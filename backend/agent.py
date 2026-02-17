"""
AI Agent for Drone Operations Coordinator
Uses LangChain with custom tools for handling drone operations
"""
import json
from typing import List, Dict, Any, Optional
from datetime import date, datetime

from langchain.tools import BaseTool, StructuredTool
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain_core.pydantic_v1 import BaseModel, Field

from data_manager import DataManager
from conflict_detector import ConflictDetector
from models import PilotStatus, DroneStatus


class DroneOperationsAgent:
    """AI Agent for Drone Operations Coordination"""
    
    def __init__(self, data_manager: DataManager, openai_api_key: str):
        self.dm = data_manager
        self.conflict_detector = ConflictDetector(data_manager)
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=openai_api_key
        )
        
        # Create tools
        self.tools = self._create_tools()
        
        # Create agent
        self.agent = self._create_agent()
        
        # Memory for conversation
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Create agent executor
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True
        )
    
    def _create_tools(self) -> List[BaseTool]:
        """Create all tools for the agent"""
        tools = []
        
        # ==================== PILOT TOOLS ====================
        
        tools.append(StructuredTool.from_function(
            func=self._get_all_pilots,
            name="get_all_pilots",
            description="Get a list of all pilots with their details including ID, name, skills, certifications, location, status, and daily rate"
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._get_available_pilots,
            name="get_available_pilots",
            description="Get a list of all pilots who are currently available for assignment"
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._query_pilots,
            name="query_pilots",
            description="Query pilots by skill, certification, or location. Provide at least one filter parameter.",
            args_schema=QueryPilotsInput
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._calculate_pilot_cost,
            name="calculate_pilot_cost",
            description="Calculate the total cost for a pilot on a specific mission",
            args_schema=PilotCostInput
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._update_pilot_status,
            name="update_pilot_status",
            description="Update a pilot's status. Valid statuses are: Available, On Leave, Unavailable, Assigned. This will sync to Google Sheets.",
            args_schema=UpdatePilotStatusInput
        ))
        
        # ==================== DRONE TOOLS ====================
        
        tools.append(StructuredTool.from_function(
            func=self._get_all_drones,
            name="get_all_drones",
            description="Get a list of all drones with their details including ID, model, capabilities, location, status, and weather resistance"
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._get_available_drones,
            name="get_available_drones",
            description="Get a list of all drones that are currently available for deployment"
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._query_drones,
            name="query_drones",
            description="Query drones by capability, location, or weather resistance",
            args_schema=QueryDronesInput
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._get_drones_for_weather,
            name="get_drones_for_weather",
            description="Get drones that can operate in specific weather conditions (Sunny, Cloudy, or Rainy)",
            args_schema=WeatherInput
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._update_drone_status,
            name="update_drone_status",
            description="Update a drone's status. Valid statuses are: Available, Maintenance, Deployed. This will sync to Google Sheets.",
            args_schema=UpdateDroneStatusInput
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._check_maintenance_issues,
            name="check_maintenance_issues",
            description="Check for drones with upcoming or overdue maintenance"
        ))
        
        # ==================== MISSION TOOLS ====================
        
        tools.append(StructuredTool.from_function(
            func=self._get_all_missions,
            name="get_all_missions",
            description="Get a list of all missions with their details"
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._get_mission_details,
            name="get_mission_details",
            description="Get detailed information about a specific mission by project ID",
            args_schema=MissionIdInput
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._get_active_assignments,
            name="get_active_assignments",
            description="Get all currently active mission assignments"
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._get_urgent_missions,
            name="get_urgent_missions",
            description="Get all missions marked as Urgent priority"
        ))
        
        # ==================== ASSIGNMENT TOOLS ====================
        
        tools.append(StructuredTool.from_function(
            func=self._find_suitable_pilots,
            name="find_suitable_pilots_for_mission",
            description="Find pilots who are suitable for a specific mission based on skills, certifications, location, budget, and availability",
            args_schema=MissionIdInput
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._find_suitable_drones,
            name="find_suitable_drones_for_mission",
            description="Find drones that are suitable for a specific mission based on location, weather compatibility, and maintenance status",
            args_schema=MissionIdInput
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._assign_to_mission,
            name="assign_to_mission",
            description="Assign a pilot and/or drone to a mission. Validates the assignment and warns about conflicts.",
            args_schema=AssignInput
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._handle_reassignment,
            name="handle_reassignment",
            description="Handle reassignment for a mission. Can unassign current pilot/drone and optionally assign new ones. Use for urgent reassignments.",
            args_schema=ReassignInput
        ))
        
        # ==================== CONFLICT DETECTION TOOLS ====================
        
        tools.append(StructuredTool.from_function(
            func=self._check_all_conflicts,
            name="check_all_conflicts",
            description="Check for all conflicts across pilots, drones, and missions. Returns errors, warnings, and info."
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._validate_assignment,
            name="validate_assignment",
            description="Validate a potential assignment before making it. Checks for conflicts without actually making the assignment.",
            args_schema=AssignInput
        ))
        
        # ==================== SUMMARY TOOLS ====================
        
        tools.append(StructuredTool.from_function(
            func=self._get_operations_summary,
            name="get_operations_summary",
            description="Get an overview summary of current operations including pilot counts, drone counts, and mission status"
        ))
        
        tools.append(StructuredTool.from_function(
            func=self._refresh_data,
            name="refresh_data",
            description="Refresh data from Google Sheets to get the latest updates"
        ))
        
        return tools
    
    def _create_agent(self):
        """Create the agent with system prompt"""
        system_prompt = """You are an AI Drone Operations Coordinator for Skylark Drones. Your role is to help manage:

1. **Pilot Roster Management**: Track pilot availability, skills, certifications, locations, and daily rates. You can query pilots and update their status.

2. **Assignment Tracking**: Match pilots to missions based on requirements, track active assignments, and handle reassignments.

3. **Drone Inventory**: Query the drone fleet by capability, location, and weather compatibility. Track deployment status and maintenance schedules.

4. **Conflict Detection**: Identify and alert about:
   - Double-booking (pilot or drone assigned to overlapping projects)
   - Skill/certification mismatches
   - Equipment-pilot location mismatches
   - Budget overrun warnings (when pilot cost exceeds mission budget)
   - Weather risk alerts (non-waterproof drone assigned to rainy mission)

**Important Rules:**
- Always validate assignments before making them to check for conflicts
- When suggesting pilots/drones, consider: location match, skills match, budget fit, and weather compatibility
- For urgent missions, prioritize finding alternatives quickly
- Always provide clear, actionable information
- When updating status, the changes sync to Google Sheets

**Urgent Reassignment Handling:**
When handling urgent reassignments:
1. First unassign the current pilot/drone from the mission
2. Immediately find suitable alternatives
3. Check for conflicts with new assignments
4. Make the new assignment if valid
5. Report the complete reassignment action taken

Be helpful, concise, and proactive in identifying potential issues."""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        return create_openai_functions_agent(self.llm, self.tools, prompt)
    
    # ==================== TOOL IMPLEMENTATIONS ====================
    
    def _get_all_pilots(self) -> str:
        """Get all pilots"""
        pilots = self.dm.get_all_pilots()
        result = []
        for p in pilots:
            result.append({
                "pilot_id": p.pilot_id,
                "name": p.name,
                "skills": p.skills,
                "certifications": p.certifications,
                "location": p.location,
                "status": p.status.value,
                "current_assignment": p.current_assignment,
                "available_from": p.available_from.isoformat(),
                "daily_rate_inr": p.daily_rate_inr
            })
        return json.dumps(result, indent=2)
    
    def _get_available_pilots(self) -> str:
        """Get available pilots"""
        pilots = self.dm.get_available_pilots()
        result = []
        for p in pilots:
            result.append({
                "pilot_id": p.pilot_id,
                "name": p.name,
                "skills": p.skills,
                "certifications": p.certifications,
                "location": p.location,
                "daily_rate_inr": p.daily_rate_inr
            })
        return json.dumps(result, indent=2)
    
    def _query_pilots(self, skill: str = None, certification: str = None, 
                      location: str = None) -> str:
        """Query pilots by filters"""
        pilots = self.dm.get_all_pilots()
        
        if skill:
            pilots = [p for p in pilots if any(skill.lower() in s.lower() for s in p.skills)]
        if certification:
            pilots = [p for p in pilots if any(certification.lower() in c.lower() for c in p.certifications)]
        if location:
            pilots = [p for p in pilots if location.lower() in p.location.lower()]
        
        result = []
        for p in pilots:
            result.append({
                "pilot_id": p.pilot_id,
                "name": p.name,
                "skills": p.skills,
                "certifications": p.certifications,
                "location": p.location,
                "status": p.status.value,
                "daily_rate_inr": p.daily_rate_inr
            })
        return json.dumps(result, indent=2) if result else "No pilots found matching the criteria."
    
    def _calculate_pilot_cost(self, pilot_id: str, mission_id: str) -> str:
        """Calculate pilot cost for a mission"""
        result = self.dm.calculate_pilot_cost(pilot_id, mission_id)
        if result:
            return json.dumps(result, indent=2)
        return "Could not calculate cost. Please verify pilot_id and mission_id."
    
    def _update_pilot_status(self, pilot_id: str, new_status: str) -> str:
        """Update pilot status"""
        try:
            status = PilotStatus(new_status)
            pilot = self.dm.update_pilot_status(pilot_id, status)
            if pilot:
                return f"✅ Successfully updated pilot {pilot.name} ({pilot_id}) status to {new_status}. Changes synced to Google Sheets."
            return f"❌ Pilot {pilot_id} not found."
        except ValueError:
            return f"❌ Invalid status '{new_status}'. Valid statuses: Available, On Leave, Unavailable, Assigned"
    
    def _get_all_drones(self) -> str:
        """Get all drones"""
        drones = self.dm.get_all_drones()
        result = []
        for d in drones:
            result.append({
                "drone_id": d.drone_id,
                "model": d.model,
                "capabilities": d.capabilities,
                "status": d.status.value,
                "location": d.location,
                "current_assignment": d.current_assignment,
                "maintenance_due": d.maintenance_due.isoformat(),
                "weather_resistance": d.weather_resistance
            })
        return json.dumps(result, indent=2)
    
    def _get_available_drones(self) -> str:
        """Get available drones"""
        drones = self.dm.get_available_drones()
        result = []
        for d in drones:
            result.append({
                "drone_id": d.drone_id,
                "model": d.model,
                "capabilities": d.capabilities,
                "location": d.location,
                "weather_resistance": d.weather_resistance
            })
        return json.dumps(result, indent=2)
    
    def _query_drones(self, capability: str = None, location: str = None,
                      weather_resistance: str = None) -> str:
        """Query drones by filters"""
        drones = self.dm.get_all_drones()
        
        if capability:
            drones = [d for d in drones if any(capability.lower() in c.lower() for c in d.capabilities)]
        if location:
            drones = [d for d in drones if location.lower() in d.location.lower()]
        if weather_resistance:
            drones = [d for d in drones if weather_resistance.lower() in d.weather_resistance.lower()]
        
        result = []
        for d in drones:
            result.append({
                "drone_id": d.drone_id,
                "model": d.model,
                "capabilities": d.capabilities,
                "location": d.location,
                "status": d.status.value,
                "weather_resistance": d.weather_resistance
            })
        return json.dumps(result, indent=2) if result else "No drones found matching the criteria."
    
    def _get_drones_for_weather(self, weather: str) -> str:
        """Get drones that can fly in specific weather"""
        drones = self.dm.get_drones_for_weather(weather)
        available_drones = [d for d in drones if d.status.value == "Available"]
        
        result = []
        for d in available_drones:
            result.append({
                "drone_id": d.drone_id,
                "model": d.model,
                "capabilities": d.capabilities,
                "location": d.location,
                "weather_resistance": d.weather_resistance
            })
        return json.dumps(result, indent=2) if result else f"No available drones can fly in {weather} conditions."
    
    def _update_drone_status(self, drone_id: str, new_status: str) -> str:
        """Update drone status"""
        try:
            status = DroneStatus(new_status)
            drone = self.dm.update_drone_status(drone_id, status)
            if drone:
                return f"✅ Successfully updated drone {drone_id} ({drone.model}) status to {new_status}. Changes synced to Google Sheets."
            return f"❌ Drone {drone_id} not found."
        except ValueError:
            return f"❌ Invalid status '{new_status}'. Valid statuses: Available, Maintenance, Deployed"
    
    def _check_maintenance_issues(self) -> str:
        """Check maintenance issues"""
        warnings = self.conflict_detector.check_maintenance_warnings()
        if warnings:
            result = []
            for w in warnings:
                result.append({
                    "type": w.type,
                    "severity": w.severity,
                    "message": w.message
                })
            return json.dumps(result, indent=2)
        return "No maintenance issues found."
    
    def _get_all_missions(self) -> str:
        """Get all missions"""
        missions = self.dm.get_all_missions()
        result = []
        for m in missions:
            result.append({
                "project_id": m.project_id,
                "client": m.client,
                "location": m.location,
                "required_skills": m.required_skills,
                "required_certs": m.required_certs,
                "start_date": m.start_date.isoformat(),
                "end_date": m.end_date.isoformat(),
                "priority": m.priority.value,
                "mission_budget_inr": m.mission_budget_inr,
                "weather_forecast": m.weather_forecast,
                "assigned_pilot": m.assigned_pilot,
                "assigned_drone": m.assigned_drone
            })
        return json.dumps(result, indent=2)
    
    def _get_mission_details(self, mission_id: str) -> str:
        """Get details of a specific mission"""
        mission = self.dm.get_mission_by_id(mission_id)
        if mission:
            return json.dumps({
                "project_id": mission.project_id,
                "client": mission.client,
                "location": mission.location,
                "required_skills": mission.required_skills,
                "required_certs": mission.required_certs,
                "start_date": mission.start_date.isoformat(),
                "end_date": mission.end_date.isoformat(),
                "duration_days": mission.get_duration_days(),
                "priority": mission.priority.value,
                "mission_budget_inr": mission.mission_budget_inr,
                "weather_forecast": mission.weather_forecast,
                "assigned_pilot": mission.assigned_pilot,
                "assigned_drone": mission.assigned_drone
            }, indent=2)
        return f"Mission {mission_id} not found."
    
    def _get_active_assignments(self) -> str:
        """Get active assignments"""
        missions = self.dm.get_all_missions()
        today = date.today()
        
        active = []
        for m in missions:
            if m.start_date <= today <= m.end_date:
                if m.assigned_pilot or m.assigned_drone:
                    entry = {
                        "mission_id": m.project_id,
                        "client": m.client,
                        "location": m.location,
                        "dates": f"{m.start_date} to {m.end_date}"
                    }
                    if m.assigned_pilot:
                        pilot = self.dm.get_pilot_by_id(m.assigned_pilot)
                        entry["assigned_pilot"] = f"{pilot.name} ({m.assigned_pilot})" if pilot else m.assigned_pilot
                    if m.assigned_drone:
                        drone = self.dm.get_drone_by_id(m.assigned_drone)
                        entry["assigned_drone"] = f"{drone.model} ({m.assigned_drone})" if drone else m.assigned_drone
                    active.append(entry)
        
        return json.dumps(active, indent=2) if active else "No active assignments currently."
    
    def _get_urgent_missions(self) -> str:
        """Get urgent missions"""
        missions = self.dm.get_urgent_missions()
        result = []
        for m in missions:
            result.append({
                "project_id": m.project_id,
                "client": m.client,
                "location": m.location,
                "dates": f"{m.start_date} to {m.end_date}",
                "assigned_pilot": m.assigned_pilot,
                "assigned_drone": m.assigned_drone
            })
        return json.dumps(result, indent=2) if result else "No urgent missions."
    
    def _find_suitable_pilots(self, mission_id: str) -> str:
        """Find suitable pilots for a mission"""
        suitable = self.dm.find_suitable_pilots_for_mission(mission_id)
        
        if not suitable:
            return f"No pilots found for mission {mission_id}."
        
        result = []
        for s in suitable:
            pilot = s["pilot"]
            result.append({
                "pilot_id": pilot.pilot_id,
                "name": pilot.name,
                "location": pilot.location,
                "skills": pilot.skills,
                "certifications": pilot.certifications,
                "daily_rate": pilot.daily_rate_inr,
                "total_cost": s["total_cost"],
                "suitability": {
                    "fully_suitable": s["is_fully_suitable"],
                    "location_match": s["location_match"],
                    "has_required_skills": s["has_required_skills"],
                    "has_required_certs": s["has_required_certs"],
                    "within_budget": s["within_budget"],
                    "available_in_time": s["available_in_time"]
                }
            })
        
        return json.dumps(result, indent=2)
    
    def _find_suitable_drones(self, mission_id: str) -> str:
        """Find suitable drones for a mission"""
        suitable = self.dm.find_suitable_drones_for_mission(mission_id)
        
        if not suitable:
            return f"No available drones found for mission {mission_id}."
        
        result = []
        for s in suitable:
            drone = s["drone"]
            result.append({
                "drone_id": drone.drone_id,
                "model": drone.model,
                "location": drone.location,
                "capabilities": drone.capabilities,
                "weather_resistance": drone.weather_resistance,
                "suitability": {
                    "fully_suitable": s["is_fully_suitable"],
                    "location_match": s["location_match"],
                    "weather_compatible": s["weather_compatible"],
                    "maintenance_ok": s["maintenance_ok"]
                }
            })
        
        return json.dumps(result, indent=2)
    
    def _assign_to_mission(self, mission_id: str, pilot_id: str = None, 
                          drone_id: str = None) -> str:
        """Assign pilot/drone to mission"""
        # First validate
        warnings = self.conflict_detector.validate_assignment(mission_id, pilot_id, drone_id)
        errors = [w for w in warnings if w.severity == "error"]
        
        if errors:
            error_msgs = "\n".join([f"❌ {e.message}" for e in errors])
            return f"Assignment blocked due to conflicts:\n{error_msgs}"
        
        # Make assignment
        mission = self.dm.assign_to_mission(mission_id, pilot_id, drone_id)
        
        if mission:
            response = f"✅ Assignment successful for {mission_id}:\n"
            if pilot_id:
                pilot = self.dm.get_pilot_by_id(pilot_id)
                response += f"  - Pilot: {pilot.name} ({pilot_id})\n"
            if drone_id:
                drone = self.dm.get_drone_by_id(drone_id)
                response += f"  - Drone: {drone.model} ({drone_id})\n"
            
            # Add warnings if any
            warning_msgs = [w for w in warnings if w.severity == "warning"]
            if warning_msgs:
                response += "\n⚠️ Warnings:\n"
                for w in warning_msgs:
                    response += f"  - {w.message}\n"
            
            return response
        
        return f"❌ Failed to assign to mission {mission_id}."
    
    def _handle_reassignment(self, mission_id: str, reason: str,
                            unassign_pilot: bool = False, unassign_drone: bool = False,
                            new_pilot_id: str = None, new_drone_id: str = None) -> str:
        """Handle reassignment for urgent situations"""
        response = f"🔄 Processing reassignment for {mission_id}\nReason: {reason}\n\n"
        
        mission = self.dm.get_mission_by_id(mission_id)
        if not mission:
            return f"❌ Mission {mission_id} not found."
        
        # Step 1: Unassign current resources
        if unassign_pilot or unassign_drone:
            old_pilot = mission.assigned_pilot
            old_drone = mission.assigned_drone
            
            self.dm.unassign_from_mission(mission_id, unassign_pilot, unassign_drone)
            
            if unassign_pilot and old_pilot:
                response += f"✅ Unassigned pilot {old_pilot} from mission\n"
            if unassign_drone and old_drone:
                response += f"✅ Unassigned drone {old_drone} from mission\n"
        
        # Step 2: Assign new resources
        if new_pilot_id or new_drone_id:
            # Validate new assignment
            warnings = self.conflict_detector.validate_assignment(mission_id, new_pilot_id, new_drone_id)
            errors = [w for w in warnings if w.severity == "error"]
            
            if errors:
                response += "\n⚠️ Cannot complete new assignment due to conflicts:\n"
                for e in errors:
                    response += f"  - {e.message}\n"
                response += "\nPlease resolve conflicts before reassigning."
            else:
                self.dm.assign_to_mission(mission_id, new_pilot_id, new_drone_id)
                if new_pilot_id:
                    pilot = self.dm.get_pilot_by_id(new_pilot_id)
                    response += f"✅ Assigned new pilot: {pilot.name} ({new_pilot_id})\n"
                if new_drone_id:
                    drone = self.dm.get_drone_by_id(new_drone_id)
                    response += f"✅ Assigned new drone: {drone.model} ({new_drone_id})\n"
        
        response += "\n📋 Changes synced to Google Sheets."
        return response
    
    def _check_all_conflicts(self) -> str:
        """Check all conflicts"""
        summary = self.conflict_detector.get_conflict_summary()
        
        result = f"📊 Conflict Summary:\n"
        result += f"  - Total Issues: {summary['total_issues']}\n"
        result += f"  - Errors: {summary['errors']}\n"
        result += f"  - Warnings: {summary['warnings']}\n"
        result += f"  - Info: {summary['info']}\n"
        
        if summary['error_details']:
            result += "\n🔴 Errors:\n"
            for e in summary['error_details']:
                result += f"  - [{e['type']}] {e['message']}\n"
        
        if summary['warning_details']:
            result += "\n🟡 Warnings:\n"
            for w in summary['warning_details']:
                result += f"  - [{w['type']}] {w['message']}\n"
        
        if summary['info_details']:
            result += "\n🔵 Info:\n"
            for i in summary['info_details']:
                result += f"  - [{i['type']}] {i['message']}\n"
        
        return result
    
    def _validate_assignment(self, mission_id: str, pilot_id: str = None,
                            drone_id: str = None) -> str:
        """Validate assignment without making it"""
        warnings = self.conflict_detector.validate_assignment(mission_id, pilot_id, drone_id)
        
        if not warnings:
            return "✅ Assignment is valid with no conflicts detected."
        
        result = "Validation Results:\n"
        errors = [w for w in warnings if w.severity == "error"]
        warns = [w for w in warnings if w.severity == "warning"]
        
        if errors:
            result += "\n🔴 Blocking Issues:\n"
            for e in errors:
                result += f"  - {e.message}\n"
        
        if warns:
            result += "\n🟡 Warnings (assignment can proceed):\n"
            for w in warns:
                result += f"  - {w.message}\n"
        
        return result
    
    def _get_operations_summary(self) -> str:
        """Get operations summary"""
        summary = self.dm.get_summary()
        
        result = "📊 Operations Summary:\n\n"
        result += "👨‍✈️ Pilots:\n"
        result += f"  - Total: {summary['total_pilots']}\n"
        result += f"  - Available: {summary['available_pilots']}\n"
        result += f"  - Assigned: {summary['assigned_pilots']}\n"
        result += f"  - On Leave: {summary['pilots_on_leave']}\n"
        
        result += "\n🚁 Drones:\n"
        result += f"  - Total: {summary['total_drones']}\n"
        result += f"  - Available: {summary['available_drones']}\n"
        result += f"  - Deployed: {summary['deployed_drones']}\n"
        result += f"  - In Maintenance: {summary['drones_in_maintenance']}\n"
        
        result += "\n📋 Missions:\n"
        result += f"  - Total: {summary['total_missions']}\n"
        result += f"  - Active: {summary['active_missions']}\n"
        result += f"  - Upcoming: {summary['upcoming_missions']}\n"
        result += f"  - Urgent: {summary['urgent_missions']}\n"
        
        return result
    
    def _refresh_data(self) -> str:
        """Refresh data from Google Sheets"""
        self.dm.reload_data()
        return "✅ Data refreshed from Google Sheets."
    
    def chat(self, message: str) -> str:
        """Process a chat message and return response"""
        try:
            result = self.agent_executor.invoke({"input": message})
            return result["output"]
        except Exception as e:
            return f"I encountered an error processing your request: {str(e)}. Please try rephrasing your question."


# Input schemas for tools
class QueryPilotsInput(BaseModel):
    skill: Optional[str] = Field(None, description="Filter by skill (e.g., Mapping, Inspection)")
    certification: Optional[str] = Field(None, description="Filter by certification (e.g., DGCA, Night Ops)")
    location: Optional[str] = Field(None, description="Filter by location (e.g., Bangalore, Mumbai)")


class PilotCostInput(BaseModel):
    pilot_id: str = Field(..., description="The pilot ID (e.g., P001)")
    mission_id: str = Field(..., description="The mission/project ID (e.g., PRJ001)")


class UpdatePilotStatusInput(BaseModel):
    pilot_id: str = Field(..., description="The pilot ID (e.g., P001)")
    new_status: str = Field(..., description="New status: Available, On Leave, Unavailable, or Assigned")


class QueryDronesInput(BaseModel):
    capability: Optional[str] = Field(None, description="Filter by capability (e.g., RGB, Thermal, LiDAR)")
    location: Optional[str] = Field(None, description="Filter by location")
    weather_resistance: Optional[str] = Field(None, description="Filter by weather resistance (e.g., IP43)")


class WeatherInput(BaseModel):
    weather: str = Field(..., description="Weather condition: Sunny, Cloudy, or Rainy")


class UpdateDroneStatusInput(BaseModel):
    drone_id: str = Field(..., description="The drone ID (e.g., D001)")
    new_status: str = Field(..., description="New status: Available, Maintenance, or Deployed")


class MissionIdInput(BaseModel):
    mission_id: str = Field(..., description="The mission/project ID (e.g., PRJ001)")


class AssignInput(BaseModel):
    mission_id: str = Field(..., description="The mission/project ID")
    pilot_id: Optional[str] = Field(None, description="The pilot ID to assign")
    drone_id: Optional[str] = Field(None, description="The drone ID to assign")


class ReassignInput(BaseModel):
    mission_id: str = Field(..., description="The mission/project ID")
    reason: str = Field(..., description="Reason for reassignment")
    unassign_pilot: bool = Field(False, description="Whether to unassign current pilot")
    unassign_drone: bool = Field(False, description="Whether to unassign current drone")
    new_pilot_id: Optional[str] = Field(None, description="New pilot ID to assign")
    new_drone_id: Optional[str] = Field(None, description="New drone ID to assign")
