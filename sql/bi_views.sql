-- ==============================================================================
-- KHO DỮ LIỆU THƯƠNG MẠI ĐIỆN TỬ - CÁC VIEW PHÂN TÍCH BUSINESS INTELLIGENCE (BI)
-- Hỗ trợ Star Schema đa nguồn (Amazon Reviews + DummyJSON + Open Food Facts)
-- Phục vụ trực quan hóa trên Streamlit / Metabase / PowerBI / Superset
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- VIEW 1: HIỆU SUẤT TƯƠNG TÁC & DOANH THU THEO NGÀY / THÁNG / DANH MỤC
-- Cho phép phân tích xu hướng theo thời gian và cơ cấu ngành hàng
-- ------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_sales_performance_daily_category AS
SELECT 
    t.full_timestamp::DATE AS interaction_date,
    t.year,
    t.quarter,
    t.month,
    t.day,
    t.day_of_week,
    COALESCE(c.category_id, 'unknown') AS category_id,
    COALESCE(c.category_name, 'Chưa phân loại') AS category_name,
    COUNT(DISTINCT f.interaction_id) AS total_transactions,
    COUNT(DISTINCT f.user_id) AS unique_customers,
    ROUND(SUM(COALESCE(p.price, 19.99))::NUMERIC, 2) AS total_revenue,
    ROUND(AVG(COALESCE(f.rating_score, 4.0))::NUMERIC, 2) AS avg_rating,
    ROUND((SUM(COALESCE(p.price, 19.99)) / NULLIF(COUNT(DISTINCT f.interaction_id), 0))::NUMERIC, 2) AS avg_order_value
FROM fact_interactions f
JOIN dim_time t ON f.time_id = t.time_id
LEFT JOIN dim_product p ON f.product_id = p.product_id
LEFT JOIN dim_category c ON p.category_id = c.category_id
GROUP BY 
    t.full_timestamp::DATE,
    t.year,
    t.quarter,
    t.month,
    t.day,
    t.day_of_week,
    c.category_id,
    c.category_name;


-- ------------------------------------------------------------------------------
-- VIEW 2: TỔNG HỢP HIỆU SUẤT THEO THÁNG & TĂNG TRƯỞNG (MoM GROWTH)
-- Cung cấp KPI cấp điều hành: Doanh thu tháng, AOV, và tỷ lệ tăng trưởng MoM
-- ------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_sales_monthly_summary AS
WITH monthly_data AS (
    SELECT 
        t.year,
        t.month,
        TO_CHAR(t.full_timestamp, 'YYYY-MM') AS year_month,
        COUNT(DISTINCT f.interaction_id) AS monthly_orders,
        COUNT(DISTINCT f.user_id) AS monthly_active_buyers,
        ROUND(SUM(COALESCE(p.price, 19.99))::NUMERIC, 2) AS monthly_revenue,
        ROUND(AVG(COALESCE(f.rating_score, 4.0))::NUMERIC, 2) AS avg_rating
    FROM fact_interactions f
    JOIN dim_time t ON f.time_id = t.time_id
    LEFT JOIN dim_product p ON f.product_id = p.product_id
    GROUP BY t.year, t.month, TO_CHAR(t.full_timestamp, 'YYYY-MM')
)
SELECT 
    year,
    month,
    year_month,
    monthly_orders,
    monthly_active_buyers,
    monthly_revenue,
    avg_rating,
    ROUND((monthly_revenue / NULLIF(monthly_orders, 0))::NUMERIC, 2) AS avg_order_value,
    ROUND((
        (monthly_revenue - LAG(monthly_revenue, 1) OVER (ORDER BY year, month))
        / NULLIF(LAG(monthly_revenue, 1) OVER (ORDER BY year, month), 0) * 100
    )::NUMERIC, 2) AS mom_revenue_growth_pct
FROM monthly_data
ORDER BY year, month;


-- ------------------------------------------------------------------------------
-- VIEW 3: PHỄU TƯƠNG TÁC (INTERACTION FUNNEL) & ĐÁNH GIÁ TRUNG BÌNH THEO SẢN PHẨM
-- ------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_interaction_funnel AS
SELECT 
    COALESCE(c.category_name, 'Chưa phân loại') AS category_name,
    p.product_id,
    p.product_name,
    COUNT(CASE WHEN f.event_type = 'view' THEN 1 END) AS total_views,
    COUNT(CASE WHEN f.event_type = 'cart' THEN 1 END) AS total_carts,
    COUNT(CASE WHEN f.event_type = 'purchase' THEN 1 END) AS total_purchases,
    COUNT(CASE WHEN f.event_type = 'review' THEN 1 END) AS total_reviews,
    ROUND(AVG(COALESCE(f.rating_score, 4.0))::NUMERIC, 2) AS avg_rating,
    ROUND(SUM(COALESCE(f.helpful_vote, 0))::NUMERIC, 0) AS total_helpful_votes
