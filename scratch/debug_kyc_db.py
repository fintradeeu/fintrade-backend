import sqlalchemy as sa

def debug():
    url = "postgresql://lms_user:lms_password@localhost:5433/lms_db"
    engine = sa.create_engine(url)
    
    try:
        with engine.connect() as conn:
            res = conn.execute(sa.text("SELECT udt_name FROM information_schema.columns WHERE table_name='kyc_submissions' AND column_name='status'"))
            row = res.fetchone()
            print("udt_name for status column:", row[0] if row else "None")
    except Exception as e:
        print("Sync DB debug failed:", e)

if __name__ == "__main__":
    debug()
