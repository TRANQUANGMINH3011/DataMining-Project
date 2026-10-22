-- ==============================================================================
-- KHO DỮ LIỆU THƯƠNG MẠI ĐIỆN TỬ - STAR SCHEMA (DATA WAREHOUSE DDL)
-- Hệ thống gợi ý sản phẩm cá nhân hóa
-- ==============================================================================

-- 1. BẢNG CHIỀU DANH MỤC (Dim_Category)
CREATE TABLE IF NOT EXISTS Dim_Category (
    category_id VARCHAR(100) PRIMARY KEY,
    category_name VARCHAR(255) NOT NULL
);

-- 2. BẢNG CHIỀU NGƯỜI DÙNG (Dim_User)
CREATE TABLE IF NOT EXISTS Dim_User (
    user_id VARCHAR(100) PRIMARY KEY,
    age INT,
    gender VARCHAR(20),
    location VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rfm_segment VARCHAR(50) DEFAULT 'Unassigned'
);

-- 3. BẢNG CHIỀU SẢN PHẨM (Dim_Product)
CREATE TABLE IF NOT EXISTS Dim_Product (
    product_id VARCHAR(100) PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category_id VARCHAR(100),
    price NUMERIC(12, 2) DEFAULT 0.00,
    brand VARCHAR(100),
    description TEXT,
    CONSTRAINT fk_product_category 
        FOREIGN KEY (category_id) 
        REFERENCES Dim_Category(category_id) 
        ON DELETE SET NULL
);

-- 4. BẢNG CHIỀU THỜI GIAN (Dim_Time)
CREATE TABLE IF NOT EXISTS Dim_Time (
    time_id BIGINT PRIMARY KEY,
    full_timestamp TIMESTAMP NOT NULL,
    day INT NOT NULL,
    month INT NOT NULL,
    quarter INT NOT NULL,
    year INT NOT NULL,
    day_of_week INT NOT NULL
);

-- 5. BẢNG SỰ KIỆN TƯƠNG TÁC & GIAO DỊCH (Fact_Interactions)
CREATE TABLE IF NOT EXISTS Fact_Interactions (
    interaction_id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    product_id VARCHAR(100) NOT NULL,
    time_id BIGINT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    rating_value NUMERIC(3, 2),
    quantity INT DEFAULT 1,
    total_amount NUMERIC(12, 2) DEFAULT 0.00,
    CONSTRAINT fk_fact_user 
        FOREIGN KEY (user_id) 
        REFERENCES Dim_User(user_id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_fact_product 
        FOREIGN KEY (product_id) 
        REFERENCES Dim_Product(product_id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_fact_time 
        FOREIGN KEY (time_id) 
        REFERENCES Dim_Time(time_id) 
        ON DELETE CASCADE
);

-- ==============================================================================
-- TỐI ƯU HÓA TRUY VẤN OLAP - TẠO CÁC CHỈ MỤC (INDEXES)
-- ==============================================================================

-- Chỉ mục trên các cột khóa ngoại trong Fact_Interactions
CREATE INDEX IF NOT EXISTS idx_fact_user_id ON Fact_Interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_fact_product_id ON Fact_Interactions(product_id);
CREATE INDEX IF NOT EXISTS idx_fact_time_id ON Fact_Interactions(time_id);

-- Chỉ mục trên loại tương tác (event_type: view, cart, purchase, rating)
CREATE INDEX IF NOT EXISTS idx_fact_event_type ON Fact_Interactions(event_type);

-- Chỉ mục liên kết danh mục trên Dim_Product
CREATE INDEX IF NOT EXISTS idx_dim_product_category ON Dim_Product(category_id);

-- Chỉ mục thời gian trên Dim_Time phục vụ lọc Roll-up/Drill-down
CREATE INDEX IF NOT EXISTS idx_dim_time_ymd ON Dim_Time(year, month, day);

-- Chỉ mục tổ hợp hỗ trợ nhanh cho Recommender System & Phân tích tương tác
CREATE INDEX IF NOT EXISTS idx_fact_user_event ON Fact_Interactions(user_id, event_type);
CREATE INDEX IF NOT EXISTS idx_fact_product_event ON Fact_Interactions(product_id, event_type);
