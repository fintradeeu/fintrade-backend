"""
Direct database schema fix for production Neon/Vercel Postgres.
"""
import asyncio
import ssl
import asyncpg

NEON_URL = "postgresql://neondb_owner:npg_ntbmE2jcy4aU@ep-raspy-lab-aq05aqgy.c-8.us-east-1.aws.neon.tech/neondb"

ALTER_STATEMENTS = [
    "ALTER TABLE entrance_exams ADD COLUMN IF NOT EXISTS questions_per_attempt INTEGER",
    "ALTER TABLE entrance_exams ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true",
    "ALTER TABLE entrance_exams ADD COLUMN IF NOT EXISTS start_time TIMESTAMPTZ",
    "ALTER TABLE entrance_exams ADD COLUMN IF NOT EXISTS end_time TIMESTAMPTZ",
    "ALTER TABLE entrance_exams ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
    "ALTER TABLE entrance_exams ADD COLUMN IF NOT EXISTS description TEXT",
    "ALTER TABLE entrance_exams ADD COLUMN IF NOT EXISTS max_attempts INTEGER DEFAULT 0",
    "ALTER TABLE course_exams ADD COLUMN IF NOT EXISTS questions_per_attempt INTEGER",
    "ALTER TABLE course_exams ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true",
    "ALTER TABLE course_exams ADD COLUMN IF NOT EXISTS start_time TIMESTAMPTZ",
    "ALTER TABLE course_exams ADD COLUMN IF NOT EXISTS end_time TIMESTAMPTZ",
    "ALTER TABLE course_exams ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
    "ALTER TABLE exam_answers ADD COLUMN IF NOT EXISTS is_correct BOOLEAN",
    "ALTER TABLE course_exam_answers ADD COLUMN IF NOT EXISTS is_correct BOOLEAN",

    # --- exam_questions ---
    "ALTER TABLE exam_questions ADD COLUMN IF NOT EXISTS category VARCHAR(100)",
    "ALTER TABLE exam_questions ADD COLUMN IF NOT EXISTS negative_marks FLOAT DEFAULT 0.0",
    "ALTER TABLE exam_questions ADD COLUMN IF NOT EXISTS explanation TEXT",

    # --- course_exam_questions ---
    "ALTER TABLE course_exam_questions ADD COLUMN IF NOT EXISTS category VARCHAR(100)",
    "ALTER TABLE course_exam_questions ADD COLUMN IF NOT EXISTS negative_marks FLOAT DEFAULT 0.0",
    "ALTER TABLE course_exam_questions ADD COLUMN IF NOT EXISTS explanation TEXT",

    # --- entrance_exams ---
    "ALTER TABLE entrance_exams ADD COLUMN IF NOT EXISTS questions_per_attempt INTEGER",
    "ALTER TABLE entrance_exams ADD COLUMN IF NOT EXISTS start_time TIMESTAMPTZ",
    "ALTER TABLE entrance_exams ADD COLUMN IF NOT EXISTS end_time TIMESTAMPTZ",

    # --- course_exams ---
    "ALTER TABLE course_exams ADD COLUMN IF NOT EXISTS questions_per_attempt INTEGER",

    # --- exam_attempts (Entrance) ---
    "ALTER TABLE exam_attempts ADD COLUMN IF NOT EXISTS needs_manual_evaluation BOOLEAN DEFAULT FALSE",

    # --- course_exam_attempts ---
    "ALTER TABLE course_exam_attempts ADD COLUMN IF NOT EXISTS device_id VARCHAR(255)",
    "ALTER TABLE course_exam_attempts ADD COLUMN IF NOT EXISTS needs_manual_evaluation BOOLEAN DEFAULT FALSE",

    # --- exam_results (Entrance) ---
    "ALTER TABLE exam_results ADD COLUMN IF NOT EXISTS evaluated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP",

    # --- course_exam_results ---
    "ALTER TABLE course_exam_results ADD COLUMN IF NOT EXISTS evaluated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP",

    # --- course_exam_answers ---
    "ALTER TABLE course_exam_answers ADD COLUMN IF NOT EXISTS descriptive_text TEXT",
]

CREATE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS exam_violations (
        id SERIAL PRIMARY KEY,
        attempt_id INTEGER NOT NULL REFERENCES course_exam_attempts(id) ON DELETE CASCADE,
        violation_type VARCHAR(100) NOT NULL,
        timestamp TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS category_scores (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        exam_id INTEGER REFERENCES course_exams(id) ON DELETE CASCADE,
        category VARCHAR(100) NOT NULL,
        score FLOAT DEFAULT 0.0,
        max_score FLOAT DEFAULT 100.0,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
]


async def main():
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    print("Connecting to Neon database...")
    conn = await asyncpg.connect(NEON_URL, ssl=ssl_ctx)
    print("Connected!")

    print("\n--- Applying ALTER TABLE statements ---")
    for stmt in ALTER_STATEMENTS:
        try:
            await conn.execute(stmt)
            print(f"  OK: {stmt[:80]}")
        except Exception as e:
            print(f"  SKIP: {stmt[:80]} -- {e}")

    print("\n--- Creating tables if missing ---")
    for stmt in CREATE_TABLES:
        try:
            await conn.execute(stmt)
            table_name = stmt.split("CREATE TABLE IF NOT EXISTS ")[1].split("(")[0].strip()
            print(f"  OK: {table_name}")
        except Exception as e:
            print(f"  SKIP: {e}")

    print("\n--- Stamping alembic_version ---")
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL PRIMARY KEY
            )
        """)
        await conn.execute("DELETE FROM alembic_version")
        await conn.execute("INSERT INTO alembic_version (version_num) VALUES ('002_add_exam_features')")
        print("  OK: Stamped at 002_add_exam_features")
    except Exception as e:
        print(f"  SKIP: {e}")

    print("\n--- Verification: entrance_exams columns AFTER fix ---")
    rows = await conn.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'entrance_exams' 
        ORDER BY ordinal_position
    """)
    for r in rows:
        print(f"  {r['column_name']:30s} {r['data_type']}")

    print("\n--- Verification: course_exams columns AFTER fix ---")
    rows = await conn.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'course_exams' 
        ORDER BY ordinal_position
    """)
    for r in rows:
        print(f"  {r['column_name']:30s} {r['data_type']}")

    await conn.close()
    print("\nDone! Database schema is now in sync.")


if __name__ == "__main__":
    asyncio.run(main())
