# Backend API Changes — May 2026

This document summarizes backend behavior changes for other developers and API consumers.

---

## 1. Course Progress Calculation — `POST /learning/lesson/complete`

**File**: `app/modules/learning/services.py`  
**Impact**: Course progress percentage is now calculated accurately.

### Previous Behavior (BROKEN)
- Every call to `POST /learning/lesson/complete` incremented `progress_percent` by a **flat +5%**
- This meant:
  - A course with 1 lesson required 20 completions to reach 100% (impossible)
  - A course with 50 lessons would max out at 100% after only 20 lessons
- `completed_at` on `CourseEnrollment` was **never set**

### New Behavior ✅
- Progress is now calculated as:
  ```
  progress_percent = (completed_lessons / total_published_lessons) * 100
  ```
- `total_published_lessons` counts all lessons across all modules in the course where `is_published = True`
- `completed_lessons` counts `LessonCompletion` records for the current user in that course
- When `progress_percent` reaches **100%**, the `completed_at` field is automatically set to the current UTC timestamp
- Progress is **idempotent** — re-completing a lesson doesn't change the percentage
- The calculation happens server-side on every `POST /learning/lesson/complete` call

### API Contract (unchanged)
```
POST /learning/lesson/complete
Authorization: Bearer <token>
Body: { "course_id": int, "lesson_id": int }
Response: true
```

### Side Effects
| Field | Table | Change |
|-------|-------|--------|
| `progress_percent` | `course_enrollments` | Now accurate real percentage |
| `completed_at` | `course_enrollments` | Auto-set to UTC timestamp at 100% |

### Downstream Impact
- **Exam unlock**: Course exams are gated on `progress_percent >= 100` on the frontend. This fix ensures exams properly unlock when all lessons are completed.
- **Certificates**: Any logic checking `completed_at` will now work correctly.

---

## 2. AI Chat History — `GET /ai/chat-history`

**File**: `app/modules/ai/services.py`  
**Impact**: Privacy fix — chat sessions are now properly scoped to the requesting user.

### Previous Behavior (BUG)
- `GET /ai/chat-history` returned **ALL users' chat sessions** because the query was missing a `WHERE user_id = ?` filter

### New Behavior ✅
- Chat sessions are now filtered by the authenticated user's ID
- Only the requesting user's own sessions and messages are returned

### API Contract (unchanged)
```
GET /ai/chat-history
Authorization: Bearer <token>
Response: [
  {
    "id": int,
    "user_id": int,
    "title": string,
    "is_active": bool,
    "messages": [
      { "id": int, "role": "user"|"assistant", "content": string }
    ]
  }
]
```

> **⚠️ Breaking Change for anyone relying on the old behavior**: If you had admin tooling that used this endpoint to view all users' chats, it will now only return the authenticated user's chats. Use a direct DB query for admin-level access.

---

## Summary of Changed Files

| File | Change | Risk |
|------|--------|------|
| `app/modules/learning/services.py` | Real progress % + `completed_at` | Low — fixes broken logic |
| `app/modules/ai/services.py` | Added `user_id` filter to chat history | Low — privacy fix |

No database schema changes were made. No new endpoints were added. No existing response schemas were modified.
