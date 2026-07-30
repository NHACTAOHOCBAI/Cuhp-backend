# Hướng dẫn Luồng Hoạt động Chi tiết của Hệ thống Chatbot Tiệm Bánh Ngọt

Tài liệu này cung cấp cái nhìn chi tiết và toàn diện về cách thức hoạt động của hệ thống Chatbot tự động trả lời khách hàng thay cho Admin. Tài liệu bao gồm kiến trúc hệ thống, cấu trúc cơ sở dữ liệu (Database), luồng xử lý tin nhắn bất đồng bộ, các Agent chuyên trách và chi tiết cơ chế hoạt động của máy trạng thái (State Machine) - đặc biệt là các trạng thái liên quan đến thời gian giao hàng như `ASKING_DELIVERY_TIME` và `COLLECTING_ZALO_TODAY`.

---

## 1. Sơ đồ Kiến trúc & Luồng Dữ liệu Tổng quan

Hệ thống chatbot được thiết kế dưới dạng **Modular Service** tích hợp bên trong backend FastAPI để cô lập logic nghiệp vụ AI khỏi luồng định tuyến API chính, đồng thời đồng bộ hóa tức thời với giao diện người dùng qua WebSockets.

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Khách hàng (UI)
    actor Admin as Admin (UI)
    participant API as FastAPI Router
    participant DB as Database (Postgres)
    participant WS as WebSocket Manager
    participant Orchestrator as ChatbotOrchestrator
    participant Router as RouterAgent
    participant Agent as Chuyên Viên Agent (FAQ / ORDER / CHITCHAT)
    participant AI as AzureOpenAIClient
    participant Tools as Chatbot Tools

    Customer->>API: Gửi tin nhắn mới (POST /rooms/{room_id}/messages)
    API->>DB: 1. Lưu tin nhắn của Khách hàng vào bảng 'messages'
    API->>WS: 2. Broadcast tin nhắn mới tới Khách hàng và Admin qua WS
    API-->>Customer: 3. Trả về phản hồi HTTP 200 (Thành công tức thì)
    
    Note over API, Orchestrator: API kích hoạt FastAPI BackgroundTasks thực thi ngầm
    API->>Orchestrator: 4. Gọi process_message(room_id, customer_message)
    
    rect rgb(240, 248, 255)
        note right of Orchestrator: Giai đoạn 1: Chuẩn bị & Phân loại Ý định (Intent)
        Orchestrator->>DB: Lấy lịch sử chat & ConversationState
        Orchestrator->>Router: Phân loại ý định tin nhắn
        Router->>AI: Gọi Azure OpenAI (System prompt phân loại)
        AI-->>Router: Trả về nhóm ý định (FAQ, ORDER, CHITCHAT)
        Router-->>Orchestrator: Trả về kết quả phân loại
    end

    rect rgb(255, 245, 238)
        note right of Orchestrator: Giai đoạn 2: Xử lý Logic Nghiệp vụ & AI Tool Calling
        Orchestrator->>Agent: Chuyển tiếp tin nhắn đến Agent phù hợp
        alt Ý định = FAQ
            Agent->>DB: So khớp từ khóa FAQ trong bảng 'faqs' (> 70% khớp)
            alt Không tìm thấy FAQ phù hợp trong DB
                Agent->>Tools: Gọi handover_to_admin() để tắt bot & báo admin
                Tools->>DB: Cập nhật chatbot_enabled = False & Lưu tin nhắn hệ thống (không prefix)
                Tools->>WS: Broadcast new_message (tin nhắn hệ thống) & room_update
            end
        else Ý định = ORDER hoặc CHITCHAT
            Agent->>AI: Gửi ngữ cảnh (System Prompt + State Instructions + Lịch sử)
            loop Đệ quy xử lý Tool Calls (Tối đa 5 lần)
                AI-->>Agent: Yêu cầu gọi Tool (ví dụ: handover_to_admin, set_delivery_time, ...)
                Agent->>Tools: Thực thi hàm Python tương ứng
                alt Gọi handover_to_admin
                    Tools->>DB: Cập nhật chatbot_enabled = False & Lưu tin nhắn hệ thống (không prefix)
                    Tools->>WS: Broadcast new_message (tin nhắn hệ thống) & room_update
                else Các tools khác
                    Tools->>DB: Đọc/Ghi dữ liệu (Cập nhật giỏ hàng/thông tin khách/trạng thái)
                end
                Tools-->>AI: Trả về kết quả thực thi dạng chuỗi
            end
            AI-->>Agent: Trả về nội dung phản hồi (hoặc chuỗi rỗng nếu đã gọi handover_to_admin)
        end
        Agent-->>Orchestrator: T## 2. Thiết kế Cơ sở Dữ liệu (Database Schema) liên quan Chatbot

