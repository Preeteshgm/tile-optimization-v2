from models import db, Project, Room, TileConfig, OptimizationResult, ActivityLog
import json
from datetime import datetime

class DatabaseBridge:
    """Bridge between session storage and database"""
    
    def __init__(self, app=None):
        self.app = app
    
    def init_app(self, app):
        self.app = app
    
    def get_or_create_project(self, user_id, project_name=None):
        """Get current project or return None - DON'T auto-create projects"""
        # Check for incomplete project
        project = Project.query.filter_by(
            user_id=user_id,
            is_complete=False
        ).order_by(Project.created_at.desc()).first()
        
        # Return existing project if found
        if project:
            return project
        
        # Don't auto-create projects anymore
        # Force users to go through new_project form
        return None
    
    def save_rooms_from_session(self, project_id, rooms_data):
        """Save rooms from session format to database"""
        saved_rooms = {}
        
        for room_name, room_data in rooms_data.items():
            # Check if room exists
            room = Room.query.filter_by(
                project_id=project_id,
                room_name=room_name
            ).first()
            
            if not room:
                room = Room(
                    project_id=project_id,
                    room_name=room_name,
                    apartment_name=room_data.get('apartment_name', 'Unknown')
                )
                db.session.add(room)
            
            # Update room data
            if 'area' in room_data:
                room.area = room_data['area']
            if 'perimeter' in room_data:
                room.perimeter = room_data['perimeter']
            if 'num_vertices' in room_data:
                room.num_vertices = room_data['num_vertices']
            
            saved_rooms[room_name] = room
        
        db.session.commit()
        return saved_rooms
    
    def log_activity(self, user_id, project_id, action, details=None):
        """Log user activity"""
        log = ActivityLog(
            user_id=user_id,
            project_id=project_id,
            action=action,
            details=details
        )
        db.session.add(log)
        db.session.commit()

# Global instance
db_bridge = DatabaseBridge()