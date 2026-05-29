# FItTrade LMS — API Documentation

Base URL: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs` (Swagger UI)



---

## Roles & Access Control

| Role | Self-register | Created by |
|---|---|---|
| **student** | ✅ Yes (`POST /auth/register`) | — |
| **admin** | ❌ No | Admin (`POST /admin/users/create-admin`) |
| **faculty** | ❌ No | Admin (`POST /admin/users/create-faculty`) |
| **distributor** | ❌ No | Admin (`POST /admin/users/create-distributor`) |

Default admin account (created via seed): `admin@platform.com` / `admin123!`

---

## Health Check

### `GET /health`

```json
// Response 200
{
  "status": "ok",
  "app": "FItTrade LMS",
  "version": "1.0.0"
}
```

---

## Authentication

### `POST /auth/register`

Register a new **student** account.

```json
// Request
{
  "email": "student@example.com",
  "full_name": "John Doe",
  "phone": "+919876543210",
  "password": "securePass123"
}

// Response 201
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "student@example.com",
    "full_name": "John Doe",
    "phone": "+919876543210",
    "is_active": true,
    "is_verified": false,
    "avatar_url": null,
    "roles": [{"id": 1, "name": "student"}],
    "created_at": "2026-03-14T15:30:00Z"
  }
}
```

### `POST /auth/login`

```json
// Request
{
  "email": "student@example.com",
  "password": "securePass123"
}

// Response 200 — same shape as register response
```

### `GET /auth/me`

**Auth required.** Returns current user profile.

### `POST /auth/logout`

**Auth required.** Revokes the current session.

---

## Courses

### `GET /courses`

List published courses. Query params: `skip`, `limit`.

### `GET /courses/{course_id}`

Full course details with modules and lessons.

### `POST /courses/{course_id}/enroll`

**Auth required.** Enroll in a published course. Optionally provide a distributor referral code for a discount.

```json
// Request (optional body)
{
  "distributor_code": "REGION123"
}

// Response 200
{
  "id": 1,
  "user_id": 1,
  "course_id": 1,
  "enrolled_at": "2026-03-14T15:30:00Z",
  "is_active": true,
  "progress_percent": 0.0,
  "discount_applied": 500.0,
  "price_paid": 4499.0,
  "course": { ... }
}
```

### `GET /courses/enrolled`

**Auth required.** List current user's enrolled courses.

---

## Entrance Exams

### `GET /exams/entrance`

List all active entrance exams.

### `POST /exams/start?exam_id=1`

**Auth required.** Start a new exam attempt. Returns 403 if within 30-day cooldown.

### `GET /exams/questions?exam_id=1`

**Auth required.** Get questions for active attempt (correct answers hidden).

### `POST /exams/answer?attempt_id=1`

**Auth required.** Save an individual answer.

### `POST /exams/submit`

**Auth required.** Submit exam and get auto-evaluated result.

### `GET /exams/result?exam_id=1`

**Auth required.** Get most recent exam result.

---

## Offers

### `GET /offers`

List active offers.

### `POST /offers/apply`

**Auth required.** Apply an offer code to a course.

---

## Lectures

### `GET /lectures`

List scheduled lectures. Query params: `course_id`, `skip`, `limit`.

### `POST /lectures/join?lecture_id=1`

**Auth required.** Get meeting link to join a lecture.

---

## AI Chatbot

### `POST /ai/ask`

**Auth required.** Ask the AI chatbot a question.

### `GET /ai/chat-history`

**Auth required.** Get all chat sessions and messages.

---

## Admin APIs (Requires `admin` role)

All admin endpoints require `Authorization: Bearer <token>` from an admin user.

### Dashboard

#### `GET /admin/stats`

```json
// Response 200
{
  "total_users": 150,
  "total_courses": 5,
  "total_enrollments": 320,
  "total_exams": 3,
  "total_lectures": 12,
  "total_distributors": 8
}
```

### User Management

#### `GET /admin/users`

List all users. Query params: `skip`, `limit`.

#### `POST /admin/users/create-admin`

Create a new admin account.

```json
// Request
{
  "email": "admin2@platform.com",
  "full_name": "Admin Two",
  "password": "secureAdmin123"
}
```

#### `POST /admin/users/create-faculty`

Create a new faculty account.

```json
// Request
{
  "email": "faculty@platform.com",
  "full_name": "Prof. Smith",
  "password": "secureFaculty123"
}
```

#### `POST /admin/users/create-distributor`

Create a new distributor account with profile.

```json
// Request
{
  "email": "dist@partner.com",
  "full_name": "Regional Partner",
  "password": "secureDist123",
  "region": "Maharashtra",
  "referral_code": "REGION123",
  "discount_percentage": 10.0
}