Hệ thống sử dụng các bảng cơ sở dữ liệu để lưu trữ cấu hình phòng chat, tin nhắn, cấu hình thuộc tính động và đặc biệt là bảng lưu trữ trạng thái hội thoại của khách hàng để làm bộ nhớ ngắn hạn cho AI.

### 2.1 Bảng `chat_rooms` (Phòng chat)
Lưu trữ thông tin phòng chat giữa Khách hàng và Tiệm.
* **`id`** (`String`, Khóa chính): ID phòng chat (thường có dạng `room-{user_id}` cho Web UI hoặc `room-fb-{sender_id}` cho Facebook Messenger).
* **`chatbot_enabled`** (`Boolean`, Mặc định: `True`): Cấu hình bật/tắt chatbot. Nếu `True`, chatbot sẽ tự động trả lời tin nhắn của Khách hàng. Nếu tắt (`False`), chatbot dừng hoạt động để Admin hỗ trợ thủ công.
* **`user_id`** (`String`, Khóa ngoại): Liên kết đến Khách hàng sở hữu phòng chat (có thể rỗng đối với phòng chat tạo tự động qua kênh Facebook).

### 2.2 Bảng `messages` (Tin nhắn)
Lưu trữ toàn bộ lịch sử tin nhắn trong phòng chat, hỗ trợ liên kết và phản hồi tin nhắn gốc.
* **`id`** (`String`, Khóa chính): Định dạng `msg-{random_hex}`.
* **`room_id`** (`String`, Khóa ngoại): Liên kết đến phòng chat.
* **`content`** (`String`): Nội dung tin nhắn (chữ thô).
* **`sender_id`** (`String`): ID người gửi (`usr-admin` đại diện cho Chatbot/Admin, ID người dùng đại diện cho Khách hàng).
* **`sender_name`** (`String`): Tên người hiển thị (`Support Admin` hoặc tên Khách hàng).
* **`timestamp`** (`DateTime`): Thời điểm gửi tin nhắn (UTC).
* **`fb_message_id`** (`String`, Tùy chọn): ID tin nhắn trên hệ thống Facebook Messenger để phục vụ đồng bộ luồng.
* **`parent_id`** (`String`, Khóa ngoại tự tham chiếu): ID tin nhắn gốc mà tin nhắn này đang trả lời (dùng cho tính năng Trích dẫn/Reply).

