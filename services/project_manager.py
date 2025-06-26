import json
from datetime import datetime
from models import db, Project, ProjectArchive, User, UserDashboard
from db_bridge import db_bridge

class ProjectManager:
    """Handles project lifecycle with limits and archiving"""
    
    @staticmethod
    def can_create_project(user):
        """Check if user can create new project - NOW COUNTS ALL PROJECTS"""
        # Get user's TOTAL projects count (both active and completed)
        total_projects = user.projects.count()  # This counts ALL projects
        project_limit = getattr(user, 'project_limit', 5)
        
        return total_projects < project_limit
    
    @staticmethod
    def get_user_project_stats(user):
        """Get project statistics for user - Updated for total project quota"""
        projects = user.projects.all()
        active_projects = [p for p in projects if not p.is_complete]
        completed_projects = [p for p in projects if p.is_complete]
        total_projects = len(projects)  # This is what counts toward the limit
        project_limit = getattr(user, 'project_limit', 5)
        
        return {
            'total_projects': total_projects,           # All projects (what counts toward limit)
            'active_projects': len(active_projects),    # In-progress projects
            'completed_projects': len(completed_projects), # Finished projects
            'project_limit': project_limit,             # Maximum allowed (5)
            'remaining_slots': project_limit - total_projects,  # How many can still create
            'can_create_new': total_projects < project_limit   # Can create new project?
        }
    
    @staticmethod
    def archive_project(project):
        """Archive project data before deletion"""
        try:
            # Collect all project data
            archive_data = {
                'project_info': {
                    'id': project.id,
                    'name': project.project_name,
                    'created_at': project.created_at.isoformat() if project.created_at else None,
                    'completed_at': datetime.utcnow().isoformat(),
                    'total_area': project.total_area,
                    'num_apartments': project.num_apartments,
                    'num_rooms': project.num_rooms,
                    'design_waste_percent': project.design_waste_percent,
                    'optimized_waste_percent': project.optimized_waste_percent,
                    'actual_waste_percent': project.actual_waste_percent
                },
                'rooms': [],
                'optimization_results': []
            }
            
            # Archive room data
            for room in project.rooms:
                room_data = {
                    'room_name': ProjectManager._anonymize_text(room.room_name),
                    'apartment_name': ProjectManager._anonymize_text(room.apartment_name),
                    'area': room.area,
                    'perimeter': room.perimeter,
                    'num_vertices': room.num_vertices,
                    'is_rectangular': room.is_rectangular,
                    'aspect_ratio': room.aspect_ratio,
                    'tile_configs': []
                }
                
                # Archive tile configurations
                for config in room.tile_configs:
                    room_data['tile_configs'].append({
                        'tile_size': f"{config.tile_width}x{config.tile_height}",
                        'grout_thickness': config.grout_thickness,
                        'total_tiles': config.total_tiles,
                        'full_tiles': config.full_tiles,
                        'cut_tiles': config.cut_tiles,
                        'full_tile_ratio': config.full_tile_ratio,
                        'cut_tile_ratio': config.cut_tile_ratio
                    })
                
                archive_data['rooms'].append(room_data)
            
            # Archive optimization results
            for result in project.optimization_results:
                archive_data['optimization_results'].append({
                    'design_waste_percent': result.design_waste_percent,
                    'optimized_waste_percent': result.optimized_waste_percent,
                    'improvement_percent': result.improvement_percent,
                    'matched_cuts': result.matched_cuts,
                    'unmatched_cuts': result.unmatched_cuts
                })
            
            # Create archive record
            archive_json = json.dumps(archive_data, indent=2)
            archive = ProjectArchive(
                original_project_id=project.id,
                user_id=project.user_id,
                project_name=project.project_name,
                data_json=archive_json,
                file_size_mb=len(archive_json) / (1024 * 1024),
                anonymized=True
            )
            
            db.session.add(archive)
            db.session.commit()
            
            # Log activity
            db_bridge.log_activity(
                project.user_id, 
                project.id, 
                'project_archived', 
                f'Project {project.project_name} archived for AI training'
            )
            
            return True
            
        except Exception as e:
            print(f"Error archiving project {project.id}: {str(e)}")
            return False
    
    @staticmethod
    def _anonymize_text(text):
        """Remove potentially identifying information"""
        if not text:
            return text
            
        import re
        # Remove apartment numbers, unit numbers, etc.
        text = re.sub(r'\b(apt|apartment|unit|flat|suite)\s*#?\s*\d+\w?\b', 'unit_xxx', text, flags=re.I)
        text = re.sub(r'\b\d{1,3}[a-z]?\b', 'xxx', text)  # Remove door numbers
        text = re.sub(r'\b(floor|level)\s*\d+\b', 'floor_x', text, flags=re.I)
        
        return text
    
    @staticmethod
    def delete_project(project_id, archive=True):
        """Delete project with optional archiving"""
        project = Project.query.get(project_id)
        if not project:
            return False
        
        # Archive if requested
        if archive:
            ProjectManager.archive_project(project)
        
        # Delete project (cascades to related data)
        db.session.delete(project)
        db.session.commit()
        
        # Update user dashboard
        ProjectManager.update_user_dashboard(project.user_id)
        
        return True
    
    @staticmethod
    def update_user_dashboard(user_id):
        """Update user dashboard statistics"""
        user = User.query.get(user_id)
        if not user:
            return
        
        # Get or create dashboard
        dashboard = UserDashboard.query.filter_by(user_id=user_id).first()
        if not dashboard:
            dashboard = UserDashboard(user_id=user_id)
            db.session.add(dashboard)
        
        # Calculate statistics
        projects = user.projects.filter_by(is_complete=True).all()
        
        total_area = sum(p.total_area or 0 for p in projects)
        dashboard.total_area_optimized = total_area
        
        # Calculate average waste reduction
        waste_reductions = []
        for p in projects:
            if p.design_waste_percent and p.optimized_waste_percent:
                reduction = p.design_waste_percent - p.optimized_waste_percent
                waste_reductions.append(reduction)
        
        dashboard.average_waste_reduction = sum(waste_reductions) / len(waste_reductions) if waste_reductions else 0
        dashboard.projects_completed = len(projects)
        dashboard.last_updated = datetime.utcnow()
        
        db.session.commit()