// Response 201 — UserResponse with distributor role
```

### Distributor Management

#### `GET /admin/distributors`

List all distributors with user info.

```json
// Response 200
[
  {
    "id": 1,
    "user_id": 5,
    "region": "Maharashtra",
    "referral_code": "REGION123",
    "discount_percentage": 10.0,
    "user_name": "Regional Partner",
    "user_email": "dist@partner.com",
    "created_at": "2026-03-14T10:00:00Z"
  }
]
```

#### `GET /admin/distributors/{id}/stats`

Get statistics for a specific distributor.

```json
// Response 200
{
  "distributor_id": 1,
  "region": "Maharashtra",
  "referral_code": "REGION123",
  "user_name": "Regional Partner",
  "total_students_referred": 25,
  "total_courses_purchased": 40,
  "total_revenue_generated": 175000.0
}
```

### Course / Module / Lesson Management

#### `POST /admin/courses`

Create a new course (admin/faculty).

#### `POST /admin/modules`

Create a course module (admin/faculty).

#### `POST /admin/lessons`

Create a lesson (admin/faculty).

### Exam Management

#### `POST /admin/exams/create`

Create an entrance exam with questions (admin only).

#### `POST /admin/exams/questions?exam_id=1`

Add questions to an existing exam (admin only).

### Offer Management

#### `POST /admin/offers`

Create a new offer (admin only). The `created_by_admin` is set automatically.

#### `GET /admin/offers`

List all offers including inactive ones (admin only).

### Lecture Management

#### `POST /admin/lectures`

Schedule a new lecture (admin/faculty).

---

## Faculty APIs (Requires `faculty` role)

### `GET /faculty/courses`

List courses created by this faculty member.

### `POST /faculty/lessons/upload`

Create a lesson — faculty must own the parent course.

```json
// Request
{
  "module_id": 1,
  "title": "Advanced Chart Patterns",
  "content": "In this lesson...",
  "content_type": "text",
  "order": 3,
  "is_published": true
}
```

### `POST /faculty/lectures/create`

Schedule a new lecture. Faculty is automatically set as instructor.

```json
// Request
{
  "title": "Live Trading Demo",
  "course_id": 1,
  "meeting_link": "https://zoom.us/j/123456",
  "scheduled_at": "2026-03-20T10:00:00Z",
  "duration_minutes": 60
}
```

### `GET /faculty/students`

List students enrolled in faculty's courses.

```json
// Response 200
[
  {
    "student_id": 3,
    "student_name": "John Doe",
    "student_email": "john@example.com",
    "course_id": 1,
    "course_title": "Technical Analysis",
    "enrolled_at": "2026-03-14T15:30:00Z"
  }
]
```

---

## Distributor APIs (Requires `distributor` role)

### `GET /distributor/profile`

Get the current distributor's profile.

```json
// Response 200
{
  "id": 1,
  "user_id": 5,
  "region": "Maharashtra",
  "referral_code": "REGION123",
  "discount_percentage": 10.0,
  "user_name": "Regional Partner",
  "user_email": "dist@partner.com",
  "created_at": "2026-03-14T10:00:00Z"
}
```

### `GET /distributor/referral-code`

Get the distributor's referral code and discount info.

```json
// Response 200
{
  "referral_code": "REGION123",
  "discount_percentage": 10.0,
  "region": "Maharashtra"
}
```

### `GET /distributor/referrals`

List all students referred by this distributor.

```json
// Response 200
[
  {
    "id": 1,
    "student_id": 3,
    "student_name": "John Doe",
    "student_email": "john@example.com",
    "course_id": 1,
    "course_title": "Technical Analysis",
    "created_at": "2026-03-14T15:30:00Z"
  }
]
```

### `GET /distributor/stats`

Get referral statistics for this distributor.

```json
// Response 200
{
  "distributor_id": 1,
  "region": "Maharashtra",
  "referral_code": "REGION123",
  "total_students_referred": 25,
  "total_courses_purchased": 40,
  "total_revenue_generated": 175000.0
}
```

---

## Distributor Referral Flow

1. Admin creates a distributor: `POST /admin/users/create-distributor`
2. Distributor logs in and shares their referral code: `GET /distributor/referral-code`
3. Student registers: `POST /auth/register`
4. Student enrolls with referral code: `POST /courses/{course_id}/enroll` with `{"distributor_code": "REGION123"}`
5. System validates code, applies discount, records referral
6. Distributor views referrals: `GET /distributor/referrals` and `GET /distributor/stats`

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Common HTTP status codes:

| Code | Meaning |
|---|---|
| 400 | Bad request / validation error |
| 401 | Unauthorized — missing or invalid token |
| 403 | Forbidden — insufficient role or 30-day exam restriction |
| 404 | Resource not found |
| 409 | Conflict — duplicate resource |
| 422 | Validation error — invalid request body |