### 2.3 Bảng `conversation_states` (Bộ nhớ trạng thái của Chatbot)
Đây là **bảng quan trọng nhất** quản lý ngữ cảnh hội thoại, tránh tình trạng AI "quên" thông tin đã trao đổi. Mỗi phòng chat (`room_id`) chỉ có duy nhất 1 bản ghi trạng thái.
* **`room_id`** (`String`, Khóa chính, Khóa ngoại liên kết `chat_rooms`): Xác định phòng chat.
* **`state`** (`String`, Mặc định: `"IDLE"`): Trạng thái hiện tại của cuộc trò chuyện (ví dụ: `ASKING_DELIVERY_TIME`, `SELECTING_ITEMS`, `COLLECTING_INFO`, `CONFIRMED`).
* **`cart_items`** (`String` chứa JSON): Danh sách sản phẩm/combo Khách hàng đã chốt đặt. Cấu trúc JSON: `[{"product_id": "...", "name": "...", "price": 100000, "quantity": 2, "is_combo": false}]`.
* **`draft_selection`** (`String` chứa JSON): Bộ nhớ tạm thời lưu trữ thông tin Khách hàng đang lựa chọn nhưng chưa chốt số lượng (ví dụ: lưu tạm `category`, `product_line`, `size`, `model_code`, `name` trước khi thêm vào giỏ hàng).
* **`customer_name`** (`String`): Tên người nhận hàng do khách hàng cung cấp.
* **`customer_phone`** (`String`): Số điện thoại nhận hàng (hoặc số điện thoại Zalo khi giao gấp).
* **`customer_address`** (`String`): Địa chỉ giao hàng cụ thể.
* **`delivery_time`** (`DateTime`): Thời gian giao bánh mong muốn (ngày/giờ cụ thể).
* **`history_summary`** (`String`): Bản tóm tắt cuộc hội thoại được sinh ra bởi `SummaryAgent` khi lịch sử chat tăng thêm.
* **`last_summary_message_count`** (`Integer`): Số lượng tin nhắn tại thời điểm tóm tắt gần nhất (dùng làm mốc để trigger tóm tắt mỗi khi nhận thêm 10 tin nhắn).
* **`custom_fields`** (`String` chứa JSON): Lưu trữ giá trị của các trường thông tin giao hàng tùy chỉnh (ví dụ: lời chúc viết lên bánh, ghi chú đặc biệt,...).

### 2.4 Bảng `combos` và `combo_items` (Quản lý Combo sản phẩm)
Quản lý các gói ưu đãi mua sắm theo bộ combo.
* **Bảng `combos`**: `id`, `sku`, `name`, `price` (giá gốc của cả combo), `image_url`, `description`.
* **Bảng `combo_items`**: `id`, `combo_id` (Liên kết combo), `product_id` (Liên kết sản phẩm con thành phần), `quantity` (Số lượng sản phẩm trong combo).

### 2.5 Bảng `order_field_configs` (Cấu hình trường tùy chỉnh của Đơn hàng)
Quản lý động các trường thông tin cần thu thập từ phía khách hàng khi chốt đơn.
* **`id`** (`String`, Khóa chính)
* **`key`** (`String`, duy nhất): Tên định danh kỹ thuật (ví dụ: `note_greeting`).
* **`label`** (`String`): Tên nhãn hiển thị trực quan (ví dụ: "Chữ viết lên bánh").
* **`type`** (`String`): Loại dữ liệu đầu vào (`text`, `number`, `select`, `datetime`).
* **`required`** (`Boolean`): Có bắt buộc khách hàng cung cấp hay không.
* **`active`** (`Boolean`): Trạng thái kích hoạt sử dụng trên hệ thống.
* **`options`** (`String` chứa JSON): Danh sách tùy chọn nếu kiểu là `select`.
* **`is_core`** (`Boolean`): Nếu là `True`, đây là các trường cốt lõi của hệ thống (như tên, số điện thoại, địa chỉ) không cho phép xóa từ Admin UI.

---

## 3. Luồng Xử lý Bất đồng bộ (FastAPI Background Tasks & WebSockets)

Để tối ưu hóa trải nghiệm người dùng, luồng xử lý tin nhắn được tối ưu hóa như sau:

1. **Không chặn yêu cầu gửi tin (Non-blocking HTTP Response)**: 
   Khi Khách hàng gửi tin nhắn lên API `POST /rooms/{room_id}/messages`, backend lập tức ghi nhận tin nhắn vào DB, gửi thông báo WebSocket tới Admin UI để đồng bộ, và lập tức trả về phản hồi HTTP `200 OK` cho Khách hàng. Giao diện của Khách hàng hiển thị tin nhắn của chính mình ngay lập tức mà không phải chờ AI phản hồi.
2. **Kích hoạt xử lý ngầm (BackgroundTasks)**: 
   Sau khi HTTP response được trả về, FastAPI tiếp tục gọi hàm `chatbot_orchestrator.process_message` chạy ngầm. Điều này giúp hệ thống không bị nghẽn luồng xử lý do cuộc gọi mạng đến Azure OpenAI thường mất từ 1-3 giây.
