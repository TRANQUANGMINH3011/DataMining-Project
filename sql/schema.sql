-- ==============================================================================
-- KHO DỮ LIỆU THƯƠNG MẠI ĐIỆN TỬ ĐA NGUỒN - LƯỢC ĐỒ HÌNH SAO (STAR SCHEMA DDL)
-- Nguồn dữ liệu tích hợp:
--   1. Amazon Reviews 2023 (HuggingFace): Đánh giá, tương tác, parent_asin, reviewerID
--   2. DummyJSON API: Hồ sơ người dùng làm giàu nhân khẩu học (Age, Gender, City, Country)
--   3. Open Food Facts API: Thông tin thành phần dinh dưỡng và xuất xứ sản phẩm (ingredients_text)
-- Tương thích: PostgreSQL 12+ (hỗ trợ chuyển đổi dễ dàng sang MySQL 8+)
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. BẢNG CHIỀU DANH MỤC (Dim_Category)
-- Phân loại ngành hàng, phục vụ phân tích lát cắt (Slice) và cuộn lên (Roll-up)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Dim_Category (
    category_id VARCHAR(100) PRIMARY KEY,
    category_name VARCHAR(255) NOT NULL
);

-- ------------------------------------------------------------------------------
-- 2. BẢNG CHIỀU NGƯỜI DÙNG (Dim_User)
-- Khóa chính user_id từ Amazon ReviewerID, được làm giàu thông tin nhân khẩu
-- học từ DummyJSON API (age, gender, city, country)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Dim_User (
    user_id VARCHAR(100) PRIMARY KEY,       -- Amazon Reviewer ID
    age INT,                                -- Tuổi (làm giàu từ DummyJSON)
    gender VARCHAR(20),                     -- Giới tính: male, female, other
    city VARCHAR(150),                      -- Thành phố cư trú (DummyJSON)
    country VARCHAR(100),                   -- Quốc gia cư trú (DummyJSON)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Thời điểm ghi nhận hồ sơ
    rfm_segment VARCHAR(50) DEFAULT 'Unassigned' -- Phân khúc khách hàng sau phân cụm RFM
);

-- ------------------------------------------------------------------------------
-- 3. BẢNG CHIỀU SẢN PHẨM (Dim_Product)
-- Khóa chính product_id từ Amazon parent_asin, kết hợp giá, mô tả sản phẩm
-- và làm giàu thuộc tính thành phần dinh dưỡng (ingredients_text) từ Open Food Facts API
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Dim_Product (
    product_id VARCHAR(100) PRIMARY KEY,    -- Amazon parent_asin
    product_name TEXT NOT NULL,             -- Tên sản phẩm đầy đủ
    category_id VARCHAR(100),               -- Khóa ngoại liên kết Dim_Category
    price FLOAT DEFAULT 0.0,                -- Giá bán niêm yết (USD)
    brand VARCHAR(255),                     -- Thương hiệu / Nhà sản xuất
    description TEXT,                       -- Mô tả chi tiết sản phẩm
    ingredients_text TEXT,                  -- Thành phần chi tiết (làm giàu từ Open Food Facts API)
    CONSTRAINT fk_product_category 
        FOREIGN KEY (category_id) 
        REFERENCES Dim_Category(category_id) 
        ON DELETE SET NULL 
        ON UPDATE CASCADE
);

-- ------------------------------------------------------------------------------
-- 4. BẢNG CHIỀU THỜI GIAN (Dim_Time)
-- Chiều phân tích thời gian theo chuẩn Kimball, khóa time_id định dạng YYYYMMDDHH
-- Phục vụ phân tích xu hướng MoM/YoY và phân cấp: Giờ -> Ngày -> Tháng -> Quý -> Năm
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Dim_Time (
    time_id BIGINT PRIMARY KEY,             -- Khóa số nguyên dạng YYYYMMDDHH (VD: 2023102614)
    full_timestamp TIMESTAMP NOT NULL,      -- Dấu thời gian chi tiết
    day INT NOT NULL,                       -- Ngày trong tháng (1 - 31)
    month INT NOT NULL,                     -- Tháng trong năm (1 - 12)
    quarter INT NOT NULL,                   -- Quý trong năm (1 - 4)
    year INT NOT NULL,                      -- Năm (VD: 2023, 2024)
    day_of_week VARCHAR(20) NOT NULL        -- Thứ trong tuần (Monday, Tuesday,...)
);

