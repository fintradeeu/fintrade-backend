# FItTrade LMS — Backend Walkthrough & Audit Report

> **Audit Date**: April 10, 2026  
> **Codebase**: `aaiushhh/fintrade-backend` (main branch)  
> **Stack**: FastAPI + PostgreSQL + Docker  
> **Phases Covered**: Phase 1 (Core) + Phase 2 (Learning/Exams/Security) + Phase 3 (Simulator/Certificates/Analytics)

---

## 1. Setup Guide

### Prerequisites
- Docker Desktop installed and running
- Python 3.11+ (for running test scripts locally)
- Git

### Quick Start

```bash
# 1. Clone
git clone https://github.com/aaiushhh/fintrade-backend.git
cd fintrade-backend

# 2. Start services
cd docker
docker compose up -d

# 3. Seed admin user
docker compose exec -T -w /app -e PYTHONPATH=/app backend python app/db/seed.py

# 4. Fix bcrypt compatibility (if needed)
docker compose exec -T -w /app -e PYTHONPATH=/app backend python app/fix.py

# 5. Verify
curl http://localhost:8000/health
# → {"status":"ok","app":"FItTrade LMS","version":"1.0.0"}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://lms_user:lms_password@postgres:5432/lms_db` | Async DB connection |
| `JWT_SECRET_KEY` | `change-me-in-production` | JWT signing key |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `360` | Token TTL |
| `OPENAI_API_KEY` | (empty) | Required for AI chatbot |
| `DEBUG` | `True` | SQLAlchemy echo |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:8000` | Allowed origins |

### Default Admin Credentials
- **Email**: `admin@platform.com`
- **Password**: `admin123!`

---

## 2. Database Overview — All Tables (46 tables)

### Auth & Users (5 tables + 1 association)

| Table | Purpose |
|-------|---------|
| `users` | Core user accounts |
| `roles` | Role definitions (admin, faculty, student, distributor) |
| `user_roles` | M2M association: users ↔ roles |
| `sessions` | Active JWT sessions |
| `devices` | Registered user devices |

### Courses & Learning (5 tables)

| Table | Purpose |
|-------|---------|
| `courses` | Course catalog with pricing, difficulty level |
| `course_modules` | Modules within a course |
| `lessons` | Individual lessons (text, video, pdf, quiz) |
| `course_enrollments` | Student enrollment + progress tracking |
| `lesson_completions` | Per-lesson completion tracking |

### Entrance Exams (6 tables)

| Table | Purpose |
|-------|---------|
| `entrance_exams` | Entrance exam definitions |
| `exam_questions` | Questions for entrance exams |
| `exam_options` | MCQ options |
| `exam_attempts` | Student attempt records |
| `exam_answers` | Individual answers per attempt |
| `exam_results` | Evaluated results with pass/fail |

### Course & Monthly Exams (8 tables)

| Table | Purpose |
|-------|---------|
| `course_exams` | Generic exam framework (module/final/monthly) |
| `course_exam_questions` | Questions for course exams |
| `course_exam_options` | Options for course exam questions |
| `course_exam_attempts` | Attempt records with device_id |
| `course_exam_answers` | Answers per attempt |
| `course_exam_results` | Evaluated results |
| `monthly_exams` | Maps month_number → course_exam |
| `exam_payments` | Reattempt payment records |

### Exam Security (1 table)

| Table | Purpose |
|-------|---------|
| `exam_violations` | Tab switches, camera off events |

### Skill Analysis (1 table)

| Table | Purpose |
|-------|---------|
| `category_scores` | Per-category score breakdown |

### Lectures (2 tables)

| Table | Purpose |
|-------|---------|
| `lectures` | Scheduled lectures with meeting links |
| `lecture_recordings` | Stored recordings per lecture |

### AI System (4 tables)

| Table | Purpose |
|-------|---------|
| `doubt_categories` | Categorization of student doubts |
| `faq_entries` | Auto-generated FAQs with frequency |
| `chat_sessions` | AI chat conversation sessions |
| `chat_messages` | Individual messages in sessions |

### Offers & Distributors (4 tables)

| Table | Purpose |
|-------|---------|
| `offers` | Discount offers with codes |
| `offer_redemptions` | Offer usage tracking |
| `distributors` | Distributor profiles with referral codes |
| `student_referrals` | Referral tracking |

### Certificates (1 table)

| Table | Purpose |
|-------|---------|
| `certificates` | Issued certificates with PDF links + unique codes |

### Trading Simulator (7 tables)

| Table | Purpose |
|-------|---------|
| `simulator_profiles` | Prop firm rule sets |
| `simulator_accounts` | Virtual trading accounts |
| `trades` | Trade records (open/closed) |
| `positions` | Open positions |
| `orders` | Order records |
| `risk_rules` | Per-profile risk rules |
| `performance_metrics` | Computed analytics per account |

### Placement & Feedback (2 tables)

| Table | Purpose |
|-------|---------|
| `placement_results` | Eligibility evaluation results |
| `feedback` | Student ratings and comments |

---

## 3. Complete API Endpoint Inventory (74 endpoints)

### Auth (`/auth`) — 4 endpoints

| Method | Path | Auth | Purpose | SRS Feature |
|--------|------|------|---------|-------------|
| POST | `/auth/register` | none | Register student | ✔ Entry System |
| POST | `/auth/login` | none | Authenticate + JWT | ✔ Entry System |
| GET | `/auth/me` | user | Current user profile | ✔ Entry System |
| POST | `/auth/logout` | user | Revoke session | ✔ Entry System |

### Courses (`/courses`) — 4 endpoints

| Method | Path | Auth | Purpose | SRS Feature |
|--------|------|------|---------|-------------|
| GET | `/courses` | none | List published courses | ✔ Course System |
| GET | `/courses/enrolled` | user | User's enrolled courses | ✔ Course System |
| GET | `/courses/{id}` | none | Course detail with modules/lessons | ✔ Course System |
| POST | `/courses/{id}/enroll` | user | Enroll with optional referral | ✔ Payment & Offers |

### Exams (`/exams`) — 13 endpoints

| Method | Path | Auth | Purpose | SRS Feature |
|--------|------|------|---------|-------------|
| GET | `/exams/entrance` | none | List entrance exams | ✔ Exam System |
| POST | `/exams/start` | user | Start exam (30-day check) | ✔ Exam System |
| GET | `/exams/questions` | user | Get exam questions | ✔ Exam System |
| POST | `/exams/answer` | user | Save individual answer | ✔ Exam System |
| POST | `/exams/submit` | user | Submit + auto-evaluate | ✔ Exam System |
| GET | `/exams/result` | user | Get exam result | ✔ Exam System |
| GET | `/exams/monthly` | user | List monthly exams | ✔ Exam System |
| POST | `/exams/pay` | user | Pay for reattempt | ✔ Payment & Offers |
| POST | `/exams/course/start` | user | Start course exam (device bind) | ✔ Exam Security |
| POST | `/exams/violation` | user | Log tab switch/violation | ✔ Exam Security |
| POST | `/exams/camera-status` | user | Log camera toggle | ✔ Exam Security |
| POST | `/exams/session-close` | user | Close exam session | ✔ Exam Security |
| GET | `/exams/results/analysis` | user | Skill-based analysis | ✔ Skill Analysis |

### Offers (`/offers`) — 2 endpoints

| Method | Path | Auth | Purpose | SRS Feature |
|--------|------|------|---------|-------------|
| GET | `/offers` | none | List active offers | ✔ Payment & Offers |
| POST | `/offers/apply` | user | Apply offer code | ✔ Payment & Offers |

### Lectures (`/lectures`) — 2 endpoints

| Method | Path | Auth | Purpose | SRS Feature |
|--------|------|------|---------|-------------|
| GET | `/lectures` | none | List scheduled lectures | ✔ Learning System |
| POST | `/lectures/join` | user | Join + get meeting link | ✔ Learning System |

### AI (`/ai`) — 3 endpoints

| Method | Path | Auth | Purpose | SRS Feature |
|--------|------|------|---------|-------------|
| POST | `/ai/ask` | user | Ask chatbot (RAG) | ✔ AI System |
| GET | `/ai/chat-history` | user | Chat history | ✔ AI System |
| GET | `/ai/faqs` | user | Dynamic FAQs | ✔ AI System |

### Learning (`/learning`) — 2 endpoints

| Method | Path | Auth | Purpose | SRS Feature |
|--------|------|------|---------|-------------|
| GET | `/learning/dashboard` | user | Dashboard data | ✔ Learning System |
| POST | `/learning/lesson/complete` | user | Mark lesson done | ✔ Learning System |

### Certificates (`/certificates`) — 3 endpoints

| Method | Path | Auth | Purpose | SRS Feature |
|--------|------|------|---------|-------------|
| POST | `/certificates/generate` | user | Generate after completion | ✔ Certification |
| GET | `/certificates/{id}` | user | View certificate | ✔ Certification |
| GET | `/certificates/download/{id}` | user | Download PDF | ✔ Certification |

### Simulator (`/simulator`) — 7 endpoints

| Method | Path | Auth | Purpose | SRS Feature |
|--------|------|------|---------|-------------|
| POST | `/simulator/start` | user (certified) | Create trading account | ✔ Trading Simulator |
| POST | `/simulator/trade` | user | Open a trade | ✔ Trading Simulator |
| POST | `/simulator/close` | user | Close position + PnL | ✔ Trading Simulator |
| GET | `/simulator/positions` | user | List open positions | ✔ Trading Simulator |
| GET | `/simulator/trades` | user | Trade history | ✔ Trading Simulator |
| GET | `/simulator/profiles` | user | Prop firm profiles | ✔ Simulator Profiles |
| GET | `/simulator/performance` | user | Analytics computation | ✔ Performance Analytics |

### Placement (`/placement`) — 2 endpoints

| Method | Path | Auth | Purpose | SRS Feature |
|--------|------|------|---------|-------------|
| GET | `/placement/status` | user | Check eligibility | ✔ Placement System |
| POST | `/placement/evaluate` | user | Trigger evaluation | ✔ Placement System |

### Feedback (`/feedback`) — 3 endpoints

| Method | Path | Auth | Purpose | SRS Feature |
|--------|------|------|---------|-------------|
| POST | `/feedback` | user | Submit feedback | ✔ Feedback System |
| GET | `/feedback` | admin | List all feedback | ✔ Feedback System |
| GET | `/feedback/my` | user | User's own feedback | ✔ Feedback System |

### Faculty (`/faculty`) — 5 endpoints

| Method | Path | Auth | Purpose | SRS Feature |
|--------|------|------|---------|-------------|
| GET | `/faculty/courses` | faculty | List own courses | ✔ Course System |
| POST | `/faculty/lessons/upload` | faculty | Create lesson | ✔ Course System |
| POST | `/faculty/lectures/create` | faculty | Schedule lecture | ✔ Learning System |
| POST | `/faculty/lectures/{id}/complete` | faculty | Mark lecture done | ✔ Learning System |
| POST | `/faculty/lectures/{id}/recordings` | faculty | Upload recording | ✔ Learning System |
| GET | `/faculty/students` | faculty | List enrolled students | ✔ Admin Controls |

### Distributor (`/distributor`) — 4 endpoints

| Method | Path | Auth | Purpose | SRS Feature |
|--------|------|------|---------|-------------|
| GET | `/distributor/profile` | distributor | Own profile | ✔ Payment & Offers |
| GET | `/distributor/referral-code` | distributor | Referral code + discount | ✔ Payment & Offers |
| GET | `/distributor/referrals` | distributor | Referred students | ✔ Payment & Offers |
| GET | `/distributor/stats` | distributor | Revenue stats | ✔ Payment & Offers |

### Admin (`/admin`) — 20 endpoints

| Method | Path | Auth | Purpose | SRS Feature |
|--------|------|------|---------|-------------|
| GET | `/admin/stats` | admin | Dashboard stats | ✔ Admin Controls |
| GET | `/admin/users` | admin | List all users | ✔ Admin Controls |
| POST | `/admin/users/create-admin` | admin | Create admin | ✔ Admin Controls |
| POST | `/admin/users/create-faculty` | admin | Create faculty | ✔ Admin Controls |
| POST | `/admin/users/create-distributor` | admin | Create distributor | ✔ Admin Controls |
| GET | `/admin/distributors` | admin | List distributors | ✔ Admin Controls |
| GET | `/admin/distributors/{id}/stats` | admin | Distributor stats | ✔ Admin Controls |
| POST | `/admin/courses` | admin/faculty | Create course | ✔ Admin Controls |
| POST | `/admin/modules` | admin/faculty | Create module | ✔ Admin Controls |
| POST | `/admin/lessons` | admin/faculty | Create lesson | ✔ Admin Controls |
| POST | `/admin/exams/create` | admin | Create entrance exam | ✔ Admin Controls |
| POST | `/admin/exams/questions` | admin | Add questions | ✔ Admin Controls |
| POST | `/admin/offers` | admin | Create offer | ✔ Admin Controls |
| GET | `/admin/offers` | admin | List all offers | ✔ Admin Controls |
| POST | `/admin/lectures` | admin/faculty | Schedule lecture | ✔ Admin Controls |
| POST | `/admin/upload` | admin/faculty | Upload media file | ✔ Admin Controls |
| GET | `/admin/reports` | admin | Aggregated analytics | ✔ Admin Controls |
| GET | `/admin/certificates` | admin | Certificate stats | ✔ Admin Controls |
| GET | `/admin/simulator` | admin | Simulator overview | ✔ Admin Controls |

### Health — 1 endpoint

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | none | Readiness probe |

---

## 4. SRS Feature Validation Matrix

### ✔ Fully Implemented (14/16)

| # | SRS Feature | Status | Evidence |
|---|-------------|--------|----------|
| 1 | Entry System (exam, pass/fail, 30-day restrict) | ✔ Complete | `_check_reattempt_allowed()` enforces 30-day wait. `submit_exam()` auto-evaluates pass/fail |
| 2 | Course System (levels, modules, lessons, content types) | ✔ Complete | `difficulty_level` field supports beginner/intermediate/advanced. `content_type` supports text/video/pdf/quiz |
| 3 | Payment & Offers | ✔ Complete | `offers` table + apply logic. `exam_payments` for reattempts. Distributor referral discounts on enrollment |
| 5 | Exam System (entrance, monthly, progression) | ✔ Complete | `entrance_exams` + `monthly_exams` + `course_exams`. Reattempt gating with payment check |
| 6 | Exam Security (device, tab, camera, session) | ✔ Complete | `device_id` on attempts, `exam_violations` for tab_switch/camera_off, session-close endpoint |
| 7 | AI System (chatbot, FAQ, doubt categorization) | ✔ Complete | RAG-powered `/ai/ask`, dynamic FAQs with frequency, `doubt_categories` table |
| 8 | Certification (generate, download) | ✔ Complete | PDF generation via reportlab, unique codes, `/certificates/download/{id}` |
| 9 | Skill Analysis (category scoring, strong/weak) | ✔ Complete | `category_scores` table, `/exams/results/analysis` returns strong/weak/suggestions |
| 10 | Trading Simulator (account, trade, position, PnL) | ✔ Complete | Full engine with open/close/PnL, 7 tables, risk validation |
| 11 | Risk Management (stop-loss, daily loss, rules) | ✔ Complete | `_check_risk_rules()` enforces all 3 rules before every trade |
| 12 | Simulator Profiles (multiple rule sets) | ✔ Complete | `simulator_profiles` table with configurable limits |
| 13 | Performance Analytics (PnL, risk, consistency) | ✔ Complete | On-demand computation: win_rate, max_drawdown, risk_score, consistency_score |
| 14 | Placement System (eligibility, performance-based) | ✔ Complete | Weighted composite scoring from simulator metrics |
| 15 | Feedback System (ratings, comments) | ✔ Complete | POST for students, GET for admin, 1-5 rating with validation |
| 16 | Admin Controls | ✔ Complete | 20 admin endpoints covering users, courses, exams, offers, lectures, reports, certificates, simulator |

### ⚠ Partially Implemented (2/16)

| # | SRS Feature | Status | Gap |
|---|-------------|--------|-----|
| 2 | Course System — "text-to-audio" | ⚠ Missing | No TTS endpoint or service. `content_type` supports "text/video/pdf/quiz" but no audio conversion |
| 4 | Learning System — "lecture recording" | ⚠ Partial | Recordings model + faculty upload endpoint exist, but no student-facing recording playback endpoint |

---

## 5. Bugs & Issues Found

### 🔴 Critical

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 1 | **Course `difficulty_level` missing "Master" level** | `courses/models.py:32` | SRS specifies 4 levels: Basic, Intermediate, Advanced, **Master**. The column comment shows only 3. This is a data validation gap — "master" can be stored but isn't documented/enforced. |

### 🟡 Medium

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 2 | **No PUT/PATCH/DELETE endpoints exist** | All modules | Cannot update or delete any resource (courses, exams, users, etc.). Only create + read operations exist. |
| 3 | **No course payment/checkout flow** | `courses/routes.py` | Enrollment stores `price_paid` but there's no payment gateway integration or validation. Students can enroll without paying. |
| 4 | **`category_scores` are never populated** | `exams/services.py` | The `CategoryScore` table exists and analysis endpoint works, but no service ever inserts records into this table. Exam submission doesn't categorize scores. |
| 5 | **Monthly exam count not enforced as 3** | `exams/models.py` | SRS says "3 monthly exams". The `MonthlyExam` table has `month_number` but there's no validation enforcing exactly 3 per course. |
| 6 | **Pass/fail progression not enforced for course levels** | `courses/services.py` | SRS says pass/fail determines level progression. Enrollment doesn't check exam results before allowing access to next level. |

### 🟢 Low

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 7 | **Debug traceback exposed in faculty lecture creation** | `faculty/routes.py:52` | `traceback.format_exc()` is returned in the 500 response body. Security risk in production. |
| 8 | **`app.fix.py` committed to repo** | `app/fix.py` | Internal bcrypt fix script should not be in production code. |
| 9 | **No input validation on `difficulty_level`** | `courses/schemas.py` | Any string accepted — no enum constraint for beginner/intermediate/advanced/master. |
| 10 | **`docker/dump_logs.py` committed** | `docker/dump_logs.py` | Debug utility should not be in production. |

---

## 6. Feature Testing Guide

### 6.1 Authentication Flow

```
1. POST /auth/register → {"email":"test@test.com","full_name":"Test","password":"test1234"}
   Expected: 201 + access_token + refresh_token

