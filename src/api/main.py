"""FastAPI Application phục vụ Demo Hệ thống Gợi ý & Tích hợp BI.

Các endpoint chính:
  1. GET /recommend/user/{user_id}?k=5: Gợi ý cá nhân hóa cho người dùng.
  2. GET /recommend/similar/{product_id}?k=5: Gợi ý sản phẩm tương tự (Content-based).
  3. GET /recommend/frequently-bought-together/{product_id}: Gợi ý mua kèm (Market Basket Analysis).
  4. Các endpoint hỗ trợ Demo, kiểm tra Healthcheck và truy vấn BI Views.
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.database import engine, query_dataframe, test_connection
from src.recommender.collaborative_filtering import (
    SVDRecommender,
    build_user_item_matrix,
    load_interactions,
)
from src.recommender.content_based import ContentBasedRecommender, load_product_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("API.Main")

# ==============================================================================
# KHỞI TẠO BỘ NHỚ ĐỆM CHO CÁC MÔ HÌNH (STATE REGISTRY)
# ==============================================================================

app_state: Dict[str, Any] = {
    "cb_model": None,
    "cf_model": None,
    "df_interactions": None,
    "df_products": None,
    "product_catalog": {},
    "rules_df": None,
    "popular_products": [],
    "db_healthy": False,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý vòng đời ứng dụng: Nạp dữ liệu và khởi tạo mô hình khi khởi động."""
    logger.info("==================================================")
    logger.info(" KHỞI ĐỘNG HỆ THỐNG GỢI Ý (RECOMMENDER ENGINE)...")
    logger.info("==================================================")

    # 1. Kiểm tra kết nối cơ sở dữ liệu
    app_state["db_healthy"] = test_connection()

    # 2. Tải danh mục sản phẩm (Dim_Product + Dim_Category)
    try:
        df_prod = load_product_data(engine_instance=engine if app_state["db_healthy"] else None)
        app_state["df_products"] = df_prod
        # Tạo từ điển tra cứu nhanh O(1) theo product_id
        catalog = {}
        for _, r in df_prod.iterrows():
            catalog[str(r["product_id"])] = {
                "product_id": str(r["product_id"]),
                "product_name": str(r.get("product_name", "Sản phẩm không tên")),
                "category_id": str(r.get("category_id", "unknown")),
                "category_name": str(r.get("category_name", "Chưa phân loại")),
                "price": float(r.get("price", 0.0)),
                "brand": str(r.get("brand", "")) if pd.notna(r.get("brand")) else "",
            }
        app_state["product_catalog"] = catalog
        logger.info("-> Đã lập chỉ mục danh mục: %d sản phẩm.", len(catalog))
    except Exception as exc:
        logger.error("Lỗi tải danh mục sản phẩm: %s", exc)

    # 3. Huấn luyện mô hình Content-Based Recommender (TF-IDF + Cosine)
    try:
        cb = ContentBasedRecommender(max_features=5000, use_price=True)
        cb.fit(app_state["df_products"])
        app_state["cb_model"] = cb
        logger.info("-> Content-Based Recommender sẵn sàng.")
    except Exception as exc:
        logger.error("Lỗi huấn luyện Content-Based: %s", exc)

    # 4. Tải lịch sử tương tác và huấn luyện Collaborative Filtering (SVD)
    try:
        df_inter = load_interactions(engine_instance=engine if app_state["db_healthy"] else None)
        app_state["df_interactions"] = df_inter
        mat, users, items = build_user_item_matrix(df_inter)
        cf = SVDRecommender(n_components=50)
        cf.fit(mat, users, items)
        app_state["cf_model"] = cf
        logger.info("-> Collaborative Filtering (SVD) sẵn sàng.")

        # Xác định top sản phẩm bán chạy nhất cho Cold-Start
        pop_counts = df_inter[df_inter["event_type"] == "purchase"]["product_id"].value_counts()
        app_state["popular_products"] = pop_counts.head(50).index.tolist()
    except Exception as exc:
        logger.error("Lỗi huấn luyện Collaborative Filtering: %s", exc)

    # 5. Tải bảng Luật kết hợp (Association Rules)
    try:
        project_root = Path(__file__).resolve().parent.parent.parent
        rules_path = project_root / "data" / "processed" / "association_rules.csv"
        if rules_path.exists():
            rules_df = pd.read_csv(rules_path)
            app_state["rules_df"] = rules_df
            logger.info("-> Đã nạp %d luật kết hợp giỏ hàng.", len(rules_df))
    except Exception as exc:
        logger.error("Lỗi nạp luật kết hợp: %s", exc)

    logger.info(" Khởi tạo toàn bộ mô hình thành công. API sẵn sàng nhận request!\n")
    yield
    logger.info(" Đang dừng Recommender API Server...")