3. **Phát sóng phản hồi (WebSocket Broadcasting)**: 
   Khi ChatbotOrchestrator sinh câu trả lời thành công, nó lưu tin nhắn của AI dưới dạng `sender_id="usr-admin"` và gửi một sự kiện WebSocket `new_message` tới phòng chat. Cả Khách hàng và Admin đều nhận được tin nhắn phản hồi của Bot cùng một thời điểm trên UI theo thời gian thực (Real-time).

---

## 4. Cơ chế Hoạt động của Máy Trạng thái (Chatbot State Machine)

Hệ thống áp dụng máy trạng thái chặt chẽ nhằm định hình hành vi và chỉ dẫn (Prompt instructions) của AI tại từng thời điểm. Dưới đây là các trạng thái chính:

```mermaid
stateDiagram-v2
    [*] --> IDLE
    
    IDLE --> ASKING_DELIVERY_TIME : Khách muốn mua bánh & Chưa có delivery_time
    ASKING_DELIVERY_TIME --> COLLECTING_ZALO_TODAY : Khách muốn giao gấp TRONG NGÀY (is_today=True)
    ASKING_DELIVERY_TIME --> SELECTING_ITEMS : Khách giao NGÀY KHÁC (is_today=False)
    
    COLLECTING_ZALO_TODAY --> IDLE : Khách cung cấp số Zalo (Tắt chatbot tự động, Admin tiếp quản)
    
    SELECTING_ITEMS --> CONFIRMING_ITEMS : Khách đã chốt xong sản phẩm (Muốn xem giỏ hàng)
    CONFIRMING_ITEMS --> SELECTING_ITEMS : Khách muốn thay đổi/thêm bánh khác
    
    CONFIRMING_ITEMS --> COLLECTING_INFO : Khách đồng ý chốt giỏ hàng (Chuyển sang điền thông tin ship)
    COLLECTING_INFO --> CONFIRMED : Điền đủ Tên, SĐT, Địa chỉ, Thời gian + Khách đồng ý chốt
    
    CONFIRMED --> IDLE : Tạo đơn hàng nháp thành công (Draft Order)
    
    state "Tắt Chatbot & Admin Tiếp quản" as Handover
    IDLE --> Handover : Gọi handover_to_admin (Thiếu thông tin / Yêu cầu gặp nhân viên)
    ASKING_DELIVERY_TIME --> Handover : Gọi handover_to_admin hoặc FAQ không tìm thấy
    SELECTING_ITEMS --> Handover : Gọi handover_to_admin
    COLLECTING_INFO --> Handover : Gọi handover_to_admin
```

### 4.1 Chi tiết Luồng Xác định Thời gian Giao hàng

Mục tiêu cốt lõi của quy trình này là **xác định thời điểm giao bánh trước khi tư vấn**, vì tiệm cần chuẩn bị nguyên liệu và một số loại bánh phức tạp không thể làm gấp lấy ngay.

#### Bước 1: Kích hoạt Trạng thái `ASKING_DELIVERY_TIME`
* **Điều kiện kích hoạt**: Khi khách hàng gửi tin nhắn bày tỏ ý định mua bánh (Intent = `ORDER`), hệ thống kiểm tra trường `delivery_time` trong bảng `conversation_states`. Nếu trường này đang rỗng (`None`), `OrderAgent` sẽ tự động cập nhật trạng thái phòng chat sang `ASKING_DELIVERY_TIME`.
* **Hành vi của Chatbot**: 
  - Hệ thống nạp chỉ dẫn đặc biệt vào System Prompt: **Yêu cầu chatbot bắt buộc phải lịch sự hỏi khách hàng thời gian muốn nhận bánh (ngày/giờ cụ thể).**
  - **Quy tắc tuyệt đối**: Chatbot **TUYỆT ĐỐI KHÔNG ĐƯỢC** tư vấn, giới thiệu bất kỳ món bánh nào hoặc hiển thị danh mục sản phẩm lúc này. Nếu khách hỏi thực đơn, bot phải từ chối khéo: *"Để tư vấn loại bánh phù hợp nhất (vì một số bánh không làm kịp trong ngày), em xin phép hỏi anh/chị dự định nhận bánh vào ngày giờ nào ạ?"*.
