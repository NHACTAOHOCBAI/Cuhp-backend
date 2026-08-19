# Cuhp — Backend API

FastAPI service phục vụ cho Cuhp web (admin) + mobile companion. Cung cấp REST API cho 4 miền chính: **Tiếng Anh** (audio, vocabulary, reading), **Tập gym** (categories + exercises + stats), **Công việc** (todo + stats), **Quản trị** (users + role), cùng hệ thống auth (token + role).

Upload file bài nghe dùng Cloudflare R2 (S3-compatible) qua `boto3`. Có sẵn migration idempotent và seed admin mặc định ở lần chạy đầu.

---

## 🛠️ Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12+ (khuyên dùng [uv](https://github.com/astral-sh/uv)) |
| Framework | FastAPI (async, WebSocket, Background Tasks) |
| Web server | Uvicorn |
| ORM | SQLAlchemy (declarative) |
| DB | PostgreSQL (`psycopg2-binary`) |
| Settings | pydantic-settings + `.env` |
| Logging | loguru |
| File storage | Cloudflare R2 via `boto3` |
| Khác | httpx, websockets, python-multipart, openpyxl, pillow, pandas |

---

## 📁 Cấu trúc thư mục

```text
backend/
├── app/
│   ├── main.py                 # FastAPI factory, lifespan, CORS, idempotent migrations, seed admin
│   ├── models.py               # Tất cả SQLAlchemy ORM models
│   ├── core/
│   │   ├── config.py           # Pydantic Settings (DB, R2, APP_NAME, APP_VERSION, ...)
│   │   ├── database.py         # SQLAlchemy engine/session/Base
│   │   └── websocket.py        # ConnectionManager
│   ├── api/
│   │   ├── deps.py             # get_current_user, get_current_admin (Bearer token)
│   │   └── v1/
│   │       ├── api.py          # Aggregator: gắn tất cả router vào /api/v1
│   │       └── endpoints/
│   │           ├── hello.py    # GET /hello (healthcheck + DB ping)
│   │           ├── auth.py     # Đăng ký / Đăng nhập / Đăng xuất
│   │           ├── users.py    # CRUD + role (admin)
│   │           ├── audio.py    # Upload R2, list, comments
│   │           ├── vocabulary.py  # CRUD + lookup từ điển + review SRS
│   │           ├── reading.py  # Passages + translation + comments
│   │           ├── gym.py      # Categories + exercises + stats
│   │           └── todo.py     # Tasks + stats + bulk delete
│   ├── schemas/                # Pydantic schemas cho request/response
│   │   ├── user.py, audio.py, vocabulary.py, reading.py, gym.py, todo.py
│   └── services/               # (chỗ để dành cho business logic tách riêng)
├── Dockerfile                  # Build image cho backend
├── docker-compose.yml          # Chạy Postgres + backend
├── requirements.txt            # Dependencies Python
├── .env                        # (cần tạo) DATABASE_URL, R2_*, ...
└── README.md
```

---

## 🚀 Cài đặt & chạy local

### 1. Yêu cầu
- Python 3.12+
- PostgreSQL (hoặc chạy qua Docker)

### 2. Thiết lập biến môi trường
Tạo file `backend/.env`:
```env
APP_NAME="Cuhp Service"
APP_VERSION="1.0.0"

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5439/cuhp_db

# Cloudflare R2 (audio file storage)
R2_ENDPOINT=https://<your-cloudflare-account-id>.r2.cloudflarestorage.com
R2_ACCESS_KEY=your_cloudflare_r2_access_key
R2_SECRET_KEY=your_cloudflare_r2_secret_key
R2_BUCKET=your_bucket_name
R2_PUBLIC_URL=https://pub-<your-unique-subdomain>.r2.dev
```

### 3. Khởi động Postgres (tuỳ chọn, dùng Docker)
```bash
docker compose up -d postgres
```
`docker-compose.yml` map cổng `5439:5432` ra máy host. Nếu dùng Postgres đã cài sẵn, sửa `DATABASE_URL` cho phù hợp.

### 4. Cài dependencies & chạy

