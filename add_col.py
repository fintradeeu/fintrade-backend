import asyncio
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect('postgresql://lms_user:lms_password@localhost:5432/lms_db')
        await conn.execute('ALTER TABLE assignments ADD COLUMN resources JSON')
        await conn.close()
        print("Column added")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
