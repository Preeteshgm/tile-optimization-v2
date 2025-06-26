import json
import pandas as pd
from flask import session
from models import db, Project
from datetime import datetime

class SessionDataManager:
    """Manages saving and restoring session data to/from database"""
    
    # Define which session keys belong to each step
    STEP_SESSION_KEYS = {
        1: ['rooms_data', 'start_points_data', 'tile_sizes', 'cluster_plot', 
            'room_df', 'room_polygons', 'uploaded_file'],
        2: ['final_room_df', 'apartments_data', 'apartment_orientations'],
        3: ['apartments_data', 'apartment_orientations'],
        4: ['tile_analysis_results', 'apartments_data'],
        5: ['tile_classification_results', 'tile_analysis_results'],
        6: ['small_tiles_results', 'tile_polygon_mapping', 'tiles_remaining', 'small_tiles_removed'],
        7: ['export_results', 'tiles_remaining', 'small_tiles_removed'],
        8: ['matching_history', 'current_matching', 'cut_pieces_by_half'],
        9: ['final_reports', 'export_files']
    }
    
    @staticmethod
    def save_step_data(project_id, step_number, auto_save=True):
        """Save current session data for a specific step to database"""
        try:
            project = Project.query.get(project_id)
            if not project:
                print(f"Project {project_id} not found")
                return False
            
            # Get session keys for this step
            session_keys = SessionDataManager.STEP_SESSION_KEYS.get(step_number, [])
            
            # Collect session data
            step_data = {}
            for key in session_keys:
                if key in session:
                    value = session[key]
                    # Convert pandas DataFrames to dict for JSON storage
                    if isinstance(value, pd.DataFrame):
                        step_data[key] = value.to_dict('records')
                    else:
                        step_data[key] = value
            
            # Store in appropriate database field
            setattr(project, f'step{step_number}_session_data', step_data)
            
            # Mark step as complete
            setattr(project, f'step{step_number}_complete', True)
            project.current_step = max(project.current_step, step_number)
            project.updated_at = datetime.utcnow()
            
            db.session.commit()
            print(f"Step {step_number} data saved to database ({'auto' if auto_save else 'manual'} save)")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Error saving step {step_number} data: {str(e)}")
            return False
    
    @staticmethod
    def restore_step_data(project_id, step_number):
        """Restore session data for a specific step from database"""
        try:
            project = Project.query.get(project_id)
            if not project:
                print(f"Project {project_id} not found")
                return False
            
            # Get stored data
            step_data = getattr(project, f'step{step_number}_session_data', None)
            if not step_data:
                print(f"No stored data found for step {step_number}")
                return False
            
            # Restore data to session
            for key, value in step_data.items():
                session[key] = value
            
            # Also restore project metadata to session
            session['project_id'] = project.id
            session['project_name'] = project.project_name
            
            print(f"Step {step_number} data restored to session")
            return True
            
        except Exception as e:
            print(f"Error restoring step {step_number} data: {str(e)}")
            return False
    
    @staticmethod
    def restore_all_completed_steps(project_id):
        """Restore session data for all completed steps of a project"""
        try:
            project = Project.query.get(project_id)
            if not project:
                print(f"Project {project_id} not found")
                return False
            
            # Restore data for each completed step in order
            restored_steps = []
            for step in range(1, 10):
                if getattr(project, f'step{step}_complete', False):
                    if SessionDataManager.restore_step_data(project_id, step):
                        restored_steps.append(step)
            
            print(f"Restored data for steps: {restored_steps}")
            return len(restored_steps) > 0
            
        except Exception as e:
            print(f"Error restoring all step data: {str(e)}")
            return False
    
    @staticmethod
    def auto_save_current_step(project_id):
        """Auto-save current step based on what's in session"""
        try:
            project = Project.query.get(project_id)
            if not project:
                return False
            
            current_step = project.current_step
            return SessionDataManager.save_step_data(project_id, current_step, auto_save=True)
            
        except Exception as e:
            print(f"Error in auto-save: {str(e)}")
            return False