* **So khớp thời gian & Gọi Tool**:
  Khi khách hàng trả lời thời gian nhận bánh, Chatbot (thông qua Azure OpenAI) sẽ tự động phân tích câu trả lời để xác định giá trị của tham số `is_today`:
  - `is_today=True`: Khách muốn nhận bánh trong ngày hôm nay hoặc giao gấp ngay lập tức (ví dụ: *"chiều nay"*, *"hôm nay"*, *"16h chiều nay"*, *"giao gấp nhé"*).
  - `is_today=False`: Khách muốn nhận bánh vào ngày khác (ví dụ: *"ngày mai"*, *"chủ nhật tuần này"*, *"ngày 29/7"*,...).
  - Bot bắt buộc gọi công cụ `set_delivery_time(delivery_time, is_today)`.

---

#### Bước 2A: Khách hàng giao bánh trong ngày (`is_today=True`) -> Chuyển sang `COLLECTING_ZALO_TODAY`
* **Logic trong code**: Công cụ `set_delivery_time` cập nhật `delivery_time` của khách hàng vào database và chuyển trạng thái (`state`) sang `COLLECTING_ZALO_TODAY`.
* **Hành vi của Chatbot**:
  - Hệ thống chỉ dẫn Bot: **Khách hàng muốn giao bánh gấp trong ngày hôm nay. Bot cần lịch sự xin số điện thoại Zalo của khách hàng.**
  - **Quy tắc tuyệt đối**: Không giới thiệu, không tư vấn sản phẩm. Chỉ tập trung xin số điện thoại Zalo để chuyển tiếp cho Admin xử lý đơn gấp.
* **Tắt Chatbot tự động (Hand-off to Human)**:
  - Khi khách hàng nhắn số điện thoại, chatbot tự động phân tích và gọi công cụ `save_zalo_phone_and_turn_off_bot(zalo_phone)`.
  - Công cụ này thực hiện chuỗi hành động:
    1. Lưu số điện thoại vào cột `customer_phone` trong bảng `conversation_states`.
    2. Chuyển trạng thái (`state`) hội thoại về lại `IDLE`.
    3. Đặt `chatbot_enabled = False` trong bảng `chat_rooms` để **tắt chatbot hoàn toàn**.
    4. Gửi một tin nhắn hệ thống vào phòng chat: *"Đã lưu số điện thoại Zalo '{zalo_phone}' và tắt chatbot thành công. Admin sẽ liên hệ trực tiếp hỗ trợ giao bánh gấp qua Zalo."*
    5. Phát đi sự kiện WebSocket `room_update` báo cho Admin UI biết phòng chat này đã tắt bot để Admin thực tế vào chat trực tiếp với khách hàng.

---

#### Bước 2B: Khách hàng giao bánh ngày khác (`is_today=False`) -> Chuyển sang `SELECTING_ITEMS`
* **Logic trong code**: Công cụ `set_delivery_time` cập nhật `delivery_time` vào DB và chuyển trạng thái (`state`) sang `SELECTING_ITEMS`.
* **Hành vi của Chatbot**:
  - Hệ thống giải phóng giới hạn tư vấn. Bot lúc này có thể chào mừng khách hàng, gọi công cụ `list_menu_categories` để hiển thị menu các danh mục bánh, và nhiệt tình giới thiệu các mẫu bánh phù hợp với nhu cầu.

---

### 4.2 Chi tiết Luồng Tư vấn và Lên Đơn hàng (`SELECTING_ITEMS` -> `CONFIRMED`)

Khi đã vào trạng thái chọn bánh (`SELECTING_ITEMS`), chatbot tuân thủ nghiêm ngặt **Quy trình tư vấn 4 bước phân cấp**:

1. **Bước 1: Xác định Danh mục bánh** (Sử dụng công cụ `list_menu_categories`).
2. **Bước 2: Xác định Dòng bánh cụ thể** (Sử dụng công cụ `get_product_line_details` để lấy thông tin giá, size và **hình ảnh sản phẩm**).
   - *Lưu ý*: Bot bắt buộc phải giữ nguyên đường dẫn hình ảnh dạng markdown `![Tên mẫu bánh](image_url)` từ tool trả về để hiển thị lên màn hình chat của khách hàng.