# ==============================================================================
# TẠO KHUNG ỨNG DỤNG FASTAPI
# ==============================================================================

app = FastAPI(
    title="E-Commerce Recommender & BI Analytics API",
    description=(
        "Hệ thống gợi ý sản phẩm cá nhân hóa thương mại điện tử kết hợp Data Warehouse, "
        "Khai phá dữ liệu (RFM K-Means, Association Rules) và Máy học (TF-IDF, SVD)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Bật CORS cho phép kết nối từ mọi giao diện UI (Streamlit, React, Vue, Swagger)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# PYDANTIC SCHEMAS (ĐỊNH DẠNG DỮ LIỆU ĐẦU RA CHUẨN JSON)
# ==============================================================================


class ProductItem(BaseModel):
    product_id: str
    product_name: str
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    price: float = 0.0
    brand: Optional[str] = None
    score: float = Field(default=0.0, description="Độ tương đồng hoặc điểm dự báo")
    recommendation_reason: Optional[str] = Field(
        default=None, description="Lý do gợi ý cho người dùng"
    )


class UserRecommendationResponse(BaseModel):
    user_id: str
    rfm_segment: str
    algorithm_used: str
    is_cold_start: bool
    total_recommendations: int
    recommendations: List[ProductItem]


class SimilarProductResponse(BaseModel):
    source_product: ProductItem
    top_k: int
    similar_products: List[ProductItem]


class FrequentlyBoughtTogetherItem(BaseModel):
    product_id: str
    product_name: str
    category_name: str
    price: float
    confidence: float
    lift: float
    support: float
    cross_sell_reason: str


class FrequentlyBoughtTogetherResponse(BaseModel):
    source_product: ProductItem
    association_rules_found: int
    frequently_bought_together: List[FrequentlyBoughtTogetherItem]
    bundle_offer: Optional[Dict[str, Any]] = None


# ==============================================================================
# HÀM HỖ TRỢ NỘI BỘ (HELPER FUNCTIONS)
# ==============================================================================


def _get_product_card(product_id: str, score: float = 0.0, reason: str = "") -> ProductItem:
    """Tra cứu và trả về thẻ sản phẩm đầy đủ thông tin từ catalog."""
    catalog = app_state["product_catalog"]
    prod = catalog.get(product_id, {})
    return ProductItem(
        product_id=product_id,
        product_name=prod.get("product_name", f"Sản phẩm {product_id[:8]}"),
        category_id=prod.get("category_id", "unknown"),
        category_name=prod.get("category_name", "Chưa phân loại"),
        price=prod.get("price", 0.0),
        brand=prod.get("brand", ""),
        score=round(float(score), 4),
        recommendation_reason=reason,
    )


def _get_user_rfm_segment(user_id: str) -> str:
    """Tra cứu phân khúc RFM của khách hàng từ DWH."""
    try:
        sql = f"SELECT rfm_segment FROM dim_user WHERE user_id = '{user_id}' LIMIT 1;"
        res = query_dataframe(sql)
        if not res.empty and pd.notna(res.iloc[0]["rfm_segment"]):
            return str(res.iloc[0]["rfm_segment"])
    except Exception:
        pass
    return "Khách hàng mới"


# ==============================================================================
# CÁC ENDPOINT CHÍNH (REQUIREMENT ENDPOINTS)
# ==============================================================================


@app.get("/", response_class=HTMLResponse, tags=["Giao diện Quản trị"])
@app.get("/dashboard", response_class=HTMLResponse, tags=["Giao diện Quản trị"])
def executive_dashboard():
    """Giao diện Dashboard Quản trị Doanh nghiệp & Demo Hệ thống Gợi ý (Executive BI Dashboard)."""
    template_path = Path(__file__).resolve().parent / "templates" / "dashboard.html"
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>Dashboard template not found. Please access /docs for API documentation.</h2>")


@app.get("/api-overview", tags=["Tổng quan"])
def api_overview():
    """API Metadata giới thiệu các endpoint."""
    return {
        "title": "E-Commerce Recommender System API",
        "author": "BTL Kho dữ liệu & Khai phá dữ liệu",
        "status": "Online",
        "documentation": "/docs",
        "dashboard": "/dashboard",
        "endpoints": {
            "Gợi ý cá nhân hóa": "/recommend/user/{user_id}?k=5",
            "Sản phẩm tương tự": "/recommend/similar/{product_id}?k=5",
            "Sản phẩm mua kèm": "/recommend/frequently-bought-together/{product_id}",
            "Danh sách User mẫu": "/demo/sample-users",
            "Danh sách Sản phẩm mẫu": "/demo/sample-products",
            "Báo cáo phân khúc RFM": "/bi/segments",
            "Phễu chuyển đổi": "/bi/funnel",
        },
    }


@app.get("/health", tags=["Hệ thống"])
def health_check():
    """Kiểm tra tình trạng hoạt động của cơ sở dữ liệu và các mô hình."""
    return {
        "status": "healthy",
        "database_connected": app_state["db_healthy"],
        "database_dialect": engine.dialect.name.upper() if app_state["db_healthy"] else "NONE",
        "models_status": {
            "content_based_fitted": app_state["cb_model"] is not None,
            "collaborative_filtering_fitted": app_state["cf_model"] is not None,
            "association_rules_loaded": app_state["rules_df"] is not None,
        },
        "stats": {
            "total_products_indexed": len(app_state["product_catalog"]),
            "total_interactions": len(app_state["df_interactions"]) if app_state["df_interactions"] is not None else 0,
            "total_association_rules": len(app_state["rules_df"]) if app_state["rules_df"] is not None else 0,
        },
    }


# ------------------------------------------------------------------------------
# 1. GỢI Ý CÁ NHÂN HÓA CHO NGƯỜI DÙNG (PERSONALIZED RECOMMENDATIONS)
# ------------------------------------------------------------------------------
@app.get(
    "/recommend/user/{user_id}",
    response_model=UserRecommendationResponse,
    tags=["Gợi ý sản phẩm"],
    summary="Top K gợi ý cá nhân hóa cho khách hàng",
)
def recommend_for_user(
    user_id: str,
    k: int = Query(5, ge=1, le=50, description="Số lượng sản phẩm cần gợi ý"),
    algorithm: str = Query(
        "hybrid",
        pattern="^(hybrid|content_based|cf_svd|popularity)$",
        description="Thuật toán: 'hybrid', 'content_based', 'cf_svd', hoặc 'popularity'",
    ),
):
    """Gợi ý danh sách sản phẩm cá nhân hóa phù hợp nhất với sở thích và lịch sử mua hàng của khách hàng.

    - Nếu user có lịch sử: Áp dụng Content-Based (profile weighting) hoặc SVD Matrix Factorization.
    - Nếu user mới (Cold-Start): Tự động chuyển tiếp (Fallback) sang Top sản phẩm bán chạy nhất.
    """
    df_inter = app_state["df_interactions"]
    cb_model: ContentBasedRecommender = app_state["cb_model"]
    cf_model: SVDRecommender = app_state["cf_model"]
    popular_products = app_state["popular_products"]

    # Xác định phân khúc RFM
    rfm_segment = _get_user_rfm_segment(user_id)

    # Lấy lịch sử tương tác của user
    user_history = pd.DataFrame()
    seen_products = set()
    if df_inter is not None:
        user_history = df_inter[df_inter["user_id"] == user_id]
        seen_products = set(user_history["product_id"].unique())

    is_cold_start = len(user_history) == 0
    recommendations: List[ProductItem] = []
    algo_used = algorithm

    # TRƯỜNG HỢP 1: COLD-START HOẶC YÊU CẦU POPULARITY
    if is_cold_start or algorithm == "popularity":
        algo_used = "popularity_baseline"
        top_candidates = [p for p in popular_products if p not in seen_products][:k]
        for p in top_candidates:
            recommendations.append(
                _get_product_card(
                    p,
                    score=1.0,
                    reason="Sản phẩm thịnh hành được nhiều khách hàng yêu thích nhất",
                )
            )

    # TRƯỜNG HỢP 2: COLLABORATIVE FILTERING (SVD)
    elif algorithm == "cf_svd" and cf_model is not None:
        try:
            cf_recs = cf_model.recommend_for_user(user_id, top_k=k, exclude_seen=seen_products)
            for _, row in cf_recs.iterrows():
                recommendations.append(
                    _get_product_card(
                        str(row["product_id"]),
                        score=float(row["predicted_score"]),
                        reason=f"Mô hình SVD phát hiện tương đồng hành vi với phân khúc {rfm_segment}",
                    )
                )
        except Exception as exc:
            logger.warning("Lỗi chạy SVD cho user %s: %s", user_id, exc)

    # TRƯỜNG HỢP 3: CONTENT-BASED HOẶC HYBRID (ƯU TIÊN CONTENT-BASED VÌ CHÍNH XÁC CAO HƠN TRÊN DỮ LIỆU THƯA)
    if not recommendations and cb_model is not None:
        algo_used = "content_based_hybrid"
        try:
            cb_recs = cb_model.recommend_for_user(user_id, df_inter, top_k=k, n_seed_products=3)
            for _, row in cb_recs.iterrows():
                p_id = str(row["product_id"])
                if p_id not in seen_products:
                    recommendations.append(
                        _get_product_card(
                            p_id,
                            score=float(row["similarity_score"]),
                            reason="Tương đồng cao với các sản phẩm bạn từng xem và đánh giá tốt",
                        )
                    )
        except Exception as exc:
            logger.warning("Lỗi chạy CB cho user %s: %s", user_id, exc)

    # Fallback nếu vẫn chưa đủ K sản phẩm
    if len(recommendations) < k:
        existing_ids = {r.product_id for r in recommendations}.union(seen_products)
        extras = [p for p in popular_products if p not in existing_ids][: (k - len(recommendations))]
        for p in extras:
            recommendations.append(
                _get_product_card(
                    p,
                    score=0.5,
                    reason="Gợi ý bổ sung từ sản phẩm bán chạy toàn sàn",
                )
            )

    return UserRecommendationResponse(
        user_id=user_id,
        rfm_segment=rfm_segment,
        algorithm_used=algo_used,
        is_cold_start=is_cold_start,
        total_recommendations=len(recommendations),
        recommendations=recommendations[:k],
    )


# ------------------------------------------------------------------------------
# 2. GỢI Ý SẢN PHẨM TƯƠNG TỰ (SIMILAR PRODUCTS - CONTENT BASED)
# ------------------------------------------------------------------------------
@app.get(
    "/recommend/similar/{product_id}",
    response_model=SimilarProductResponse,
    tags=["Gợi ý sản phẩm"],
    summary="Top K sản phẩm tương tự dựa trên nội dung",
)
def recommend_similar_products(
    product_id: str,
    k: int = Query(5, ge=1, le=50, description="Số lượng sản phẩm tương tự cần tìm"),
):
    """Tìm top K sản phẩm có đặc trưng tương đồng nhất (Category, Tên, Mô tả, Thương hiệu, Giá cả)

    dựa trên vector hóa TF-IDF và Cosine Similarity.
    """
    catalog = app_state["product_catalog"]
    if product_id not in catalog:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy mã sản phẩm '{product_id}' trong danh mục.",
        )

    cb_model: ContentBasedRecommender = app_state["cb_model"]
    if cb_model is None:
        raise HTTPException(status_code=503, detail="Mô hình Content-Based chưa sẵn sàng.")

    target_card = _get_product_card(product_id)
    similar_df = cb_model.recommend_by_product(product_id, top_k=k, exclude_self=True)

    similar_list = []
    for _, row in similar_df.iterrows():
        p_id = str(row["product_id"])
        score = float(row["similarity_score"])
        similar_list.append(
            _get_product_card(
                p_id,
                score=score,
                reason=f"Độ tương đồng nội dung {score * 100:.1f}% với sản phẩm gốc",
            )
        )

    return SimilarProductResponse(
        source_product=target_card,
        top_k=len(similar_list),
        similar_products=similar_list,
    )


# ------------------------------------------------------------------------------
# 3. GỢI Ý MUA KÈM / CROSS-SELL (FREQUENTLY BOUGHT TOGETHER - FP-GROWTH RULES)
# ------------------------------------------------------------------------------
@app.get(
    "/recommend/frequently-bought-together/{product_id}",
    response_model=FrequentlyBoughtTogetherResponse,
    tags=["Gợi ý sản phẩm"],
    summary="Gợi ý sản phẩm thường được mua kèm (Luật kết hợp giỏ hàng)",
)
def recommend_frequently_bought_together(
    product_id: str,
    k: int = Query(5, ge=1, le=20, description="Số lượng sản phẩm mua kèm đề xuất"),
):
    """Phát hiện các sản phẩm khách hàng thường mua kèm trong cùng giỏ hàng

    dựa trên thuật toán Khai phá luật kết hợp (FP-Growth / Market Basket Analysis).
    """
    catalog = app_state["product_catalog"]
    if product_id not in catalog:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy mã sản phẩm '{product_id}' trong danh mục.",
        )

    source_card = _get_product_card(product_id)
    rules_df = app_state["rules_df"]
    df_prod = app_state["df_products"]

    fbt_items: List[FrequentlyBoughtTogetherItem] = []
    rules_matched_count = 0

    if rules_df is not None and not rules_df.empty:
        # Tra cứu theo category_id hoặc category_name của sản phẩm gốc
        cat_id = source_card.category_id.lower()
        matched_rules = []

        for _, r in rules_df.iterrows():
            ant_str = str(r["antecedents"]).lower()
            if cat_id in ant_str or source_card.category_name.lower() in ant_str:
                matched_rules.append(r)

        rules_matched_count = len(matched_rules)

        if matched_rules:
            # Sắp xếp luật theo Lift và Confidence cao nhất
            sorted_rules = sorted(
                matched_rules,
                key=lambda x: (float(x["lift"]), float(x["confidence"])),
                reverse=True,
            )

            for rule in sorted_rules:
                consequent_cat = str(rule["consequents"]).strip()
                lift = float(rule["lift"])
                conf = float(rule["confidence"])
                supp = float(rule["support"])

                if df_prod is not None:
                    cat_candidates = pd.DataFrame()
                    if "category_id" in df_prod.columns:
                        cat_candidates = df_prod[
                            df_prod["category_id"].astype(str).str.lower() == consequent_cat.lower()
                        ]
                    if cat_candidates.empty and "category_name" in df_prod.columns:
                        cat_candidates = df_prod[
                            df_prod["category_name"].astype(str).str.lower() == consequent_cat.lower()
                        ]
                    if not cat_candidates.empty:
                        for _, cand_row in cat_candidates.head(2).iterrows():
                            cand_id = str(cand_row["product_id"])
                            if cand_id != product_id and not any(x.product_id == cand_id for x in fbt_items):
                                fbt_items.append(
                                    FrequentlyBoughtTogetherItem(
                                        product_id=cand_id,
                                        product_name=str(cand_row.get("product_name", f"Sản phẩm {cand_id[:8]}")),
                                        category_name=str(cand_row.get("category_name", consequent_cat)),
                                        price=float(cand_row.get("price", 0.0)),
                                        confidence=round(conf, 4),
                                        lift=round(lift, 2),
                                        support=round(supp, 4),
                                        cross_sell_reason=(
                                            f"{conf * 100:.1f}% khách mua '{source_card.category_name}' "
                                            f"thường mua kèm '{consequent_cat}' (Tỷ lệ gấp {lift:.1f} lần ngẫu nhiên)"
                                        ),
                                    )
                                )
                if len(fbt_items) >= k:
                    break

    # Nếu không tìm thấy luật trực tiếp, gợi ý sản phẩm bán chạy bổ sung
    if not fbt_items:
        popular_products = app_state["popular_products"]
        for p in popular_products:
            if p != product_id and not any(x.product_id == p for x in fbt_items):
                p_card = _get_product_card(p)
                fbt_items.append(
                    FrequentlyBoughtTogetherItem(
                        product_id=p,
                        product_name=p_card.product_name,
                        category_name=p_card.category_name or "Phổ biến",
                        price=p_card.price,
                        confidence=0.5000,
                        lift=1.20,
                        support=0.0100,
                        cross_sell_reason="Sản phẩm bán chạy nhất toàn sàn thường được đặt chung đơn",
                    )
                )
            if len(fbt_items) >= k:
                break

    # Tính toán gói Combo khuyến mãi (Bundle Offer)
    selected_items = fbt_items[:k]
    original_sum = source_card.price + sum(x.price for x in selected_items)
    discount_pct = 10  # Giảm 10% khi mua cả Combo
    discounted_sum = round(original_sum * (1 - discount_pct / 100), 2)

    bundle_offer = {
        "bundle_items_count": len(selected_items) + 1,
        "original_total_price": round(original_sum, 2),
        "bundle_discount_pct": discount_pct,
        "bundle_discount_price": discounted_sum,
        "you_save": round(original_sum - discounted_sum, 2),
    }

    return FrequentlyBoughtTogetherResponse(
        source_product=source_card,
        association_rules_found=rules_matched_count,
        frequently_bought_together=selected_items,
        bundle_offer=bundle_offer,
    )


