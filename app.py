from flask import Flask, render_template, request, make_response, request, jsonify, session, redirect, url_for, flash, send_file
from flask_session import Session
import os

import tempfile
import base64
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import json
import re
from functools import wraps
import click
import hashlib

from dotenv import load_dotenv
import config  # Simple config file

load_dotenv()

from werkzeug.utils import secure_filename
from shapely.geometry import Polygon, Point, MultiPolygon
from datetime import datetime, timedelta

from functools import wraps

# Import processors
from processors.CustomDxfProcessor import CustomDxfProcessor
from processors.VisualizationProcessor import VisualizationProcessor
from processors.RoomClusterProcessor import RoomClusterProcessor
from processors.TileProcessor import TileProcessor
from processors.MatchingProcessor import MatchingProcessor
from processors.ExportProcessor import ExportProcessor
from processors.DataPreparationProcessor import DataPreparationProcessor

# Add these new imports
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Import your new database components
from models import db, User, Project, Room, TileConfig, OptimizationResult, ActivityLog, ProjectArchive, UserDashboard, ProjectFile
from db_bridge import db_bridge
from services.project_manager import ProjectManager
from services.session_data_manager import SessionDataManager

# Define the NumpyEncoder class first
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict('records')
        return super(NumpyEncoder, self).default(obj)

# Create Flask app
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# NOW set the JSON encoder after app is defined
app.json_encoder = NumpyEncoder