3. **Bước 3: Xác định Mẫu bánh (`model_code`) và Kích thước (`size`)** (Sử dụng công cụ `update_draft_selection` để cập nhật bộ nhớ tạm vào DB tránh AI bị quên khi khách chat lan man).
4. **Bước 4: Chốt số lượng và Thêm vào giỏ hàng** (Sử dụng công cụ `update_cart`).
   - Bot chỉ được gọi `update_cart` khi chỉ còn **duy nhất 1 sản phẩm khớp hoàn toàn** và **khách hàng đã xác nhận đồng ý** chốt số lượng.

Khi khách đồng ý chuyển sang thanh toán:
* Chuyển trạng thái sang `COLLECTING_INFO` để thu thập thông tin nhận hàng còn thiếu (Tên khách hàng, SĐT, Địa chỉ nhận hàng, kèm các thuộc tính động được cấu hình trong bảng `order_field_configs`). Mỗi lần khách cung cấp thông tin, bot gọi tool `update_shipping_info`.
* Khi đã thu thập đủ thông tin giao hàng, bot hiển thị đầy đủ tóm tắt đơn hàng và hỏi khách xác nhận chốt đơn.
* Khi khách đồng ý xác nhận, bot gọi tool `create_draft_order` để tạo bản ghi đơn hàng nháp trong cơ sở dữ liệu (`DraftOrder` và `DraftOrderItem`), sau đó chuyển trạng thái về `CONFIRMED` và reset giỏ hàng về rỗng.

---

### 4.3 Tích hợp Facebook Messenger & Phản hồi dạng Luồng (Message Thread)

1. **Webhook Facebook**:
   - Tích hợp endpoint `/api/v1/facebook/webhook` để đón nhận sự kiện tin nhắn thời gian thực từ khách hàng qua kênh Facebook Page.
   - Hệ thống tự động tạo phòng chat dạng `room-fb-{sender_id}` trong Database và kích hoạt chatbot mặc định (`chatbot_enabled=True`).
2. **Gửi tin nhắn qua Facebook Send API**:
   - Phản hồi từ chatbot được chuyển thành yêu cầu gửi API tới Graph API phiên bản `v19.0` của Facebook.
   - Hỗ trợ gửi tin nhắn văn bản thường, tin nhắn chứa hình ảnh (`send_image`), hoặc định dạng Carousel / Generic Template (`send_carousel`) để khách hàng dễ dàng trượt xem các mẫu bánh ngọt trực quan.
3. **Message Threading (Reply Tin nhắn)**:
   - Các tin nhắn được gửi đi hoặc nhận về đều có trường `fb_message_id` để định danh trên Facebook.
   - Khi Admin hoặc khách hàng thực hiện trả lời (Reply) một tin nhắn cụ thể trên UI, hệ thống sẽ liên kết trường `parent_id` trỏ về tin nhắn gốc.
   - Giao diện Admin hiển thị hộp thoại trích dẫn (quoting) trực quan và cho phép nhảy nhanh đến tin nhắn cha bằng cách click vào dòng trích dẫn.

---

### 4.4 Tự động đồng bộ thuộc tính draft_selection & Tóm tắt lịch sử hội thoại

1. **Đồng bộ draft_selection thông minh**:
   - Khi khách hàng đang phân vân lựa chọn thuộc tính sản phẩm, chatbot liên tục cập nhật các thuộc tính qua công cụ `update_draft_selection(category, product_line, size, model_code, name, product_id)`.
   - **Tự động đồng bộ ngược**: Nếu kết quả lọc thuộc tính trong database chỉ còn lại **duy nhất 1 sản phẩm khớp**, hệ thống sẽ tự động chốt sản phẩm đó và điền đầy đủ thông tin ngược trở lại trường `draft_selection` trong DB (gồm `product_id`, `name`, `size`, `model_code`, `category`, `product_line`).
