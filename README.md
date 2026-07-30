# Backend Chatbot Service 🍰🤖

Đây là dịch vụ backend FastAPI phụ trách xử lý logic nghiệp vụ cho hệ thống Chatbot Tiệm Bánh Ngọt. Hệ thống tích hợp Azure OpenAI, WebSockets thời gian thực, lưu trữ AWS S3 và kênh Facebook Messenger để tương tác tự động với khách hàng.

---

## 🛠️ Công Nghệ Sử Dụng (Tech Stack)

* **Ngôn ngữ**: [Python 3.12+](https://www.python.org/)
* **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Hỗ trợ Asynchronous, Background Tasks, WebSockets)
* **Web Server**: [Uvicorn](https://www.uvicorn.org/)
* **ORM & Database**: [SQLAlchemy](https://www.sqlalchemy.org/) + [PostgreSQL](https://www.postgresql.org/)
* **AI Model**: Azure OpenAI (AzureOpenAIClient gọi GPT-4o-mini hoặc tương đương)
* **Lưu trữ**: [AWS S3](https://aws.amazon.com/s3/) (Dùng tải ảnh sản phẩm lên đám mây)
* **Kênh kết nối**: [Facebook Messenger API v19.0](https://developers.facebook.com/)

---

## 📁 Cấu Trúc Thư Mục Backend

```text
backend/
├── app/
│   ├── api/                  # Các router và endpoint API chính
│   │   ├── deps.py           # Dependency injection (lấy database session, auth,...)
│   │   └── v1/
│   │       ├── api.py        # Đăng ký tập trung tất cả router v1
│   │       └── endpoints/    # Định nghĩa chi tiết router (Auth, Rooms, Products, combos, Facebook,...)
│   ├── core/                 # Cấu hình hệ thống cốt lõi
│   │   ├── config.py         # Quản lý cài đặt thông qua Pydantic Settings
│   │   ├── database.py       # Kết nối SQLAlchemy engine và session maker
│   │   └── websocket.py      # ConnectionManager quản lý kết nối websocket thời gian thực
│   ├── services/             # Các dịch vụ nghiệp vụ chính
│   │   ├── facebook.py       # Facebook Service gửi text, ảnh, generic template carousel
│   │   └── chatbot/          # Hệ thống các Agent AI và máy trạng thái
│   │       ├── orchestrator.py  # Điều phối tin nhắn đầu vào, gọi Agent phù hợp
│   │       ├── state_machine.py # Máy trạng thái quản lý State hội thoại
│   │       ├── tools.py         # Công cụ (Tools) cung cấp khả năng truy vấn DB cho AI
│   │       └── prompts.py       # Quản lý Prompts hệ thống cho các Agent
│   ├── models.py             # Định nghĩa toàn bộ database model SQLAlchemy
│   ├── schemas/              # Các Pydantic schemas để validate request/response
│   └── main.py               # Điểm khởi chạy FastAPI, xử lý Lifespan và Seed database
├── Dockerfile                # Cấu hình build Docker image cho backend
├── docker-compose.yml        # Docker Compose chạy PostgreSQL và Backend
├── requirements.txt          # Danh sách dependencies của Python
└── CHATBOT_WORKFLOW.md       # Sơ đồ và chi tiết luồng nghiệp vụ chatbot
```

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Local

### 1. Yêu cầu hệ thống
* Python 3.12+ (khuyên dùng [uv](https://github.com/astral-sh/uv) để quản lý chạy nhanh hơn).
* Đã cài đặt PostgreSQL (hoặc chạy qua Docker).

### 2. Thiết lập Biến Môi Trường
Sao chép hoặc tạo tệp `.env` tại thư mục `backend/` từ mẫu cấu hình sau và điền các tham số:

```env
APP_NAME="Cake Shop Chatbot AI"
APP_VERSION="1.0.0"

# Cấu hình Cơ sở dữ liệu PostgreSQL
DATABASE_URL=postgresql://postgres:postgres@localhost:5439/chatbot_db

# Cấu hình Azure OpenAI Service
AZURE_OPENAI_ENDPOINT_1=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY_1=your_azure_openai_api_key_here
AZURE_OPENAI_MODEL_1=gpt-4o-mini  # Tên model deployment của bạn

# Cấu hình AWS S3 để upload ảnh sản phẩm (tùy chọn)
AWS_ACCESS_KEY_ID=your_aws_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=ap-southeast-1
S3_BUCKET=cake-shop-assets
S3_PUBLIC_BASE_URL=https://cake-shop-assets.s3.amazonaws.com

# Cấu hình Kênh Facebook Messenger (tải webhook)
FB_PAGE_ACCESS_TOKEN=your_page_access_token_here
FB_VERIFY_TOKEN=your_custom_webhook_verify_token_here
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

## 🛠️ Cơ chế Khởi Tạo Dữ Liệu Tự Động (Lifespan Seeding & Migrations)

Khi khởi động ứng dụng FastAPI:
1. **Tạo bảng tự động**: Hệ thống tự động gọi `Base.metadata.create_all` tạo các bảng PostgreSQL nếu chúng chưa tồn tại.
2. **Dynamic Migrations**: Các cột dữ liệu mới như `delivery_time`, `last_summary_message_count`, `keywords`, `fb_message_id`, `parent_id`... được kiểm tra và thêm động thông qua lệnh raw SQL ở hàm `lifespan` trong [main.py](file:///home/aipowervn/Desktop/Chatbot/Chatbot/backend/app/main.py).
3. **Dữ liệu hạt giống (Seed)**:
   - Tự động tạo tài khoản Admin mặc định nếu CSDL trống:
     - **Username**: `admin`
     - **Password**: `admin`
     - **Role**: `admin`
   - Tự động tạo các cấu hình trường giao hàng cốt lõi (`order_field_configs`) bắt buộc bao gồm: Tên người nhận, SĐT, Địa chỉ giao hàng, Thời gian nhận bánh.

---

## 🔗 Tích hợp Webhook Facebook Messenger

Để tích hợp trang Facebook Page của bạn với chatbot:
1. **Thiết lập Webhook URL**:
   - Webhook endpoint của backend: `http://<your-public-domain>/api/v1/facebook/webhook`
   - Nhập chuỗi Verify Token trùng khớp với cấu hình `FB_VERIFY_TOKEN` trong `.env` để xác thực liên kết webhook.
2. **Nhận tin nhắn**:
   - Khi có tin nhắn gửi tới trang Facebook, Messenger API gửi POST request tới webhook.
   - Hệ thống tự tạo phòng chat `room-fb-{sender_id}` trong Database và chatbot bắt đầu tự động tư vấn (bật mặc định).
3. **Phản hồi**:
   - Tin nhắn trả lời của Chatbot được định tuyến qua `FacebookService` gửi API về người dùng (hỗ trợ text, ảnh bánh, hoặc danh sách mẫu trượt carousel).

---

## 📖 Tài Liệu Hướng Dẫn API (Swagger UI)

Sau khi khởi chạy ứng dụng thành công, bạn có thể truy cập tài liệu Swagger tương tác trực tiếp để kiểm tra thử các API tại địa chỉ:
* **Interactive Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
