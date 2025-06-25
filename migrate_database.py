import os
import sys
from sqlalchemy import create_engine, inspect, text
from datetime import datetime

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("❌ Error: DATABASE_URL not found in environment variables")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def run_migration():
    """Run all migrations safely"""
    print("🚀 Starting database migration...")
    
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()
        
        try:
            # 1. Add columns to users table
            print("📊 Checking users table...")
            inspector = inspect(engine)
            existing_columns = [col['name'] for col in inspector.get_columns('users')]
            
            if 'status' not in existing_columns:
                conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN status VARCHAR(20) DEFAULT 'active'
                """))
                print("✅ Added 'status' column to users table")
            
            if 'project_limit' not in existing_columns:
                conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN project_limit INTEGER DEFAULT 5
                """))
                print("✅ Added 'project_limit' column to users table")
            
            # Update existing users
            conn.execute(text("UPDATE users SET status = 'active' WHERE status IS NULL"))
            conn.execute(text("UPDATE users SET project_limit = 50 WHERE role = 'admin'"))
            print("✅ Updated existing users with default values")
            
            # 2. Create project_archives table
            print("📦 Creating project_archives table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS project_archives (
                    id SERIAL PRIMARY KEY,
                    original_project_id INTEGER,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    project_name VARCHAR(255),
                    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_json TEXT,
                    file_size_mb FLOAT,
                    anonymized BOOLEAN DEFAULT FALSE,
                    used_for_training BOOLEAN DEFAULT FALSE
                )
            """))
            print("✅ Created project_archives table")
            
            # 3. Create user_dashboards table for cached stats
            print("📈 Creating user_dashboards table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_dashboards (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    total_area_optimized FLOAT DEFAULT 0,
                    average_waste_reduction FLOAT DEFAULT 0,
                    total_tiles_saved INTEGER DEFAULT 0,
                    projects_completed INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id)
                )
            """))
            print("✅ Created user_dashboards table")
            
            # Commit transaction
            trans.commit()
            print("\n✨ Migration completed successfully!")
            
        except Exception as e:
            trans.rollback()
            print(f"\n❌ Migration failed: {str(e)}")
            sys.exit(1)

if __name__ == '__main__':
    run_migration()