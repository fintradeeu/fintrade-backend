import asyncio
from app.db.database import async_session_maker
from app.modules.exams.models import EntranceExam, ExamQuestion, ExamOption
from sqlalchemy import select

async def seed_questions():
    async with async_session_maker() as db:
        # Get all entrance exams
        result = await db.execute(select(EntranceExam))
        exams = result.scalars().all()
        
        if not exams:
            print("No exams found to seed.")
            return

        for exam in exams:
            print(f"Seeding questions for exam ID {exam.id} ({exam.title})...")
            
            # Check if it already has questions
            q_res = await db.execute(select(ExamQuestion).where(ExamQuestion.exam_id == exam.id))
            if q_res.scalars().first():
                print(f"Exam {exam.id} already has questions, skipping.")
                continue
                
            # Add 5 questions
            for i in range(1, 6):
                q = ExamQuestion(
                    exam_id=exam.id,
                    question_text=f"Sample Question {i} for {exam.title}",
                    question_type="multiple_choice",
                    marks=1.0,
                    negative_marks=0.0
                )
                db.add(q)
                await db.flush() # To get q.id
                
                # Add 4 options
                for j in range(4):
                    opt = ExamOption(
                        question_id=q.id,
                        option_text=f"Option {j+1}",
                        is_correct=(j == 0), # Option 1 is always correct for testing
                        order=j
                    )
                    db.add(opt)
        
        await db.commit()
        print("Done seeding questions!")

if __name__ == "__main__":
    asyncio.run(seed_questions())
