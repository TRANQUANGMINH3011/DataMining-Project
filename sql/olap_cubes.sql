-- ==============================================================================
-- KHO DỮ LIỆU THƯƠNG MẠI ĐIỆN TỬ - TÍNH TOÁN CÁC KHỐI ĐA CHIỀU (OLAP CUBES)
-- Đáp ứng yêu cầu chuẩn đầu ra CLO1 của Học phần INT1422 (Bài 12)
-- 1. Khối con 1: Doanh thu theo Danh mục & Thời gian (GROUP BY CUBE)
-- 2. Khối con 2: Khách hàng theo Phân khúc & Địa lý (GROUP BY ROLLUP)
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- KHỐI CON 1: TÍNH TRƯỚC KHỐI DỮ LIỆU DOANH THU (SALES OLAP CUBE)
-- Cú pháp: GROUP BY CUBE(category_name, year, quarter)
-- Lý do chọn: Cho phép nhà quản lý xem doanh thu ở mọi mức độ chi tiết:
--   - Theo từng (Danh mục, Năm, Quý)
--   - Theo từng (Danh mục, Năm)
--   - Theo từng (Danh mục) hoặc (Năm)
--   - Tổng toàn sàn (Grand Total)
-- ------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_cube_sales_category_time AS
SELECT 
    COALESCE(c.category_name, 'TẤT CẢ DANH MỤC') AS category_name,
    COALESCE(t.year::TEXT, 'TẤT CẢ NĂM') AS year,
    COALESCE(t.quarter::TEXT, 'TẤT CẢ QUÝ') AS quarter,
    COUNT(f.interaction_id) AS total_interactions,
    COUNT(DISTINCT f.user_id) AS unique_customers,
    ROUND(SUM(COALESCE(p.price, 19.99))::NUMERIC, 2) AS total_revenue,
    ROUND(AVG(COALESCE(f.rating_score, 4.0))::NUMERIC, 2) AS avg_rating,
    -- Xác định cấp độ phân cấp (Grouping Level)
    GROUPING(c.category_name) AS grouping_category,
    GROUPING(t.year) AS grouping_year,
    GROUPING(t.quarter) AS grouping_quarter
FROM fact_interactions f
JOIN dim_time t ON f.time_id = t.time_id
LEFT JOIN dim_product p ON f.product_id = p.product_id
LEFT JOIN dim_category c ON p.category_id = c.category_id
GROUP BY CUBE(c.category_name, t.year, t.quarter);


-- ------------------------------------------------------------------------------
-- KHỐI CON 2: TÍNH TRƯỚC KHỐI DỮ LIỆU PHÂN KHÚC & ĐỊA LÝ (CUSTOMER ROLLUP CUBE)
-- Cú pháp: GROUP BY ROLLUP(rfm_segment, country, city)
-- Lý do chọn: Phân rã theo cây phân cấp địa lý và phân khúc tiếp thị:
--   - Chi tiết: Phân khúc -> Quốc gia -> Thành phố
--   - Tổng hợp cấp 1: Phân khúc -> Quốc gia
--   - Tổng hợp cấp 2: Phân khúc
--   - Tổng toàn bộ khách hàng
-- ------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_cube_customer_segment_geo AS
SELECT 
    COALESCE(u.rfm_segment, 'TẤT CẢ PHÂN KHÚC') AS rfm_segment,
    COALESCE(u.country, 'TẤT CẢ QUỐC GIA') AS country,
    COALESCE(u.city, 'TẤT CẢ THÀNH PHỐ') AS city,
    COUNT(DISTINCT u.user_id) AS total_customers,
    COUNT(f.interaction_id) AS total_orders,
    ROUND(SUM(COALESCE(p.price, 19.99))::NUMERIC, 2) AS total_spend,
    ROUND((SUM(COALESCE(p.price, 19.99)) / NULLIF(COUNT(DISTINCT u.user_id), 0))::NUMERIC, 2) AS arpu,
    GROUPING(u.rfm_segment) AS grouping_segment,
    GROUPING(u.country) AS grouping_country,
    GROUPING(u.city) AS grouping_city
FROM dim_user u
LEFT JOIN fact_interactions f ON u.user_id = f.user_id
LEFT JOIN dim_product p ON f.product_id = p.product_id
GROUP BY ROLLUP(u.rfm_segment, u.country, u.city);