FROM fact_interactions f
JOIN dim_product p ON f.product_id = p.product_id
LEFT JOIN dim_category c ON p.category_id = c.category_id
GROUP BY c.category_name, p.product_id, p.product_name;


-- ------------------------------------------------------------------------------
-- VIEW 4: PHÂN TÍCH PHÂN KHÚC KHÁCH HÀNG TỪ KẾT QUẢ K-MEANS RFM
-- Phục vụ Pie chart, Scatter plot RFM và phân bổ nhân khẩu học
-- ------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_customer_rfm_segments AS
WITH user_aggregates AS (
    SELECT 
        u.user_id,
        COALESCE(u.rfm_segment, 'Chưa phân cụm') AS rfm_segment,
        COALESCE(u.city, 'Unknown') AS city,
        COALESCE(u.country, 'Unknown') AS country,
        u.age,
        u.gender,
        COUNT(DISTINCT f.interaction_id) AS order_count,
        SUM(COALESCE(p.price, 19.99)) AS total_spend,
        MAX(t.full_timestamp) AS last_order_timestamp
    FROM dim_user u
    LEFT JOIN fact_interactions f ON u.user_id = f.user_id
    LEFT JOIN dim_product p ON f.product_id = p.product_id
    LEFT JOIN dim_time t ON f.time_id = t.time_id
    GROUP BY u.user_id, u.rfm_segment, u.city, u.country, u.age, u.gender
),
total_revenue_overall AS (
    SELECT SUM(total_spend) AS grand_total FROM user_aggregates
)
SELECT 
    ua.rfm_segment,
    COUNT(ua.user_id) AS total_customers,
    ROUND((COUNT(ua.user_id)::NUMERIC / NULLIF((SELECT COUNT(*) FROM user_aggregates), 0) * 100)::NUMERIC, 2) AS customer_share_pct,
    SUM(ua.order_count) AS total_orders,
    ROUND(SUM(ua.total_spend)::NUMERIC, 2) AS total_revenue,
    ROUND((SUM(ua.total_spend) / NULLIF((SELECT grand_total FROM total_revenue_overall), 0) * 100)::NUMERIC, 2) AS revenue_contribution_pct,
    ROUND((SUM(ua.total_spend) / NULLIF(COUNT(ua.user_id), 0))::NUMERIC, 2) AS arpu,
    ROUND((SUM(ua.order_count)::NUMERIC / NULLIF(COUNT(ua.user_id), 0))::NUMERIC, 2) AS avg_orders_per_customer,
    ROUND(AVG(ua.age)::NUMERIC, 1) AS avg_customer_age
FROM user_aggregates ua
GROUP BY ua.rfm_segment
ORDER BY total_revenue DESC;


-- ------------------------------------------------------------------------------
-- VIEW 5: TOP SẢN PHẨM TƯƠNG TÁC CAO NHẤT VÀ DOANH THU CAO NHẤT (PARETO 80/20)
-- ------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_top_products_performance AS
SELECT 
    p.product_id,
    p.product_name,
    COALESCE(c.category_name, 'Chưa phân loại') AS category_name,
    p.price,
    p.brand,
    p.ingredients_text,
    COUNT(DISTINCT f.interaction_id) AS total_purchases,
    ROUND(SUM(COALESCE(p.price, 19.99))::NUMERIC, 2) AS total_revenue,
    ROUND(AVG(COALESCE(f.rating_score, 4.0))::NUMERIC, 2) AS avg_rating,
    SUM(COALESCE(f.helpful_vote, 0)) AS total_helpful_votes,
    DENSE_RANK() OVER (ORDER BY SUM(COALESCE(p.price, 19.99)) DESC) AS revenue_rank,
    DENSE_RANK() OVER (ORDER BY COUNT(DISTINCT f.interaction_id) DESC) AS volume_rank
FROM fact_interactions f
JOIN dim_product p ON f.product_id = p.product_id
LEFT JOIN dim_category c ON p.category_id = c.category_id
GROUP BY p.product_id, p.product_name, c.category_name, p.price, p.brand, p.ingredients_text;