# Configure server-side sessions
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(tempfile.gettempdir(), 'flask_session')
app.config['SESSION_PERMANENT'] = True  # Changed to True
app.config['SESSION_USE_SIGNER'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # Add this
app.config['SESSION_KEY_PREFIX'] = 'tile_app:'  # Add this

Session(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_url()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
db_bridge.init_app(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_request
def manage_session():
    """Better session management"""
    # Only make session permanent for authenticated users
    if current_user.is_authenticated:
        session.permanent = True
    else:
        session.permanent = False

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('You need admin privileges to access this page.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Upload folder configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize processors as global objects
dxf_processor = CustomDxfProcessor()
cluster_processor = RoomClusterProcessor(eps=7500, min_samples=1)
visualizer = VisualizationProcessor()
tile_processor = TileProcessor()
matching_processor = MatchingProcessor()
export_processor = ExportProcessor()
data_prep_processor = DataPreparationProcessor()

def check_credentials(username, password):
    """Check if username/password combination is valid using database"""
    user = User.query.filter_by(username=username).first()
    
    if user and check_password_hash(user.password_hash, password):
        return user
    
    # Migration period: Create default admin user if no users exist
    if User.query.count() == 0 and username == 'admin' and password == 'admin123':
        try:
            # Create initial admin user
            admin_user = User(
                username='admin',
                email='admin@tileoptimization.com',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin_user)
            db.session.commit()
            
            print("Created initial admin user")
            return admin_user
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating initial admin user: {e}")
    
    return None

@app.route('/')
def home():
    """Combined home/login page - No authentication required"""
    # If user is already logged in, redirect to their portal
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    # Check for logout message cookie
    logout_message = request.cookies.get('logout_message')
    if logout_message:
        flash(logout_message, 'success')
    
    return render_template('login.html')

@app.route('/portal')
@login_required
def index():
    """Enhanced landing page with session management"""
    try:
        # Clean up old files and abandoned projects
        cleanup_old_uploaded_files()
        cleanup_abandoned_projects()
        
        # Check if there's project data
        project_exists = has_project_data()
        
        # Check for active project in database (less than 24 hours old)
        if current_user.is_authenticated:
            active_project = Project.query.filter_by(
                user_id=current_user.id,
                is_complete=False
            ).filter(
                Project.created_at > datetime.utcnow() - timedelta(hours=24)
            ).first()
            
            if active_project:
                project_exists = True
                session['project_id'] = active_project.id
        
        return render_template('landing.html', 
                             project_exists=project_exists,
                             username=current_user.username if current_user.is_authenticated else None)
    except Exception as e:
        print(f"Error in index: {e}")
        return render_template('landing.html', 
                             project_exists=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page handler"""
    # If user is already logged in, redirect to their portal
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = check_credentials(username, password)
        if user:
            # Use flask_login to handle session
            login_user(user, remember=True)
            
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Log activity
            db_bridge.log_activity(user.id, None, 'user_login', f'User {username} logged in')
            
            # Check for incomplete project
            project = Project.query.filter_by(
                user_id=user.id,
                is_complete=False
            ).order_by(Project.created_at.desc()).first()
            
            if project:
                # Load project to session if exists
                flash(f'Resuming project: {project.project_name}', 'info')
                session['project_id'] = project.id
                return redirect(url_for(f'step{project.current_step}'))
            
            # Redirect to originally requested page or main portal
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))  # Go to authenticated landing page
        else:
            flash('Invalid username or password', 'error')
            # Return to home page (which shows login form)
            return redirect(url_for('home'))
    
    # For GET requests, redirect to home page
    return redirect(url_for('home'))

@app.route('/logout')
@login_required  
def logout():
    """Logout and redirect to home/login page"""
    if current_user.is_authenticated:
        db_bridge.log_activity(current_user.id, None, 'user_logout', 'User logged out')
    
    logout_user()
    session.clear()
    
    # Create response with proper cache control headers
    response = make_response(redirect('/'))
    
    # Set logout message cookie
    response.set_cookie('logout_message', 'You have been logged out successfully.', max_age=5)
    
    # Add cache control headers to prevent caching
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    # Clear any authentication cookies
    response.set_cookie('remember_token', '', expires=0)
    response.set_cookie('session', '', expires=0)
    
    return response

@app.after_request
def after_request(response):
    """Ensure responses aren't cached for authenticated pages"""
    if current_user.is_authenticated:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Allow logged-in users to change their password"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Verify current password
        if not check_password_hash(current_user.password_hash, current_password):
            flash('Current password is incorrect', 'error')
        elif new_password != confirm_password:
            flash('New passwords do not match', 'error')
        elif len(new_password) < 6:
            flash('New password must be at least 6 characters', 'error')
        else:
            try:
                # Update password in database
                current_user.password_hash = generate_password_hash(new_password)
                db.session.commit()
                
                # Log the password change
                db_bridge.log_activity(
                    current_user.id, 
                    None, 
                    'password_changed', 
                    'User changed their password'
                )
                
                flash('Password changed successfully', 'success')
                return redirect(url_for('index'))
                
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Error changing password for user {current_user.id}: {str(e)}')
                flash('An error occurred while changing password. Please try again.', 'error')
    
    return render_template('change_password.html')

def clear_project_data_only():
    """Clear project data and DELETE incomplete projects - USE CAREFULLY"""
    from services.project_manager import ProjectManager
    
    # Clear session project data
    project_keys = [
        'rooms_data', 'start_points_data', 'tile_sizes', 'cluster_plot',
        'room_df', 'room_polygons', 'final_room_df', 'apartments_data',
        'tile_analysis_results', 'tile_classification_results',
        'small_tiles_results', 'tile_polygon_mapping', 'tiles_remaining',
        'small_tiles_removed', 'export_results', 'cut_pieces_by_half',
        'matching_history', 'current_matching', 'step7_complete',
        'project_id', 'uploaded_file', 'dxf_data', 'step1_complete',
        'step2_complete', 'step3_complete', 'step4_complete', 'step5_complete',
        'step6_complete', 'step8_complete', 'step9_complete'
    ]
    
    # If there's a project in session, mark it as abandoned
    if 'project_id' in session and current_user.is_authenticated:
        project_id = session['project_id']
        project = Project.query.get(project_id)
        
        if project:
            # Archive the project before deletion (for AI training)
            try:
                ProjectManager.archive_project(project)
                print(f"Project {project_id} archived successfully")
            except Exception as e:
                print(f"Failed to archive project {project_id}: {str(e)}")
            
            # Delete the incomplete project and all related data
            if not project.is_complete:
                db.session.delete(project)  # This will cascade delete rooms, configs, etc.
                db.session.commit()
                
                # Update user dashboard statistics
                try:
                    ProjectManager.update_user_dashboard(current_user.id)
                except Exception as e:
                    print(f"Failed to update dashboard: {str(e)}")
    
    # Clear all project-related session data
    for key in project_keys:
        session.pop(key, None)
    
    # Clear any uploaded files
    if 'uploaded_file' in session:
        try:
            filepath = session.get('uploaded_file')
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
                print(f"Removed uploaded file: {filepath}")
        except Exception as e:
            print(f"Error removing file: {str(e)}")
    
    print("Project data cleared and incomplete project deleted from database")

def cleanup_abandoned_projects():
    """Clean up projects that haven't been completed within 24 hours"""
    if current_user.is_authenticated:
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        # Find and delete old incomplete projects
        old_projects = Project.query.filter(
            Project.user_id == current_user.id,
            Project.is_complete == False,
            Project.created_at < cutoff_time
        ).all()
        
        for project in old_projects:
            db.session.delete(project)
            print(f"Cleaned up abandoned project: {project.id}")
        
        if old_projects:
            db.session.commit()

    
@app.errorhandler(404)
def not_found_error(error):
    """Custom 404 page using your existing error.html"""
    return render_template('error.html', 
                         error_code=404,
                         error_message="Page Not Found",
                         error_description="The page you're looking for doesn't exist or has been moved."), 404

@app.errorhandler(500)
def internal_error(error):
    """Custom 500 page using your existing error.html"""
    db.session.rollback()
    return render_template('error.html',
                         error_code=500, 
                         error_message="Internal Server Error",
                         error_description="Something went wrong on our end. Please try again later."), 500

@app.errorhandler(403)
def forbidden_error(error):
    """Custom 403 page using your existing error.html"""
    return render_template('error.html',
                         error_code=403, 
                         error_message="Access Forbidden",
                         error_description="You don't have permission to access this resource."), 403

@app.route('/admin_panel', methods=['GET', 'POST'])
@admin_required
def admin_panel():
    """Admin panel with user management and project overview"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_user':
            # Handle new user creation
            new_username = request.form.get('new_username', '').strip()
            new_email = request.form.get('new_email', '').strip()
            new_password = request.form.get('new_password', '')
            new_role = request.form.get('new_role', 'user')
            
            # Validation
            if not new_username or not new_email or not new_password:
                flash('All fields are required for new user', 'error')
            elif len(new_password) < 6:
                flash('Password must be at least 6 characters', 'error')
            elif User.query.filter_by(username=new_username).first():
                flash(f'Username {new_username} already exists', 'error')
            elif User.query.filter_by(email=new_email).first():
                flash(f'Email {new_email} already in use', 'error')
            else:
                try:
                    # Create new user
                    new_user = User(
                        username=new_username,
                        email=new_email,
                        password_hash=generate_password_hash(new_password),
                        role=new_role
                    )
                    db.session.add(new_user)
                    db.session.commit()
                    
                    # Log activity
                    db_bridge.log_activity(
                        current_user.id,
                        None,
                        'user_created',
                        f'Admin created new user: {new_username}'
                    )
                    
                    flash(f'User {new_username} created successfully!', 'success')
                    return redirect(url_for('admin_panel'))
                    
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error creating user: {str(e)}', 'error')
        
        elif action == 'delete_project':
            # Handle project deletion
            project_id = request.form.get('project_id')
            project = Project.query.get(project_id)
            
            if project:
                project_name = project.project_name
                username = project.user.username
                
                try:
                    # Archive and delete project
                    from services.project_manager import ProjectManager
                    ProjectManager.delete_project(project_id, archive=True)
                    
                    # Log activity
                    db_bridge.log_activity(
                        current_user.id,
                        None,
                        'project_deleted_by_admin',
                        f'Admin deleted project "{project_name}" from user {username}'
                    )
                    
                    flash(f'Project "{project_name}" deleted successfully', 'success')
                except Exception as e:
                    flash(f'Error deleting project: {str(e)}', 'error')
            
            return redirect(url_for('admin_panel'))
        
        else:
            # Handle existing user actions (make_admin, remove_admin, delete_user)
            username = request.form.get('username')
            
            user = User.query.filter_by(username=username).first()
            if user and user.id != current_user.id:
                if action == 'make_admin':
                    user.role = 'admin'
                    flash(f'{username} is now an admin!', 'success')
                elif action == 'remove_admin':
                    user.role = 'user'
                    flash(f'{username} admin privileges removed.', 'info')
                elif action == 'delete_user':
                    db.session.delete(user)
                    flash(f'User {username} deleted.', 'warning')
                
                db.session.commit()
                return redirect(url_for('admin_panel'))
    
    # Get all users with project counts
    all_users = User.query.all()
    users = []
    
    for u in all_users:
        # Get actual project counts
        total_projects = u.projects.count() if hasattr(u, 'projects') else 0
        active_projects = u.projects.filter_by(is_complete=False).count() if hasattr(u, 'projects') else 0
        
        users.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'role': u.role,
            'status': getattr(u, 'status', 'active'),
            'project_limit': getattr(u, 'project_limit', 5),
            'created_at': u.created_at.isoformat() if u.created_at else None,
            'last_login': u.last_login.isoformat() if u.last_login else None,
            'total_projects': total_projects,
            'active_projects': active_projects,
            'can_delete': u.id != current_user.id  # Can't delete yourself
        })
    
    # Get all projects with detailed information
    all_projects = Project.query.order_by(Project.created_at.desc()).all()
    projects = []
    
    for p in all_projects:
        # Calculate project progress
        steps_complete = sum([
            p.step1_complete, p.step2_complete, p.step3_complete,
            p.step4_complete, p.step5_complete, p.step6_complete,
            p.step7_complete, p.step8_complete, p.step9_complete
        ])
        progress_percentage = (steps_complete / 9) * 100
        
        projects.append({
            'id': p.id,
            'project_name': p.project_name,
            'username': p.user.username,
            'user_id': p.user_id,
            'created_at': p.created_at.isoformat() if p.created_at else None,
            'updated_at': p.updated_at.isoformat() if p.updated_at else None,
            'is_complete': p.is_complete,
            'current_step': p.current_step,
            'progress': progress_percentage,
            'total_area': p.total_area,
            'num_apartments': p.num_apartments or 0,
            'num_rooms': p.num_rooms or 0,
            'design_waste': p.design_waste_percent,
            'optimized_waste': p.optimized_waste_percent,
            'waste_reduction': (p.design_waste_percent - p.optimized_waste_percent) if p.design_waste_percent and p.optimized_waste_percent else None
        })
    
    # Calculate statistics
    total_users = len(users)
    admin_users = len([u for u in users if u['role'] == 'admin'])
    total_projects = len(projects)
    active_projects_total = len([p for p in projects if not p['is_complete']])
    completed_projects = len([p for p in projects if p['is_complete']])
    
    # Calculate average waste reduction for completed projects
    waste_reductions = [p['waste_reduction'] for p in projects if p['waste_reduction'] is not None]
    avg_waste_reduction = sum(waste_reductions) / len(waste_reductions) if waste_reductions else 0
    
    stats = {
        'total_users': total_users,
        'admin_users': admin_users,
        'regular_users': total_users - admin_users,
        'total_projects': total_projects,
        'active_projects': active_projects_total,
        'completed_projects': completed_projects,
        'avg_waste_reduction': round(avg_waste_reduction, 2)
    }
    
    return render_template('admin_panel.html', 
                         users=users, 
                         projects=projects,
                         stats=stats)

# Add this dummy register route right after admin_panel
@app.route('/register')
def register():
    """Registration redirect - Contact admin"""
    flash('Registration is not available. Please contact the administrator for access.', 'info')
    return redirect(url_for('login'))

@app.route('/user_dashboard')
@login_required
def user_dashboard():
    """Enhanced user dashboard with detailed statistics - PRESERVES PROJECTS"""
    from services.project_manager import ProjectManager
    
    # ONLY clear session data, DO NOT delete projects
    clear_session_data_only()
    
    # Get project statistics
    stats = ProjectManager.get_user_project_stats(current_user)
    
    # Get user's projects - INCLUDING INCOMPLETE ONES
    projects = current_user.projects.order_by(Project.created_at.desc()).limit(10).all()
    
    # Calculate detailed statistics
    total_area_optimized = 0
    total_apartments = 0
    total_rooms = 0
    waste_reductions = []
    design_waste_percentages = []
    optimized_waste_percentages = []
    
    for project in projects:
        if project.total_area:
            total_area_optimized += project.total_area
        if project.num_apartments:
            total_apartments += project.num_apartments
        if project.num_rooms:
            total_rooms += project.num_rooms
        
        # Calculate waste reduction
        if project.design_waste_percent and project.optimized_waste_percent:
            design_waste_percentages.append(project.design_waste_percent)
            optimized_waste_percentages.append(project.optimized_waste_percent)
            reduction = project.design_waste_percent - project.optimized_waste_percent
            waste_reductions.append(reduction)
    
    # Calculate averages
    avg_design_waste = round(sum(design_waste_percentages) / len(design_waste_percentages), 2) if design_waste_percentages else 0
    avg_optimized_waste = round(sum(optimized_waste_percentages) / len(optimized_waste_percentages), 2) if optimized_waste_percentages else 0
    avg_waste_reduction = round(sum(waste_reductions) / len(waste_reductions), 2) if waste_reductions else 0
    
    # Calculate total tiles saved (estimate based on waste reduction)
    tiles_saved_estimate = 0
    if avg_waste_reduction > 0 and total_area_optimized > 0:
        # Assuming 600x600mm tiles (0.36 m² per tile)
        tile_area = 0.36
        tiles_saved_estimate = int((total_area_optimized * avg_waste_reduction / 100) / tile_area)
    
    # Update stats dictionary
    stats.update({
        'total_area_optimized': round(total_area_optimized, 2),
        'average_waste_reduction': avg_waste_reduction,
        'projects_completed': len([p for p in projects if p.is_complete]),
        'total_apartments': total_apartments,
        'total_rooms': total_rooms,
        'avg_design_waste': avg_design_waste,
        'avg_optimized_waste': avg_optimized_waste,
        'tiles_saved_estimate': tiles_saved_estimate
    })
    
    # Get recent activity
    recent_activity = ActivityLog.query.filter_by(user_id=current_user.id)\
                                     .order_by(ActivityLog.created_at.desc())\
                                     .limit(5).all()
    
    return render_template('user_dashboard.html', 
                         projects=projects,
                         stats=stats,
                         recent_activity=recent_activity)

@app.route('/delete_project/<int:project_id>', methods=['POST'])
@login_required
def delete_project(project_id):
    """Delete a project with archiving - Fixed to handle AJAX properly"""
    try:
        from services.project_manager import ProjectManager
        
        project = Project.query.get_or_404(project_id)
        
        # Check ownership
        if project.user_id != current_user.id and current_user.role != 'admin':
            # For AJAX requests, return JSON error
            return jsonify({'error': 'Unauthorized access to project'}), 403
        
        project_name = project.project_name
        
        # Archive and delete
        if ProjectManager.delete_project(project_id, archive=True):
            success_message = f'Project "{project_name}" deleted successfully. Your data has been anonymized and saved for improvement purposes.'
            
            # Always return JSON for AJAX requests
            return jsonify({
                'success': True, 
                'message': success_message,
                'redirect': url_for('user_dashboard')
            })
        else:
            return jsonify({'error': 'Failed to delete project'}), 500
            
    except Exception as e:
        # Log the error for debugging
        app.logger.error(f'Error deleting project {project_id}: {str(e)}')
        return jsonify({'error': f'Error deleting project: {str(e)}'}), 500

@app.route('/check_project_limit')
@login_required
def check_project_limit():
    """Check if user can create new project"""
    from services.project_manager import ProjectManager
    
    can_create = ProjectManager.can_create_project(current_user)
    stats = ProjectManager.get_user_project_stats(current_user)
    
    return jsonify({
        'can_create': can_create,
        'active_projects': stats['active_projects'],
        'project_limit': stats['project_limit'],
        'remaining_slots': stats['remaining_slots']
    })

@app.route('/step1', methods=['GET', 'POST'])
@login_required
def step1():
    from services.project_manager import ProjectManager
    
    # Check project limit
    if not ProjectManager.can_create_project(current_user):
        stats = ProjectManager.get_user_project_stats(current_user)
        flash(f'You have reached your project limit ({stats["project_limit"]} projects). Please delete an existing project to create a new one.', 'warning')
        return redirect(url_for('user_dashboard'))

    """Step 1: Load DXF, Extract Rooms, Start Points, and Tile Sizes"""
    
    # GET request - validate project exists
    if request.method == 'GET':
        cleanup_old_uploaded_files()
        
        # Check if user has a project in session
        if 'project_id' not in session:
            # Check if user has an incomplete project in database
            active_project = Project.query.filter_by(
                user_id=current_user.id,
                is_complete=False
            ).order_by(Project.created_at.desc()).first()
            
            if active_project and active_project.step1_complete:
                # Load existing project to session
                session['project_id'] = active_project.id
                session['project_name'] = active_project.project_name
                print(f"Loaded existing project: {active_project.project_name}")
            else:
                # No project exists, redirect to create one
                flash('Please create a new project before uploading DXF files', 'info')
                return redirect(url_for('new_project'))
        else:
            # Validate project exists in database
            project = Project.query.get(session['project_id'])
            if not project:
                # Project doesn't exist, clear session and redirect
                session.pop('project_id', None)
                session.pop('project_name', None)
                flash('Project not found. Please create a new project.', 'warning')
                return redirect(url_for('new_project'))
        
        return render_template('step1.html')
    
    # POST request - process DXF upload
    if request.method == 'POST':
        # Validate project exists before processing
        if 'project_id' not in session:
            return jsonify({'error': 'No active project. Please create a project first.'})
        
        project = Project.query.get(session['project_id'])
        if not project:
            return jsonify({'error': 'Project not found. Please create a new project.'})
        
        print(f"Processing DXF for project: {project.project_name}")
        
        # Check if the post request has the file part
        if 'dxf_file' not in request.files:
            return jsonify({'error': 'No file part'})
        
        file = request.files['dxf_file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'})
        
        # Save the file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Process the file
        try:
            # Use the existing project (don't create a new one)
            print(f"Using existing project: {project.project_name} (ID: {project.id})")
            
            # Set the file path in the processor
            dxf_processor.file_path = filepath
            
            # Load the DXF file
            if not dxf_processor.load_dxf():
                # Clean up file if processing failed
                cleanup_current_uploaded_file()
                return jsonify({'error': 'Failed to load DXF file'})
            
            # Calculate file hash for duplicate detection
            import hashlib
            with open(filepath, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            project.dxf_file_hash = file_hash
            
            # Extract room boundaries
            rooms = dxf_processor.extract_room_boundaries()
            
            # Extract start points
            start_points = dxf_processor.extract_start_points()
            
            # Extract tile sizes from SP layer
            tile_sizes = dxf_processor.extract_tile_sizes_from_sp(layer_name="SP")
            
            # Create initial dataframe for room boundaries
            room_data = []
            for i, room in enumerate(rooms):
                centroid = room.centroid
                room_data.append({
                    "room_id": i,
                    "centroid_x": centroid.x,
                    "centroid_y": centroid.y,
                    "polygon": room,
                })
            
            room_df = pd.DataFrame(room_data)
            
            # Create dataframe for start points
            if start_points:
                start_points_df = pd.DataFrame([
                    {
                        "centroid_x": sp['centroid'][0],
                        "centroid_y": sp['centroid'][1],
                        "tile_width": sp['width'],
                        "tile_height": sp['height'],
                        "room_id": sp.get('room_id', -1)
                    }
                    for sp in start_points
                ])
            else:
                start_points_df = pd.DataFrame()
            
            # Visualize room boundaries with start points
            room_plot_b64 = visualizer.plot_room_boundaries(rooms, start_points)
            
            # Cluster rooms into apartments
            room_df = cluster_processor.cluster_rooms(room_df['polygon'].tolist())
            apartment_names = cluster_processor.assign_default_names()
            
            # Preview clustering results
            cluster_processor.preview_clusters()
            
            # Visualize clustered apartments
            cluster_plot_b64 = visualizer.plot_clusters(room_df, use_final_names=False)
            
            # Store results for next steps
            final_room_df = room_df.copy()
            final_room_df['apartment_name'] = final_room_df['apartment_cluster'].apply(
                lambda x: f"A{x+1}"
            )
            
            # Clear existing rooms for this project (in case of re-upload)
            Room.query.filter_by(project_id=project.id).delete()
            
            # Save rooms to database
            saved_rooms = {}
            for idx, row in final_room_df.iterrows():
                # Convert area if it's in mm²
                room_area = float(row['polygon'].area)
                if room_area > 10000:  # Likely mm² if greater than 10,000
                    room_area = room_area / 1000000  # Convert mm² to m²
                
                room_obj = Room(
                    project_id=project.id,
                    room_name=f"Room_{idx}",  # Will be updated in step 2
                    apartment_name=row['apartment_name'],
                    polygon_json=json.dumps(serialize_polygon(row['polygon'])),
                    area=room_area,  # Use converted area
                    perimeter=float(row['polygon'].length),
                    bounds_json=json.dumps(list(row['polygon'].bounds)),
                    num_vertices=len(list(row['polygon'].exterior.coords)) - 1,
                    is_rectangular=is_room_rectangular(row['polygon']),
                    is_convex=row['polygon'].equals(row['polygon'].convex_hull)
                )
                db.session.add(room_obj)
                saved_rooms[idx] = room_obj
            
            # Update project metadata with proper unit conversion
            total_area_sum = 0
            for room in rooms:
                room_area = room.area
                # Check if area is likely in mm² (very large number)
                if room_area > 10000:  # Likely mm² if greater than 10,000
                    room_area = room_area / 1000000  # Convert mm² to m²
                total_area_sum += room_area
            
            project.num_rooms = len(rooms)
            project.num_apartments = len(apartment_names)
            project.total_area = total_area_sum  # Now properly converted to m²
            project.step1_complete = True
            project.current_step = 2
            project.updated_at = datetime.utcnow()
            
            # Commit all changes
            db.session.commit()
            
            print(f"Successfully processed DXF for project: {project.project_name}")
            
            # Log activity
            db_bridge.log_activity(
                current_user.id, 
                project.id, 
                'step1_complete',
                f'Loaded DXF with {len(rooms)} rooms in {len(apartment_names)} apartments'
            )
            
            # Store data in session (for compatibility)
            session['rooms_data'] = serialize_rooms(rooms)
            session['start_points_data'] = serialize_start_points(start_points)
            session['tile_sizes'] = tile_sizes
            session['cluster_plot'] = cluster_plot_b64
            session['room_df'] = final_room_df.drop('polygon', axis=1).to_dict('records')
            session['room_polygons'] = serialize_rooms(final_room_df['polygon'].tolist())
            
            # Return results
            return jsonify({
                'room_count': len(rooms),
                'apartment_count': len(apartment_names),
                'start_point_count': len(start_points),
                'tile_sizes': tile_sizes,
                'room_plot': room_plot_b64,
                'cluster_plot': cluster_plot_b64,
                'project_id': project.id,  # Include project ID in response
                'project_name': project.project_name  # Include project name
            })
            
        except Exception as e:
            # Clean up file if there was an error
            cleanup_current_uploaded_file()
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error processing DXF file: {str(e)}'})

@app.route('/step2', methods=['GET', 'POST'])
@login_required
def step2():
    """Step 2: Apartment/Room Naming and Orientations"""
    if request.method == 'POST':
        data = request.get_json()
        
        if not data or 'apartments' not in data:
            return jsonify({'error': 'Invalid data format'})
        
        try:
            # Get room data from session
            room_df = pd.DataFrame(session.get('room_df', []))
            
            if room_df.empty:
                return jsonify({'error': 'No room data available. Please complete step 1 first.'})
            
            # Store orientation data
            orientation_data = []
            
            # Update apartment and room names based on user input
            for apt in data['apartments']:
                original_name = apt['original_name']
                new_name = apt['new_name']
                orientation = apt.get('orientation', 0)
                
                # Store orientation data
                orientation_data.append({
                    'apartment_name': new_name,
                    'orientation': orientation
                })
                
                # Update apartment names
                room_df.loc[room_df['apartment_name'] == original_name, 'apartment_name'] = new_name
                
                # Update room names
                for room in apt['rooms']:
                    room_id = room['room_id']
                    new_room_name = room['new_name']
                    room_df.loc[room_df['room_id'] == room_id, 'room_name'] = new_room_name
            
            # Create apartment_orientations DataFrame
            apartment_orientations = pd.DataFrame(orientation_data)
            
            # Store updated data in session
            session['room_df'] = room_df.to_dict('records')
            session['apartment_orientations'] = apartment_orientations.to_dict('records')
            
            # Generate updated plot with interactive positions
            room_polygons = deserialize_rooms(session.get('room_polygons', []))
            if len(room_polygons) == len(room_df):
                room_df['polygon'] = room_polygons
                # Check if new method exists, fallback to original if not
                if hasattr(visualizer, 'plot_clusters_with_positions'):
                    updated_plot_b64, room_positions = visualizer.plot_clusters_with_positions(room_df, use_final_names=True)
                    # Convert numpy types to native Python types for JSON serialization
                    room_positions = convert_numpy_types(room_positions)
                else:
                    updated_plot_b64 = visualizer.plot_clusters(room_df, use_final_names=True)
                    room_positions = []
            else:
                updated_plot_b64 = generate_placeholder_image("Updated Room Names", 800, 600)
                room_positions = []
            
            return jsonify({
                'success': True,
                'updated_plot': updated_plot_b64,
                'room_positions': room_positions,
                'summary': {
                    'apartments_configured': len(apartment_orientations),
                    'total_rooms_named': len(room_df),
                    'orientations': dict(zip(apartment_orientations['apartment_name'], 
                                           apartment_orientations['orientation']))
                }
            })
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error updating names: {str(e)}'})
    
    # GET request
    try:
        room_df_records = session.get('room_df', [])
        
        if not room_df_records:
            print("No room_df found in session, redirecting to step1")
            return redirect(url_for('step1'))
        
        room_df = pd.DataFrame(room_df_records)
        print(f"Found {len(room_df)} rooms in session")
        
        # Generate plot with positions for interactive overlay
        room_polygons = deserialize_rooms(session.get('room_polygons', []))
        room_positions = []
        
        if len(room_polygons) == len(room_df):
            room_df['polygon'] = room_polygons
            
            # Check if new method exists, fallback to original if not
            if hasattr(visualizer, 'plot_clusters_with_positions'):
                try:
                    cluster_plot, room_positions = visualizer.plot_clusters_with_positions(room_df, use_final_names=True)
                    # Convert numpy types to native Python types for JSON serialization
                    room_positions = convert_numpy_types(room_positions)
                    print(f"Generated interactive plot with {len(room_positions)} room positions")
                except Exception as e:
                    print(f"Error with plot_clusters_with_positions: {e}")
                    # Fallback to original method
                    cluster_plot = visualizer.plot_clusters(room_df, use_final_names=True)
                    room_positions = []
            else:
                print("plot_clusters_with_positions method not found, using original method")
                cluster_plot = visualizer.plot_clusters(room_df, use_final_names=True)
                room_positions = []
        else:
            print(f"Polygon count mismatch: {len(room_polygons)} polygons vs {len(room_df)} rooms")
            cluster_plot = generate_placeholder_image("Room Layout", 800, 600)
            room_positions = []
        
        # Prepare data for template (existing form-based editing)
        apartments = []
        for apt_name, group in room_df.groupby('apartment_name'):
            rooms = [
                {
                    'room_id': int(row['room_id']),  # Convert to native int
                    'room_name': row.get('room_name', f"{apt_name}-R{int(row['room_id'])+1}")
                }
                for _, row in group.iterrows()
            ]
            
            apartments.append({
                'apartment_name': apt_name,
                'rooms': rooms
            })
        
        print(f"Prepared {len(apartments)} apartments for template")
        print(f"Room positions count: {len(room_positions)}")
        
        return render_template('step2.html', 
                             apartments=apartments, 
                             cluster_plot=cluster_plot,
                             room_positions=room_positions)

    except Exception as e:
        print(f"Error in step2 GET: {str(e)}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('step1'))

@app.route('/update_apartment_name', methods=['POST'])
@login_required
def update_apartment_name():
    """Update apartment name via AJAX"""
    try:
        data = request.get_json()
        apartment_cluster = int(data.get('apartment_cluster'))
        new_name = data.get('new_name', '').strip()
        
        if not new_name:
            return jsonify({'error': 'Apartment name cannot be empty'})
        
        # Update room_df in session
        room_df = pd.DataFrame(session.get('room_df', []))
        
        if room_df.empty:
            return jsonify({'error': 'No room data available'})
        
        # Find and update all rooms in this apartment cluster
        mask = room_df['apartment_cluster'] == apartment_cluster
        if not mask.any():
            return jsonify({'error': 'Apartment not found'})
        
        old_name = room_df.loc[mask, 'apartment_name'].iloc[0]
        room_df.loc[mask, 'apartment_name'] = new_name
        
        # Update session
        session['room_df'] = room_df.to_dict('records')
        
        # Also update apartment_orientations if it exists
        apartment_orientations = session.get('apartment_orientations', [])
        for apt in apartment_orientations:
            if apt.get('apartment_name') == old_name:
                apt['apartment_name'] = new_name
        session['apartment_orientations'] = apartment_orientations
        
        return jsonify({
            'success': True,
            'message': f'Apartment name updated from "{old_name}" to "{new_name}"',
            'old_name': old_name,
            'new_name': new_name
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error updating apartment name: {str(e)}'})

def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization"""
    if isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif hasattr(obj, 'item'):  # numpy scalar
        return obj.item()
    elif hasattr(obj, 'tolist'):  # numpy array
        return obj.tolist()
    else:
        return obj

@app.route('/step3', methods=['GET', 'POST'])
@login_required
def step3():
    """Step 3: Tile Coverage Generation"""
    if request.method == 'POST':
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Invalid data format'})
        
        try:
            # Get data from session
            rooms_data = session.get('rooms_data', [])
            start_points_data = session.get('start_points_data', [])
            apartment_orientations = pd.DataFrame(session.get('apartment_orientations', []))
            room_df = pd.DataFrame(session.get('room_df', []))
            tile_sizes = session.get('tile_sizes', [])
            
            if not rooms_data or apartment_orientations.empty:
                return jsonify({'error': 'Missing required data. Please complete previous steps first.'})
            
            # Deserialize data
            rooms = deserialize_rooms(rooms_data)
            start_points = deserialize_start_points(start_points_data)
            room_polygons = deserialize_rooms(session.get('room_polygons', []))
            
            # Add polygons back to room_df
            if len(room_polygons) == len(room_df):
                room_df['polygon'] = room_polygons
            
            # Get tile configuration
            use_default = data.get('use_default_size', True)
            if not use_default:
                tile_width = float(data.get('tile_width', 600))
                tile_height = float(data.get('tile_height', 600))
            else:
                if start_points and len(start_points) > 0:
                    sizes = [(sp['width'], sp['height']) for sp in start_points]
                    most_common_size = max(set(sizes), key=sizes.count)
                    tile_width, tile_height = most_common_size
                elif tile_sizes:
                    tile_width, tile_height = tile_sizes[0]
                else:
                    tile_width, tile_height = 600, 600
            
            # Get grout settings
            sp_includes_grout = data.get('sp_includes_grout', True)
            grout_thickness = float(data.get('grout_thickness', 3))
            
            # Get layout type
            layout_type = data.get('layout_type', 'standard')
            stagger_percent = 0
            stagger_direction = 'x'
            
            if layout_type == 'staggered':
                stagger_percent = float(data.get('stagger_percent', 0.5))
                stagger_direction = data.get('stagger_direction', 'x')
            
            # Generate tiles for all rooms
            apartments_data = tile_processor.generate_tiles_for_all_rooms(
                room_df, 
                apartment_orientations, 
                start_points,
                stagger_percent, 
                stagger_direction, 
                grout_thickness, 
                sp_includes_grout,
                tile_width,
                tile_height
            )
            
            # Verify room coverage
            coverage_df = tile_processor.verify_room_coverage(apartments_data, room_df)
            
            # Check for low coverage
            low_coverage = coverage_df[coverage_df['coverage_pct'] < 99]
            
            # Create visualization
            viz_result = visualizer.create_grout_outline_visualization(apartments_data, room_df)
            
            # Store tile data in session
            session['apartments_data'] = serialize_apartments_data(apartments_data)
            session['final_room_df'] = room_df.to_dict('records')
            session['tile_config'] = {
                'tile_width': tile_width,
                'tile_height': tile_height,
                'grout_thickness': grout_thickness,
                'sp_includes_grout': sp_includes_grout,
                'stagger_percent': stagger_percent,
                'stagger_direction': stagger_direction,
                'layout_type': layout_type
            }
            
            # Summary statistics
            total_tiles = sum(len(apt_data['tiles']) for apt_data in apartments_data.values())
            full_tiles = sum(len([t for t in apt_data['tiles'] if t['type'] == 'full']) 
                           for apt_data in apartments_data.values())
            cut_tiles = total_tiles - full_tiles
            
            return jsonify({
                'success': True,
                'tile_plot': viz_result,
                'summary': {
                    'total_tiles': total_tiles,
                    'full_tiles': full_tiles,
                    'cut_tiles': cut_tiles,
                    'full_tiles_percentage': round(full_tiles/total_tiles*100, 1) if total_tiles > 0 else 0,
                    'cut_tiles_percentage': round(cut_tiles/total_tiles*100, 1) if total_tiles > 0 else 0,
                    'average_coverage': round(coverage_df['coverage_pct'].mean(), 2),
                    'tile_size': f"{tile_width}mm x {tile_height}mm",
                    'grout_thickness': f"{grout_thickness}mm",
                    'layout_type': 'Staggered' if stagger_percent > 0 else 'Standard',
                    'low_coverage_rooms': len(low_coverage)
                }
            })
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error generating tile layout: {str(e)}'})
    
    # GET request
    try:
        if 'apartment_orientations' not in session:
            return redirect(url_for('step2'))
        
        # Get tile sizes for the form
        tile_sizes = session.get('tile_sizes', [])
        start_points = session.get('start_points_data', [])
        
        # Get default tile size
        if start_points and len(start_points) > 0:
            sizes = [(sp['width'], sp['height']) for sp in start_points]
            most_common_size = max(set(sizes), key=sizes.count)
            default_width, default_height = most_common_size
        elif tile_sizes:
            default_width, default_height = tile_sizes[0]
        else:
            default_width, default_height = 600, 600
        
        return render_template('step3.html', 
                             default_width=default_width,
                             default_height=default_height,
                             tile_sizes=tile_sizes)
    
    except Exception as e:
        print(f"Error in step3 GET: {str(e)}")
        return redirect(url_for('step2'))

@app.route('/step4', methods=['GET', 'POST'])
@login_required
def step4():
    """Step 4: Complete Tile Analysis - Modified for Irregular Tiles"""
    if request.method == 'POST':
        data = request.get_json()
        
        try:
            # Check if apartments data exists
            if 'apartments_data' not in session:
                return jsonify({'error': 'No tile data found. Please complete step 3 first.'})
            
            # Get data from session
            apartments_data = deserialize_apartments_data(session.get('apartments_data', {}))
            final_room_df = pd.DataFrame(session.get('final_room_df', []))
            
            # PART A: MultiPolygon Analysis
            mp_df = tile_processor.identify_and_list_multipolygons(apartments_data)
            
            multipolygon_handled = False
            split_count = 0
            
            if not mp_df.empty:
                # Visualize MultiPolygons (store plots in session)
                mp_detail_plot = visualizer.visualize_multipolygons_in_detail(
                    apartments_data, mp_df, final_room_df)
                mp_highlight_plot = visualizer.visualize_all_tiles_highlighting_multipolygons(
                    apartments_data, mp_df, final_room_df)
                
                # Automatically split MultiPolygons
                split_data, split_df = tile_processor.split_multipolygons_into_individual_tiles(
                    apartments_data, mp_df
                )
                
                # Visualize split results
                split_results_plot = visualizer.visualize_split_results(
                    apartments_data, split_data, mp_df, final_room_df
                )
                
                # Visualize all tiles after splitting
                split_count, regular_count = visualizer.visualize_all_tiles_after_splitting(
                    split_data, mp_df, final_room_df
                )
                
                # Count tiles by type and room
                counts_df = tile_processor.count_tiles_by_type_and_room(split_data, final_room_df)
                
                apartments_data = split_data
                multipolygon_handled = True
            
            # PART B: Small IRREGULAR tile detection with 1% threshold
            tiles_analysis_df = tile_processor.analyze_tile_sizes(apartments_data, final_room_df)
            
            # Filter to only analyze irregular tiles
            irregular_tiles_df = tiles_analysis_df[tiles_analysis_df['type'] == 'irregular'].copy()
            
            small_irregular_tiles = pd.DataFrame()
            area_threshold = 0
            
            if not irregular_tiles_df.empty:
                # Identify small irregular tiles based on area (1% threshold)
                small_irregular_tiles, area_threshold = tile_processor.identify_small_tiles(
                    irregular_tiles_df, area_threshold_percent=1.0
                )
                
                if not small_irregular_tiles.empty:
                    small_irregular_tiles['small_type'] = 'irregular_area_based'
                    small_irregular_tiles['small_criteria'] = 'area < 1%'
                    
                    # Visualize small irregular tiles
                    small_count, regular_count = visualizer.visualize_all_tiles_highlighting_small(
                        apartments_data, small_irregular_tiles, final_room_df, area_threshold
                    )
            
            # Store results in session
            tile_analysis_results = {
                'apartments_data': serialize_apartments_data(apartments_data),
                'tiles_analysis_df': tiles_analysis_df.to_dict('records'),
                'small_irregular_tiles': small_irregular_tiles.to_dict('records') if not small_irregular_tiles.empty else [],
                'area_threshold': area_threshold,
                'small_tiles_threshold': 1.0,
                'multipolygon_df': mp_df.to_dict('records') if not mp_df.empty else [],
                'multipolygon_handled': multipolygon_handled
            }
            
            session['tile_analysis_results'] = tile_analysis_results
            session['apartments_data'] = serialize_apartments_data(apartments_data)
            
            # Final summary
            total_tiles = sum(len(apt_data['tiles']) for apt_data in apartments_data.values())
            
            # Count tile types
            tile_types = {'full': 0, 'cut': 0, 'split': 0, 'irregular': 0}
            for apt_data in apartments_data.values():
                for tile in apt_data['tiles']:
                    tile_type = tile.get('type', 'unknown')
                    if 'split' in tile_type:
                        tile_types['split'] += 1
                    elif tile_type in tile_types:
                        tile_types[tile_type] += 1
            
            return jsonify({
                'success': True,
                'summary': {
                    'total_tiles': total_tiles,
                    'full_tiles': tile_types['full'],
                    'cut_tiles': tile_types['cut'],
                    'split_tiles': tile_types['split'],
                    'irregular_tiles': tile_types['irregular'],
                    'small_irregular_tiles': len(small_irregular_tiles),
                    'multipolygons_found': len(mp_df),
                    'multipolygons_split': split_count,
                    'multipolygon_handled': multipolygon_handled
                }
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error in tile analysis: {str(e)}'})
    
    # GET request
    try:
        if 'apartments_data' not in session:
            return redirect(url_for('step3'))
        
        return render_template('step4.html')
    
    except Exception as e:
        print(f"Error in step4 GET: {str(e)}")
        return redirect(url_for('step3'))

@app.route('/step5', methods=['GET', 'POST'])
@login_required
def step5():
    """Step 5: Tile Classification"""
    if request.method == 'POST':
        data = request.get_json()
        
        try:
            # Get data from session
            tile_analysis_results = session.get('tile_analysis_results', {})
            if not tile_analysis_results:
                return jsonify({'error': 'No tile analysis data found. Please complete step 4 first.'})
            
            apartments_data = deserialize_apartments_data(tile_analysis_results.get('apartments_data', {}))
            final_room_df = pd.DataFrame(session.get('final_room_df', []))
            
            # Get pattern configuration
            has_pattern = data.get('has_pattern', False)
            
            # Perform optimized classification
            (tiles_df, full_tiles, irregular_tiles, cut_x_tiles, cut_y_tiles, all_cut_tiles, 
             cut_x_df, cut_y_df, all_cut_df, stats) = tile_processor.optimize_tile_classification(
                apartments_data, final_room_df, has_pattern
            )
            
            # CRITICAL FIX: Create polygon mapping before converting to dict
            tile_polygon_mapping = {}
            
            for apt_name, apt_data in apartments_data.items():
                for tile_idx, tile in enumerate(apt_data['tiles']):
                    if 'polygon' in tile and tile['polygon'] is not None:
                        key = f"{apt_name}_{tile_idx}"
                        
                        polygon = tile['polygon']
                        if isinstance(polygon, Polygon):
                            tile_polygon_mapping[key] = {
                                'coords': list(polygon.exterior.coords),
                                'type': 'Polygon',
                                'interiors': [list(interior.coords) for interior in polygon.interiors] if polygon.interiors else []
                            }
                        elif isinstance(polygon, MultiPolygon):
                            tile_polygon_mapping[key] = {
                                'type': 'MultiPolygon',
                                'parts': []
                            }
                            for part in polygon.geoms:
                                part_data = {
                                    'exterior': list(part.exterior.coords),
                                    'interiors': [list(interior.coords) for interior in part.interiors] if part.interiors else []
                                }
                                tile_polygon_mapping[key]['parts'].append(part_data)
                        
                        # Also store actual dimensions
                        if 'actual_tile_width' in tile:
                            tile_polygon_mapping[key]['actual_width'] = tile['actual_tile_width']
                        if 'actual_tile_height' in tile:
                            tile_polygon_mapping[key]['actual_height'] = tile['actual_tile_height']
            
            # Store the polygon mapping in session
            session['tile_polygon_mapping'] = tile_polygon_mapping
            
            # CRITICAL FIX: Ensure tiles_df has necessary columns for matching
            for idx, row in tiles_df.iterrows():
                apt_name = row['apartment_name']
                tile_index = row['tile_index']
                
                # Get actual dimensions from apartments_data
                if apt_name in apartments_data and 'tiles' in apartments_data[apt_name]:
                    if tile_index < len(apartments_data[apt_name]['tiles']):
                        tile = apartments_data[apt_name]['tiles'][tile_index]
                        
                        # Preserve actual dimensions - CRITICAL for matching
                        if 'actual_tile_width' in tile:
                            tiles_df.at[idx, 'actual_width'] = tile['actual_tile_width']
                        else:
                            tiles_df.at[idx, 'actual_width'] = tile.get('width', 600)
                            
                        if 'actual_tile_height' in tile:
                            tiles_df.at[idx, 'actual_height'] = tile['actual_tile_height']
                        else:
                            tiles_df.at[idx, 'actual_height'] = tile.get('height', 600)
            
            # Create visualization
            classification_counts = visualizer.visualize_classification(
                tiles_df, final_room_df, has_pattern, with_grout=True
            )
            
            # Store classification data in session
            tile_classification_results = {
                'tiles_df': tiles_df.to_dict('records'),
                'full_tiles': full_tiles.to_dict('records'),
                'irregular_tiles': irregular_tiles.to_dict('records'),
                'cut_x_tiles': cut_x_tiles.to_dict('records') if has_pattern else [],
                'cut_y_tiles': cut_y_tiles.to_dict('records') if has_pattern else [],
                'all_cut_tiles': all_cut_tiles.to_dict('records') if not has_pattern else [],
                'cut_x_df': cut_x_df.to_dict('records') if has_pattern else [],
                'cut_y_df': cut_y_df.to_dict('records') if has_pattern else [],
                'all_cut_df': all_cut_df.to_dict('records') if not has_pattern else [],
                'stats': stats,
                'classification_counts': classification_counts,
                'has_pattern': has_pattern
            }
            
            session['tile_classification_results'] = tile_classification_results
            
            # Prepare response
            response_data = {
                'success': True,
                'classification_plot': plt_to_base64(),
                'summary': {
                    'pattern_mode': 'Yes (X/Y separation)' if has_pattern else 'No (all cuts combined)',
                    'grout_thickness': f"{stats['grout_thickness']}mm",
                    'total_classified': stats['total_tiles'],
                    'stats': []
                }
            }
            
            # Add statistics
            response_data['summary']['stats'].append({
                'type': 'Full Tiles',
                'count': stats['full_tiles'],
                'percentage': round(stats['full_tiles']/stats['total_tiles']*100, 1) if stats['total_tiles'] > 0 else 0
            })
            response_data['summary']['stats'].append({
                'type': 'Irregular Tiles',
                'count': stats['irregular_tiles'],
                'percentage': round(stats['irregular_tiles']/stats['total_tiles']*100, 1) if stats['total_tiles'] > 0 else 0
            })
            
            if has_pattern:
                response_data['summary']['stats'].append({
                    'type': 'Cut X Tiles',
                    'count': stats['cut_x_tiles'],
                    'percentage': round(stats['cut_x_tiles']/stats['total_tiles']*100, 1) if stats['total_tiles'] > 0 else 0
                })
                response_data['summary']['stats'].append({
                    'type': 'Cut Y Tiles',
                    'count': stats['cut_y_tiles'],
                    'percentage': round(stats['cut_y_tiles']/stats['total_tiles']*100, 1) if stats['total_tiles'] > 0 else 0
                })
                response_data['summary']['unique_cut_sizes'] = f"X={len(stats['cut_x_types'])} types, Y={len(stats['cut_y_types'])} types"
            else:
                response_data['summary']['stats'].append({
                    'type': 'All Cut Tiles',
                    'count': stats['all_cut_tiles'],
                    'percentage': round(stats['all_cut_tiles']/stats['total_tiles']*100, 1) if stats['total_tiles'] > 0 else 0
                })
                response_data['summary']['unique_cut_sizes'] = f"{len(stats['all_cut_types'])} types"
            
            return jsonify(response_data)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error in tile classification: {str(e)}'})
    
    # GET request
    try:
        if 'tile_analysis_results' not in session:
            return redirect(url_for('step4'))
        
        return render_template('step5.html')
    
    except Exception as e:
        print(f"Error in step5 GET: {str(e)}")
        return redirect(url_for('step4'))

@app.route('/step6', methods=['GET', 'POST'])
@login_required
def step6():
    """Step 6: Identify Small Cut Tiles (Combined Criteria)"""
    if request.method == 'POST':
        data = request.get_json()
        
        try:
            # Get data from session
            tile_classification_results = session.get('tile_classification_results', {})
            tile_analysis_results = session.get('tile_analysis_results', {})
            final_room_df = pd.DataFrame(session.get('final_room_df', []))
            
            if not tile_classification_results or not tile_analysis_results:
                return jsonify({'error': 'Missing required data. Please complete previous steps.'})
            
            # Get exclude option
            exclude_small_tiles = data.get('exclude_small_tiles', True)
            
            # Convert tiles_df back to DataFrame
            tiles_df = pd.DataFrame(tile_classification_results['tiles_df'])
            has_pattern = tile_classification_results['has_pattern']
            
            # Identify small tiles using combined criteria
            (all_small_tiles, total_small_tiles, small_irregular_count, 
             small_cut_count, size_threshold, area_threshold) = tile_processor.identify_small_tiles_combined(
                tile_classification_results, tile_analysis_results, final_room_df
            )
            
            # Fixed threshold of 10mm for dimension-based detection
            small_cut_tiles_dimension, _ = tile_processor.identify_small_cut_tiles(
                tiles_df, final_room_df, has_pattern, 10.0
            )
            
            # Get small irregular tiles from Step 4
            small_irregular_tiles = pd.DataFrame(tile_analysis_results.get('small_irregular_tiles', []))
            
            # Create visualization if small tiles found
            visualization_plot = None
            if total_small_tiles > 0:
                visualization_plot = visualizer.visualize_small_tiles(
                    tiles_df, all_small_tiles, final_room_df, size_threshold
                )
                
                # Handle exclusion if requested
                if exclude_small_tiles:
                    excluded_count, removed_counts, updated_tiles_df = tile_processor.exclude_small_tiles_from_classification(
                        tile_classification_results, tiles_df, small_cut_tiles_dimension, 
                        small_irregular_tiles, has_pattern
                    )
                    
                    if excluded_count > 0:
                        # Update the classification results
                        tile_classification_results['tiles_df'] = updated_tiles_df.to_dict('records')
                        tile_classification_results['stats']['total_tiles'] -= excluded_count
                        tile_classification_results['stats']['irregular_tiles'] -= removed_counts['irregular']
                        
                        if has_pattern:
                            tile_classification_results['stats']['cut_x_tiles'] -= removed_counts['cut_x']
                            tile_classification_results['stats']['cut_y_tiles'] -= removed_counts['cut_y']
                        else:
                            tile_classification_results['stats']['all_cut_tiles'] -= removed_counts['all_cut']
                        
                        session['tile_classification_results'] = tile_classification_results
            
            # Store small tiles results
            small_tiles_results = {
                'small_tiles_df': all_small_tiles.to_dict('records') if not all_small_tiles.empty else [],
                'small_tile_count': total_small_tiles,
                'small_irregular_count': small_irregular_count,
                'small_cut_count': small_cut_count,
                'size_threshold': size_threshold,
                'area_threshold': area_threshold,
                'tiles_excluded': exclude_small_tiles if total_small_tiles > 0 else False
            }
            
            session['small_tiles_results'] = small_tiles_results
            
            # Prepare response
            response_data = {
                'success': True,
                'visualization_plot': plt_to_base64() if visualization_plot else None,
                'summary': {
                    'total_small_tiles': total_small_tiles,
                    'irregular_tiles_area': small_irregular_count,
                    'cut_tiles_dimension': small_cut_count,
                    'tiles_excluded': 'Yes' if small_tiles_results['tiles_excluded'] else 'No'
                }
            }
            
            # Add location breakdown if small tiles found
            if not all_small_tiles.empty and 'small_type' in all_small_tiles.columns:
                location_summary = all_small_tiles.groupby(['apartment_name', 'room_name', 'small_type']).size().reset_index(name='count')
                response_data['location_summary'] = location_summary.to_dict('records')
            
            # Add statistics
            if total_small_tiles > 0:
                total_tiles = len(tiles_df)
                total_irregular = len(tiles_df[tiles_df['classification'] == 'irregular'])
                total_cuts = len(tiles_df[tiles_df['classification'].isin(['cut_x', 'cut_y', 'all_cut'])])
                
                response_data['summary']['percentages'] = {
                    'small_irregular_percentage': round(small_irregular_count/total_irregular*100, 1) if total_irregular > 0 else 0,
                    'small_cut_percentage': round(small_cut_count/total_cuts*100, 1) if total_cuts > 0 else 0,
                    'total_small_percentage': round(total_small_tiles/total_tiles*100, 1) if total_tiles > 0 else 0
                }
            
            return jsonify(response_data)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error identifying small tiles: {str(e)}'})
    
    # GET request
    try:
        if 'tile_classification_results' not in session:
            return redirect(url_for('step5'))
        
        return render_template('step6.html')
    
    except Exception as e:
        print(f"Error in step6 GET: {str(e)}")
        return redirect(url_for('step5'))

@app.route('/step7', methods=['GET', 'POST'])
@login_required
def step7():
    """Step 7: Data Preparation for Optimization - Following Colab Logic"""
    if request.method == 'POST':
        data = request.get_json() if request.is_json else {}
        action = data.get('action') if data else request.form.get('action')
        
        try:
            if action == 'prepare_apartment_data':
                # Get classification results
                tile_classification_results = session.get('tile_classification_results', {})
                if not tile_classification_results:
                    return jsonify({'error': 'No classification data found'})
                
                tiles_df = pd.DataFrame(tile_classification_results['tiles_df'])
                has_pattern = tile_classification_results['has_pattern']
                tile_config = session.get('tile_config', {})
                tile_width = tile_config.get('tile_width', 600)
                tile_height = tile_config.get('tile_height', 600)
                
                # Create cut pieces summary following Colab logic
                cut_pieces_summary = data_prep_processor.create_cut_pieces_summary(
                    tiles_df, has_pattern, tile_width, tile_height
                )
                
                # Store in session - convert DataFrames to records for serialization
                serialized_summary = {}
                for key, value in cut_pieces_summary.items():
                    if isinstance(value, pd.DataFrame):
                        serialized_summary[key] = value.to_dict('records')
                    else:
                        serialized_summary[key] = value
                
                session['cut_pieces_summary'] = serialized_summary
                session['cut_pieces_by_half'] = serialized_summary
                
                # Get statistics
                stats = data_prep_processor.get_summary_statistics(cut_pieces_summary)
                
                # Prepare response - ensure all values are JSON serializable
                response_data = {
                    'success': True,
                    'apartment_pieces': int(stats['apartment_pieces']),
                    'half_threshold': float(cut_pieces_summary['half_threshold']),
                    'has_pattern': bool(has_pattern)
                }
                
                if has_pattern:
                    # Convert numpy int64 to regular int
                    x_less = cut_pieces_summary.get('x_less_than_half', pd.DataFrame())
                    x_more = cut_pieces_summary.get('x_more_than_half', pd.DataFrame())
                    y_less = cut_pieces_summary.get('y_less_than_half', pd.DataFrame())
                    y_more = cut_pieces_summary.get('y_more_than_half', pd.DataFrame())
                    
                    response_data['x_less_count'] = int(x_less['Count'].sum()) if not x_less.empty else 0
                    response_data['x_more_count'] = int(x_more['Count'].sum()) if not x_more.empty else 0
                    response_data['y_less_count'] = int(y_less['Count'].sum()) if not y_less.empty else 0
                    response_data['y_more_count'] = int(y_more['Count'].sum()) if not y_more.empty else 0
                else:
                    all_less = cut_pieces_summary.get('all_less_than_half', pd.DataFrame())
                    all_more = cut_pieces_summary.get('all_more_than_half', pd.DataFrame())
                    
                    response_data['all_less_count'] = int(all_less['Count'].sum()) if not all_less.empty else 0
                    response_data['all_more_count'] = int(all_more['Count'].sum()) if not all_more.empty else 0
                
                return jsonify(response_data)
                
            elif action == 'download_template':
                # Create inventory template
                template_filename = data_prep_processor.create_inventory_template()
                
                if template_filename:
                    with open(template_filename, 'rb') as f:
                        file_data = f.read()
                    
                    # Clean up
                    os.remove(template_filename)
                    
                    # Encode for response
                    file_b64 = base64.b64encode(file_data).decode('utf-8')
                    
                    return jsonify({
                        'success': True,
                        'template_file': file_b64,
                        'filename': template_filename
                    })
                    
            elif action == 'upload_inventory':
                # Handle inventory upload
                if 'inventory_file' not in request.files:
                    return jsonify({'error': 'No file uploaded'})
                
                file = request.files['inventory_file']
                if file.filename == '':
                    return jsonify({'error': 'No file selected'})
                
                # Save temporarily
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Get the stored summary back
                stored_summary = session.get('cut_pieces_summary', {})
                
                # Convert back to DataFrames for processing
                cut_pieces_summary = {}
                for key, value in stored_summary.items():
                    if isinstance(value, list) and key.endswith('_than_half'):
                        cut_pieces_summary[key] = pd.DataFrame(value)
                    else:
                        cut_pieces_summary[key] = value
                
                # Read inventory file
                inventory_data = data_prep_processor.read_inventory_file(
                    filepath,
                    has_pattern=cut_pieces_summary.get('has_pattern', False)
                )
                
                if inventory_data:
                    # Validate
                    tile_config = session.get('tile_config', {})
                    if data_prep_processor.validate_inventory_data(
                        inventory_data, 
                        tile_config.get('tile_width', 600),
                        tile_config.get('tile_height', 600)
                    ):
                        # Merge with cuts
                        updated_summary = data_prep_processor.merge_inventory_with_cuts(
                            cut_pieces_summary, 
                            inventory_data
                        )
                        
                        # Serialize for storage
                        serialized_updated = {}
                        for key, value in updated_summary.items():
                            if isinstance(value, pd.DataFrame):
                                serialized_updated[key] = value.to_dict('records')
                            else:
                                serialized_updated[key] = value
                        
                        session['cut_pieces_by_half'] = serialized_updated
                        
                        # Clean up
                        os.remove(filepath)
                        
                        return jsonify({'success': True})
                
                return jsonify({'error': 'Failed to process inventory file'})
                
            elif action == 'finalize_data':
                # Get stored summary
                stored_summary = session.get('cut_pieces_by_half', {})
                
                # Convert back to DataFrames for statistics
                cut_pieces_by_half = {}
                for key, value in stored_summary.items():
                    if isinstance(value, list) and key.endswith('_than_half'):
                        cut_pieces_by_half[key] = pd.DataFrame(value)
                    else:
                        cut_pieces_by_half[key] = value
                
                # Get final statistics
                stats = data_prep_processor.get_summary_statistics(cut_pieces_by_half)
                
                # Mark step as complete
                session['step7_complete'] = True
                
                return jsonify({
                    'success': True,
                    'total_pieces': int(stats['total_pieces']),
                    'apartment_pieces': int(stats['apartment_pieces']),
                    'inventory_pieces': int(stats['inventory_pieces'])
                })
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error in data preparation: {str(e)}'})
    
    # GET request
    try:
        if 'small_tiles_results' not in session:
            return redirect(url_for('step6'))
        
        return render_template('step7.html')
        
    except Exception as e:
        print(f"Error in step7 GET: {str(e)}")
        return redirect(url_for('step6'))

@app.route('/step8', methods=['GET', 'POST'])
@login_required
def step8():
    """Step 8: Cut Piece Matching, Table Display, and Visual Preview"""
    if request.method == 'POST':
        return redirect(url_for('step8'))
    
    # GET request
    try:
        if 'cut_pieces_by_half' not in session:
            return redirect(url_for('step7'))
        
        # Get apartment list with statistics
        stored_data = session.get('cut_pieces_by_half', {})
        final_room_df = pd.DataFrame(session.get('final_room_df', []))
        has_pattern = stored_data.get('has_pattern', False)
        
        # Calculate apartment statistics
        apartments_info = []
        apartments = sorted(final_room_df['apartment_name'].unique())
        
        for apt in apartments:
            apt_info = {
                'name': apt,
                'total_pieces': 0,
                'less_than_half': 0,
                'more_than_half': 0
            }
            
            if has_pattern:
                # X direction
                x_less = pd.DataFrame(stored_data.get('x_less_than_half', []))
                x_more = pd.DataFrame(stored_data.get('x_more_than_half', []))
                if not x_less.empty:
                    apt_x_less = x_less[x_less['Apartment'] == apt]['Count'].sum()
                    apt_info['less_than_half'] += int(apt_x_less)
                if not x_more.empty:
                    apt_x_more = x_more[x_more['Apartment'] == apt]['Count'].sum()
                    apt_info['more_than_half'] += int(apt_x_more)
                
                # Y direction
                y_less = pd.DataFrame(stored_data.get('y_less_than_half', []))
                y_more = pd.DataFrame(stored_data.get('y_more_than_half', []))
                if not y_less.empty:
                    apt_y_less = y_less[y_less['Apartment'] == apt]['Count'].sum()
                    apt_info['less_than_half'] += int(apt_y_less)
                if not y_more.empty:
                    apt_y_more = y_more[y_more['Apartment'] == apt]['Count'].sum()
                    apt_info['more_than_half'] += int(apt_y_more)
            else:
                # All cuts
                all_less = pd.DataFrame(stored_data.get('all_less_than_half', []))
                all_more = pd.DataFrame(stored_data.get('all_more_than_half', []))
                if not all_less.empty:
                    apt_all_less = all_less[all_less['Apartment'] == apt]['Count'].sum()
                    apt_info['less_than_half'] += int(apt_all_less)
                if not all_more.empty:
                    apt_all_more = all_more[all_more['Apartment'] == apt]['Count'].sum()
                    apt_info['more_than_half'] += int(apt_all_more)
            
            apt_info['total_pieces'] = apt_info['less_than_half'] + apt_info['more_than_half']
            apartments_info.append(apt_info)
        
        # Calculate inventory statistics
        inventory_info = {
            'available': False,
            'x_pieces': 0,
            'y_pieces': 0,
            'all_pieces': 0
        }
        
        if has_pattern:
            x_inv_less = pd.DataFrame(stored_data.get('x_inv_less_than_half', []))
            x_inv_more = pd.DataFrame(stored_data.get('x_inv_more_than_half', []))
            y_inv_less = pd.DataFrame(stored_data.get('y_inv_less_than_half', []))
            y_inv_more = pd.DataFrame(stored_data.get('y_inv_more_than_half', []))
            
            if not x_inv_less.empty or not x_inv_more.empty:
                inventory_info['available'] = True
                inventory_info['x_pieces'] = int(x_inv_less['Count'].sum() + x_inv_more['Count'].sum())
            if not y_inv_less.empty or not y_inv_more.empty:
                inventory_info['available'] = True
                inventory_info['y_pieces'] = int(y_inv_less['Count'].sum() + y_inv_more['Count'].sum())
        else:
            all_inv_less = pd.DataFrame(stored_data.get('all_inv_less_than_half', []))
            all_inv_more = pd.DataFrame(stored_data.get('all_inv_more_than_half', []))
            
            if not all_inv_less.empty or not all_inv_more.empty:
                inventory_info['available'] = True
                inventory_info['all_pieces'] = int(all_inv_less['Count'].sum() + all_inv_more['Count'].sum())
        
        # Get matching history
        matching_history = session.get('matching_history', [])
        
        return render_template('step8.html', 
                             apartments_info=apartments_info,
                             inventory_info=inventory_info,
                             has_pattern=has_pattern,
                             matching_history=matching_history)
    
    except Exception as e:
        print(f"Error in step8 GET: {str(e)}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('step7'))

@app.route('/step8/match_selected', methods=['POST'])
@login_required
def match_selected_apartments():
    """Run matching for selected apartments only"""
    try:
        data = request.get_json()
        selected_apartments = data.get('selected_apartments', [])
        include_inventory = data.get('include_inventory', False)
        matching_name = data.get('matching_name', f"Match_{datetime.now().strftime('%H%M%S')}")
        
        if not selected_apartments:
            return jsonify({'error': 'No apartments selected'})
        
        # Get data from session
        stored_data = session.get('cut_pieces_by_half', {})
        cut_pieces_by_half = {}
        
        # Convert stored data back to DataFrames
        for key, value in stored_data.items():
            if isinstance(value, list) and key.endswith('_than_half'):
                df = pd.DataFrame(value)
                
                # For apartment data, filter by selected apartments
                if 'inv' not in key and not df.empty and 'Apartment' in df.columns:
                    filtered_df = df[df['Apartment'].isin(selected_apartments)]
                    cut_pieces_by_half[key] = filtered_df
                # For inventory data, include if requested
                elif 'inv' in key:
                    if include_inventory and not df.empty:
                        cut_pieces_by_half[key] = df
                    else:
                        cut_pieces_by_half[key] = pd.DataFrame()
                else:
                    cut_pieces_by_half[key] = df
            else:
                cut_pieces_by_half[key] = value
        
        # Get pattern mode and tile dimensions
        has_pattern = cut_pieces_by_half['has_pattern']
        tile_width = cut_pieces_by_half['tile_width']
        tile_height = cut_pieces_by_half['tile_height']
        half_threshold = cut_pieces_by_half['half_threshold']
        
        # Define tolerance ranges (following Colab logic)
        tolerance_ranges = [10, 20, 40, 60, 80, 100]
        max_tolerance = min(tile_width, tile_height) / 4
        current_max = max(tolerance_ranges)
        while current_max < max_tolerance:
            current_max += 20
            tolerance_ranges.append(current_max)
        
        print(f"Using progressive tolerance ranges (mm): {tolerance_ranges}")
        
        # Process cut pieces matching
        matching_results = matching_processor.process_cut_pieces_matching(
            cut_pieces_by_half, tolerance_ranges
        )
        
        # Create clean tables
        clean_tables = matching_processor.create_clean_tables(
            matching_results, cut_pieces_by_half
        )
        
        # Create group mapping for visualization
        group_mapping, tile_specs_to_groups = matching_processor.create_group_based_tile_mapping(clean_tables)
        
        # Get apartment and inventory data for summaries
        apartment_tables = {}
        inventory_tables = {}
        
        if has_pattern:
            if 'x_direction' in clean_tables:
                apartment_tables['x'] = clean_tables['x_direction']
            if 'y_direction' in clean_tables:
                apartment_tables['y'] = clean_tables['y_direction']
            if 'x_inv' in clean_tables:
                inventory_tables['x'] = clean_tables['x_inv']
            if 'y_inv' in clean_tables:
                inventory_tables['y'] = clean_tables['y_inv']
        else:
            if 'all_direction' in clean_tables:
                apartment_tables['all'] = clean_tables['all_direction']
            if 'all_inv' in clean_tables:
                inventory_tables['all'] = clean_tables['all_inv']
        
        # Create apartment summaries
        apartment_summaries = {}
        
        for apartment in selected_apartments:
            apartment_data = pd.DataFrame()
            
            # Combine data from all directions for this apartment
            for direction, table_data in apartment_tables.items():
                apt_specific = table_data[table_data['Apartment'] == apartment].copy()
                if not apt_specific.empty:
                    apartment_data = pd.concat([apartment_data, apt_specific], ignore_index=True)
            
            if not apartment_data.empty:
                # Calculate statistics
                total_pieces = apartment_data['Count'].sum()
                matched_pieces = apartment_data[apartment_data['Group ID'] != '']['Count'].sum()
                unmatched_pieces = apartment_data[apartment_data['Group ID'] == '']['Count'].sum()
                
                # Count by match type
                apartment_matches = apartment_data[apartment_data['Match Type'] == 'Apartment']['Count'].sum()
                inventory_matches = apartment_data[apartment_data['Match Type'] == 'Inventory']['Count'].sum()
                
                apartment_summaries[apartment] = {
                    'total_pieces': int(total_pieces),
                    'matched_pieces': int(matched_pieces),
                    'unmatched_pieces': int(unmatched_pieces),
                    'apartment_matches': int(apartment_matches),
                    'inventory_matches': int(inventory_matches),
                    'match_percentage': round(matched_pieces/total_pieces*100, 1) if total_pieces > 0 else 0,
                    'data': apartment_data.to_dict('records')
                }
            else:
                apartment_summaries[apartment] = {
                    'total_pieces': 0,
                    'matched_pieces': 0,
                    'unmatched_pieces': 0,
                    'apartment_matches': 0,
                    'inventory_matches': 0,
                    'match_percentage': 0,
                    'data': []
                }
        
        # Overall statistics
        total_pieces_all = sum(s['total_pieces'] for s in apartment_summaries.values())
        matched_pieces_all = sum(s['matched_pieces'] for s in apartment_summaries.values())
        overall_match_percentage = round(matched_pieces_all/total_pieces_all*100, 1) if total_pieces_all > 0 else 0
        
        # Store this matching attempt - CRITICAL: Store DataFrames properly
        matching_attempt = {
            'id': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'name': matching_name,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'selected_apartments': selected_apartments,
            'include_inventory': include_inventory,
            'apartment_summaries': apartment_summaries,
            'clean_tables': {k: v.to_dict('records') if isinstance(v, pd.DataFrame) else v 
                           for k, v in clean_tables.items()},
            'clean_tables_df': {k: v for k, v in clean_tables.items()},  # Store actual DataFrames
            'matching_results': matching_results,
            'group_mapping': group_mapping,
            'tile_specs_to_groups': tile_specs_to_groups,
            'has_pattern': has_pattern,
            'tile_width': tile_width,
            'tile_height': tile_height
        }
        
        # Add to history
        matching_history = session.get('matching_history', [])
        matching_history.insert(0, matching_attempt)
        if len(matching_history) > 10:  # Keep last 10
            matching_history = matching_history[:10]
        session['matching_history'] = matching_history
        
        # Set as current matching
        session['current_matching'] = matching_attempt
        
        # Save to database if project exists
        if 'project_id' in session:
            project = Project.query.get(session['project_id'])
            if project:
                # Mark project as complete since optimization is done
                project.is_complete = True
                project.current_step = 8
                project.step8_complete = True
                
                # Get waste percentages from session (from step 7)
                export_results = session.get('export_results', {})
                if export_results and 'summary_data' in export_results:
                    summary_df = export_results['summary_data']['summary_df']
                    if summary_df is not None and len(summary_df) > 0:
                        # Calculate average waste percentages across all apartments
                        project.design_waste_percent = summary_df['DESIGN WASTAGE %'].mean()
                        project.optimized_waste_percent = summary_df['OPTIMISED WASTAGE %'].mean()
                
                # Save optimization results for each apartment
                for apt_name, apt_summary in apartment_summaries.items():
                    # Find rooms for this apartment
                    apt_rooms = Room.query.join(Project).filter(
                        Project.id == project.id,
                        Room.apartment_name == apt_name
                    ).all()
                    
                    for room in apt_rooms:
                        opt_result = OptimizationResult(
                            project_id=project.id,
                            room_id=room.id,
                            matched_cuts=apt_summary['matched_pieces'],
                            unmatched_cuts=apt_summary['unmatched_pieces'],
                            processing_time_seconds=0  # You can add timing if needed
                        )
                        
                        # Add more detailed matching data if available
                        if 'apartment_matches' in apt_summary:
                            # We don't have separate fields for these in the current schema
                            # but we can store the match percentage
                            opt_result.improvement_percent = apt_summary['match_percentage']
                        
                        db.session.add(opt_result)
                
                # Save inventory data if used
                if include_inventory and inventory_tables:
                    # First check if InventoryPiece model exists
                    try:
                        from models import InventoryPiece
                        
                        for direction, inv_table in inventory_tables.items():
                            if not inv_table.empty:
                                for _, row in inv_table.iterrows():
                                    inventory = InventoryPiece(
                                        project_id=project.id,
                                        piece_type=direction,
                                        cut_size=row.get('Cut Size (mm)', 0),
                                        remaining_size=row.get('Remaining Size (mm)', 0),
                                        apartment_name=row.get('Apartment', ''),
                                        location=row.get('Location', ''),
                                        is_matched=row.get('Group ID', '') != '',
                                        match_id=row.get('Group ID', '')
                                    )
                                    db.session.add(inventory)
                    except ImportError:
                        print("InventoryPiece model not found - skipping inventory data save")
                
                # Commit all changes
                db.session.commit()
                
                # Log activity
                db_bridge.log_activity(
                    current_user.id,
                    project.id,
                    'optimization_complete',
                    f'Optimization completed for {len(selected_apartments)} apartments with {overall_match_percentage:.1f}% matching'
                )
                
                print(f"Project {project.id} marked as complete and saved to database")
        
        return jsonify({
            'success': True,
            'matching_id': matching_attempt['id'],
            'summary': {
                'apartments': selected_apartments,
                'apartment_summaries': apartment_summaries,
                'overall': {
                    'total_pieces': int(total_pieces_all),
                    'matched_pieces': int(matched_pieces_all),
                    'match_percentage': overall_match_percentage
                }
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error in matching process: {str(e)}'})

@app.route('/step8/visualize_apartment', methods=['POST'])
@login_required
def visualize_apartment():
    """Create visualization for a specific apartment"""
    try:
        data = request.get_json()
        apartment_name = data.get('apartment_name')
        matching_id = data.get('matching_id')
        
        if not apartment_name:
            return jsonify({'error': 'Apartment name required'})
        
        # Get the matching attempt
        current_matching = None
        if matching_id:
            matching_history = session.get('matching_history', [])
            for match in matching_history:
                if match['id'] == matching_id:
                    current_matching = match
                    break
        else:
            current_matching = session.get('current_matching')
        
        if not current_matching:
            return jsonify({'error': 'No matching data found'})
        
        # Get required data
        tile_classification_results = session.get('tile_classification_results', {})
        tiles_df = pd.DataFrame(tile_classification_results['tiles_df'])
        final_room_df = pd.DataFrame(session.get('final_room_df', []))
        
        # CRITICAL FIX: Get the original apartments_data with polygons
        apartments_data_serialized = session.get('apartments_data', {})
        if not apartments_data_serialized:
            return jsonify({'error': 'No tile data found'})
        
        # Deserialize the apartments data to get actual polygons
        apartments_data = deserialize_apartments_data(apartments_data_serialized)
        
        # Deserialize room polygons and add to final_room_df
        room_polygons = deserialize_rooms(session.get('room_polygons', []))
        if len(room_polygons) == len(final_room_df):
            final_room_df['polygon'] = room_polygons
        
        # Filter for specific apartment
        apt_tiles = tiles_df[tiles_df['apartment_name'] == apartment_name].copy()
        apt_rooms = final_room_df[final_room_df['apartment_name'] == apartment_name].copy()
        
        if apt_tiles.empty or apt_rooms.empty:
            return jsonify({'error': f'No data found for apartment {apartment_name}'})
        
        # CRITICAL FIX: Restore polygons to tiles_df from apartments_data
        if apartment_name in apartments_data:
            apt_tile_data = apartments_data[apartment_name]['tiles']
            
            # Create a mapping from tile_index to polygon
            tile_polygons = {}
            for tile_idx, tile_data in enumerate(apt_tile_data):
                if 'polygon' in tile_data:
                    tile_polygons[tile_idx] = tile_data['polygon']
                    
                    # Also get actual dimensions if available
                    actual_width = tile_data.get('actual_tile_width', tile_data.get('width', 600))
                    actual_height = tile_data.get('actual_tile_height', tile_data.get('height', 600))
                    
                    # Update the corresponding row in apt_tiles
                    matching_rows = apt_tiles[apt_tiles['tile_index'] == tile_idx]
                    if not matching_rows.empty:
                        idx = matching_rows.index[0]
                        apt_tiles.at[idx, 'actual_width'] = actual_width
                        apt_tiles.at[idx, 'actual_height'] = actual_height
            
            # Restore polygons to apt_tiles
            for idx, row in apt_tiles.iterrows():
                tile_idx = row['tile_index']
                if tile_idx in tile_polygons:
                    apt_tiles.at[idx, 'polygon'] = tile_polygons[tile_idx]
        
        # Get clean tables with proper DataFrame format
        clean_tables = {}
        if 'clean_tables_df' in current_matching and current_matching['clean_tables_df']:
            clean_tables = current_matching['clean_tables_df']
        else:
            # Recreate from serialized data
            clean_tables_serialized = current_matching.get('clean_tables', {})
            for table_name, table_data in clean_tables_serialized.items():
                if isinstance(table_data, list) and len(table_data) > 0:
                    clean_tables[table_name] = pd.DataFrame(table_data)
                else:
                    clean_tables[table_name] = pd.DataFrame()
        
        # Get tile configuration
        tile_config = session.get('tile_config', {})
        tile_width = tile_config.get('tile_width', 600)
        tile_height = tile_config.get('tile_height', 600)
        
        # Create group mapping following Colab exactly
        group_mapping, tile_specs_to_groups = matching_processor.create_group_based_tile_mapping(clean_tables)
              
        # Call the visualizer method following Colab Step 9
        match_type_counts = visualizer.visualize_apartment_tiles(
            apartment_name, 
            apt_tiles, 
            apt_rooms, 
            group_mapping, 
            tile_specs_to_groups, 
            tile_width, 
            tile_height,
            matching_processor.get_tile_color_group_based
        )
        
        # Convert plot to base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        plt.close()
        buf.seek(0)
        plot_base64 = base64.b64encode(buf.read()).decode('utf-8')
        
        return jsonify({
            'success': True,
            'plot': plot_base64,
            'summary': match_type_counts
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error creating visualization: {str(e)}'})

@app.route('/step8/load_matching', methods=['POST'])
@login_required
def load_matching():
    """Load a previous matching attempt"""
    try:
        data = request.get_json()
        matching_id = data.get('matching_id')
        
        # Find the matching attempt
        matching_history = session.get('matching_history', [])
        for match in matching_history:
            if match['id'] == matching_id:
                session['current_matching'] = match
                return jsonify({
                    'success': True,
                    'matching': {
                        'id': match['id'],
                        'name': match['name'],
                        'apartment_summaries': match['apartment_summaries'],
                        'selected_apartments': match['selected_apartments']
                    }
                })
        
        return jsonify({'error': 'Matching not found'})
        
    except Exception as e:
        return jsonify({'error': f'Error loading matching: {str(e)}'})

@app.route('/step9', methods=['GET', 'POST'])
@login_required
def step9():
    """Step 9: Export Full Excel Files and Create Visual Reports per Apartment - Enhanced with Consolidated Summary Report"""
    if request.method == 'POST':
        data = request.get_json()
        
        try:
            # Get selected matching ID
            matching_id = data.get('matching_id')
            if not matching_id:
                return jsonify({'error': 'No matching selected'})
            
            # Find the selected matching
            matching_history = session.get('matching_history', [])
            selected_matching = None
            for match in matching_history:
                if match['id'] == matching_id:
                    selected_matching = match
                    break
            
            if not selected_matching:
                return jsonify({'error': 'Selected matching not found'})
            
            # Get options
            export_choice = data.get('export_choice', '3')  # 1: Excel only, 2: Visual only, 3: Both
            
            # Get data from the selected matching
            clean_tables = selected_matching.get('clean_tables_df', {})
            
            # If clean_tables_df not available, recreate from serialized
            if not clean_tables:
                clean_tables_serialized = selected_matching.get('clean_tables', {})
                clean_tables = {}
                for table_name, table_data in clean_tables_serialized.items():
                    if isinstance(table_data, list):
                        clean_tables[table_name] = pd.DataFrame(table_data)
                    else:
                        clean_tables[table_name] = table_data
            
            apartment_summaries = selected_matching.get('apartment_summaries', {})
            apartments_list = selected_matching.get('selected_apartments', [])
            has_pattern = selected_matching.get('has_pattern', False)
            
            # Create temporary directory for exports
            export_dir = "tile_matching_exports"
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)
            
            created_files = []
            
            # Part A: Excel Export with Consolidated Summary
            if export_choice in ["1", "3"]:
                # Get apartment and inventory data
                apartment_tables = {}
                inventory_tables = {}
                
                if has_pattern:
                    if 'x_direction' in clean_tables:
                        apartment_tables['x'] = clean_tables['x_direction']
                    if 'y_direction' in clean_tables:
                        apartment_tables['y'] = clean_tables['y_direction']
                    if 'x_inv' in clean_tables:
                        inventory_tables['x'] = clean_tables['x_inv']
                    if 'y_inv' in clean_tables:
                        inventory_tables['y'] = clean_tables['y_inv']
                else:
                    if 'all_direction' in clean_tables:
                        apartment_tables['all'] = clean_tables['all_direction']
                    if 'all_inv' in clean_tables:
                        inventory_tables['all'] = clean_tables['all_inv']
                
                # Create individual apartment workbooks
                for apartment in apartments_list:
                    apartment_data = pd.DataFrame()
                    
                    for direction, table_data in apartment_tables.items():
                        apt_specific = table_data[table_data['Apartment'] == apartment].copy()
                        if not apt_specific.empty:
                            apartment_data = pd.concat([apartment_data, apt_specific], ignore_index=True)
                    
                    if apartment_data.empty:
                        continue
                    
                    # Get matching inventory data
                    apartment_group_ids = set(apartment_data['Group ID'].dropna().unique())
                    
                    x_inv_for_apartment = pd.DataFrame()
                    y_inv_for_apartment = pd.DataFrame()
                    
                    for direction, inv_data in inventory_tables.items():
                        if direction in ['x', 'all']:
                            matching_inv = inv_data[inv_data['Group ID'].isin(apartment_group_ids)].copy()
                            if not matching_inv.empty:
                                x_inv_for_apartment = pd.concat([x_inv_for_apartment, matching_inv], ignore_index=True)
                        
                        if direction in ['y', 'all']:
                            matching_inv = inv_data[inv_data['Group ID'].isin(apartment_group_ids)].copy()
                            if not matching_inv.empty:
                                y_inv_for_apartment = pd.concat([y_inv_for_apartment, matching_inv], ignore_index=True)
                    
                    filename = export_processor.create_apartment_workbook(
                        apartment, 
                        apartment_data,
                        x_inv_for_apartment if not x_inv_for_apartment.empty else None,
                        y_inv_for_apartment if not y_inv_for_apartment.empty else None,
                        has_pattern
                    )
                    
                    if filename:
                        created_files.append(filename)
                
                # *** CONSOLIDATED MASTER WORKBOOK WITH ENHANCED SUMMARY ***
                master_filename = os.path.join(export_dir, f"MASTER_SUMMARY_{matching_id}.xlsx")
                
                with pd.ExcelWriter(master_filename, engine='openpyxl') as writer:
                    # EXISTING SHEETS - Keep your current summary sheets
                    # Summary sheet
                    summary_data = []
                    for apt, summary in apartment_summaries.items():
                        summary_data.append({
                            'Apartment': apt,
                            'Total Pieces': summary['total_pieces'],
                            'Matched': summary['matched_pieces'],
                            'Unmatched': summary['unmatched_pieces'],
                            'Match %': f"{summary.get('match_percentage', 0)}%",
                            'Apartment Matches': summary['apartment_matches'],
                            'Inventory Matches': summary['inventory_matches']
                        })
                    
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='1. Matching Summary', index=False)
                    
                    # Matching info sheet
                    info_data = {
                        'Property': ['Matching Name', 'Date', 'Selected Apartments', 'Include Inventory'],
                        'Value': [
                            selected_matching['name'],
                            selected_matching['timestamp'],
                            ', '.join(apartments_list),
                            'Yes' if selected_matching['include_inventory'] else 'No'
                        ]
                    }
                    info_df = pd.DataFrame(info_data)
                    info_df.to_excel(writer, sheet_name='2. Matching Info', index=False)
                    
                    # All apartments data
                    if apartment_tables:
                        all_data = pd.concat(list(apartment_tables.values()), ignore_index=True)
                        all_data.to_excel(writer, sheet_name='3. All Apartments Data', index=False)
                    
                    # All inventory data
                    if inventory_tables:
                        all_inv = pd.concat(list(inventory_tables.values()), ignore_index=True)
                        all_inv.to_excel(writer, sheet_name='4. All Inventory Data', index=False)
                    
                    # *** NEW: ENHANCED SUMMARY SHEETS ***
                    try:
                        # Get required data for enhanced summary
                        tile_classification_results = session.get('tile_classification_results', {})
                        tiles_df = pd.DataFrame(tile_classification_results['tiles_df'])
                        small_tiles_results = session.get('small_tiles_results', {})
                        small_tiles_df = pd.DataFrame(small_tiles_results.get('small_tiles_df', []))
                        final_room_df = pd.DataFrame(session.get('final_room_df', []))
                        
                        if not tiles_df.empty and not final_room_df.empty:
                            # Create enhanced summary data using the NEW method
                            enhanced_summary_data = export_processor.create_enhanced_summary_data_for_master(
                                tiles_df, small_tiles_df, final_room_df, selected_matching
                            )
                            
                            if enhanced_summary_data:
                                # Add enhanced summary sheets
                                enhanced_summary_data['summary_df'].to_excel(writer, sheet_name='5. Wastage Analysis', index=False)
                                enhanced_summary_data['detailed_df'].to_excel(writer, sheet_name='6. Detailed Breakdown', index=False)
                                enhanced_summary_data['project_summary_df'].to_excel(writer, sheet_name='7. Project Summary', index=False)
                                enhanced_summary_data['tile_specs_df'].to_excel(writer, sheet_name='8. Tile Specifications', index=False)
                                
                                print("✅ Enhanced summary sheets added to master workbook")
                            else:
                                print("⚠️ Could not create enhanced summary data")
                        else:
                            print("⚠️ Missing tile or room data for enhanced summary")
                            
                    except Exception as summary_error:
                        print(f"⚠️ Error adding enhanced summary to master workbook: {summary_error}")
                        import traceback
                        traceback.print_exc()
                
                created_files.append(master_filename)
                
                # DO NOT CREATE SEPARATE ENHANCED SUMMARY - It's now part of master workbook
            
            # Part B: Visual Reports (unchanged from your existing code)
            if export_choice in ["2", "3"]:
                visual_dir = os.path.join(export_dir, "visual_reports")
                if not os.path.exists(visual_dir):
                    os.makedirs(visual_dir)
                
                # Get required data
                tile_classification_results = session.get('tile_classification_results', {})
                tiles_df = pd.DataFrame(tile_classification_results['tiles_df'])
                final_room_df = pd.DataFrame(session.get('final_room_df', []))
                
                # Deserialize room polygons
                room_polygons = deserialize_rooms(session.get('room_polygons', []))
                if len(room_polygons) == len(final_room_df):
                    final_room_df['polygon'] = room_polygons
                
                # Deserialize tile polygons
                apartments_data = session.get('apartments_data', {})
                if apartments_data:
                    deserialized_data = deserialize_apartments_data(apartments_data)
                
                # Get matching data
                group_mapping = selected_matching.get('group_mapping', {})
                tile_specs_to_groups = selected_matching.get('tile_specs_to_groups', {})
                tile_width = selected_matching.get('tile_width', 600)
                tile_height = selected_matching.get('tile_height', 600)
                
                # If group mapping not available, recreate it
                if not group_mapping:
                    group_mapping, tile_specs_to_groups = matching_processor.create_group_based_tile_mapping(clean_tables)
                
                for apartment_name in apartments_list:
                    apt_tiles = tiles_df[tiles_df['apartment_name'] == apartment_name].copy()
                    apt_rooms = final_room_df[final_room_df['apartment_name'] == apartment_name].copy()
                    
                    if apt_tiles.empty or apt_rooms.empty:
                        continue
                    
                    # Add polygons back to tiles
                    if apartment_name in deserialized_data:
                        tile_polygon_map = {}
                        for idx, tile in enumerate(deserialized_data[apartment_name]['tiles']):
                            if 'polygon' in tile:
                                tile_polygon_map[idx] = tile['polygon']
                        
                        for idx, tile in apt_tiles.iterrows():
                            tile_idx = tile['tile_index']
                            if tile_idx in tile_polygon_map:
                                apt_tiles.at[idx, 'polygon'] = tile_polygon_map[tile_idx]
                    
                    # Create visualization
                    summary = visualizer.visualize_apartment_tiles(
                        apartment_name, apt_tiles, apt_rooms, 
                        group_mapping, tile_specs_to_groups, 
                        tile_width, tile_height,
                        matching_processor.get_tile_color_group_based
                    )
                    
                    # Save figure
                    visual_file = os.path.join(visual_dir, f"{apartment_name}_visual_report.png")
                    plt.savefig(visual_file, dpi=300, bbox_inches='tight')
                    plt.close()
                    
                    created_files.append(visual_file)
            
            # Part C: Create ZIP file (unchanged from your existing code)
            if created_files:
                import zipfile
                import re
                
                # Clean the matching name to remove invalid characters
                clean_matching_name = re.sub(r'[<>:"/\\|?*]', '_', selected_matching['name'])
                zip_filename = f"Tile_Matching_{clean_matching_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                
                with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in created_files:
                        arcname = os.path.relpath(file_path, os.path.dirname(export_dir))
                        zipf.write(file_path, arcname)
                
                # Clean up temporary files
                import shutil
                try:
                    shutil.rmtree(export_dir)
                except:
                    pass
                
                # Read zip file for download
                with open(zip_filename, 'rb') as f:
                    zip_data = f.read()
                
                # Clean up zip file
                os.remove(zip_filename)
                
                # Encode for response
                zip_b64 = base64.b64encode(zip_data).decode('utf-8')
                
                return jsonify({
                    'success': True,
                    'zip_file': zip_b64,
                    'filename': zip_filename,
                    'summary': {
                        'apartments_processed': len(apartments_list),
                        'excel_files': len([f for f in created_files if f.endswith('.xlsx')]),
                        'visual_reports': len([f for f in created_files if f.endswith('.png')])
                    }
                })
            
            return jsonify({'error': 'No files created'})
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error in export process: {str(e)}'})
    
    # GET request
    try:
        matching_history = session.get('matching_history', [])
        
        return render_template('step9.html', matching_history=matching_history)
    
    except Exception as e:
        print(f"Error in step9 GET: {str(e)}")
        return redirect(url_for('step8'))

# Helper functions
def plt_to_base64():
    """Convert current matplotlib plot to base64 string"""
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

def generate_placeholder_image(title, width=800, height=600):
    """Generate a placeholder image with a title"""
    plt.figure(figsize=(width/100, height/100), dpi=100)
    plt.text(0.5, 0.5, title, ha='center', va='center', fontsize=24)
    plt.axis('off')
    plt.tight_layout()
    
    return plt_to_base64()

def serialize_polygon(polygon):
    """Serialize a Shapely polygon to a JSON-compatible format"""
    if polygon is None:
        return None
    return {
        'type': 'Polygon',
        'coordinates': [list(polygon.exterior.coords)]
    }

def is_room_rectangular(polygon):
    """Check if a room is rectangular (4 vertices and all right angles)"""
    coords = list(polygon.exterior.coords)[:-1]  # Remove duplicate last coordinate
    if len(coords) != 4:
        return False
    
    # Check if all angles are approximately 90 degrees
    # This is a simplified check - you can make it more sophisticated
    return True  # Simplified for now

def calculate_file_hash(filepath):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read file in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def has_project_data():
    """Check if there's project data in the session"""
    return any(key in session for key in ['rooms_data', 'room_df', 'apartments_data'])


def serialize_rooms(rooms):
    """Convert room polygons to a serializable format"""
    serialized_rooms = []
    for room in rooms:
        coords = list(room.exterior.coords)
        serialized_rooms.append({
            'coords': coords,
            'bounds': room.bounds
        })
    return serialized_rooms

def serialize_start_points(start_points):
    """Convert start point data to a serializable format"""
    serialized_points = []
    for sp in start_points:
        serialized_points.append({
            'centroid': sp['centroid'],
            'width': sp['width'],
            'height': sp['height'],
            'area': sp.get('area', 0),
            'room_id': sp.get('room_id', -1),
            'polygon_coords': list(sp['polygon'].exterior.coords) if 'polygon' in sp else []
        })
    return serialized_points

def deserialize_rooms(serialized_rooms):
    """Convert serialized room data back to Shapely polygons"""
    rooms = []
    for room_data in serialized_rooms:
        poly = Polygon(room_data['coords'])
        rooms.append(poly)
    return rooms

def deserialize_start_points(serialized_points):
    """Convert serialized start point data back to original format"""
    start_points = []
    for sp_data in serialized_points:
        sp = {
            'centroid': sp_data['centroid'],
            'width': sp_data['width'],
            'height': sp_data['height'],
            'area': sp_data.get('area', 0),
            'room_id': sp_data.get('room_id', -1)
        }
        if 'polygon_coords' in sp_data and sp_data['polygon_coords']:
            sp['polygon'] = Polygon(sp_data['polygon_coords'])
        start_points.append(sp)
    return start_points

def serialize_apartments_data(apartments_data):
    """Serialize apartment data with tiles for storage in session"""
    serialized_data = {}
    
    for apt_name, apt_data in apartments_data.items():
        serialized_tiles = []
        
        for tile in apt_data['tiles']:
            # Create a base serializable tile without polygons
            serialized_tile = {k: v for k, v in tile.items() if k != 'polygon' and k != 'layout_polygon'}
            
            # Serialize each tile's polygon - handle both Polygon and MultiPolygon
            if 'polygon' in tile and tile['polygon'] is not None:
                polygon = tile['polygon']
                if isinstance(polygon, Polygon):
                    serialized_tile['polygon_coords'] = list(polygon.exterior.coords)
                    serialized_tile['polygon_type'] = 'Polygon'
                    # Also serialize interior rings if present
                    if len(polygon.interiors) > 0:
                        serialized_tile['polygon_interiors'] = [list(interior.coords) 
                                                            for interior in polygon.interiors]
                elif isinstance(polygon, MultiPolygon):
                    # For MultiPolygon, store coordinates of each part
                    serialized_tile['polygon_parts'] = []
                    for part in polygon.geoms:
                        geom_data = {'exterior': list(part.exterior.coords)}
                        if len(part.interiors) > 0:
                            geom_data['interiors'] = [list(interior.coords) 
                                                    for interior in part.interiors]
                        serialized_tile['polygon_parts'].append(geom_data)
                    serialized_tile['polygon_type'] = 'MultiPolygon'
            
            # Serialize layout_polygon if it exists
            if 'layout_polygon' in tile and tile['layout_polygon'] is not None:
                layout_polygon = tile['layout_polygon']
                if isinstance(layout_polygon, Polygon):
                    serialized_tile['layout_polygon_coords'] = list(layout_polygon.exterior.coords)
                    serialized_tile['layout_polygon_type'] = 'Polygon'
                    # Serialize interior rings if present
                    if len(layout_polygon.interiors) > 0:
                        serialized_tile['layout_polygon_interiors'] = [list(interior.coords) 
                                                                   for interior in layout_polygon.interiors]
                elif isinstance(layout_polygon, MultiPolygon):
                    # For MultiPolygon, store coordinates of each part
                    serialized_tile['layout_polygon_parts'] = []
                    for part in layout_polygon.geoms:
                        geom_data = {'exterior': list(part.exterior.coords)}
                        if len(part.interiors) > 0:
                            geom_data['interiors'] = [list(interior.coords) 
                                                    for interior in part.interiors]
                        serialized_tile['layout_polygon_parts'].append(geom_data)
                    serialized_tile['layout_polygon_type'] = 'MultiPolygon'
            
            serialized_tiles.append(serialized_tile)
        
        serialized_data[apt_name] = {
            'orientation': apt_data['orientation'],
            'tiles': serialized_tiles
        }
    
    return serialized_data

def deserialize_apartments_data(serialized_data):
    """Deserialize apartment data from session storage"""
    apartments_data = {}
    
    for apt_name, apt_data in serialized_data.items():
        tiles = []
        
        for tile_data in apt_data['tiles']:
            # Create a base tile without polygons
            tile = {k: v for k, v in tile_data.items() 
                  if k not in ['polygon_coords', 'polygon_parts', 'polygon_type',
                              'layout_polygon_coords', 'layout_polygon_parts', 'layout_polygon_type',
                              'polygon_interiors', 'layout_polygon_interiors']}
            
            # Deserialize the polygon
            if 'polygon_type' in tile_data:
                if tile_data['polygon_type'] == 'Polygon' and 'polygon_coords' in tile_data:
                    # Handle interior rings if present
                    if 'polygon_interiors' in tile_data:
                        tile['polygon'] = Polygon(
                            tile_data['polygon_coords'], 
                            [interior for interior in tile_data['polygon_interiors']]
                        )
                    else:
                        tile['polygon'] = Polygon(tile_data['polygon_coords'])
                elif tile_data['polygon_type'] == 'MultiPolygon' and 'polygon_parts' in tile_data:
                    # Create polygons for each part
                    polygons = []
                    for part in tile_data['polygon_parts']:
                        if isinstance(part, dict) and 'exterior' in part:
                            if 'interiors' in part:
                                poly = Polygon(part['exterior'], part['interiors'])
                            else:
                                poly = Polygon(part['exterior'])
                        else:
                            # Backward compatibility
                            poly = Polygon(part)
                        polygons.append(poly)
                    tile['polygon'] = MultiPolygon(polygons)
            
            # Deserialize the layout polygon
            if 'layout_polygon_type' in tile_data:
                if tile_data['layout_polygon_type'] == 'Polygon' and 'layout_polygon_coords' in tile_data:
                    # Handle interior rings if present
                    if 'layout_polygon_interiors' in tile_data:
                        tile['layout_polygon'] = Polygon(
                            tile_data['layout_polygon_coords'], 
                            [interior for interior in tile_data['layout_polygon_interiors']]
                        )
                    else:
                        tile['layout_polygon'] = Polygon(tile_data['layout_polygon_coords'])
                elif tile_data['layout_polygon_type'] == 'MultiPolygon' and 'layout_polygon_parts' in tile_data:
                    # Create polygons for each part
                    polygons = []
                    for part in tile_data['layout_polygon_parts']:
                        if isinstance(part, dict) and 'exterior' in part:
                            if 'interiors' in part:
                                poly = Polygon(part['exterior'], part['interiors'])
                            else:
                                poly = Polygon(part['exterior'])
                        else:
                            # Backward compatibility
                            poly = Polygon(part)
                        polygons.append(poly)
                    tile['layout_polygon'] = MultiPolygon(polygons)
            
            tiles.append(tile)
        
        apartments_data[apt_name] = {
            'orientation': apt_data['orientation'],
            'tiles': tiles
        }
    
    return apartments_data

def make_serializable_for_session(export_info):
    """Convert DataFrames to dictionaries for session storage"""
    result = {}
    
    # Copy everything except DataFrames
    for key, value in export_info.items():
        if isinstance(value, pd.DataFrame):
            # Convert DataFrame to records
            result[key] = value.to_dict('records')
        else:
            result[key] = value
    
    return result

@app.route('/navigate/<step>')
def navigate(step):
    """Handle navigation between steps"""
    valid_steps = ['step1', 'step2', 'step3', 'step4', 'step5', 'step6', 'step7', 'step8', 'step9']
    
    if step in valid_steps:
        return redirect(url_for(step))
    else:
        return redirect(url_for('index'))
    
@app.route('/download/<filename>')
def download_file(filename):
    """Download exported file"""
    try:
        filepath = os.path.join('exports', filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            return "File not found", 404
    except Exception as e:
        print(f"Error downloading file: {str(e)}")
        return "Error downloading file", 500
    
def clear_all_session_data():
    """Clear all session data EXCEPT login information"""
    # Preserve login information
    logged_in = session.get('logged_in')
    username = session.get('username')
    login_time = session.get('login_time')
    next_url = session.get('next_url')
    
    # Clear all session data
    session.clear()
    
    # Restore login information
    if logged_in:
        session['logged_in'] = logged_in
        session['username'] = username
        session['login_time'] = login_time
        session.permanent = True
        if next_url:
            session['next_url'] = next_url
    
    print("Project data cleared, login preserved")

def cleanup_old_uploaded_files():
    """Remove uploaded files older than 24 hours"""
    try:
        upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
        if os.path.exists(upload_folder):
            now = datetime.now()
            for filename in os.listdir(upload_folder):
                filepath = os.path.join(upload_folder, filename)
                if os.path.isfile(filepath):
                    # Remove files older than 24 hours
                    file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                    if now - file_time > timedelta(hours=24):
                        os.remove(filepath)
                        print(f"Removed old file: {filename}")
    except Exception as e:
        print(f"Error cleaning up files: {e}")

def cleanup_all_uploaded_files():
    """Remove ALL uploaded files immediately"""
    try:
        upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
        if os.path.exists(upload_folder):
            for filename in os.listdir(upload_folder):
                filepath = os.path.join(upload_folder, filename)
                if os.path.isfile(filepath):
                    try:
                        os.remove(filepath)
                        print(f"Removed uploaded file: {filename}")
                    except Exception as e:
                        print(f"Error removing file {filename}: {e}")
    except Exception as e:
        print(f"Error cleaning up upload folder: {e}")

def cleanup_current_uploaded_file():
    """Remove the most recently uploaded DXF file"""
    try:
        upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
        if os.path.exists(upload_folder):
            # Get the most recent file
            files = []
            for filename in os.listdir(upload_folder):
                filepath = os.path.join(upload_folder, filename)
                if os.path.isfile(filepath) and filename.lower().endswith('.dxf'):
                    files.append((filepath, os.path.getctime(filepath)))
            
            if files:
                # Sort by creation time, newest first
                files.sort(key=lambda x: x[1], reverse=True)
                # Remove the newest file (current project file)
                newest_file = files[0][0]
                os.remove(newest_file)
                print(f"Removed current project file: {os.path.basename(newest_file)}")
    except Exception as e:
        print(f"Error cleaning up current file: {e}")

def has_project_data():
    """Check if there's any project data in session"""
    key_indicators = [
        'rooms_data', 'apartments_data', 'tile_classification_results', 
        'matching_history', 'cut_pieces_by_half'
    ]
    return any(session.get(key) for key in key_indicators)

@app.route('/clear-session', methods=['POST'])
@login_required
def clear_session_route():
    """API endpoint to clear session data only"""
    try:
        clear_session_data_only()  # Only clear session, preserve projects
        return jsonify({
            'success': True, 
            'message': 'Session data cleared successfully!'
        })
    except Exception as e:
        return jsonify({'error': f'Error clearing session: {str(e)}'})
    
@app.route('/update_room_name', methods=['POST'])
@login_required
def update_room_name():
    """Update individual room name via AJAX"""
    try:
        data = request.get_json()
        room_id = int(data.get('room_id'))
        new_name = data.get('new_name', '').strip()
        
        if not new_name:
            return jsonify({'error': 'Room name cannot be empty'})
        
        # Update room_df in session
        room_df = pd.DataFrame(session.get('room_df', []))
        
        if room_df.empty:
            return jsonify({'error': 'No room data available'})
        
        # Find and update the room
        mask = room_df['room_id'] == room_id
        if not mask.any():
            return jsonify({'error': 'Room not found'})
        
        old_name = room_df.loc[mask, 'room_name'].iloc[0]
        room_df.loc[mask, 'room_name'] = new_name
        
        # Update session
        session['room_df'] = room_df.to_dict('records')
        
        return jsonify({
            'success': True,
            'message': f'Room name updated from "{old_name}" to "{new_name}"',
            'old_name': old_name,
            'new_name': new_name
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error updating room name: {str(e)}'})

@app.route('/toggle_edit_mode', methods=['POST'])
@login_required
def toggle_edit_mode():
    """Toggle between view and edit mode"""
    try:
        data = request.get_json()
        edit_mode = data.get('edit_mode', False)
        
        # Store edit mode preference in session if needed
        session['edit_mode'] = edit_mode
        
        return jsonify({'success': True, 'edit_mode': edit_mode})
        
    except Exception as e:
        return jsonify({'error': f'Error toggling edit mode: {str(e)}'})

@app.route('/finish-project', methods=['POST'])
@login_required
def finish_project():
    """Handle project completion with data cleanup"""
    try:
        # Mark project as complete in database before clearing
        if 'project_id' in session:
            project = Project.query.get(session['project_id'])
            if project:
                project.is_complete = True
                project.updated_at = datetime.utcnow()
                db.session.commit()
                print(f"Project {project.id} marked as complete")
        
        # Now clear session data only
        clear_session_data_only()
        
        return jsonify({
            'success': True,
            'message': 'Project completed successfully!',
            'redirect': url_for('index')
        })
    except Exception as e:
        return jsonify({'error': f'Error finishing project: {str(e)}'})
    
@app.route('/new-project', methods=['GET', 'POST'])
@login_required
def new_project():
    """Create new project with details"""
    from services.project_manager import ProjectManager
    
    # Check project limit
    if not ProjectManager.can_create_project(current_user):
        stats = ProjectManager.get_user_project_stats(current_user)
        flash(f'You have reached your project limit ({stats["project_limit"]} projects). Please delete an existing project to create a new one.', 'error')
        return redirect(url_for('user_dashboard'))
    
    if request.method == 'POST':
        project_name = request.form.get('project_name', '').strip()
        project_area = request.form.get('project_area', '').strip()
        project_description = request.form.get('project_description', '').strip()
        
        if not project_name:
            flash('Project name is required', 'error')
            return redirect(url_for('new_project'))
        
        try:
            # Create new project in database
            project = Project(
                user_id=current_user.id,
                project_name=project_name,
                current_step=1,
                created_at=datetime.utcnow()
            )
            
            # Add optional fields if provided
            if project_area:
                try:
                    project.total_area = float(project_area)
                except ValueError:
                    pass
            
            # Store description in session for now
            if project_description:
                session['project_description'] = project_description
            
            db.session.add(project)
            db.session.commit()
            
            # Store project ID in session
            session['project_id'] = project.id
            session['project_name'] = project_name
            
            # Log activity
            db_bridge.log_activity(
                current_user.id,
                project.id,
                'project_created',
                f'Created new project: {project_name}'
            )
            
            flash(f'Project "{project_name}" created successfully!', 'success')
            return redirect(url_for('step1'))
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Error creating project: {str(e)}')
            flash('Error creating project. Please try again.', 'error')
            return redirect(url_for('new_project'))
    
    return render_template('new_project.html')

@app.route('/navigate_to_step/<int:step_number>')
@login_required
def navigate_to_step(step_number):
    """Navigate to a specific step with data restoration"""
    try:
        # Validate step number
        if step_number < 1 or step_number > 9:
            flash('Invalid step number', 'error')
            return redirect(url_for('index'))
        
        # Check if there's an active project
        if 'project_id' not in session:
            flash('No active project found. Please start a new project.', 'warning')
            return redirect(url_for('step1'))
        
        project_id = session['project_id']
        project = Project.query.get(project_id)
        
        if not project:
            flash('Project not found', 'error')
            session.pop('project_id', None)
            return redirect(url_for('step1'))
        
        # Check if user can access this step
        if not project.can_access_step(step_number):
            flash(f'Please complete the previous steps first', 'warning')
            return redirect(url_for(f'step{project.current_step}'))
        
        # If navigating to a completed step, restore its data
        if getattr(project, f'step{step_number}_complete', False):
            # Restore all data up to this step
            SessionDataManager.restore_all_completed_steps(project_id)
            flash(f'Resumed at Step {step_number}', 'info')
        
        # Redirect to the appropriate step
        return redirect(url_for(f'step{step_number}'))
        
    except Exception as e:
        print(f'Error navigating to step {step_number}: {str(e)}')
        flash('Error navigating to step', 'error')
        return redirect(url_for('index'))

@app.route('/api/save_progress', methods=['POST'])
@login_required
def save_progress():
    """Save current step progress manually or automatically"""
    try:
        data = request.get_json()
        step_number = data.get('step_number')
        manual_save = data.get('manual_save', False)
        
        print(f"Save progress request: step={step_number}, manual={manual_save}")
        
        if 'project_id' not in session:
            return jsonify({'error': 'No active project found'}), 400
        
        project_id = session['project_id']
        project = Project.query.get(project_id)
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Check if step is valid
        if not step_number or step_number < 1 or step_number > 9:
            return jsonify({'error': 'Invalid step number'}), 400
        
        # Simple save approach - mark step as saved and update project
        try:
            # Update project current step if this is further than current
            if step_number > project.current_step:
                project.current_step = step_number
            
            # Mark the step as complete (this will vary based on what data exists)
            step_complete_field = f'step{step_number}_complete'
            if hasattr(project, step_complete_field):
                setattr(project, step_complete_field, True)
            
            # Update timestamps
            project.updated_at = datetime.utcnow()
            
            # Commit changes
            db.session.commit()
            
            # Log activity
            save_type = "manual" if manual_save else "auto"
            db_bridge.log_activity(
                current_user.id,
                project.id,
                f'step{step_number}_saved',
                f'Step {step_number} {save_type} save completed'
            )
            
            print(f"Successfully saved step {step_number} for project {project_id}")
            
            return jsonify({
                'success': True,
                'message': f'Step {step_number} saved successfully',
                'save_type': save_type,
                'project_id': project.id,
                'current_step': project.current_step
            })
            
        except Exception as db_error:
            print(f"Database error saving step {step_number}: {str(db_error)}")
            db.session.rollback()
            return jsonify({'error': f'Database error: {str(db_error)}'}), 500
        
    except Exception as e:
        print(f'Error in save_progress: {str(e)}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to save progress: {str(e)}'}), 500

@app.route('/api/auto_save', methods=['POST'])
@login_required
def api_auto_save():
    """Auto-save current step data - simplified version"""
    try:
        if 'project_id' not in session:
            return jsonify({'error': 'No active project'}), 400
        
        project_id = session['project_id']
        project = Project.query.get(project_id)
        
        if not project:
            return jsonify({'error': 'Project not found'}), 400
        
        # Simple auto-save: just update the timestamp
        project.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Data auto-saved successfully'
        })
        
    except Exception as e:
        print(f'Auto-save error: {str(e)}')
        return jsonify({'error': f'Auto-save error: {str(e)}'}), 500

@app.route('/resume_project/<int:project_id>')
@login_required
def resume_project(project_id):
    """Resume an existing project by restoring its session data"""
    try:
        project = Project.query.get_or_404(project_id)
        
        # Check ownership
        if project.user_id != current_user.id:
            flash('Unauthorized access to project', 'error')
            return redirect(url_for('user_dashboard'))
        
        # Clear any existing session data ONLY (don't delete projects)
        clear_session_data_only()
        
        # Set the project ID in session
        session['project_id'] = project.id
        session['project_name'] = project.project_name
        
        # Restore all completed steps data to session
        from services.session_data_manager import SessionDataManager
        success = SessionDataManager.restore_all_completed_steps(project_id)
        
        if success:
            flash(f'Resumed project: {project.project_name}', 'info')
            # Redirect to the current step
            return redirect(url_for(f'step{project.current_step}'))
        else:
            flash('Could not restore project data. Starting from current step.', 'warning')
            return redirect(url_for(f'step{project.current_step}'))
        
    except Exception as e:
        print(f'Error resuming project {project_id}: {str(e)}')
        flash('Error resuming project', 'error')
        return redirect(url_for('user_dashboard'))

def simple_step_save(project_id, step_number):
    """Simple helper function to save step progress"""
    try:
        project = Project.query.get(project_id)
        if not project:
            return False
        
        # Update current step if this is further
        if step_number > project.current_step:
            project.current_step = step_number
        
        # Mark step as complete
        step_complete_field = f'step{step_number}_complete'
        if hasattr(project, step_complete_field):
            setattr(project, step_complete_field, True)
        
        project.updated_at = datetime.utcnow()
        db.session.commit()
        
        return True
        
    except Exception as e:
        print(f"Error in simple_step_save: {str(e)}")
        db.session.rollback()
        return False

def clear_session_data_only():
    """Clear only session data, DO NOT delete projects from database"""
    # Clear session project data
    project_keys = [
        'rooms_data', 'start_points_data', 'tile_sizes', 'cluster_plot',
        'room_df', 'room_polygons', 'final_room_df', 'apartments_data',
        'tile_analysis_results', 'tile_classification_results',
        'small_tiles_results', 'tile_polygon_mapping', 'tiles_remaining',
        'small_tiles_removed', 'export_results', 'cut_pieces_by_half',
        'matching_history', 'current_matching', 'step7_complete',
        'project_id', 'uploaded_file', 'dxf_data', 'step1_complete',
        'step2_complete', 'step3_complete', 'step4_complete', 'step5_complete',
        'step6_complete', 'step8_complete', 'step9_complete'
    ]
    
    # Clear any uploaded files from session ONLY
    if 'uploaded_file' in session:
        try:
            filepath = session.get('uploaded_file')
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
                print(f"Removed uploaded file: {filepath}")
        except Exception as e:
            print(f"Error removing file: {str(e)}")
    
    # Clear all project-related session data
    for key in project_keys:
        session.pop(key, None)
    
    print("Session data cleared, projects preserved in database")

@app.cli.command('create-user')
@click.argument('username')
@click.argument('email')
@click.argument('password')
@click.option('--admin', is_flag=True, help='Give user admin privileges')
def create_user_command(username, email, password, admin):
    """Create a new user via command line"""
    try:
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            click.echo(f'Error: User {username} already exists')
            return
        
        if User.query.filter_by(email=email).first():
            click.echo(f'Error: Email {email} already in use')
            return
        
        # Create new user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role='admin' if admin else 'user'
        )
        
        db.session.add(user)
        db.session.commit()
        
        click.echo(f'Successfully created user: {username} ({"admin" if admin else "user"})')
        
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error creating user: {str(e)}')

@app.cli.command('reset-password')
@click.argument('username')
@click.argument('new_password')
def reset_password_command(username, new_password):
    """Reset a user's password via command line"""
    try:
        user = User.query.filter_by(username=username).first()
        
        if not user:
            click.echo(f'Error: User {username} not found')
            return
        
        if len(new_password) < 6:
            click.echo('Error: Password must be at least 6 characters')
            return
        
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        click.echo(f'Successfully reset password for user: {username}')
        
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error resetting password: {str(e)}')

@app.cli.command('list-users')
def list_users_command():
    """List all users in the system"""
    users = User.query.all()
    
    if not users:
        click.echo('No users found in the database')
        return
    
    click.echo('\nRegistered Users:')
    click.echo('-' * 60)
    click.echo(f'{"Username":<20} {"Email":<30} {"Role":<10}')
    click.echo('-' * 60)
    
    for user in users:
        click.echo(f'{user.username:<20} {user.email:<30} {user.role:<10}')
    
    click.echo(f'\nTotal users: {len(users)}')

@app.cli.command('migrate-users')
def migrate_users_command():
    """Migrate hardcoded users to database"""
    # Define the old hardcoded users that need migration
    old_users = {
        'admin': ('admin123', 'admin@tileoptimization.com', 'admin'),
        'user': ('password123', 'user@tileoptimization.com', 'user'),
        'demo': ('demo123', 'demo@tileoptimization.com', 'user'),
        'J384_TileOptz': ('J384', 'j384@tileoptimization.com', 'user'),
        'J386_TileOptz': ('J386', 'j386@tileoptimization.com', 'user'),
        'J385_TileOptz': ('J385', 'j385@tileoptimization.com', 'user'),
        'J388_TileOptz': ('J388', 'j388@tileoptimization.com', 'user'),
        'J390_TileOptz': ('J390', 'j390@tileoptimization.com', 'user'),
        'TestDemo2025': ('TDemo25', 'testdemo2025@tileoptimization.com', 'user')
    }
    
    migrated = 0
    skipped = 0
    
    for username, (password, email, role) in old_users.items():
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            click.echo(f'Skipping {username} - already exists')
            skipped += 1
            continue
        
        try:
            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role=role
            )
            db.session.add(user)
            db.session.commit()
            
            click.echo(f'Migrated user: {username}')
            migrated += 1
            
        except Exception as e:
            db.session.rollback()
            click.echo(f'Error migrating {username}: {str(e)}')
            skipped += 1
    
    click.echo(f'\nMigration complete: {migrated} users migrated, {skipped} skipped')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)