from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import json

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    company_name = db.Column(db.String(255))
    role = db.Column(db.String(50), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    projects = db.relationship('Project', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'company_name': self.company_name,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Project(db.Model):
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    project_name = db.Column(db.String(255))
    dxf_file_hash = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_complete = db.Column(db.Boolean, default=False)
    
    # Project data
    total_area = db.Column(db.Float)
    num_apartments = db.Column(db.Integer)
    num_rooms = db.Column(db.Integer)
    
    # Results
    design_waste_percent = db.Column(db.Float)
    optimized_waste_percent = db.Column(db.Float)
    actual_waste_percent = db.Column(db.Float)
    
    # Step tracking
    current_step = db.Column(db.Integer, default=1)
    step1_complete = db.Column(db.Boolean, default=False)
    step2_complete = db.Column(db.Boolean, default=False)
    step3_complete = db.Column(db.Boolean, default=False)
    step4_complete = db.Column(db.Boolean, default=False)
    step5_complete = db.Column(db.Boolean, default=False)
    step6_complete = db.Column(db.Boolean, default=False)
    step7_complete = db.Column(db.Boolean, default=False)
    step8_complete = db.Column(db.Boolean, default=False)
    step9_complete = db.Column(db.Boolean, default=False)
    
    # Relationships
    rooms = db.relationship('Room', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    files = db.relationship('ProjectFile', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    optimization_results = db.relationship('OptimizationResult', backref='project', lazy='dynamic', cascade='all, delete-orphan')

class Room(db.Model):
    __tablename__ = 'rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'))
    room_name = db.Column(db.String(100))
    apartment_name = db.Column(db.String(100))
    
    # Geometry
    polygon_json = db.Column(db.Text)  # Store as GeoJSON string
    area = db.Column(db.Float)
    perimeter = db.Column(db.Float)
    bounds_json = db.Column(db.Text)  # Store as JSON string
    
    # AI features
    num_vertices = db.Column(db.Integer)
    is_rectangular = db.Column(db.Boolean)
    is_convex = db.Column(db.Boolean)
    compactness = db.Column(db.Float)
    rectangularity = db.Column(db.Float)
    aspect_ratio = db.Column(db.Float)
    
    # Start point
    start_point_x = db.Column(db.Float)
    start_point_y = db.Column(db.Float)
    sp_relative_x = db.Column(db.Float)
    sp_relative_y = db.Column(db.Float)
    sp_dist_to_centroid = db.Column(db.Float)
    sp_dist_to_nearest_wall = db.Column(db.Float)
    
    # Orientation
    orientation_angle = db.Column(db.Float)
    is_clockwise = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    tile_configs = db.relationship('TileConfig', backref='room', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert to dictionary for session compatibility"""
        return {
            'id': self.id,
            'room_name': self.room_name,
            'apartment_name': self.apartment_name,
            'polygon': json.loads(self.polygon_json) if self.polygon_json else None,
            'area': self.area,
            'perimeter': self.perimeter,
            'bounds': json.loads(self.bounds_json) if self.bounds_json else None,
            'num_vertices': self.num_vertices,
            'start_point': {'x': self.start_point_x, 'y': self.start_point_y} if self.start_point_x else None,
            'orientation': self.orientation_angle,
            'is_clockwise': self.is_clockwise
        }
    
class TileConfig(db.Model):
    __tablename__ = 'tile_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'))
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id', ondelete='CASCADE'))
    
    # Tile specs
    tile_width = db.Column(db.Float)
    tile_height = db.Column(db.Float)
    grout_thickness = db.Column(db.Float, default=3.0)
    has_pattern = db.Column(db.Boolean, default=False)
    pattern_direction = db.Column(db.String(20))
    
    # Results
    total_tiles = db.Column(db.Integer)
    full_tiles = db.Column(db.Integer)
    cut_tiles = db.Column(db.Integer)
    irregular_tiles = db.Column(db.Integer)
    
    # Detailed classification
    cut_x_tiles = db.Column(db.Integer)
    cut_y_tiles = db.Column(db.Integer)
    all_cut_tiles = db.Column(db.Integer)
    small_cuts_count = db.Column(db.Integer)
    
    # Ratios
    full_tile_ratio = db.Column(db.Float)
    cut_tile_ratio = db.Column(db.Float)
    irregular_ratio = db.Column(db.Float)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OptimizationResult(db.Model):
    __tablename__ = 'optimization_results'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'))
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id', ondelete='CASCADE'))
    
    # Waste analysis
    design_waste_percent = db.Column(db.Float)
    optimized_waste_percent = db.Column(db.Float)
    improvement_percent = db.Column(db.Float)
    
    # Matching
    matched_cuts = db.Column(db.Integer)
    unmatched_cuts = db.Column(db.Integer)
    matched_less_than_half = db.Column(db.Integer)
    matched_more_than_half = db.Column(db.Integer)
    unmatched_less_than_half = db.Column(db.Integer)
    unmatched_more_than_half = db.Column(db.Integer)
    
    # Performance
    processing_time_seconds = db.Column(db.Float)
    optimization_iterations = db.Column(db.Integer)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ProjectFile(db.Model):
    __tablename__ = 'project_files'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'))
    file_type = db.Column(db.String(50))
    file_name = db.Column(db.String(255))
    file_path = db.Column(db.Text)
    file_size = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'))
    action = db.Column(db.String(100))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class InventoryPiece(db.Model):
    __tablename__ = 'inventory_pieces'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'))
    piece_type = db.Column(db.String(20))
    cut_size = db.Column(db.Float)
    remaining_size = db.Column(db.Float)
    apartment_name = db.Column(db.String(100))
    location = db.Column(db.String(100))
    is_matched = db.Column(db.Boolean, default=False)
    match_id = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)