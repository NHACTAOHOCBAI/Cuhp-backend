# Cuhp Backend & Audio Service 🍰🎧

Đây là dịch vụ backend FastAPI phụ trách xử lý logic nghiệp vụ cho hệ thống Cuhp và hệ thống Quản lý bài nghe tiếng Anh chạy nền cho Mobile. Hệ thống tích hợp WebSockets thời gian thực và lưu trữ Cloudflare R2 (S3-compatible API).

---

## 🛠️ Công Nghệ Sử Dụng (Tech Stack)

* **Ngôn ngữ**: [Python 3.12+](https://www.python.org/)
* **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Hỗ trợ Asynchronous, Background Tasks, WebSockets)
* **Web Server**: [Uvicorn](https://www.uvicorn.org/)
* **ORM & Database**: [SQLAlchemy](https://www.sqlalchemy.org/) + [PostgreSQL](https://www.postgresql.org/)
* **Lưu trữ đám mây**: [Cloudflare R2](https://www.cloudflare.com/developer-platform/r2/) (Sử dụng SDK `boto3` để quản lý upload/delete file âm thanh bài học)

---

## 📁 Cấu Trúc Thư Mục Backend

```text
backend/
├── app/
│   ├── api/                  # Các router và endpoint API chính
│   │   ├── deps.py           # Dependency injection (lấy database session, auth,...)
│   │   └── v1/
│   │       ├── api.py        # Đăng ký tập trung tất cả router v1
│   │       └── endpoints/    # Định nghĩa chi tiết router
│   │           ├── auth.py   # Xác thực, Đăng nhập, Đăng ký
│   │           ├── users.py  # Quản lý người dùng, phân quyền
│   │           ├── audio.py  # [NEW] Upload file nghe lên Cloudflare R2, Quản lý bài nghe
│   │           └── ...
│   ├── core/                 # Cấu hình hệ thống cốt lõi
│   │   ├── config.py         # Quản lý cài đặt thông qua Pydantic Settings
│   │   ├── database.py       # Kết nối SQLAlchemy engine và session maker
│   │   └── websocket.py      # ConnectionManager quản lý kết nối websocket
│   ├── models.py             # Định nghĩa toàn bộ database model SQLAlchemy (gồm User, Token, Audio)
│   ├── schemas/              # Các Pydantic schemas để validate request/response
│   │   ├── user.py           # Schema xác thực người dùng
│   │   └── audio.py          # [NEW] Schema bài nghe tiếng Anh
│   └── main.py               # Điểm khởi chạy FastAPI, xử lý Lifespan, Seed database & CORS
├── Dockerfile                # Cấu hình build Docker image cho backend
├── docker-compose.yml        # Docker Compose chạy PostgreSQL và Backend
├── requirements.txt          # Danh sách dependencies của Python (gồm boto3, python-multipart)

```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Local

### 1. Yêu cầu hệ thống
* Python 3.12+ (khuyên dùng [uv](https://github.com/astral-sh/uv) để quản lý chạy nhanh hơn).
* Đã cài đặt PostgreSQL (hoặc chạy qua Docker).

### 2. Thiết lập Biến Môi Trường
Sao chép hoặc tạo tệp `.env` tại thư mục `backend/` từ mẫu cấu hình sau và điền các tham số:

```env
APP_NAME="Cuhp Service"
APP_VERSION="1.0.0"

# Cấu hình Cơ sở dữ liệu PostgreSQL
DATABASE_URL=postgresql://postgres:postgres@localhost:5439/cuhp_db

# Cấu hình Cloudflare R2 (Lưu trữ file bài nghe)
R2_ENDPOINT=https://<your-cloudflare-account-id>.r2.cloudflarestorage.com
R2_ACCESS_KEY=your_cloudflare_r2_access_key
R2_SECRET_KEY=your_cloudflare_r2_secret_key
R2_BUCKET=your_bucket_name
R2_PUBLIC_URL=https://pub-<your-unique-subdomain>.r2.dev
```

### 3. Khởi Chạy Cơ Sở Dữ Liệu qua Docker (Nếu chưa có Postgres ngoài)
Chạy lệnh sau tại thư mục `backend/` để khởi động Postgres Container:
```bash
docker compose up -d postgres
```
*Lưu ý*: Cấu hình docker-compose map cổng PostgreSQL ra máy ngoài là `5439:5432`.

### 4. Cài Đặt Dependencies và Chạy Backend
Nếu bạn sử dụng `uv`:
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Nếu sử dụng virtualenv thông thường và `pip`:
```bash
# Tạo và kích hoạt môi trường ảo
python -m venv .venv
source .venv/bin/activate  # Trên Linux/macOS
# .venv\Scripts\activate   # Trên Windows

# Cài đặt thư viện
pip install -r requirements.txt

# Khởi chạy server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Server backend sẽ khởi chạy tại địa chỉ: `http://localhost:8000`.

---

## 🎧 Các Tính Năng Nổi Bật

### 1. Quản Lý Bài Nghe Tiếng Anh (`/api/v1/audio`)
* **Đồng bộ đám mây Cloudflare R2**: Tải lên file nghe thông qua giao diện Web Admin, lưu trữ trực tiếp trên Cloudflare R2.
* **API Streaming**: Cung cấp URL phát trực tiếp tốc độ cao để ứng dụng Mobile có thể stream và phát nhạc chạy nền.
* **Xóa file an toàn**: Khi xóa một bài học, hệ thống tự động xóa bản ghi trong CSDL PostgreSQL và dọn dẹp file vật lý tương ứng trên Cloudflare R2.

### 2. Hệ Thống Khởi Tạo Dữ Liệu Tự Động (Lifespan Seeding & Migrations)
* **Tạo bảng tự động**: Hệ thống tự động gọi `Base.metadata.create_all` tạo các bảng PostgreSQL (gồm `users`, `tokens`, `audios`) khi khởi chạy nếu chúng chưa tồn tại.
* **Dữ liệu hạt giống (Seed)**: Tự động tạo tài khoản Admin mặc định (`admin` / `admin`) nếu CSDL trống.



## 📖 Tài Liệu Hướng Dẫn API (Swagger UI)

Sau khi khởi chạy ứng dụng thành công, bạn có thể truy cập tài liệu Swagger tương tác trực tiếp để kiểm tra thử các API tại địa chỉ:
* **Interactive Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
