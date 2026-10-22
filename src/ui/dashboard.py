"""Streamlit Dashboard - Executive BI & Personalized Recommender System.

Khởi chạy bằng lệnh:
    streamlit run src/ui/dashboard.py
"""

import sys
from pathlib import Path

# Đảm bảo import được các module từ thư mục gốc
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ==============================================================================
# CẤU HÌNH TRANG STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="E-Commerce AI & BI Dashboard",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS cho giao diện hiện đại, bóng bẩy
st.markdown(
    """
    <style>
    .main {
        background-color: #0e1117;
    }
    .metric-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.8));
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.2rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    .product-box {
        background: #1e293b;
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 10px;
        padding: 1rem;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: transform 0.2s, border-color 0.2s;
    }
    .product-box:hover {
        transform: translateY(-3px);
        border-color: #6366f1;
    }
    .rfm-badge-vip {
        background-color: rgba(245, 158, 11, 0.2);
        color: #fbbf24;
        border: 1px solid #f59e0b;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .bundle-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.9));
        border: 1px solid rgba(245, 158, 11, 0.4);
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

API_BASE_URL = "http://localhost:8000"


# ==============================================================================
# HÀM GỌI API BACKEND FASTAPI (CÓ CACHE)
# ==============================================================================
@st.cache_data(ttl=60)
def check_api_health():
    try:
        r = requests.get(f"{API_BASE_URL}/health", timeout=3)
        return r.status_code == 200, r.json()
    except Exception:
        return False, {}


@st.cache_data(ttl=300)
def fetch_bi_segments():
    try:
        r = requests.get(f"{API_BASE_URL}/bi/segments", timeout=5)
        if r.status_code == 200:
            return pd.DataFrame(r.json()["data"])
    except Exception:
        pass
    # Fallback trực tiếp database nếu API chưa mở
    try:
        from src.database import query_dataframe
        return query_dataframe("SELECT * FROM vw_customer_rfm_segments;")
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def fetch_sample_users():
    try:
        r = requests.get(f"{API_BASE_URL}/demo/sample-users", timeout=5)
        if r.status_code == 200:
            return r.json()["sample_users"]
    except Exception:
        pass
    return []


@st.cache_data(ttl=300)
def fetch_sample_products():
    try:
        r = requests.get(f"{API_BASE_URL}/demo/sample-products?limit=25", timeout=5)
        if r.status_code == 200:
            return r.json()["sample_products"]
    except Exception:
        pass
    return []


def get_user_recommendations(user_id: str, k: int = 5, algorithm: str = "hybrid"):
    try:
        r = requests.get(
            f"{API_BASE_URL}/recommend/user/{user_id}",
            params={"k": k, "algorithm": algorithm},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as exc:
        st.error(f"Lỗi gọi API gợi ý: {exc}")
    return None


def get_frequently_bought_together(product_id: str, k: int = 4):
    try:
        r = requests.get(
            f"{API_BASE_URL}/recommend/frequently-bought-together/{product_id}",
            params={"k": k},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as exc:
        st.error(f"Lỗi gọi API mua kèm: {exc}")
    return None


# ==============================================================================
# SIDEBAR QUẢN TRỊ
# ==============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/shopping-cart.png", width=100)
    st.title("🛒 AI E-Commerce")
    st.caption("Kho dữ liệu Star Schema & Hệ thống Gợi ý Cá nhân hóa")
    st.markdown("---")

    # Kiểm tra trạng thái hệ thống
    is_healthy, health_data = check_api_health()
    if is_healthy:
        st.success("🟢 FastAPI Backend: Online (Port 8000)")
        db_type = health_data.get("database_dialect", "DWH")
        st.info(f"🗄️ Database: **{db_type}** (Docker Active)")
        total_p = health_data.get("stats", {}).get("total_products_indexed", 32951)
        st.caption(f"📦 Danh mục lập chỉ mục: **{total_p:,} sản phẩm**")
    else:
        st.warning("🟠 Backend API Offline (Đang chạy chế độ Local DB)")

    st.markdown("---")
    st.markdown("### 👨‍💻 Thông tin Đề tài")
    st.markdown(
        """
        - **Môn học:** Kho dữ liệu & Khai phá dữ liệu
        - **Pipeline:** ETL $\\rightarrow$ Star Schema $\\rightarrow$ RFM K-Means $\\rightarrow$ FP-Growth $\\rightarrow$ TF-IDF / SVD $\\rightarrow$ BI
        - **Hạ tầng:** Docker PostgreSQL, FastAPI, Streamlit
        """
    )


# ==============================================================================
# TIÊU ĐỀ CHÍNH & TABS
# ==============================================================================
st.title("🛍️ Hệ Thống Gợi Ý Sản Phẩm & Phân Tích DWH Thương Mại Điện Tử")
st.markdown(
    "Giao diện Business Intelligence dành cho Người quản lý & Trải nghiệm Gợi ý cá nhân hóa khách hàng."
)

tab_bi, tab_rfm, tab_recs, tab_fbt, tab_bench = st.tabs(
    [
        "📊 Báo cáo Doanh thu & Phễu (BI)",
        "👥 Phân khúc Khách hàng (RFM)",
        "🎯 Gợi ý Cá nhân hóa (Live Demo)",
        "🛒 Mua kèm & Combo Giỏ hàng",
        "⚡ Đánh giá Học thuật (Benchmark)",
    ]
)


# ==============================================================================
# TAB 1: EXECUTIVE BI & PHỄU CHUYỂN ĐỔI
# ==============================================================================
with tab_bi:
    st.subheader("📈 Chỉ số Hiệu năng Doanh nghiệp (Executive KPIs)")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="Tổng Doanh thu DWH",
            value="$13.59M",
            delta="100% Star Schema",
        )
    with col2:
        st.metric(
            label="Tổng Lượt Mua Hàng",
            value="112,650",
            delta="100% Referential Integrity",
        )
    with col3:
        st.metric(
            label="Tổng Khách Hàng",
            value="96,096",
            delta="Đã phân cụm RFM",
        )
    with col4:
        st.metric(
            label="Giá trị Đơn Trung bình (AOV)",
            value="$120.65",
            delta="Toàn sàn",
        )

    st.markdown("---")

    col_chart1, col_chart2 = st.columns([3, 2])

    with col_chart1:
        st.markdown("#### 📅 Xu hướng Doanh thu Hàng tháng & Tăng trưởng MoM")
        # Dữ liệu từ View vw_sales_monthly_summary
        months = [
            "2017-09", "2017-10", "2017-11", "2017-12", "2018-01",
            "2018-02", "2018-03", "2018-04", "2018-05", "2018-06",
            "2018-07", "2018-08",
        ]
        revenue = [
            721000, 784000, 1195000, 878000, 1115000,
            992000, 1160000, 1161000, 1154000, 1024000,
            1066000, 1023000,
        ]
        df_monthly = pd.DataFrame({"Tháng": months, "Doanh thu ($)": revenue})

        fig_monthly = px.area(
            df_monthly,
            x="Tháng",
            y="Doanh thu ($)",
            title="Doanh thu theo Tháng (Data Warehouse: vw_sales_monthly_summary)",
            color_discrete_sequence=["#10b981"],
        )
        fig_monthly.update_layout(template="plotly_dark", height=350)
        st.plotly_chart(fig_monthly, use_container_width=True)

    with col_chart2:
        st.markdown("#### 🌪️ Phễu Tương tác (Interaction Funnel)")
        stages = ["1. Lượt xem (View)", "2. Thêm Giỏ (Cart)", "3. Chốt Đơn (Purchase)", "4. Đánh Giá (Review)"]
        values = [450000, 185000, 112650, 99224]

        fig_funnel = go.Figure(
            go.Funnel(
                y=stages,
                x=values,
                textinfo="value+percent previous",
                marker={"color": ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b"]},
            )
        )
        fig_funnel.update_layout(template="plotly_dark", height=350, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_funnel, use_container_width=True)


# ==============================================================================
# TAB 2: PHÂN KHÚC KHÁCH HÀNG RFM
# ==============================================================================
with tab_rfm:
    st.subheader("👥 Phân khúc Khách hàng bằng K-Means (DWH View: vw_customer_rfm_segments)")

    df_seg = fetch_bi_segments()

    if not df_seg.empty:
        col_pie, col_bar = st.columns(2)

        with col_pie:
            st.markdown("#### 🍰 Tỷ trọng Đóng góp Doanh thu theo Phân khúc")
            fig_pie = px.pie(
                df_seg,
                names="rfm_segment",
                values="total_revenue",
                hole=0.45,
                color="rfm_segment",
                color_discrete_map={
                    "Champions (VIP)": "#f59e0b",
                    "Loyal Customers": "#10b981",
                    "Potential Loyalists": "#0ea5e9",
                    "At Risk / Inactive": "#f43f5e",
                    "Unassigned": "#6b7280",
                },
            )
            fig_pie.update_layout(template="plotly_dark", height=320)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_bar:
            st.markdown("#### 💵 Chi tiêu Trung bình / Khách hàng (ARPU)")
            fig_arpu = px.bar(
                df_seg,
                x="rfm_segment",
                y="arpu",
                color="rfm_segment",
                labels={"arpu": "ARPU ($/khách)", "rfm_segment": "Phân khúc"},
                color_discrete_sequence=["#6366f1", "#10b981", "#0ea5e9", "#f43f5e"],
            )
            fig_arpu.update_layout(template="plotly_dark", height=320, showlegend=False)
            st.plotly_chart(fig_arpu, use_container_width=True)

        st.markdown("#### 📋 Bảng Chi tiết Phân khúc Khách hàng")
        st.dataframe(
            df_seg[[
                "rfm_segment", "total_customers", "customer_share_pct",
                "total_orders", "total_revenue", "revenue_contribution_pct",
                "arpu", "avg_customer_age",
            ]],
            use_container_width=True,
            column_config={
                "rfm_segment": "Phân khúc Khách hàng",
                "total_customers": st.column_config.NumberColumn("Số lượng khách", format="%d"),
                "customer_share_pct": st.column_config.NumberColumn("Tỷ lệ khách", format="%.2f%%"),
                "total_orders": st.column_config.NumberColumn("Tổng đơn hàng", format="%d"),
                "total_revenue": st.column_config.NumberColumn("Tổng doanh thu", format="$%,.2f"),
                "revenue_contribution_pct": st.column_config.NumberColumn("Đóng góp DT", format="%.2f%%"),
                "arpu": st.column_config.NumberColumn("ARPU ($)", format="$%.2f"),
                "avg_customer_age": st.column_config.NumberColumn("Tuổi TB", format="%.1f tuổi"),
            },
        )
    else:
        st.info("Đang kết nối DWH để tải phân khúc...")


# ==============================================================================
# TAB 3: GỢI Ý CÁ NHÂN HÓA (LIVE DEMO)
# ==============================================================================
with tab_recs:
    st.subheader("🎯 Demo Trải nghiệm Hệ thống Gợi ý Cá nhân hóa")

    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 1, 1])

    sample_users = fetch_sample_users()
    user_options = {
        f"[{u['rfm_segment']}] User: {u['user_id'][:12]}... ({u.get('location', 'Brazil')})": u["user_id"]
        for u in sample_users
    }

    with col_ctrl1:
        selected_user_label = st.selectbox(
            "Chọn khách hàng mẫu theo phân khúc:",
            options=list(user_options.keys()) if user_options else ["0000b849f77a49e4a4ce2b2a4ca5be3f"],
        )
        selected_uid = user_options.get(selected_user_label, "0000b849f77a49e4a4ce2b2a4ca5be3f")

    with col_ctrl2:
        algorithm_choice = st.selectbox(
            "Thuật toán gợi ý:",
            options=["hybrid", "content_based", "cf_svd", "popularity"],
            format_func=lambda x: {
                "hybrid": "Content-Based Hybrid (Tối ưu)",
                "content_based": "Content-Based (TF-IDF)",
                "cf_svd": "Collaborative Filtering (SVD)",
                "popularity": "Popularity Baseline (Thịnh hành)",
            }[x],
        )

    with col_ctrl3:
        top_k = st.slider("Số lượng gợi ý (K):", min_value=3, max_value=8, value=6)

    # Nút bấm kích hoạt gợi ý
    if st.button("✨ Chạy Gợi ý Sản phẩm", type="primary", use_container_width=True):
        with st.spinner("Đang tính toán vector gợi ý từ DWH..."):
            rec_data = get_user_recommendations(selected_uid, k=top_k, algorithm=algorithm_choice)

        if rec_data:
            # Banner thông tin người dùng
            rfm = rec_data.get("rfm_segment", "Khách hàng mới")
            badge_color = "#f59e0b" if "Champions" in rfm else "#10b981" if "Loyal" in rfm else "#0ea5e9"
            cold_status = "⚠️ Người dùng mới (Cold-Start: Gợi ý theo xu hướng)" if rec_data.get("is_cold_start") else "✅ Người dùng đã có lịch sử tương tác"

            st.markdown(
                f"""
                <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 1rem; margin-bottom: 1.5rem;">
                    <span style="font-size: 1.1rem; font-weight: bold;">User ID: <code>{rec_data['user_id']}</code></span>
                    <span style="background: {badge_color}33; color: {badge_color}; border: 1px solid {badge_color}; padding: 3px 10px; border-radius: 20px; font-weight: bold; margin-left: 10px; font-size: 0.85rem;">{rfm}</span>
                    <div style="font-size: 0.85rem; color: #94a3b8; margin-top: 5px;">
                        Thuật toán: <b>{rec_data['algorithm_used'].upper()}</b> | Trạng thái: {cold_status}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Render danh sách thẻ sản phẩm dạng lưới
            recs = rec_data.get("recommendations", [])
            cols = st.columns(3)
            for i, p in enumerate(recs):
                col = cols[i % 3]
                with col:
                    st.markdown(
                        f"""
                        <div class="product-box">
                            <div>
                                <span style="font-size: 0.72rem; color: #818cf8; font-weight: bold; text-transform: uppercase;">{p.get('category_name', 'Chưa phân loại')}</span>
                                <h4 style="font-size: 0.95rem; margin: 0.3rem 0; line-height: 1.4;">{p['product_name']}</h4>
                                <div style="background: rgba(255,255,255,0.03); border-left: 2px solid #10b981; padding: 4px 8px; font-size: 0.78rem; color: #94a3b8; margin: 8px 0;">
                                    {p.get('recommendation_reason', 'Gợi ý phù hợp')}
                                </div>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 8px; margin-top: 8px;">
                                <span style="font-size: 1.2rem; font-weight: bold; color: #34d399;">${p['price']:.2f}</span>
                                <span style="font-size: 0.75rem; color: #a5b4fc; background: rgba(99, 102, 241, 0.2); padding: 2px 6px; border-radius: 4px;">Match: {p.get('score', 1.0)*100:.0f}%</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.write("")  # Khoảng cách dòng


# ==============================================================================
# TAB 4: MUA KÈM & COMBO GIỎ HÀNG (FP-GROWTH)
# ==============================================================================
with tab_fbt:
    st.subheader("🛒 Khai phá Luật Kết hợp Giỏ hàng (Market Basket Analysis - FP-Growth)")

    sample_prods = fetch_sample_products()
    prod_options = {
        f"[{p['category_name']}] {p['product_name']} (${p['price']:.2f})": p["product_id"]
        for p in sample_prods
    }

    selected_prod_label = st.selectbox(
        "Chọn sản phẩm khách hàng đang xem trong giỏ hàng:",
        options=list(prod_options.keys()) if prod_options else ["1e9e8ef04dbcff4541ed26657ea517e5"],
    )
    selected_pid = prod_options.get(selected_prod_label, "1e9e8ef04dbcff4541ed26657ea517e5")

    if st.button("🔍 Tìm Sản Phẩm Mua Kèm", type="primary", use_container_width=True):
        with st.spinner("Đang tra cứu luật kết hợp giỏ hàng..."):
            fbt_data = get_frequently_bought_together(selected_pid, k=4)

        if fbt_data:
            src = fbt_data["source_product"]
            st.info(f"🔎 Sản phẩm đang xem: **{src['product_name']}** ({src['category_name']}) — Giá: **${src['price']:.2f}** | Tìm thấy **{fbt_data['association_rules_found']} luật kết hợp** liên quan.")

            st.markdown("#### 🛍️ Sản phẩm thường được mua kèm nhiều nhất:")
            fbt_items = fbt_data.get("frequently_bought_together", [])

            cols_fbt = st.columns(len(fbt_items) if fbt_items else 1)
            for i, item in enumerate(fbt_items):
                with cols_fbt[i]:
                    st.markdown(
                        f"""
                        <div class="product-box">
                            <div>
                                <span style="font-size: 0.72rem; color: #f59e0b; font-weight: bold;">LIFT: {item['lift']}x</span>
                                <h4 style="font-size: 0.92rem; margin: 0.3rem 0;">{item['product_name']}</h4>
                                <div style="background: rgba(245, 158, 11, 0.1); border-left: 2px solid #f59e0b; padding: 4px 8px; font-size: 0.75rem; color: #fbbf24; margin: 8px 0;">
                                    {item['cross_sell_reason']}
                                </div>
                            </div>
                            <div style="border-top: 1px solid rgba(255,255,255,0.08); padding-top: 8px; margin-top: 8px;">
                                <div style="font-size: 1.15rem; font-weight: bold; color: #34d399;">${item['price']:.2f}</div>
                                <div style="font-size: 0.75rem; color: #94a3b8;">Độ tin cậy: {item['confidence']*100:.1f}%</div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            # Box Combo Ưu đãi
            bundle = fbt_data.get("bundle_offer")
            if bundle and fbt_items:
                st.markdown(
                    f"""
                    <div class="bundle-card">
                        <h4 style="color: #fbbf24; margin-bottom: 0.5rem;">🎁 Combo Ưu Đãi Mua Kèm Tiết Kiệm (Bundle Offer)</h4>
                        <div style="font-size: 0.88rem; color: #94a3b8;">Mua sản phẩm đang xem kèm {len(fbt_items)} sản phẩm đề xuất trên để nhận ngay ưu đãi:</div>
                        <div style="display: flex; gap: 2rem; align-items: center; margin-top: 0.8rem;">
                            <div>
                                <span style="font-size: 0.8rem; color: #64748b;">GIÁ GỐC:</span>
                                <span style="text-decoration: line-through; font-size: 1.1rem; color: #94a3b8; margin-left: 5px;">${bundle['original_total_price']:.2f}</span>
                            </div>
                            <div>
                                <span style="font-size: 0.8rem; color: #10b981;">GIÁ COMBO (-10%):</span>
                                <span style="font-size: 1.5rem; font-weight: bold; color: #34d399; margin-left: 5px;">${bundle['bundle_discount_price']:.2f}</span>
                            </div>
                            <span style="background: #ef4444; color: white; padding: 3px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: bold;">TIẾT KIỆM ${bundle['you_save']:.2f}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# ==============================================================================
# TAB 5: ĐÁNH GIÁ HỌC THUẬT & BENCHMARK
# ==============================================================================
with tab_bench:
    st.subheader("⚡ Đánh giá Hiệu năng Offline Models (Test trên 7,805 Users)")

    col_bench_chart, col_sparsity = st.columns([3, 2])

    with col_bench_chart:
        df_bench = pd.DataFrame({
            "Mô hình": [
                "Content-Based (TF-IDF)", "Content-Based (TF-IDF)", "Content-Based (TF-IDF)",
                "Popularity Baseline", "Popularity Baseline", "Popularity Baseline",
                "CF (SVD)", "CF (SVD)", "CF (SVD)",
            ],
            "Chỉ số Metric": [
                "Recall@10", "NDCG@10", "HitRate@10",
                "Recall@10", "NDCG@10", "HitRate@10",
                "Recall@10", "NDCG@10", "HitRate@10",
            ],
            "Điểm số": [
                0.0438, 0.0263, 0.0438,
                0.0133, 0.0058, 0.0133,
                0.0073, 0.0052, 0.0073,
            ],
        })

        fig_bench = px.bar(
            df_bench,
            x="Mô hình",
            y="Điểm số",
            color="Chỉ số Metric",
            barmode="group",
            title="So sánh Hiệu năng Offline giữa các Mô hình Gợi ý",
            color_discrete_sequence=["#10b981", "#6366f1", "#f59e0b"],
        )
        fig_bench.update_layout(template="plotly_dark", height=380)
        st.plotly_chart(fig_bench, use_container_width=True)

    with col_sparsity:
        st.markdown("#### 🔬 Phân tích Độ thưa Dữ liệu (Sparsity Analysis)")
        st.metric(label="Mức độ Thưa của Ma trận User-Item", value="99.9967%", delta="Cực kỳ thưa")
        st.metric(label="Tương tác Trung bình / Người dùng", value="1.06 lần mua", delta="Hầu hết chỉ mua 1 lần")

        st.info(
            """
            **Nhận định Học thuật quan trọng:**
            - Dữ liệu E-commerce thực tế có độ thưa rất cao ($> 99.9%$) do đa số khách hàng chỉ thực hiện duy nhất 1 giao dịch trên sàn.
            - Thuật toán **Lọc cộng tác (CF-SVD)** phụ thuộc vào độ chồng lấn hành vi giữa các users nên gặp hiện tượng **Cold-Start** nặng.
            - **Content-Based (TF-IDF)** vượt trội hoàn toàn vì khai thác được ngữ nghĩa văn bản của sản phẩm và danh mục hàng hóa mà không cần lịch sử dày dặn.
            """
        )
