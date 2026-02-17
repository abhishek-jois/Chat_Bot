"""
Data Manager - Handles CSV files and Google Sheets synchronization
"""
import csv
import os
from typing import List, Optional, Dict, Any
from datetime import date, datetime
import json

# Google Sheets imports
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

from models import Pilot, Drone, Mission, PilotStatus, DroneStatus


class DataManager:
    """Manages data from CSV files and Google Sheets"""
    
    def __init__(self, data_dir: str = "data", use_google_sheets: bool = False):
        self.data_dir = data_dir
        self.use_google_sheets = use_google_sheets and GSPREAD_AVAILABLE
        self.gsheet_client = None
        self.spreadsheet = None
        
        # Cache for data
        self._pilots: List[Pilot] = []
        self._drones: List[Drone] = []
        self._missions: List[Mission] = []
        
        # Initialize Google Sheets if enabled
        if self.use_google_sheets:
            self._init_google_sheets()
        
        # Load initial data
        self.reload_data()
    
    def _init_google_sheets(self):
        """Initialize Google Sheets connection"""
        try:
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Look for credentials in environment or file
            creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
            if creds_json:
                creds_dict = json.loads(creds_json)
                creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            else:
                creds_path = os.environ.get('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
                if os.path.exists(creds_path):
                    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
                else:
                    print("Warning: Google Sheets credentials not found. Using local CSV only.")
                    self.use_google_sheets = False
                    return
            
            self.gsheet_client = gspread.authorize(creds)
            
            # Get spreadsheet ID from environment
            spreadsheet_id = os.environ.get('GOOGLE_SPREADSHEET_ID')
            if spreadsheet_id:
                self.spreadsheet = self.gsheet_client.open_by_key(spreadsheet_id)
                print(f"Connected to Google Sheets: {self.spreadsheet.title}")
            else:
                print("Warning: GOOGLE_SPREADSHEET_ID not set. Using local CSV only.")
                self.use_google_sheets = False
                
        except Exception as e:
            print(f"Warning: Failed to initialize Google Sheets: {e}")
            self.use_google_sheets = False
    
    def reload_data(self):
        """Reload all data from source (Google Sheets or CSV)"""
        if self.use_google_sheets:
            self._load_from_google_sheets()
        else:
            self._load_from_csv()
    
    def _load_from_csv(self):
        """Load data from CSV files"""
        # Load pilots
        pilot_path = os.path.join(self.data_dir, "pilot_roster.csv")
        if os.path.exists(pilot_path):
            with open(pilot_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self._pilots = [Pilot.from_csv_row(row) for row in reader]
        
        # Load drones
        drone_path = os.path.join(self.data_dir, "drone_fleet.csv")
        if os.path.exists(drone_path):
            with open(drone_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self._drones = [Drone.from_csv_row(row) for row in reader]
        
        # Load missions
        mission_path = os.path.join(self.data_dir, "missions.csv")
        if os.path.exists(mission_path):
            with open(mission_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self._missions = [Mission.from_csv_row(row) for row in reader]
    
    def _load_from_google_sheets(self):
        """Load data from Google Sheets"""
        try:
            # Load pilots
            pilot_sheet = self.spreadsheet.worksheet("pilot_roster")
            pilot_data = pilot_sheet.get_all_records()
            self._pilots = [Pilot.from_csv_row(row) for row in pilot_data]
            
            # Load drones
            drone_sheet = self.spreadsheet.worksheet("drone_fleet")
            drone_data = drone_sheet.get_all_records()
            self._drones = [Drone.from_csv_row(row) for row in drone_data]
            
            # Load missions
            mission_sheet = self.spreadsheet.worksheet("missions")
            mission_data = mission_sheet.get_all_records()
            self._missions = [Mission.from_csv_row(row) for row in mission_data]
            
            # Also save to local CSV as backup
            self._save_to_csv()
            
        except Exception as e:
            print(f"Error loading from Google Sheets: {e}. Falling back to CSV.")
            self._load_from_csv()
    
    def _save_to_csv(self):
        """Save current data to CSV files"""
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Save pilots
        if self._pilots:
            pilot_path = os.path.join(self.data_dir, "pilot_roster.csv")
            with open(pilot_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = list(self._pilots[0].to_csv_row().keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for pilot in self._pilots:
                    writer.writerow(pilot.to_csv_row())
        
        # Save drones
        if self._drones:
            drone_path = os.path.join(self.data_dir, "drone_fleet.csv")
            with open(drone_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = list(self._drones[0].to_csv_row().keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for drone in self._drones:
                    writer.writerow(drone.to_csv_row())
        
        # Save missions
        if self._missions:
            mission_path = os.path.join(self.data_dir, "missions.csv")
            with open(mission_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = list(self._missions[0].to_csv_row().keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for mission in self._missions:
                    writer.writerow(mission.to_csv_row())
    
    def _sync_pilot_to_sheets(self, pilot: Pilot):
        """Sync pilot data back to Google Sheets"""
        if not self.use_google_sheets:
            return
        
        try:
            pilot_sheet = self.spreadsheet.worksheet("pilot_roster")
            # Find the row for this pilot
            cell = pilot_sheet.find(pilot.pilot_id)
            if cell:
                row_num = cell.row
                # Update the entire row
                row_data = pilot.to_csv_row()
                values = list(row_data.values())
                pilot_sheet.update(f'A{row_num}:I{row_num}', [values])
                print(f"Synced pilot {pilot.pilot_id} to Google Sheets")
        except Exception as e:
            print(f"Error syncing pilot to Google Sheets: {e}")
    
    def _sync_drone_to_sheets(self, drone: Drone):
        """Sync drone data back to Google Sheets"""
        if not self.use_google_sheets:
            return
        
        try:
            drone_sheet = self.spreadsheet.worksheet("drone_fleet")
            # Find the row for this drone
            cell = drone_sheet.find(drone.drone_id)
            if cell:
                row_num = cell.row
                # Update the entire row
                row_data = drone.to_csv_row()
                values = list(row_data.values())
                drone_sheet.update(f'A{row_num}:H{row_num}', [values])
                print(f"Synced drone {drone.drone_id} to Google Sheets")
        except Exception as e:
            print(f"Error syncing drone to Google Sheets: {e}")
    
    # ==================== PILOT OPERATIONS ====================
    
    def get_all_pilots(self) -> List[Pilot]:
        """Get all pilots"""
        return self._pilots
    
    def get_pilot_by_id(self, pilot_id: str) -> Optional[Pilot]:
        """Get a specific pilot by ID"""
        for pilot in self._pilots:
            if pilot.pilot_id == pilot_id:
                return pilot
        return None
    
    def get_pilots_by_status(self, status: PilotStatus) -> List[Pilot]:
        """Get pilots by status"""
        return [p for p in self._pilots if p.status == status]
    
    def get_available_pilots(self) -> List[Pilot]:
        """Get all available pilots"""
        return self.get_pilots_by_status(PilotStatus.AVAILABLE)
    
    def get_pilots_by_skill(self, skill: str) -> List[Pilot]:
        """Get pilots with a specific skill"""
        skill_lower = skill.lower()
        return [p for p in self._pilots if any(skill_lower in s.lower() for s in p.skills)]
    
    def get_pilots_by_certification(self, cert: str) -> List[Pilot]:
        """Get pilots with a specific certification"""
        cert_lower = cert.lower()
        return [p for p in self._pilots if any(cert_lower in c.lower() for c in p.certifications)]
    
    def get_pilots_by_location(self, location: str) -> List[Pilot]:
        """Get pilots by location"""
        location_lower = location.lower()
        return [p for p in self._pilots if location_lower in p.location.lower()]
    
    def update_pilot_status(self, pilot_id: str, new_status: PilotStatus, 
                           assignment: Optional[str] = None) -> Optional[Pilot]:
        """Update pilot status and optionally assignment"""
        for i, pilot in enumerate(self._pilots):
            if pilot.pilot_id == pilot_id:
                self._pilots[i].status = new_status
                if assignment is not None:
                    self._pilots[i].current_assignment = assignment if assignment != "-" else None
                
                # Sync to Google Sheets
                self._sync_pilot_to_sheets(self._pilots[i])
                # Save to CSV backup
                self._save_to_csv()
                return self._pilots[i]
        return None
    
    def calculate_pilot_cost(self, pilot_id: str, mission_id: str) -> Optional[Dict[str, Any]]:
        """Calculate total cost for a pilot on a mission"""
        pilot = self.get_pilot_by_id(pilot_id)
        mission = self.get_mission_by_id(mission_id)
        
        if not pilot or not mission:
            return None
        
        duration = mission.get_duration_days()
        total_cost = pilot.daily_rate_inr * duration
        
        return {
            "pilot_id": pilot_id,
            "pilot_name": pilot.name,
            "mission_id": mission_id,
            "daily_rate": pilot.daily_rate_inr,
            "duration_days": duration,
            "total_cost": total_cost,
            "mission_budget": mission.mission_budget_inr,
            "within_budget": total_cost <= mission.mission_budget_inr
        }
    
    # ==================== DRONE OPERATIONS ====================
    
    def get_all_drones(self) -> List[Drone]:
        """Get all drones"""
        return self._drones
    
    def get_drone_by_id(self, drone_id: str) -> Optional[Drone]:
        """Get a specific drone by ID"""
        for drone in self._drones:
            if drone.drone_id == drone_id:
                return drone
        return None
    
    def get_drones_by_status(self, status: DroneStatus) -> List[Drone]:
        """Get drones by status"""
        return [d for d in self._drones if d.status == status]
    
    def get_available_drones(self) -> List[Drone]:
        """Get all available drones"""
        return self.get_drones_by_status(DroneStatus.AVAILABLE)
    
    def get_drones_by_capability(self, capability: str) -> List[Drone]:
        """Get drones with a specific capability"""
        cap_lower = capability.lower()
        return [d for d in self._drones if any(cap_lower in c.lower() for c in d.capabilities)]
    
    def get_drones_by_location(self, location: str) -> List[Drone]:
        """Get drones by location"""
        location_lower = location.lower()
        return [d for d in self._drones if location_lower in d.location.lower()]
    
    def get_drones_for_weather(self, weather: str) -> List[Drone]:
        """Get drones that can operate in specific weather"""
        return [d for d in self._drones if d.can_fly_in_weather(weather)]
    
    def get_drones_needing_maintenance(self, within_days: int = 7) -> List[Drone]:
        """Get drones with maintenance due within specified days"""
        today = date.today()
        return [d for d in self._drones 
                if (d.maintenance_due - today).days <= within_days]
    
    def update_drone_status(self, drone_id: str, new_status: DroneStatus,
                           assignment: Optional[str] = None) -> Optional[Drone]:
        """Update drone status and optionally assignment"""
        for i, drone in enumerate(self._drones):
            if drone.drone_id == drone_id:
                self._drones[i].status = new_status
                if assignment is not None:
                    self._drones[i].current_assignment = assignment if assignment != "-" else None
                
                # Sync to Google Sheets
                self._sync_drone_to_sheets(self._drones[i])
                # Save to CSV backup
                self._save_to_csv()
                return self._drones[i]
        return None
    
    # ==================== MISSION OPERATIONS ====================
    
    def get_all_missions(self) -> List[Mission]:
        """Get all missions"""
        return self._missions
    
    def get_mission_by_id(self, mission_id: str) -> Optional[Mission]:
        """Get a specific mission by ID"""
        for mission in self._missions:
            if mission.project_id == mission_id:
                return mission
        return None
    
    def get_missions_by_priority(self, priority: str) -> List[Mission]:
        """Get missions by priority"""
        return [m for m in self._missions if m.priority.value.lower() == priority.lower()]
    
    def get_missions_by_location(self, location: str) -> List[Mission]:
        """Get missions by location"""
        location_lower = location.lower()
        return [m for m in self._missions if location_lower in m.location.lower()]
    
    def get_active_missions(self) -> List[Mission]:
        """Get missions that are currently active"""
        today = date.today()
        return [m for m in self._missions if m.start_date <= today <= m.end_date]
    
    def get_upcoming_missions(self) -> List[Mission]:
        """Get missions that haven't started yet"""
        today = date.today()
        return [m for m in self._missions if m.start_date > today]
    
    def get_urgent_missions(self) -> List[Mission]:
        """Get urgent priority missions"""
        return [m for m in self._missions if m.priority.value == "Urgent"]
    
    def assign_to_mission(self, mission_id: str, pilot_id: Optional[str] = None,
                         drone_id: Optional[str] = None) -> Optional[Mission]:
        """Assign pilot and/or drone to a mission"""
        for i, mission in enumerate(self._missions):
            if mission.project_id == mission_id:
                if pilot_id:
                    self._missions[i].assigned_pilot = pilot_id
                    # Update pilot status
                    self.update_pilot_status(pilot_id, PilotStatus.ASSIGNED, mission_id)
                
                if drone_id:
                    self._missions[i].assigned_drone = drone_id
                    # Update drone status
                    self.update_drone_status(drone_id, DroneStatus.DEPLOYED, mission_id)
                
                self._save_to_csv()
                return self._missions[i]
        return None
    
    def unassign_from_mission(self, mission_id: str, unassign_pilot: bool = False,
                              unassign_drone: bool = False) -> Optional[Mission]:
        """Unassign pilot and/or drone from a mission"""
        for i, mission in enumerate(self._missions):
            if mission.project_id == mission_id:
                if unassign_pilot and mission.assigned_pilot:
                    pilot_id = mission.assigned_pilot
                    self._missions[i].assigned_pilot = None
                    # Update pilot status back to available
                    self.update_pilot_status(pilot_id, PilotStatus.AVAILABLE, "-")
                
                if unassign_drone and mission.assigned_drone:
                    drone_id = mission.assigned_drone
                    self._missions[i].assigned_drone = None
                    # Update drone status back to available
                    self.update_drone_status(drone_id, DroneStatus.AVAILABLE, "-")
                
                self._save_to_csv()
                return self._missions[i]
        return None
    
    # ==================== QUERY HELPERS ====================
    
    def find_suitable_pilots_for_mission(self, mission_id: str) -> List[Dict[str, Any]]:
        """Find pilots suitable for a mission based on requirements"""
        mission = self.get_mission_by_id(mission_id)
        if not mission:
            return []
        
        suitable = []
        for pilot in self._pilots:
            # Check status
            if pilot.status != PilotStatus.AVAILABLE:
                continue
            
            # Check location match
            location_match = pilot.location.lower() == mission.location.lower()
            
            # Check skills
            has_skills = all(
                any(rs.lower() in ps.lower() for ps in pilot.skills)
                for rs in mission.required_skills
            )
            
            # Check certifications
            has_certs = all(
                any(rc.lower() in pc.lower() for pc in pilot.certifications)
                for rc in mission.required_certs
            )
            
            # Calculate cost
            duration = mission.get_duration_days()
            total_cost = pilot.daily_rate_inr * duration
            within_budget = total_cost <= mission.mission_budget_inr
            
            # Check availability date
            available_in_time = pilot.available_from <= mission.start_date
            
            suitable.append({
                "pilot": pilot,
                "location_match": location_match,
                "has_required_skills": has_skills,
                "has_required_certs": has_certs,
                "within_budget": within_budget,
                "total_cost": total_cost,
                "available_in_time": available_in_time,
                "is_fully_suitable": all([location_match, has_skills, has_certs, 
                                          within_budget, available_in_time])
            })
        
        # Sort by suitability
        suitable.sort(key=lambda x: (
            x["is_fully_suitable"],
            x["has_required_skills"],
            x["has_required_certs"],
            x["within_budget"],
            x["location_match"]
        ), reverse=True)
        
        return suitable
    
    def find_suitable_drones_for_mission(self, mission_id: str) -> List[Dict[str, Any]]:
        """Find drones suitable for a mission based on requirements"""
        mission = self.get_mission_by_id(mission_id)
        if not mission:
            return []
        
        suitable = []
        for drone in self._drones:
            # Check status
            if drone.status != DroneStatus.AVAILABLE:
                continue
            
            # Check location match
            location_match = drone.location.lower() == mission.location.lower()
            
            # Check weather compatibility
            weather_compatible = drone.can_fly_in_weather(mission.weather_forecast)
            
            # Check if maintenance is not due during mission
            maintenance_ok = drone.maintenance_due > mission.end_date
            
            suitable.append({
                "drone": drone,
                "location_match": location_match,
                "weather_compatible": weather_compatible,
                "maintenance_ok": maintenance_ok,
                "is_fully_suitable": all([location_match, weather_compatible, maintenance_ok])
            })
        
        # Sort by suitability
        suitable.sort(key=lambda x: (
            x["is_fully_suitable"],
            x["weather_compatible"],
            x["location_match"],
            x["maintenance_ok"]
        ), reverse=True)
        
        return suitable
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of current operations"""
        return {
            "total_pilots": len(self._pilots),
            "available_pilots": len(self.get_available_pilots()),
            "pilots_on_leave": len(self.get_pilots_by_status(PilotStatus.ON_LEAVE)),
            "assigned_pilots": len(self.get_pilots_by_status(PilotStatus.ASSIGNED)),
            "total_drones": len(self._drones),
            "available_drones": len(self.get_available_drones()),
            "drones_in_maintenance": len(self.get_drones_by_status(DroneStatus.MAINTENANCE)),
            "deployed_drones": len(self.get_drones_by_status(DroneStatus.DEPLOYED)),
            "total_missions": len(self._missions),
            "active_missions": len(self.get_active_missions()),
            "upcoming_missions": len(self.get_upcoming_missions()),
            "urgent_missions": len(self.get_urgent_missions())
        }
