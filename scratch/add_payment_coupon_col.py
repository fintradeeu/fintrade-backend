import asyncio
import asyncpg

async def main():
    try:
        # Connecting to postgres container mapped locally to port 5432
        conn = await asyncpg.connect('postgresql://lms_user:lms_password@localhost:5432/lms_db')
        await conn.execute('ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS coupon_code VARCHAR(100)')
        await conn.close()
        print("Column coupon_code added successfully to payment_transactions")
    except Exception as e:
        print(f"Error executing migration: {e}")

if __name__ == "__main__":
    asyncio.run(main())