Với `uv` (khuyên dùng):
```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Với `venv` + `pip`:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Server chạy tại [http://localhost:8000](http://localhost:8000).

### 5. Tài liệu API
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🗄️ Database

PostgreSQL. Tất cả model khai báo trong `app/models.py`. Schema được tạo tự động khi backend khởi động qua `Base.metadata.create_all` + một loạt `ALTER TABLE ... IF NOT EXISTS` idempotent (chạy an toàn nhiều lần). Không dùng Alembic — patches inline trong `main.py`.

### Bảng chính

| Bảng | Mô tả |
|---|---|
| `users` | Tài khoản, role (admin/user), daily_target, current_streak, last_reviewed_date, words_reviewed_today |
| `tokens` | Bearer token + expires_at |
| `audios` | Audio metadata + r2_key + url + transcript |
| `vocabularies` | Từ vựng cá nhân + box_number (Leitner 1–5) + next_review_at |
| `reading_passages` | Bài đọc song ngữ |
| `translation_practices` | Bản dịch của user cho passage |
| `reading_comments` / `audio_comments` | Comments theo vùng chọn |
| `workout_categories` | Nhóm cơ (mặc định 7 nhóm) |
| `workout_exercises` | Bài tập theo ngày, sets/reps/weight |
| `todo_tasks` | Task + quadrant (do/schedule/delegate/eliminate) + due_date + position |

### Auth
- Mật khẩu hash = SHA-256(salt `chat_pepper_123` + password).
- `get_current_user` parse `Authorization: Bearer <token>`, lookup DB, check expiry.
- `get_current_admin` yêu cầu `role == "admin"`.
- Tài khoản admin mặc định: `admin` / `admin` (được seed ở lần chạy đầu nếu DB trống).

---

## 🔌 API Endpoints (gắn tại `/api/v1`)

| Tag | Endpoints |
|---|---|
| `hello` | `GET /hello` — healthcheck + DB ping |
| `auth` | `POST /register`, `POST /login`, `POST /logout` |
| `users` | `GET /me`, `PUT /me`, `GET ""` (admin), `DELETE /{id}` (admin), `PUT /{id}/role` (admin) |
| `audio` | `POST /upload` (multipart → R2), `GET ""` (list, paged, q/level/category), `GET /{id}`, `PATCH /{id}`, `POST /bulk-delete`, `DELETE /{id}`, `GET/POST /{id}/comments`, `PATCH/DELETE /comments/{id}` |
| `vocabulary` | `POST/GET ""`, `GET /lookup/word?word=...` (dictionaryapi.dev + Google Translate), `GET/PATCH/DELETE /{id}`, `POST /bulk-delete`, `POST /{id}/review` (SRS Leitner + streak) |
| `reading` | `POST/GET ""`, `GET/PATCH/DELETE /{passage_id}`, `GET/POST /{passage_id}/translation`, `GET/POST /{passage_id}/comments`, `PATCH/DELETE /comments/{id}` |
| `gym` | Categories CRUD, Exercises CRUD (`?date=...`), `POST /exercises/copy-day-forward`, `GET /stats` |
| `todo` | `GET /tasks` (scope=today\|week\|all, q, quadrant), `POST /tasks`, `PUT/toggle/move /tasks/{id}`, `DELETE /tasks/completed`, `DELETE /tasks/{id}`, `GET /stats` |

Tất cả endpoint trừ `/hello` và `/auth/*` yêu cầu `get_current_user`. Endpoint admin-only yêu cầu `get_current_admin`.

---

## 🌟 Tính năng nổi bật

### SRS Leitner cho từ vựng
`POST /vocabulary/{id}/review` chuyển từ giữa các hộp 1→1d, 2→2d, 3→4d, 4→7d, 5→14d; cập nhật `next_review_at`, `words_reviewed_today`, `current_streak`, `last_reviewed_date`.

### Lookup từ điển
`GET /vocabulary/lookup/word?word=...` ưu tiên `dictionaryapi.dev`, fallback `translate.googleapis.com` (gọi trực tiếp qua `urllib`).

### Upload audio an toàn
Upload dùng multipart form qua `python-multipart`. File được đẩy thẳng lên Cloudflare R2 qua `boto3`, lưu `r2_key`. Xóa bài nghe đồng bộ xóa record DB + file vật lý trên R2.

### Workout stats
`GET /gym/stats` trả về weekly volume + per-exercise strength progress để vẽ biểu đồ ở FE.

### Todo Eisenhower Matrix
`POST /todo/tasks/{id}/move` cập nhật quadrant + reorder bằng field `position` (dense ordering). `GET /todo/stats` trả quadrant totals, 7-day completion, overdue/due-today, completion rate, focus rate.

### Migration idempotent
`main.py` lifespan chạy `Base.metadata.create_all` + một loạt `ALTER TABLE ... IF NOT EXISTS` để thêm cột mới nếu schema phát triển (không cần Alembic).

### Seed admin
Lần đầu chạy, nếu DB trống sẽ tạo user `admin` / `admin` (role=admin). Đổi password ngay sau lần đăng nhập đầu tiên.

---

## 📦 Docker

`docker-compose.yml` chạy 2 service:
- `postgres` — PostgreSQL 16, port `5439:5432`
- `backend` — build từ `Dockerfile`, port `8000:8000`, mount `.:/app`

```bash
docker compose up -d              # chạy Postgres + backend
docker compose logs -f backend    # xem log
docker compose down -v            # tắt + xóa volume
```

---

## 🔒 Lưu ý bảo mật

- CORS hiện đang mở hoàn toàn (`allow_origins=["*"]`) — chỉ phù hợp dev. Khi deploy production, restrict lại theo domain FE.
- Salt mật khẩu (`chat_pepper_123`) đang hardcode — production nên chuyển sang biến môi trường và dùng `bcrypt`/`argon2`.
- R2 credentials lưu `.env` — đảm bảo `.env` nằm trong `.gitignore`.
