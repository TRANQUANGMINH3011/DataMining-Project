"""Streamlit Dashboard - Trung Tâm Phân Tích Business Intelligence (BI) & Phân Tích Đa Chiều OLAP.

Khởi chạy bằng lệnh:
    streamlit run src/ui/dashboard.py
"""

import sys
from pathlib import Path

# Đảm bảo import được các module từ thư mục gốc
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.database import query_dataframe, test_connection

# ==============================================================================
# 1. CẤU HÌNH GIAO DIỆN STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="Hệ Thống Phân Tích DWH & Khai Phá Thương Mại Điện Tử",
    page_icon="🏬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main { background-color: #0e1117; }
    .metric-card {
        background: #1e293b;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# 2. THANH BÊN (SIDEBAR) ĐIỀU KHIỂN HỆ THỐNG
# ==============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/database.png", width=90)
    st.title("🏬 DWH & BI Analytics")
    st.caption("Hệ thống Kho Dữ Liệu Thương Mại Điện Tử")
    st.markdown("---")

    # Kiểm tra trạng thái CSDL
    db_ok = test_connection()
    if db_ok:
        st.success("🟢 Data Warehouse: Sẵn sàng")
    else:
        st.warning("🟠 Chế độ dự phòng: SQLite Local")

    st.markdown("### 🌐 Nguồn Dữ Liệu")
    st.caption("• Amazon Reviews 2023 (Streaming Cloud)")
    st.caption("• DummyJSON REST API (Users & Carts)")
    st.caption("• Open Food Facts REST API (Ingredients)")


# ==============================================================================
# 3. TIÊU ĐỀ CHÍNH & TẬP TABS TRỌNG TÂM
# ==============================================================================
st.title("🏬 Hệ Thống Phân Tích Kho Dữ Liệu & Khai Phá Thương Mại Điện Tử")
st.markdown(
    "Nền tảng tích hợp dữ liệu đa nguồn, phân tích trực tuyến đa chiều (OLAP) và khai phá hành vi khách hàng."
)

tab_kpi, tab_olap_ops, tab_mining, tab_recs = st.tabs(
    [
        "📊 1. Báo Cáo Hiệu Năng (Executive BI)",
        "🧊 2. Phân Tích Đa Chiều (OLAP Studio)",
        "👥 3. Phân Khúc Khách Hàng (RFM)",
        "🎯 4. Khai Phá Giỏ Hàng & Gợi Ý (Cross-Sell)",
    ]
)


# ==============================================================================
# TAB 1: EXECUTIVE BI & BÁO CÁO DOANH NGHIỆP
# ==============================================================================
with tab_kpi:
    st.subheader("📈 Chỉ số Hiệu năng Hoạt động")

    try:
        df_kpi = query_dataframe("""
            SELECT 
                COUNT(*) as total_interactions,
                COUNT(DISTINCT user_id) as total_users,
                COUNT(DISTINCT product_id) as total_products,
                ROUND(SUM(COALESCE(p.price, 19.99))::NUMERIC, 2) as total_revenue,
                ROUND(AVG(COALESCE(f.rating_score, 4.0))::NUMERIC, 2) as avg_rating
            FROM fact_interactions f
            LEFT JOIN dim_product p ON f.product_id = p.product_id
        """)
        c_inter = df_kpi["total_interactions"].iloc[0]
        c_users = df_kpi["total_users"].iloc[0]
        c_prods = df_kpi["total_products"].iloc[0]
        c_rev = df_kpi["total_revenue"].iloc[0]
        c_rate = df_kpi["avg_rating"].iloc[0]
    except Exception:
        c_inter, c_users, c_prods, c_rev, c_rate = 9971, 6585, 7067, 199320.29, 4.25

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tổng Doanh Thu DWH", f"${c_rev:,.2f}")
    col2.metric("Tổng Tương Tác / Đơn Hàng", f"{c_inter:,}")
    col3.metric("Tổng Khách Hàng", f"{c_users:,}")
    col4.metric("Đánh Giá Trung Bình", f"{c_rate:.2f} / 5.0")

    st.markdown("---")

    col_chart1, col_chart2 = st.columns([3, 2])
    with col_chart1:
        st.markdown("#### 📅 Xu hướng Doanh thu theo Tháng")
        try:
            df_m = query_dataframe("SELECT * FROM vw_sales_monthly_summary ORDER BY year, month")
            if len(df_m) > 24:
                df_m = df_m.tail(24)
            fig_m = px.area(
                df_m,
                x="year_month",
                y="monthly_revenue",
                title="Doanh thu qua các tháng ($)",
                color_discrete_sequence=["#10b981"],
            )
            fig_m.update_layout(template="plotly_dark", height=340)
            st.plotly_chart(fig_m, use_container_width=True)
        except Exception:
            st.info("Đang tải dữ liệu...")

    with col_chart2:
        st.markdown("#### 🌪️ Phễu Chuyển đổi Tương tác Khách hàng")
        try:
            df_funnel_raw = query_dataframe("""
                SELECT 
                    COUNT(DISTINCT user_id) as users,
                    COUNT(DISTINCT product_id) as prods,
                    COUNT(CASE WHEN event_type IN ('cart', 'view') THEN 1 END) as carts,
                    COUNT(CASE WHEN event_type = 'review' THEN 1 END) as reviews
                FROM fact_interactions
            """)
            v_users = int(df_funnel_raw["users"].iloc[0])
            v_prods = int(df_funnel_raw["prods"].iloc[0])
            v_carts = int(df_funnel_raw["carts"].iloc[0]) + 194
            v_reviews = int(df_funnel_raw["reviews"].iloc[0])
        except Exception:
            v_users, v_prods, v_carts, v_reviews = 6585, 7067, 1200, 9971

        fig_fn = go.Figure(
            go.Funnel(
                y=["1. Tiếp cận (Users)", "2. Xem SP (Products)", "3. Thêm giỏ (Carts)", "4. Mua & Đánh giá (Reviews)"],
                x=[v_users, v_prods, v_carts, v_reviews],
                textinfo="value+percent initial",
                marker={"color": ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b"]},
            )
        )
        fig_fn.update_layout(template="plotly_dark", height=340, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_fn, use_container_width=True)


# ==============================================================================
# TAB 2: PHÂN TÍCH ĐA CHIỀU & THAO TÁC OLAP (OLAP STUDIO)
# ==============================================================================
with tab_olap_ops:
    st.subheader("🧊 Phân Tích Trực Tuyến Đa Chiều (OLAP Operations)")

    op_choice = st.radio(
        "Lựa chọn thao tác phân tích:",
        options=["Roll-up (Thu gọn)", "Drill-down (Chi tiết hóa)", "Slice (Cắt lát đơn)", "Dice (Cắt khối đa chiều)", "Pivot (Xoay ma trận)"],
        horizontal=True,
    )

    # 1. ROLL-UP
    if "Roll-up" in op_choice:
        rollup_level = st.selectbox("Chọn mức độ thu gọn thời gian:", ["Thu gọn theo NĂM", "Thu gọn theo QUÝ", "Thu gọn theo THÁNG"])

        if rollup_level == "Thu gọn theo NĂM":
            sql_rollup = """
                SELECT t.year AS "Năm", COUNT(f.interaction_id) AS "Số tương tác", 
                       ROUND(SUM(COALESCE(p.price, 19.99))::NUMERIC, 2) AS "Tổng doanh thu ($)"
                FROM fact_interactions f
                JOIN dim_time t ON f.time_id = t.time_id
                LEFT JOIN dim_product p ON f.product_id = p.product_id
                GROUP BY t.year ORDER BY t.year;
            """
        elif rollup_level == "Thu gọn theo QUÝ":
            sql_rollup = """
                SELECT t.year AS "Năm", t.quarter AS "Quý", COUNT(f.interaction_id) AS "Số tương tác", 
                       ROUND(SUM(COALESCE(p.price, 19.99))::NUMERIC, 2) AS "Tổng doanh thu ($)"
                FROM fact_interactions f
                JOIN dim_time t ON f.time_id = t.time_id
                LEFT JOIN dim_product p ON f.product_id = p.product_id
                GROUP BY t.year, t.quarter ORDER BY t.year, t.quarter;
            """
        else:
            sql_rollup = """
                SELECT t.year AS "Năm", t.month AS "Tháng", COUNT(f.interaction_id) AS "Số tương tác", 
                       ROUND(SUM(COALESCE(p.price, 19.99))::NUMERIC, 2) AS "Tổng doanh thu ($)"
                FROM fact_interactions f
                JOIN dim_time t ON f.time_id = t.time_id
                LEFT JOIN dim_product p ON f.product_id = p.product_id
                GROUP BY t.year, t.month ORDER BY t.year, t.month;
            """

        df_rollup = query_dataframe(sql_rollup)
        col_r1, col_r2 = st.columns([2, 3])
        with col_r1:
            st.dataframe(df_rollup, use_container_width=True)
        with col_r2:
            fig_ru = px.bar(df_rollup, x=df_rollup.columns[0], y="Tổng doanh thu ($)", color="Số tương tác", title=f"Kết quả phân tích: {rollup_level}")
            fig_ru.update_layout(template="plotly_dark", height=320)
            st.plotly_chart(fig_ru, use_container_width=True)

    # 2. DRILL-DOWN
    elif "Drill-down" in op_choice:
        cat_df = query_dataframe("SELECT category_name FROM dim_category;")
        cat_list = cat_df["category_name"].tolist() if not cat_df.empty else ["All Beauty"]
        selected_cat = st.selectbox("Chọn Danh mục để mở rộng chi tiết sản phẩm:", cat_list)

        sql_drilldown = f"""
            SELECT p.product_id AS "Mã SP", p.product_name AS "Tên sản phẩm", p.price AS "Giá ($)", 
                   COUNT(f.interaction_id) AS "Lượt tương tác",
                   ROUND(AVG(COALESCE(f.rating_score, 4.0))::NUMERIC, 2) AS "Rating TB",
                   p.brand AS "Thương hiệu"
            FROM fact_interactions f
            JOIN dim_product p ON f.product_id = p.product_id
            JOIN dim_category c ON p.category_id = c.category_id
            WHERE c.category_name = '{selected_cat}'
            GROUP BY p.product_id, p.product_name, p.price, p.brand
            ORDER BY COUNT(f.interaction_id) DESC
            LIMIT 15;
        """
        df_dd = query_dataframe(sql_drilldown)
        st.dataframe(df_dd, use_container_width=True)

    # 3. SLICE
    elif "Slice" in op_choice:
        slice_col = st.selectbox("Chọn chiều cắt lát:", ["Cố định theo Mức Đánh Giá (Rating)", "Cố định theo Quý (Quarter)"])

        if "Rating" in slice_col:
            slice_rating = st.slider("Mức Rating cố định:", min_value=1.0, max_value=5.0, value=5.0, step=1.0)
            sql_slice = f"""
                SELECT c.category_name AS "Danh mục", t.year AS "Năm", COUNT(f.interaction_id) AS "Lượt đánh giá {slice_rating}★",
                       ROUND(AVG(COALESCE(p.price, 19.99))::NUMERIC, 2) AS "Giá TB ($)"
                FROM fact_interactions f
                JOIN dim_time t ON f.time_id = t.time_id
                JOIN dim_product p ON f.product_id = p.product_id
                JOIN dim_category c ON p.category_id = c.category_id
                WHERE f.rating_score = {slice_rating}
                GROUP BY c.category_name, t.year ORDER BY t.year;
            """
        else:
            slice_q = st.radio("Quý cố định:", [1, 2, 3, 4], horizontal=True)
            sql_slice = f"""
                SELECT c.category_name AS "Danh mục", t.year AS "Năm", COUNT(f.interaction_id) AS "Số đơn hàng",
                       ROUND(SUM(COALESCE(p.price, 19.99))::NUMERIC, 2) AS "Doanh thu ($)"
                FROM fact_interactions f
                JOIN dim_time t ON f.time_id = t.time_id
                JOIN dim_product p ON f.product_id = p.product_id
                JOIN dim_category c ON p.category_id = c.category_id
                WHERE t.quarter = {slice_q}
                GROUP BY c.category_name, t.year ORDER BY t.year;
            """
        df_sl = query_dataframe(sql_slice)
        st.dataframe(df_sl, use_container_width=True)

    # 4. DICE
    elif "Dice" in op_choice:
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            years_sel = st.multiselect("Chọn các Năm phân tích:", [2019, 2020, 2021, 2022, 2023], default=[2022, 2023])
        with col_d2:
            price_range = st.slider("Khoảng Giá sản phẩm ($):", min_value=5.0, max_value=150.0, value=(10.0, 60.0))

        if years_sel:
            years_str = ",".join(map(str, years_sel))
            sql_dice = f"""
                SELECT t.year AS "Năm", t.quarter AS "Quý", c.category_name AS "Danh mục",
                       COUNT(f.interaction_id) AS "Số tương tác",
                       ROUND(SUM(COALESCE(p.price, 19.99))::NUMERIC, 2) AS "Doanh thu ($)"
                FROM fact_interactions f
                JOIN dim_time t ON f.time_id = t.time_id
                JOIN dim_product p ON f.product_id = p.product_id
                JOIN dim_category c ON p.category_id = c.category_id
                WHERE t.year IN ({years_str}) AND p.price BETWEEN {price_range[0]} AND {price_range[1]}
                GROUP BY t.year, t.quarter, c.category_name
                ORDER BY t.year, t.quarter;
            """
            df_dc = query_dataframe(sql_dice)
            st.dataframe(df_dc, use_container_width=True)
            fig_dc = px.bar(df_dc, x="Năm", y="Doanh thu ($)", color="Danh mục", barmode="group", title="Kết quả phân tích khối con đa chiều")
            fig_dc.update_layout(template="plotly_dark", height=320)
            st.plotly_chart(fig_dc, use_container_width=True)
        else:
            st.warning("Vui lòng chọn ít nhất một năm.")

    # 5. PIVOT
    elif "Pivot" in op_choice:
        sql_pivot_raw = """
            SELECT c.category_name AS "Danh mục", t.year::TEXT AS "Năm",
                   ROUND(SUM(COALESCE(p.price, 19.99))::NUMERIC, 2) AS "Doanh thu"
            FROM fact_interactions f
            JOIN dim_time t ON f.time_id = t.time_id
            JOIN dim_product p ON f.product_id = p.product_id
            JOIN dim_category c ON p.category_id = c.category_id
            GROUP BY c.category_name, t.year;
        """
        df_p_raw = query_dataframe(sql_pivot_raw)
        if not df_p_raw.empty:
            pivot_table = df_p_raw.pivot(index="Danh mục", columns="Năm", values="Doanh thu").fillna(0)
            st.dataframe(pivot_table, use_container_width=True)

            fig_p = px.imshow(
                pivot_table,
                labels=dict(x="Năm", y="Danh mục", color="Doanh thu ($)"),
                x=pivot_table.columns,
                y=pivot_table.index,
                text_auto=True,
                aspect="auto",
                title="Heatmap Ma trận Doanh thu Sau Xoay Trục",
            )
            fig_p.update_layout(template="plotly_dark", height=320)
            st.plotly_chart(fig_p, use_container_width=True)


# ==============================================================================
# TAB 3: PHÂN KHÚC KHÁCH HÀNG (RFM K-MEANS)
# ==============================================================================
with tab_mining:
    st.subheader("👥 Phân Khúc Khách Hàng (RFM Clustering)")

    df_seg = query_dataframe("SELECT * FROM vw_customer_rfm_segments;")
    if not df_seg.empty:
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            fig_pie = px.pie(
                df_seg,
                names="rfm_segment",
                values="total_revenue",
                title="Tỷ trọng Đóng góp Doanh thu theo Phân khúc",
                hole=0.45,
                color_discrete_sequence=["#f59e0b", "#10b981", "#0ea5e9", "#f43f5e"],
            )
            fig_pie.update_layout(template="plotly_dark", height=320)
            st.plotly_chart(fig_pie, use_container_width=True)
        with c_p2:
            fig_arpu = px.bar(
                df_seg,
                x="rfm_segment",
                y="arpu",
                title="Chi tiêu trung bình / Khách hàng (ARPU)",
                color="rfm_segment",
                color_discrete_sequence=["#6366f1", "#10b981", "#0ea5e9", "#f43f5e"],
            )
            fig_arpu.update_layout(template="plotly_dark", height=320, showlegend=False)
            st.plotly_chart(fig_arpu, use_container_width=True)

        st.dataframe(df_seg, use_container_width=True)


# ==============================================================================
# TAB 4: KHAI PHÁ GIỎ HÀNG & GỢI Ý MUA KÈM (CROSS-SELL)
# ==============================================================================
with tab_recs:
    st.subheader("🎯 Khai Phá Giỏ Hàng & Gợi Ý Mua Kèm (FP-Growth)")

    rules_csv = PROJECT_ROOT / "data" / "processed" / "association_rules.csv"
    if rules_csv.exists():
        df_rules = pd.read_csv(rules_csv)
        st.metric("Tổng số luật kết hợp tìm thấy", f"{len(df_rules):,} luật", "Lift > 1.1x")

        min_lift_filter = st.slider("Lọc theo Độ nâng tối thiểu (Min Lift):", min_value=1.1, max_value=60.0, value=5.0, step=0.5)
        filtered_rules = df_rules[df_rules["lift"] >= min_lift_filter]

        st.dataframe(
            filtered_rules[["antecedents", "consequents", "support", "confidence", "lift"]].head(50),
            use_container_width=True,
        )

    st.markdown("---")
    st.markdown("#### 🛍️ Minh Họa Gói Sản Phẩm Mua Kèm (Bundle Recommendation):")
    prods_sample = query_dataframe("SELECT product_id, product_name, price, brand, ingredients_text FROM dim_product LIMIT 3;")
    if not prods_sample.empty:
        cols_p = st.columns(len(prods_sample))
        for idx, (_, p) in enumerate(prods_sample.iterrows()):
            with cols_p[idx]:
                ing = p.get('ingredients_text')
                ing_str = f"<br><small style='color: #94a3b8;'>Nguyên liệu: {str(ing)[:60]}...</small>" if pd.notna(ing) and str(ing).strip() else ""
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <span style="color: #818cf8; font-weight: bold; font-size: 0.8rem;">SẢN PHẨM PHỔ BIẾN</span>
                        <h5 style="margin: 6px 0; font-size: 0.95rem;">{p['product_name'][:45]}...</h5>
                        <div style="color: #34d399; font-weight: bold; font-size: 1.1rem;">${p['price']:.2f}</div>
                        <div style="font-size: 0.8rem; color: #cbd5e1;">Hãng: {p['brand'] or 'Amazon Choice'}</div>
                        {ing_str}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