2. POST /auth/login → {"email":"admin@platform.com","password":"admin123!"}
   Expected: 200 + tokens

3. GET /auth/me (with Bearer token)
   Expected: 200 + user profile with roles

4. POST /auth/logout (with Bearer token)
   Expected: 200 + "Logged out successfully"
```

### 6.2 Course Enrollment Flow

```
1. GET /courses → List all published courses
2. GET /courses/{id} → Course detail with modules + lessons
3. POST /courses/{id}/enroll → Enroll
4. GET /courses/enrolled → See enrolled courses with progress
```

### 6.3 Entrance Exam Flow

```
1. GET /exams/entrance → List available exams
2. POST /exams/start?exam_id=1 → Start attempt (checks 30-day rule)
3. GET /exams/questions?exam_id=1 → Get questions (no correct answers shown)
4. POST /exams/answer?attempt_id=1 → {"question_id":1,"selected_option_id":1}
5. POST /exams/submit → {"attempt_id":1,"answers":[...]}
   Expected: Auto-evaluate, return pass/fail + percentage
6. GET /exams/result?exam_id=1 → View result
```

### 6.4 Certificate Generation

```
1. Complete course (progress_percent = 100%)
2. POST /certificates/generate → {"course_id": 1}
   Expected: 201 + certificate with unique_code + PDF URL