# ==============================================================================
# CÁC ENDPOINT HỖ TRỢ DEMO & TRUY VẤN BI CHO GIẢNG VIÊN
# ==============================================================================


@app.get("/demo/sample-users", tags=["Dữ liệu Demo"])
def get_sample_users():
    """Trả về danh sách các user mẫu thuộc các phân khúc RFM khác nhau để dễ dàng test API."""
    try:
        sql = """
        SELECT rfm_segment, user_id, COALESCE(city || ', ' || country, city, country, 'Unknown') AS location, age, created_at
        FROM (
            SELECT rfm_segment, user_id, city, country, age, created_at,
                   ROW_NUMBER() OVER(PARTITION BY rfm_segment ORDER BY user_id) as rn
            FROM dim_user
            WHERE rfm_segment IS NOT NULL
        ) t
        WHERE rn <= 2
        ORDER BY rfm_segment;
        """
        df = query_dataframe(sql)
        return {
            "description": "Copy user_id dưới đây để dán vào endpoint GET /recommend/user/{user_id}",
            "sample_users": df.to_dict(orient="records"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/demo/sample-products", tags=["Dữ liệu Demo"])
def get_sample_products(limit: int = 10):
    """Trả về danh sách sản phẩm mẫu kèm danh mục để test gợi ý tương tự và mua kèm."""
    try:
        sql = f"""
        SELECT p.product_id, p.product_name, c.category_name, p.price
        FROM dim_product p
        JOIN dim_category c ON p.category_id = c.category_id
        WHERE p.price > 0
        LIMIT {limit};
        """
        df = query_dataframe(sql)
        return {
            "description": "Copy product_id dưới đây để test /recommend/similar và /recommend/frequently-bought-together",
            "sample_products": df.to_dict(orient="records"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/bi/segments", tags=["Business Intelligence (BI)"])
def get_bi_segments():
    """Truy vấn dữ liệu từ View 'vw_customer_rfm_segments' trong DWH."""
    try:
        sql = "SELECT * FROM vw_customer_rfm_segments;"
        df = query_dataframe(sql)
        return {
            "view_name": "vw_customer_rfm_segments",
            "total_segments": len(df),
            "data": df.to_dict(orient="records"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/bi/funnel", tags=["Business Intelligence (BI)"])
def get_bi_funnel(limit: int = 15):
    """Truy vấn dữ liệu từ View 'vw_interaction_funnel' trong DWH."""
    try:
        sql = f"SELECT * FROM vw_interaction_funnel LIMIT {limit};"
        df = query_dataframe(sql)
        return {
            "view_name": "vw_interaction_funnel",
            "data": df.to_dict(orient="records"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn

    print("Khởi động FastAPI Server trên cổng 8000...")
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=False)
