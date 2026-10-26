"""Module biến đổi (Transform) dữ liệu đa nguồn vào Lược đồ hình sao (Star Schema).

Quy trình:
1. Làm sạch Amazon Reviews: xử lý khuyết thiếu ở rating, chuẩn hóa timestamp, loại bỏ duplicate user_id + parent_asin.
2. Ghép nối Dim_User: ánh xạ xoay vòng (round-robin) nhân khẩu học từ DummyJSON vào user_id Amazon.
3. Ghép nối Dim_Product & Dim_Category: tích hợp metadata Amazon với ingredients_text từ Open Food Facts.
4. Xây dựng Dim_Time: phân rã full_timestamp thành time_id (YYYYMMDDHH), day, month, quarter, year, day_of_week.
5. Xây dựng Fact_Interactions: ánh xạ chính xác khóa ngoại user_id, product_id, time_id.
"""

import logging
import re
import sys
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ETL.Transform")


def clean_amazon_reviews(df_reviews: pd.DataFrame) -> pd.DataFrame:
    """Làm sạch dữ liệu Amazon Reviews thô.

    - Xử lý rating rỗng, kẹp giá trị rating trong khoảng [1.0, 5.0].
    - Chuẩn hóa timestamp thành đối tượng pandas datetime (full_timestamp).
    - Khử trùng lặp theo cặp (user_id, parent_asin).
    - Điền giá trị mặc định cho helpful_vote và review_text.
    """
    logger.info("Đang làm sạch và chuẩn hóa Amazon Reviews...")
    df = df_reviews.copy()

    # 1. Loại bỏ bản ghi thiếu user_id hoặc parent_asin
    initial_count = len(df)
    df = df.dropna(subset=["user_id", "parent_asin"])
    df["user_id"] = df["user_id"].astype(str).str.strip()
    df["parent_asin"] = df["parent_asin"].astype(str).str.strip()
    df = df[(df["user_id"] != "") & (df["parent_asin"] != "")]

    # 2. Xử lý rating
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    median_rating = df["rating"].median() if not df["rating"].dropna().empty else 4.0
    df["rating"] = df["rating"].fillna(median_rating).clip(1.0, 5.0).round(1)

    # 3. Chuẩn hóa timestamp sang full_timestamp datetime
    if pd.api.types.is_numeric_dtype(df["timestamp"]):
        max_ts = df["timestamp"].max() if not df["timestamp"].empty else 0
        # Timestamp trên Amazon Reviews '23 thường ở dạng millisecond Unix timestamp
        unit = "ms" if max_ts > 1e11 else "s"
        df["full_timestamp"] = pd.to_datetime(df["timestamp"], unit=unit, errors="coerce")
    else:
        df["full_timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # Điền giá trị dự phòng nếu timestamp không hợp lệ
    df["full_timestamp"] = df["full_timestamp"].fillna(pd.Timestamp("2023-01-01 12:00:00"))

    # 4. Chuẩn hóa helpful_vote và review text
    df["helpful_vote"] = pd.to_numeric(df["helpful_vote"], errors="coerce").fillna(0).astype(int)
    df["text"] = df["text"].fillna("").astype(str).str.strip()

    # 5. Khử trùng lặp trên cặp (user_id, parent_asin)
    df = df.drop_duplicates(subset=["user_id", "parent_asin"], keep="first").reset_index(drop=True)
    dropped_dups = initial_count - len(df)
    logger.info(
        f"-> Đã làm sạch Reviews: {len(df):,} bản ghi hợp lệ "
        f"(Đã loại bỏ {dropped_dups:,} dòng thiếu trường hoặc trùng lặp)."
    )

    return df


def build_dim_user(
    df_reviews: pd.DataFrame,
    df_dummy_users: pd.DataFrame,
) -> pd.DataFrame:
    """Ghép nối thông tin người dùng Dim_User.

    Lấy các user_id duy nhất từ Amazon Reviews và ánh xạ xoay vòng (round-robin)
    các thuộc tính nhân khẩu học (age, gender, city, country) từ DummyJSON API.
    """
    logger.info("Đang xây dựng bảng Dim_User từ Amazon ReviewerID và DummyJSON...")
    unique_users = df_reviews["user_id"].unique()
    num_users = len(unique_users)

    if df_dummy_users is None or df_dummy_users.empty:
        # Dự phòng hồ sơ mẫu nếu DummyJSON API offline
        df_dummy_users = pd.DataFrame([
            {"age": 28, "gender": "female", "city": "New York", "country": "United States"},
            {"age": 35, "gender": "male", "city": "Los Angeles", "country": "United States"},
            {"age": 42, "gender": "female", "city": "Chicago", "country": "United States"},
            {"age": 25, "gender": "male", "city": "Houston", "country": "United States"},
        ])

    num_dummy = len(df_dummy_users)
    # Ánh xạ xoay vòng (Round-robin)
    ages = [int(df_dummy_users["age"].iloc[i % num_dummy]) for i in range(num_users)]
    genders = [str(df_dummy_users["gender"].iloc[i % num_dummy]) for i in range(num_users)]
    cities = [str(df_dummy_users["city"].iloc[i % num_dummy]) for i in range(num_users)]
    countries = [str(df_dummy_users["country"].iloc[i % num_dummy]) for i in range(num_users)]

    # Lấy thời điểm tạo hồ sơ (dựa theo thời điểm tương tác sớm nhất của user)
    user_min_time = df_reviews.groupby("user_id")["full_timestamp"].min().to_dict()
    created_ats = [user_min_time.get(u, pd.Timestamp("2023-01-01")) for u in unique_users]

    dim_user = pd.DataFrame({
        "user_id": unique_users,
        "age": ages,
        "gender": genders,
        "city": cities,
        "country": countries,
        "created_at": created_ats,
    })

    logger.info(f"-> Đã xây dựng Dim_User thành công: {len(dim_user):,} khách hàng hoàn chỉnh.")
    return dim_user


def build_dim_category_and_product(
    df_reviews: pd.DataFrame,
    df_meta: pd.DataFrame,
    df_off: Optional[pd.DataFrame] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Xây dựng bảng Dim_Category và Dim_Product.

    - Đảm bảo 100% parent_asin xuất hiện trong reviews đều có mặt trong Dim_Product.
    - Làm giàu thành phần dinh dưỡng ingredients_text từ Open Food Facts.
    """
    logger.info("Đang xây dựng Dim_Category và Dim_Product (tích hợp Open Food Facts)...")

    # 1. Chuẩn hóa Metadata
    meta = df_meta.copy() if df_meta is not None and not df_meta.empty else pd.DataFrame()
    if meta.empty:
        meta = pd.DataFrame(columns=["parent_asin", "title", "price", "main_category", "description"])

    meta["parent_asin"] = meta["parent_asin"].astype(str).str.strip()
    meta = meta.drop_duplicates(subset=["parent_asin"])

    # 2. Đảm bảo mọi sản phẩm trong Reviews đều tồn tại trong Meta
    review_asins = set(df_reviews["parent_asin"].unique())
    meta_asins = set(meta["parent_asin"].unique())
    missing_asins = list(review_asins - meta_asins)

    if missing_asins:
        logger.info(f"Phát hiện {len(missing_asins):,} sản phẩm chưa có trong metadata. Đang tự động bổ sung...")
        missing_df = pd.DataFrame({
            "parent_asin": missing_asins,
            "title": [f"Amazon Product {asin}" for asin in missing_asins],
            "price": 19.99,
            "main_category": "All Beauty",
            "description": "Amazon featured product.",
        })
        meta = pd.concat([meta, missing_df], ignore_index=True)

    # Lọc chỉ giữ các sản phẩm có tương tác trong tập reviews
    meta = meta[meta["parent_asin"].isin(review_asins)].copy()

    # 3. Tạo bảng Dim_Category
    categories = meta[["main_category"]].dropna().drop_duplicates().copy()
    categories["category_id"] = (
        categories["main_category"]
        .astype(str)
        .str.lower()
        .str.replace(r"[^\w\s-]", "", regex=True)
        .str.replace(r"\s+", "_", regex=True)
    )
    categories["category_name"] = categories["main_category"].astype(str).str.strip().str.title()
    dim_category = categories[["category_id", "category_name"]].drop_duplicates(subset=["category_id"]).reset_index(drop=True)

    # Ánh xạ category_id vào metadata
    cat_map = dict(zip(categories["main_category"], categories["category_id"]))
    meta["category_id"] = meta["main_category"].map(cat_map).fillna("general_category")

    if not any(dim_category["category_id"] == "general_category"):
        dim_category = pd.concat([
            dim_category,
            pd.DataFrame([{"category_id": "general_category", "category_name": "Sản Phẩm Chung"}])
        ], ignore_index=True)

    # 4. Tích hợp dữ liệu Open Food Facts (ingredients_text & brand)
    off_map = {}
    if df_off is not None and not df_off.empty:
        for _, row in df_off.iterrows():
            pid = row.get("product_id")
            if pid:
                off_map[pid] = {
                    "ingredients_text": row.get("ingredients_text", ""),
                    "brands": row.get("brands", ""),
                }

    ingredients_list = []
    brand_list = []
    for _, row in meta.iterrows():
        p_id = row["parent_asin"]
        off_info = off_map.get(p_id, {})
        # Gán ingredients_text nếu có từ Open Food Facts
        ingredients_list.append(off_info.get("ingredients_text", ""))
        # Gán brand
        brand_list.append(off_info.get("brands") or "Amazon Choice")

    dim_product = pd.DataFrame({
        "product_id": meta["parent_asin"],
        "product_name": meta["title"].fillna("Sản phẩm Amazon"),
        "category_id": meta["category_id"],
        "price": meta["price"].fillna(0.0).astype(float),
        "brand": brand_list,
        "description": meta["description"].fillna(""),
        "ingredients_text": ingredients_list,
    }).drop_duplicates(subset=["product_id"]).reset_index(drop=True)

    logger.info(
        f"-> Đã xây dựng Dim_Category ({len(dim_category):,} danh mục) "
        f"và Dim_Product ({len(dim_product):,} sản phẩm)."
    )
    return dim_category, dim_product


def build_dim_time(df_reviews: pd.DataFrame) -> pd.DataFrame:
    """Xây dựng bảng Dim_Time từ dấu thời gian full_timestamp.

    Khóa time_id dạng số nguyên BIGINT: YYYYMMDDHH (ví dụ: 2023102615).
    Phân rã: full_timestamp, day, month, quarter, year, day_of_week.
    """
    logger.info("Đang xây dựng bảng Dim_Time...")
    times = df_reviews[["full_timestamp"]].dropna().drop_duplicates().copy()

    # Sinh khóa thời gian YYYYMMDDHH
    times["time_id"] = (
        times["full_timestamp"].dt.year * 1000000
        + times["full_timestamp"].dt.month * 10000
        + times["full_timestamp"].dt.day * 100
        + times["full_timestamp"].dt.hour
    ).astype("int64")

    times["day"] = times["full_timestamp"].dt.day.astype(int)
    times["month"] = times["full_timestamp"].dt.month.astype(int)
    times["quarter"] = times["full_timestamp"].dt.quarter.astype(int)
    times["year"] = times["full_timestamp"].dt.year.astype(int)
    times["day_of_week"] = times["full_timestamp"].dt.day_name().astype(str)

    dim_time = times[[
        "time_id", "full_timestamp", "day", "month", "quarter", "year", "day_of_week"
    ]].drop_duplicates(subset=["time_id"]).reset_index(drop=True)

    logger.info(f"-> Đã xây dựng Dim_Time thành công: {len(dim_time):,} mốc thời gian duy nhất.")
    return dim_time


def build_fact_interactions(
    df_reviews: pd.DataFrame,
    dim_user: pd.DataFrame,
    dim_product: pd.DataFrame,
    dim_time: pd.DataFrame,
) -> pd.DataFrame:
    """Xây dựng bảng sự kiện trung tâm Fact_Interactions.

    Ánh xạ khóa ngoại user_id, product_id, time_id;
    Đi kèm rating_score, review_text, helpful_vote, event_type.
    """
    logger.info("Đang xây dựng bảng Fact_Interactions...")
    df = df_reviews.copy()

    # Tính time_id khớp với Dim_Time
    df["time_id"] = (
        df["full_timestamp"].dt.year * 1000000
        + df["full_timestamp"].dt.month * 10000
        + df["full_timestamp"].dt.day * 100
        + df["full_timestamp"].dt.hour
    ).astype("int64")

    # Kiểm tra tính toàn vẹn tham chiếu
    valid_users = set(dim_user["user_id"])
    valid_prods = set(dim_product["product_id"])
    valid_times = set(dim_time["time_id"])

    df = df[
        df["user_id"].isin(valid_users)
        & df["parent_asin"].isin(valid_prods)
        & df["time_id"].isin(valid_times)
    ].copy()

    fact_interactions = pd.DataFrame({
        "user_id": df["user_id"],
        "product_id": df["parent_asin"],
        "time_id": df["time_id"],
        "rating_score": df["rating"].astype(float),
        "review_text": df["text"].astype(str),
        "helpful_vote": df["helpful_vote"].astype(int),
        "event_type": "review",
    }).reset_index(drop=True)

    logger.info(f"-> Đã xây dựng Fact_Interactions thành công: {len(fact_interactions):,} tương tác.")
    return fact_interactions


def transform_all(
    raw_reviews: pd.DataFrame,
    raw_metadata: pd.DataFrame,
    raw_dummyjson_users: pd.DataFrame,
    raw_off_enriched: Optional[pd.DataFrame] = None,
) -> Dict[str, pd.DataFrame]:
    """Hàm điều phối toàn bộ quá trình biến đổi dữ liệu đa nguồn.

    Returns:
        dict chứa: 'dim_category', 'dim_user', 'dim_product', 'dim_time', 'fact_interactions'
    """
    logger.info("================ BẮT ĐẦU QUÁ TRÌNH BIẾN ĐỔI (TRANSFORM ALL) ================")

    # 1. Làm sạch Reviews
    cleaned_reviews = clean_amazon_reviews(raw_reviews)

    # 2. Xây dựng Dim_User
    dim_user = build_dim_user(cleaned_reviews, raw_dummyjson_users)

    # 3. Xây dựng Dim_Category & Dim_Product
    dim_category, dim_product = build_dim_category_and_product(
        cleaned_reviews, raw_metadata, raw_off_enriched
    )

    # 4. Xây dựng Dim_Time
    dim_time = build_dim_time(cleaned_reviews)

    # 5. Xây dựng Fact_Interactions
    fact_interactions = build_fact_interactions(
        cleaned_reviews, dim_user, dim_product, dim_time
    )

    logger.info("================ HOÀN TẤT BIẾN ĐỔI TOÀN BỘ STAR SCHEMA ================")
    return {
        "dim_category": dim_category,
        "dim_user": dim_user,
        "dim_product": dim_product,
        "dim_time": dim_time,
        "fact_interactions": fact_interactions,
    }