3. GET /certificates/{id} → View metadata
4. GET /certificates/download/{id} → Download PDF
```

### 6.5 Trading Simulator Complete Flow

```
1. (Must have certificate first)
2. POST /simulator/start → {} (or {"profile_id": 1})
   Expected: 201 + account with $100,000 balance
3. POST /simulator/trade → {
     "symbol":"AAPL","side":"buy","quantity":10,
     "price":150.0,"stop_loss":145.0
   }
   Expected: 201 + trade record (risk rules validated)
4. GET /simulator/positions → Open positions
5. POST /simulator/close → {"position_id":1,"exit_price":155.0}
   Expected: Closed trade with PnL = $50
6. GET /simulator/trades → History
7. GET /simulator/performance → Computed metrics
```

### 6.6 Feedback + Placement

```
1. POST /feedback → {"rating":5,"comments":"Great!"}
2. GET /feedback/my → Own feedback list
3. POST /placement/evaluate → Evaluates from simulator metrics
4. GET /placement/status → Check eligibility
```

### 6.7 Admin Dashboard

```
1. GET /admin/stats → Overall counts
2. GET /admin/reports → Aggregated analytics across phases
3. GET /admin/certificates → Certificate stats + list
4. GET /admin/simulator → Top performers
5. GET /admin/users → User list with pagination
6. POST /admin/courses → Create course
7. POST /admin/exams/create → Create exam with questions
```

---

## 7. Security Validation

| Check | Status | Details |
|-------|--------|---------|
| JWT Authentication | ✔ | `oauth2_scheme` + `get_current_user` dependency |
| Session Management | ✔ | Active session check on every authenticated request |
| Role-Based Access Control | ✔ | `require_roles()` factory guards admin/faculty endpoints |
| Student Data Isolation | ✔ | Services filter by `user_id` for own-data access |
| Exam Device Binding | ✔ | `device_id` stored on `course_exam_attempts` |
| Simulator Gating | ✔ | Certificate required before account creation |
| Admin-Only Reports | ✔ | `require_roles(["admin"])` on `/admin/reports`, `/admin/certificates`, `/admin/simulator` |
| Password Hashing | ✔ | bcrypt via passlib |

---

## 8. Final System Status

| SRS Feature | Status |
|-------------|--------|
| 1. Entry System | ✔ Complete |
| 2. Course System | ⚠ Partial — missing text-to-audio, "master" level not enforced |
| 3. Payment & Offers | ⚠ Partial — offer/discount logic works, but no real payment gateway |
| 4. Learning System | ⚠ Partial — recording model + upload exists, no student playback endpoint |
| 5. Exam System | ✔ Complete |
| 6. Exam Security | ✔ Complete |
| 7. AI System | ✔ Complete |
| 8. Certification | ✔ Complete |
| 9. Skill Analysis | ⚠ Partial — endpoint works but `category_scores` never populated by exam submission |
| 10. Trading Simulator | ✔ Complete |
| 11. Risk Management | ✔ Complete |
| 12. Simulator Profiles | ✔ Complete |
| 13. Performance Analytics | ✔ Complete |
| 14. Placement System | ✔ Complete |
| 15. Feedback System | ✔ Complete |
| 16. Admin Controls | ✔ Complete |

### Summary

| Metric | Count |
|--------|-------|
| Total API Endpoints | **74** |
| Total Database Tables | **46** |
| SRS Features Fully Implemented | **12 / 16** |
| SRS Features Partially Implemented | **4 / 16** |
| SRS Features Missing | **0 / 16** |
| Critical Bugs | **1** |
| Medium Issues | **5** |
| Low Issues | **4** |

### Recommended Next Steps (Priority Order)

1. **Populate `category_scores`** during exam submission to make skill analysis functional end-to-end
2. **Add text-to-audio** endpoint (e.g., via OpenAI TTS or gTTS) for lesson content
3. **Add student recording playback** endpoint under `/lectures/{id}/recordings`
4. **Enforce course level progression** — check exam pass before next-level enrollment
5. **Add UPDATE/DELETE operations** for courses, exams, users (admin CRUD)
6. **Validate `difficulty_level`** via enum constraint (beginner, intermediate, advanced, master)
7. **Remove debug files** (`app/fix.py`, `docker/dump_logs.py`) from production
8. **Remove traceback exposure** in `faculty/routes.py`