2. **Tự động tóm tắt sau mỗi 10 tin nhắn**:
   - Để ngăn chặn việc quá tải Token (Context Window) khi gọi Azure OpenAI với các cuộc hội thoại dài, hệ thống lưu trường `last_summary_message_count` để ghi nhận mốc tóm tắt gần nhất.
   - Mỗi khi phòng chat nhận thêm 10 tin nhắn mới kể từ mốc trước đó, `SummaryAgent` sẽ tự động được chạy ngầm để cập nhật cột `history_summary`, sau đó nạp bản tóm tắt này làm ngữ cảnh nền cho các cuộc gọi OpenAI tiếp theo.

---

### 4.5 Truy vấn trạng thái Đơn hàng (Order Status Query)

* Chatbot được tích hợp khả năng phục vụ khách hàng hỏi về đơn hàng của họ (ví dụ: *"Đơn hàng của mình được duyệt chưa?"*, *"Kiểm tra đơn hàng cho mình"*).
* `OrderAgent` sẽ tiếp quản ý định này và kích hoạt công cụ `get_user_orders` để lấy danh sách các đơn hàng nháp liên quan đến phòng chat hiện tại.
* Bot trả về chi tiết danh sách đơn hàng bao gồm mã đơn hàng, ngày tạo, trạng thái tiếng Việt (`Đang chờ duyệt`, `Đã duyệt`, `Đã hủy/Từ chối`), địa chỉ giao hàng và tổng số tiền để thông báo lại cho khách.

---

### 4.6 Cơ chế Bàn giao cho Admin và Tắt Chatbot Tự động (Handover to Admin)

Hệ thống tích hợp cơ chế tự động chuyển giao cuộc hội thoại cho nhân viên tư vấn hỗ trợ khi chatbot không đủ thông tin hoặc khi khách hàng trực tiếp yêu cầu:

1. **Các kịch bản kích hoạt bàn giao**:
   - **Không tìm thấy FAQ trong database**: Khi tin nhắn của khách thuộc nhóm ý định `FAQ` nhưng không khớp bất kỳ câu hỏi nào trong DB với tỉ lệ >= 70%.
   - **Thiếu thông tin/căn cứ trong DB**: Khi khách hàng hỏi sâu về hương vị, nguyên liệu chi tiết mà kết quả từ công cụ trả về không cung cấp. AI tuân thủ quy tắc chống bịa đặt và chủ động chuyển Admin.
   - **Khách hàng yêu cầu gặp nhân viên**: Khi khách nhắn các từ khóa như *"gặp nhân viên"*, *"gặp admin trực tiếp"*,... AI tự nhận diện và gọi tool bàn giao.
2. **Hành động nghiệp vụ khi bàn giao**:
   - Tắt chatbot bằng cách đặt `chatbot_enabled = False` trong bảng `chat_rooms`.
   - Lưu và gửi tin nhắn hệ thống: *"Chatbot đã được tắt. Nhân viên hỗ trợ sẽ tiếp quản cuộc hội thoại này để hỗ trợ trực tiếp cho anh/chị ngay nhé."*
   - Phát đi các gói WebSocket `new_message` và `room_update` để cập nhật sidebar và hiển thị tức thời trên UI khách hàng và Admin dashboard.
   - Hủy bỏ tin nhắn văn bản cuối cùng của chatbot (trả về chuỗi rỗng) để đảm bảo chỉ hiển thị tin nhắn hệ thống sạch sẽ.

---

## 5. Đặc tả Chi tiết các Chatbot Tools (Công cụ AI gọi)

