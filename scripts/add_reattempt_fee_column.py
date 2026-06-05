import os
import sqlalchemy as sa
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

def main():
    # Force loading of local .env file first
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(script_dir)
    env_path = os.path.join(backend_dir, ".env")
    
    if os.path.exists(env_path):
        print(f"Loading local .env from: {env_path}")
        load_dotenv(env_path, override=True)
    else:
        print("No local .env file found, using default dotenv loading.")
        load_dotenv()
        
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        database_url = "postgresql+asyncpg://lms_user:lms_password@localhost:5433/lms_db"

    # Replace async pg driver with sync driver for standard SQLAlchemy connection
    database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    database_url = database_url.replace("sqlite+aiosqlite://", "sqlite://")
    
    parsed = urlparse(database_url)
    if parsed.scheme == "postgresql":
        params = parse_qs(parsed.query)
        params["sslmode"] = ["prefer"]
        database_url = urlunparse(parsed._replace(query=urlencode(params, doseq=True)))
        
    print(f"Connecting to database: {database_url.split('@')[-1]}")
    engine = sa.create_engine(database_url)
    
    with engine.begin() as conn:
        try:
            conn.execute(sa.text("ALTER TABLE course_exams ADD COLUMN reattempt_fee DOUBLE PRECISION DEFAULT 500.0;"))
            print("Successfully added reattempt_fee column to course_exams table.")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                print("Column reattempt_fee already exists in course_exams table.")
            else:
                print(f"Failed to add column: {e}")

if __name__ == "__main__":
    main()