-- ------------------------------------------------------------------------------
-- 5. BẢNG SỰ KIỆN TƯƠNG TÁC (Fact_Interactions)
-- Bảng sự kiện trung tâm (Fact Table) lưu vết tương tác khách hàng - sản phẩm:
-- Đánh giá sao (rating_score 1-5), nội dung nhận xét (review_text), số lượt hữu ích
-- (helpful_vote), và loại sự kiện (event_type: 'review', 'purchase', 'view', 'cart')
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Fact_Interactions (
    interaction_id BIGSERIAL PRIMARY KEY,   -- Khóa chính tự tăng (MySQL: BIGINT AUTO_INCREMENT PRIMARY KEY)
    user_id VARCHAR(100) NOT NULL,          -- Khóa ngoại liên kết Dim_User
    product_id VARCHAR(100) NOT NULL,       -- Khóa ngoại liên kết Dim_Product
    time_id BIGINT NOT NULL,                -- Khóa ngoại liên kết Dim_Time
    rating_score FLOAT,                     -- Điểm đánh giá chất lượng (1.0 - 5.0)
    review_text TEXT,                       -- Nội dung nhận xét của khách hàng
    helpful_vote INT DEFAULT 0,             -- Số lượt bình chọn đánh giá hữu ích
    event_type VARCHAR(50) DEFAULT 'review',-- Loại sự kiện: 'review', 'purchase', 'view', 'cart'
    CONSTRAINT fk_fact_user 
        FOREIGN KEY (user_id) 
        REFERENCES Dim_User(user_id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE,
    CONSTRAINT fk_fact_product 
        FOREIGN KEY (product_id) 
        REFERENCES Dim_Product(product_id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE,
    CONSTRAINT fk_fact_time 
        FOREIGN KEY (time_id) 
        REFERENCES Dim_Time(time_id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE
);

-- ==============================================================================
-- TỐI ƯU HÓA TRUY VẤN OLAP - TẠO CÁC CHỈ MỤC (INDEXES)
-- ==============================================================================

-- 1. Chỉ mục trên các khóa ngoại bảng Fact (Bắt buộc để tăng tốc JOIN với các Dim)
CREATE INDEX IF NOT EXISTS idx_fact_user_id ON Fact_Interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_fact_product_id ON Fact_Interactions(product_id);
CREATE INDEX IF NOT EXISTS idx_fact_time_id ON Fact_Interactions(time_id);

-- 2. Chỉ mục hỗ trợ lọc lát cắt (Slice/Dice) trên loại sự kiện và điểm đánh giá
CREATE INDEX IF NOT EXISTS idx_fact_event_type ON Fact_Interactions(event_type);
CREATE INDEX IF NOT EXISTS idx_fact_rating_score ON Fact_Interactions(rating_score);

-- 3. Chỉ mục liên kết danh mục trên bảng Dim_Product
CREATE INDEX IF NOT EXISTS idx_dim_product_category ON Dim_Product(category_id);

-- 4. Chỉ mục thời gian đa cấp độ trên Dim_Time phục vụ phép cuộn (Roll-up) / khoan sâu (Drill-down)
CREATE INDEX IF NOT EXISTS idx_dim_time_hierarchy ON Dim_Time(year, quarter, month, day);

-- 5. Chỉ mục tổ hợp tối ưu hóa truy vấn phân tích người dùng và sản phẩm trong Recommender/BI
CREATE INDEX IF NOT EXISTS idx_fact_user_product ON Fact_Interactions(user_id, product_id);
CREATE INDEX IF NOT EXISTS idx_fact_product_rating ON Fact_Interactions(product_id, rating_score);