Dưới đây là danh sách các công cụ được định nghĩa trong [tools.py](file:///home/aipowervn/Desktop/Chatbot/Chatbot/backend/app/services/chatbot/tools.py) mà Azure OpenAI có thể kích hoạt trong quá trình trò chuyện:

| Tên Công cụ (Tool Name) | Tham số đầu vào (Arguments) | Logic Xử lý & Tác động Database | Kết quả trả về cho AI (Output) |
| :--- | :--- | :--- | :--- |
| **`list_menu_categories`** | Không | Truy vấn bảng `products` để lấy danh sách các danh mục bánh hiện có (ví dụ: Bánh kem, Bánh mì,...). | Chuỗi văn bản danh sách các danh mục bánh. |
| **`get_product_line_details`** | `product_line_name` (str) | Tìm kiếm chi tiết dòng bánh trong bảng `products`. Lấy ra tất cả kích thước (size) và mẫu mã (`model_code`) cùng hình ảnh tương ứng. | Thông tin kích thước, mẫu mã, hình ảnh của dòng bánh đó để hiển thị cho khách. |
| **`search_products`** | `keyword` (str) | Truy vấn tìm kiếm sản phẩm theo từ khóa tương ứng trong tên hoặc mô tả bánh. | Danh sách sản phẩm khớp từ khóa kèm thông tin chi tiết. |
| **`update_draft_selection`** | `category` (str), `product_line` (str), `size` (str), `model_code` (str), `name` (str), `product_id` (str) (Tất cả optional) | Lưu trữ các thuộc tính lựa chọn tạm thời của khách hàng vào trường `draft_selection` của bảng `conversation_states`. Nếu chỉ còn đúng 1 sản phẩm khớp, tự động điền đầy đủ và cập nhật `product_id`. | Trả về trạng thái lựa chọn nháp hiện tại và gợi ý bước tiếp theo cho AI. |
| **`update_cart`** | `items` (list[dict]) chứa `product_id` (hoặc combo_sku/product_sku) và `quantity` | Thêm, cập nhật số lượng hoặc xóa sản phẩm/combo khỏi giỏ hàng (`cart_items` trong bảng `conversation_states`). Nếu `quantity <= 0`, sản phẩm sẽ bị xóa khỏi giỏ. | Chuỗi văn bản liệt kê danh sách giỏ hàng sau khi cập nhật và tổng tiền. |
| **`update_shipping_info`** | `customer_name`, `customer_phone`, `customer_address` (Tất cả optional) | Lưu thông tin giao hàng của khách vào các cột tương ứng trong bảng `conversation_states`. Cho phép tự động cập nhật các thuộc tính tùy chỉnh động (`custom_fields`) từ cấu hình. | Báo cáo thông tin giao hàng hiện tại, liệt kê các thông tin còn thiếu. |
| **`set_delivery_time`** | `delivery_time` (str), `is_today` (bool) | Lưu thời gian giao bánh vào cột `delivery_time` trong bảng `conversation_states`. Cập nhật trạng thái `state` thành `COLLECTING_ZALO_TODAY` (nếu `is_today=True`) hoặc `SELECTING_ITEMS` (nếu `is_today=False`). | Thông báo trạng thái mới và hướng dẫn bước tiếp theo cho AI. |
| **`save_zalo_phone_and_turn_off_bot`** | `zalo_phone` (str) | Lưu số Zalo vào cột `customer_phone` của bảng `conversation_states`. Chuyển trạng thái `state` về `IDLE`. Tìm phòng chat tương ứng trong bảng `chat_rooms` và đặt `chatbot_enabled = False`. Phát sóng sự kiện WebSocket cập nhật phòng chat. | Chuỗi thông báo xác nhận đã lưu số Zalo và tắt bot thành công. |
| **`create_draft_order`** | Không | Đọc giỏ hàng và thông tin giao hàng từ bảng `conversation_states`. Tạo bản ghi mới trong bảng `draft_orders` và `draft_order_items`. Chuyển trạng thái `state` về `CONFIRMED` và dọn sạch giỏ hàng (`cart_items = "[]"`). | Xác nhận tạo đơn hàng nháp thành công kèm ID đơn hàng để AI phản hồi khách. |
| **`handover_to_admin`** | `reason` (str, optional) | Tìm phòng chat trong bảng `chat_rooms` và đặt `chatbot_enabled = False`. Lưu và broadcast tin nhắn hệ thống bàn giao, cập nhật trạng thái UI. | Chuỗi thông báo tắt bot thành công. |
| **`get_user_orders`** | Không | Truy vấn danh sách tất cả `DraftOrder` của phòng chat hiện tại để lấy thông tin mã đơn, ngày tạo, địa chỉ nhận, chi tiết sản phẩm và trạng thái đơn hàng. | Chuỗi văn bản định dạng danh sách đơn hàng cho AI trả lời khách. |

