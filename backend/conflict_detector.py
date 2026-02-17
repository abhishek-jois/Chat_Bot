"""
Conflict Detection System for Drone Operations
Detects scheduling conflicts, skill mismatches, equipment issues, and budget overruns
"""
from typing import List, Dict, Any, Optional
from datetime import date
from models import (
    Pilot, Drone, Mission, PilotStatus, DroneStatus,
    ConflictWarning
)
from data_manager import DataManager


class ConflictDetector:
    """Detects and reports conflicts in drone operations"""
    
    def __init__(self, data_manager: DataManager):
        self.dm = data_manager
    
    def check_all_conflicts(self) -> List[ConflictWarning]:
        """Run all conflict checks and return combined warnings"""
        warnings = []
        
        # Check each mission for conflicts
        for mission in self.dm.get_all_missions():
            warnings.extend(self.check_mission_conflicts(mission.project_id))
        
        # Check for general fleet/roster issues
        warnings.extend(self.check_maintenance_warnings())
        warnings.extend(self.check_pilot_availability_issues())
        
        return warnings
    
    def check_mission_conflicts(self, mission_id: str) -> List[ConflictWarning]:
        """Check all conflicts for a specific mission"""
        mission = self.dm.get_mission_by_id(mission_id)
        if not mission:
            return []
        
        warnings = []
        
        # Check pilot assignment conflicts
        if mission.assigned_pilot:
            pilot = self.dm.get_pilot_by_id(mission.assigned_pilot)
            if pilot:
                warnings.extend(self._check_pilot_assignment_conflicts(pilot, mission))
        
        # Check drone assignment conflicts
        if mission.assigned_drone:
            drone = self.dm.get_drone_by_id(mission.assigned_drone)
            if drone:
                warnings.extend(self._check_drone_assignment_conflicts(drone, mission))
        
        # Check pilot-drone location mismatch
        if mission.assigned_pilot and mission.assigned_drone:
            warnings.extend(self._check_pilot_drone_location_mismatch(
                mission.assigned_pilot, mission.assigned_drone, mission
            ))
        
        return warnings
    
    def _check_pilot_assignment_conflicts(self, pilot: Pilot, mission: Mission) -> List[ConflictWarning]:
        """Check conflicts for a pilot assignment"""
        warnings = []
        
        # 1. Double-booking detection
        double_booking = self._check_pilot_double_booking(pilot, mission)
        if double_booking:
            warnings.append(double_booking)
        
        # 2. Skill mismatch
        skill_issues = self._check_pilot_skill_mismatch(pilot, mission)
        warnings.extend(skill_issues)
        
        # 3. Certification mismatch
        cert_issues = self._check_pilot_certification_mismatch(pilot, mission)
        warnings.extend(cert_issues)
        
        # 4. Budget overrun
        budget_warning = self._check_budget_overrun(pilot, mission)
        if budget_warning:
            warnings.append(budget_warning)
        
        # 5. Location mismatch
        if pilot.location.lower() != mission.location.lower():
            warnings.append(ConflictWarning(
                type="location_mismatch",
                severity="warning",
                message=f"Pilot {pilot.name} ({pilot.pilot_id}) is in {pilot.location} but mission {mission.project_id} is in {mission.location}",
                affected_entities=[pilot.pilot_id, mission.project_id]
            ))
        
        # 6. Availability check
        if pilot.available_from > mission.start_date:
            warnings.append(ConflictWarning(
                type="availability_conflict",
                severity="error",
                message=f"Pilot {pilot.name} ({pilot.pilot_id}) is not available until {pilot.available_from}, but mission starts on {mission.start_date}",
                affected_entities=[pilot.pilot_id, mission.project_id]
            ))
        
        return warnings
    
    def _check_drone_assignment_conflicts(self, drone: Drone, mission: Mission) -> List[ConflictWarning]:
        """Check conflicts for a drone assignment"""
        warnings = []
        
        # 1. Double-booking detection
        double_booking = self._check_drone_double_booking(drone, mission)
        if double_booking:
            warnings.append(double_booking)
        
        # 2. Maintenance status check
        if drone.status == DroneStatus.MAINTENANCE:
            warnings.append(ConflictWarning(
                type="maintenance_conflict",
                severity="error",
                message=f"Drone {drone.drone_id} ({drone.model}) is currently in maintenance and cannot be assigned to mission {mission.project_id}",
                affected_entities=[drone.drone_id, mission.project_id]
            ))
        
        # 3. Maintenance due during mission
        if drone.maintenance_due <= mission.end_date and drone.maintenance_due >= mission.start_date:
            warnings.append(ConflictWarning(
                type="maintenance_warning",
                severity="warning",
                message=f"Drone {drone.drone_id} ({drone.model}) has maintenance due on {drone.maintenance_due}, which falls during mission {mission.project_id} ({mission.start_date} to {mission.end_date})",
                affected_entities=[drone.drone_id, mission.project_id]
            ))
        
        # 4. Weather compatibility
        if not drone.can_fly_in_weather(mission.weather_forecast):
            warnings.append(ConflictWarning(
                type="weather_incompatible",
                severity="error",
                message=f"Drone {drone.drone_id} ({drone.model}) with weather resistance '{drone.weather_resistance}' cannot operate in {mission.weather_forecast} conditions for mission {mission.project_id}",
                affected_entities=[drone.drone_id, mission.project_id]
            ))
        
        # 5. Location mismatch
        if drone.location.lower() != mission.location.lower():
            warnings.append(ConflictWarning(
                type="location_mismatch",
                severity="warning",
                message=f"Drone {drone.drone_id} ({drone.model}) is in {drone.location} but mission {mission.project_id} is in {mission.location}",
                affected_entities=[drone.drone_id, mission.project_id]
            ))
        
        return warnings
    
    def _check_pilot_double_booking(self, pilot: Pilot, mission: Mission) -> Optional[ConflictWarning]:
        """Check if pilot is double-booked on overlapping missions"""
        for other_mission in self.dm.get_all_missions():
            if other_mission.project_id == mission.project_id:
                continue
            
            if other_mission.assigned_pilot != pilot.pilot_id:
                continue
            
            # Check for date overlap
            if self._dates_overlap(mission.start_date, mission.end_date,
                                  other_mission.start_date, other_mission.end_date):
                return ConflictWarning(
                    type="double_booking",
                    severity="error",
                    message=f"Pilot {pilot.name} ({pilot.pilot_id}) is double-booked: Mission {mission.project_id} ({mission.start_date} to {mission.end_date}) overlaps with Mission {other_mission.project_id} ({other_mission.start_date} to {other_mission.end_date})",
                    affected_entities=[pilot.pilot_id, mission.project_id, other_mission.project_id]
                )
        
        return None
    
    def _check_drone_double_booking(self, drone: Drone, mission: Mission) -> Optional[ConflictWarning]:
        """Check if drone is double-booked on overlapping missions"""
        for other_mission in self.dm.get_all_missions():
            if other_mission.project_id == mission.project_id:
                continue
            
            if other_mission.assigned_drone != drone.drone_id:
                continue
            
            # Check for date overlap
            if self._dates_overlap(mission.start_date, mission.end_date,
                                  other_mission.start_date, other_mission.end_date):
                return ConflictWarning(
                    type="double_booking",
                    severity="error",
                    message=f"Drone {drone.drone_id} ({drone.model}) is double-booked: Mission {mission.project_id} ({mission.start_date} to {mission.end_date}) overlaps with Mission {other_mission.project_id} ({other_mission.start_date} to {other_mission.end_date})",
                    affected_entities=[drone.drone_id, mission.project_id, other_mission.project_id]
                )
        
        return None
    
    def _check_pilot_skill_mismatch(self, pilot: Pilot, mission: Mission) -> List[ConflictWarning]:
        """Check if pilot has required skills for mission"""
        warnings = []
        pilot_skills_lower = [s.lower() for s in pilot.skills]
        
        for required_skill in mission.required_skills:
            if not any(required_skill.lower() in ps for ps in pilot_skills_lower):
                warnings.append(ConflictWarning(
                    type="skill_mismatch",
                    severity="error",
                    message=f"Pilot {pilot.name} ({pilot.pilot_id}) lacks required skill '{required_skill}' for mission {mission.project_id}. Pilot skills: {', '.join(pilot.skills)}",
                    affected_entities=[pilot.pilot_id, mission.project_id]
                ))
        
        return warnings
    
    def _check_pilot_certification_mismatch(self, pilot: Pilot, mission: Mission) -> List[ConflictWarning]:
        """Check if pilot has required certifications for mission"""
        warnings = []
        pilot_certs_lower = [c.lower() for c in pilot.certifications]
        
        for required_cert in mission.required_certs:
            if not any(required_cert.lower() in pc for pc in pilot_certs_lower):
                warnings.append(ConflictWarning(
                    type="certification_mismatch",
                    severity="error",
                    message=f"Pilot {pilot.name} ({pilot.pilot_id}) lacks required certification '{required_cert}' for mission {mission.project_id}. Pilot certifications: {', '.join(pilot.certifications)}",
                    affected_entities=[pilot.pilot_id, mission.project_id]
                ))
        
        return warnings
    
    def _check_budget_overrun(self, pilot: Pilot, mission: Mission) -> Optional[ConflictWarning]:
        """Check if pilot cost exceeds mission budget"""
        duration = mission.get_duration_days()
        total_cost = pilot.daily_rate_inr * duration
        
        if total_cost > mission.mission_budget_inr:
            return ConflictWarning(
                type="budget_overrun",
                severity="warning",
                message=f"Budget overrun for mission {mission.project_id}: Pilot {pilot.name} ({pilot.pilot_id}) costs ₹{total_cost} ({pilot.daily_rate_inr}/day × {duration} days) but mission budget is ₹{mission.mission_budget_inr}",
                affected_entities=[pilot.pilot_id, mission.project_id]
            )
        
        return None
    
    def _check_pilot_drone_location_mismatch(self, pilot_id: str, drone_id: str, 
                                             mission: Mission) -> List[ConflictWarning]:
        """Check if pilot and drone are in different locations"""
        warnings = []
        pilot = self.dm.get_pilot_by_id(pilot_id)
        drone = self.dm.get_drone_by_id(drone_id)
        
        if pilot and drone and pilot.location.lower() != drone.location.lower():
            warnings.append(ConflictWarning(
                type="equipment_pilot_location_mismatch",
                severity="warning",
                message=f"Pilot {pilot.name} ({pilot_id}) is in {pilot.location} but assigned drone {drone_id} ({drone.model}) is in {drone.location} for mission {mission.project_id}",
                affected_entities=[pilot_id, drone_id, mission.project_id]
            ))
        
        return warnings
    
    def check_maintenance_warnings(self) -> List[ConflictWarning]:
        """Check for drones with upcoming maintenance"""
        warnings = []
        today = date.today()
        
        for drone in self.dm.get_all_drones():
            days_until_maintenance = (drone.maintenance_due - today).days
            
            if days_until_maintenance <= 0:
                warnings.append(ConflictWarning(
                    type="maintenance_overdue",
                    severity="error",
                    message=f"Drone {drone.drone_id} ({drone.model}) has overdue maintenance (was due {drone.maintenance_due})",
                    affected_entities=[drone.drone_id]
                ))
            elif days_until_maintenance <= 7:
                warnings.append(ConflictWarning(
                    type="maintenance_upcoming",
                    severity="info",
                    message=f"Drone {drone.drone_id} ({drone.model}) has maintenance due in {days_until_maintenance} days ({drone.maintenance_due})",
                    affected_entities=[drone.drone_id]
                ))
        
        return warnings
    
    def check_pilot_availability_issues(self) -> List[ConflictWarning]:
        """Check for pilot availability issues"""
        warnings = []
        today = date.today()
        
        # Check for pilots on extended leave
        for pilot in self.dm.get_all_pilots():
            if pilot.status == PilotStatus.ON_LEAVE:
                days_until_available = (pilot.available_from - today).days
                if days_until_available > 7:
                    warnings.append(ConflictWarning(
                        type="extended_leave",
                        severity="info",
                        message=f"Pilot {pilot.name} ({pilot.pilot_id}) is on leave until {pilot.available_from} ({days_until_available} days)",
                        affected_entities=[pilot.pilot_id]
                    ))
        
        return warnings
    
    def validate_assignment(self, mission_id: str, pilot_id: Optional[str] = None,
                           drone_id: Optional[str] = None) -> List[ConflictWarning]:
        """Validate a potential assignment before making it"""
        warnings = []
        mission = self.dm.get_mission_by_id(mission_id)
        
        if not mission:
            warnings.append(ConflictWarning(
                type="invalid_mission",
                severity="error",
                message=f"Mission {mission_id} does not exist",
                affected_entities=[mission_id]
            ))
            return warnings
        
        if pilot_id:
            pilot = self.dm.get_pilot_by_id(pilot_id)
            if not pilot:
                warnings.append(ConflictWarning(
                    type="invalid_pilot",
                    severity="error",
                    message=f"Pilot {pilot_id} does not exist",
                    affected_entities=[pilot_id]
                ))
            else:
                # Temporarily set assigned pilot to check conflicts
                original_assigned = mission.assigned_pilot
                mission.assigned_pilot = pilot_id
                warnings.extend(self._check_pilot_assignment_conflicts(pilot, mission))
                mission.assigned_pilot = original_assigned
        
        if drone_id:
            drone = self.dm.get_drone_by_id(drone_id)
            if not drone:
                warnings.append(ConflictWarning(
                    type="invalid_drone",
                    severity="error",
                    message=f"Drone {drone_id} does not exist",
                    affected_entities=[drone_id]
                ))
            else:
                # Temporarily set assigned drone to check conflicts
                original_assigned = mission.assigned_drone
                mission.assigned_drone = drone_id
                warnings.extend(self._check_drone_assignment_conflicts(drone, mission))
                mission.assigned_drone = original_assigned
        
        # Check pilot-drone location mismatch if both are provided
        if pilot_id and drone_id:
            pilot = self.dm.get_pilot_by_id(pilot_id)
            drone = self.dm.get_drone_by_id(drone_id)
            if pilot and drone:
                warnings.extend(self._check_pilot_drone_location_mismatch(pilot_id, drone_id, mission))
        
        return warnings
    
    def _dates_overlap(self, start1: date, end1: date, start2: date, end2: date) -> bool:
        """Check if two date ranges overlap"""
        return start1 <= end2 and start2 <= end1
    
    def get_conflict_summary(self) -> Dict[str, Any]:
        """Get a summary of all current conflicts"""
        all_warnings = self.check_all_conflicts()
        
        errors = [w for w in all_warnings if w.severity == "error"]
        warnings = [w for w in all_warnings if w.severity == "warning"]
        info = [w for w in all_warnings if w.severity == "info"]
        
        return {
            "total_issues": len(all_warnings),
            "errors": len(errors),
            "warnings": len(warnings),
            "info": len(info),
            "error_details": [{"type": w.type, "message": w.message} for w in errors],
            "warning_details": [{"type": w.type, "message": w.message} for w in warnings],
            "info_details": [{"type": w.type, "message": w.message} for w in info]
        }
