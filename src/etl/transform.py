"""Module biến đổi (Transform) dữ liệu: làm sạch, phân rã Dim và ánh xạ Fact."""

import hashlib
import logging
from typing import Optional, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ETL.Transform")


def clean_dataframe(
    df: pd.DataFrame,
    drop_duplicates_subset: Optional[list] = None,
    fillna_dict: Optional[dict] = None,
) -> pd.DataFrame:
    """Làm sạch DataFrame: loại bỏ duplicates, xử lý missing values."""
    cleaned_df = df.copy()

    if drop_duplicates_subset:
        initial_len = len(cleaned_df)
        cleaned_df = cleaned_df.drop_duplicates(subset=drop_duplicates_subset)
        dropped = initial_len - len(cleaned_df)
        if dropped > 0:
            logger.debug(f"Đã loại bỏ {dropped:,} bản ghi trùng lặp.")

    if fillna_dict:
        cleaned_df = cleaned_df.fillna(fillna_dict)

    return cleaned_df


def transform_dim_category(
    df_products: pd.DataFrame,
    df_translation: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Tạo bảng Dim_Category từ danh mục sản phẩm."""
    logger.info("Đang biến đổi bảng Dim_Category...")

    categories = (
        df_products[["product_category_name"]]
        .dropna()
        .drop_duplicates()
        .copy()
    )

    if df_translation is not None and not df_translation.empty:
        categories = categories.merge(
            df_translation, on="product_category_name", how="left"
        )
        # Điền tên tiếng Anh nếu có, ngược lại dùng tên gốc
        categories["category_id"] = categories["product_category_name_english"].fillna(
            categories["product_category_name"]
        )
    else:
        categories["category_id"] = categories["product_category_name"]

    # Chuẩn hóa tên hiển thị viết hoa từng từ
    categories["category_name"] = (
        categories["category_id"]
        .astype(str)
        .str.replace("_", " ")
        .str.title()
    )

    df_dim_category = categories[["category_id", "category_name"]].drop_duplicates(
        subset=["category_id"]
    )

    # Thêm bản ghi danh mục mặc định cho sản phẩm thiếu thông tin (tránh orphan FK)
    default_row = pd.DataFrame(
        [{"category_id": "unknown", "category_name": "Other / Uncategorized"}]
    )
    df_dim_category = pd.concat([df_dim_category, default_row], ignore_index=True)
    df_dim_category = df_dim_category.drop_duplicates(subset=["category_id"])

    logger.info(f"-> Dim_Category hoàn tất: {len(df_dim_category):,} danh mục.")
    return df_dim_category


def transform_dim_user(
    df_customers: pd.DataFrame,
    df_orders: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Tạo bảng Dim_User từ thông tin khách hàng."""
    logger.info("Đang biến đổi bảng Dim_User...")

    # Sử dụng customer_unique_id làm user_id định danh khách hàng
    df_user = df_customers[["customer_unique_id", "customer_city", "customer_state"]].copy()
    df_user = df_user.rename(columns={"customer_unique_id": "user_id"})
    df_user = df_user.drop_duplicates(subset=["user_id"])

    # Chuẩn hóa địa chỉ: City, State (VD: Sao Paulo, SP)
    city_clean = df_user["customer_city"].fillna("Unknown").str.title()
    state_clean = df_user["customer_state"].fillna("XX").str.upper()
    df_user["location"] = city_clean + ", " + state_clean

    # Tạo tuổi và giới tính mô phỏng thực tế nếu chưa có trong dữ liệu gốc
    def _hash_to_int(uid: str, min_v: int, max_v: int) -> int:
        h = int(hashlib.md5(str(uid).encode("utf-8")).hexdigest()[:6], 16)
        return min_v + (h % (max_v - min_v + 1))

    df_user["age"] = df_user["user_id"].apply(lambda u: _hash_to_int(u, 18, 65))
    df_user["gender"] = df_user["user_id"].apply(
        lambda u: "M" if _hash_to_int(u, 0, 1) == 1 else "F"
    )

    # Thời gian tạo tài khoản (lấy từ đơn hàng đầu tiên hoặc mặc định)
    if df_orders is not None and not df_orders.empty:
        orders_cust = df_orders.merge(
            df_customers[["customer_id", "customer_unique_id"]],
            on="customer_id",
            how="inner",
        )
        orders_cust["order_purchase_timestamp"] = pd.to_datetime(
            orders_cust["order_purchase_timestamp"]
        )
        first_orders = orders_cust.groupby("customer_unique_id")[
            "order_purchase_timestamp"
        ].min().reset_index()
        first_orders = first_orders.rename(
            columns={
                "customer_unique_id": "user_id",
                "order_purchase_timestamp": "created_at",
            }
        )
        df_user = df_user.merge(first_orders, on="user_id", how="left")
        df_user["created_at"] = df_user["created_at"].fillna(pd.Timestamp.now())
    else:
        df_user["created_at"] = pd.Timestamp.now()

    df_user["rfm_segment"] = "Unassigned"

    cols = ["user_id", "age", "gender", "location", "created_at", "rfm_segment"]
    df_dim_user = df_user[cols].drop_duplicates(subset=["user_id"])

    logger.info(f"-> Dim_User hoàn tất: {len(df_dim_user):,} người dùng.")
    return df_dim_user


def transform_dim_product(
    df_products: pd.DataFrame,
    df_order_items: Optional[pd.DataFrame] = None,
    df_translation: Optional[pd.DataFrame] = None,
    valid_category_ids: Optional[set] = None,
) -> pd.DataFrame:
    """Tạo bảng Dim_Product từ thông tin sản phẩm và giá giao dịch."""
    logger.info("Đang biến đổi bảng Dim_Product...")

    products = df_products.copy()

    # Ánh xạ category sang category_id tiếng Anh
    if df_translation is not None and not df_translation.empty:
        products = products.merge(
            df_translation, on="product_category_name", how="left"
        )
        products["category_id"] = products["product_category_name_english"].fillna(
            products["product_category_name"]
        )
    else:
        products["category_id"] = products["product_category_name"]

    # Điền 'unknown' nếu danh mục bị thiếu
    products["category_id"] = products["category_id"].fillna("unknown")

    # Đảm bảo category_id tồn tại trong Dim_Category
    if valid_category_ids:
        products["category_id"] = products["category_id"].apply(
            lambda c: c if c in valid_category_ids else "unknown"
        )

    # Tính giá trung bình từ order_items
    if df_order_items is not None and not df_order_items.empty:
        price_map = df_order_items.groupby("product_id")["price"].mean().to_dict()
        median_price = df_order_items["price"].median()
        products["price"] = products["product_id"].map(price_map).fillna(median_price)
    else:
        products["price"] = 50.0

    products["price"] = products["price"].round(2)

    # Tạo tên sản phẩm trực quan
    cat_names = products["category_id"].str.replace("_", " ").str.title()
    short_ids = products["product_id"].astype(str).str[:6].str.upper()
    products["product_name"] = cat_names + " #" + short_ids

    # Thông tin bổ trợ
    products["brand"] = "Olist Merchant"
    products["description"] = (
        "Trọng lượng: "
        + products["product_weight_g"].fillna(0).astype(int).astype(str)
        + "g | Kích thước: "
        + products["product_length_cm"].fillna(0).astype(int).astype(str)
        + "x"
        + products["product_height_cm"].fillna(0).astype(int).astype(str)
        + "x"
        + products["product_width_cm"].fillna(0).astype(int).astype(str)
        + "cm"
    )

    cols = ["product_id", "product_name", "category_id", "price", "brand", "description"]
    df_dim_product = products[cols].drop_duplicates(subset=["product_id"])

    logger.info(f"-> Dim_Product hoàn tất: {len(df_dim_product):,} sản phẩm.")
    return df_dim_product


def transform_dim_time(timestamps: pd.Series) -> pd.DataFrame:
    """Tạo bảng Dim_Time bóc tách đầy đủ các trường thời gian và khóa time_id.

    time_id được tạo theo định dạng số: YYYYMMDDHHmm (ví dụ 201805121430).
    """
    logger.info("Đang biến đổi bảng Dim_Time...")

    ts = pd.to_datetime(timestamps).dropna().drop_duplicates()
    if ts.empty:
        logger.warning("Không có dữ liệu thời gian để tạo Dim_Time.")
        return pd.DataFrame()

    time_df = pd.DataFrame({"full_timestamp": ts})
    time_df["year"] = time_df["full_timestamp"].dt.year
    time_df["month"] = time_df["full_timestamp"].dt.month
    time_df["day"] = time_df["full_timestamp"].dt.day
    time_df["quarter"] = time_df["full_timestamp"].dt.quarter
    # day_of_week: 1 = Thứ hai, ..., 7 = Chủ nhật
    time_df["day_of_week"] = time_df["full_timestamp"].dt.dayofweek + 1

    # Tạo khóa time_id dạng BIGINT: YYYYMMDDHHmm (đảm bảo int64 chống tràn số 32-bit)
    hour = time_df["full_timestamp"].dt.hour
    minute = time_df["full_timestamp"].dt.minute
    y_64 = time_df["year"].astype("int64")
    m_64 = time_df["month"].astype("int64")
    d_64 = time_df["day"].astype("int64")
    h_64 = hour.astype("int64")
    mi_64 = minute.astype("int64")

    time_df["time_id"] = (
        y_64 * 100000000
        + m_64 * 1000000
        + d_64 * 10000
        + h_64 * 100
        + mi_64
    )

    cols = [
        "time_id",
        "full_timestamp",
        "day",
        "month",
        "quarter",
        "year",
        "day_of_week",
    ]
    df_dim_time = time_df[cols].drop_duplicates(subset=["time_id"])

    logger.info(f"-> Dim_Time hoàn tất: {len(df_dim_time):,} mốc thời gian.")
    return df_dim_time


def transform_fact_interactions(
    df_orders: pd.DataFrame,
    df_order_items: pd.DataFrame,
    df_customers: pd.DataFrame,
    df_reviews: Optional[pd.DataFrame] = None,
    valid_user_ids: Optional[set] = None,
    valid_product_ids: Optional[set] = None,
    valid_time_ids: Optional[set] = None,
) -> pd.DataFrame:
    """Tạo bảng Fact_Interactions ánh xạ chuẩn xác khóa ngoại tới các Dimension."""
    logger.info("Đang biến đổi bảng Fact_Interactions...")

    # 1. Join orders với customers để lấy user_id (customer_unique_id)
    orders = df_orders[["order_id", "customer_id", "order_purchase_timestamp"]].copy()
    cust_map = df_customers[["customer_id", "customer_unique_id"]].drop_duplicates()
    merged = orders.merge(cust_map, on="customer_id", how="inner")
    merged = merged.rename(columns={"customer_unique_id": "user_id"})

    # 2. Join với order_items để lấy thông tin sản phẩm và giá
    items = df_order_items[["order_id", "product_id", "price"]].copy()
    merged = merged.merge(items, on="order_id", how="inner")

    # 3. Join với reviews để lấy điểm đánh giá (nếu có)
    if df_reviews is not None and not df_reviews.empty:
        reviews = df_reviews[["order_id", "review_score"]].dropna().drop_duplicates(subset=["order_id"])
        merged = merged.merge(reviews, on="order_id", how="left")
    else:
        merged["review_score"] = np.nan

    # 4. Tính toán time_id từ order_purchase_timestamp (chống tràn 32-bit)
    ts = pd.to_datetime(merged["order_purchase_timestamp"])
    merged["time_id"] = (
        ts.dt.year.astype("int64") * 100000000
        + ts.dt.month.astype("int64") * 1000000
        + ts.dt.day.astype("int64") * 10000
        + ts.dt.hour.astype("int64") * 100
        + ts.dt.minute.astype("int64")
    )

    # 5. Thiết lập các trường nghiệp vụ
    merged["event_type"] = "purchase"
    merged["rating_value"] = merged["review_score"]
    merged["quantity"] = 1
    merged["total_amount"] = merged["price"].round(2)

    cols = [
        "user_id",
        "product_id",
        "time_id",
        "event_type",
        "rating_value",
        "quantity",
        "total_amount",
    ]
    df_fact = merged[cols].copy()
    df_fact.insert(0, "interaction_id", range(1, len(df_fact) + 1))

    # 6. Ràng buộc toàn vẹn tham chiếu (Referential Integrity Check)
    initial_count = len(df_fact)
    if valid_user_ids is not None:
        df_fact = df_fact[df_fact["user_id"].isin(valid_user_ids)]
    if valid_product_ids is not None:
        df_fact = df_fact[df_fact["product_id"].isin(valid_product_ids)]
    if valid_time_ids is not None:
        df_fact = df_fact[df_fact["time_id"].isin(valid_time_ids)]

    dropped_fk = initial_count - len(df_fact)
    if dropped_fk > 0:
        logger.warning(
            f"Đã lọc bỏ {dropped_fk:,} dòng vi phạm khóa ngoại tham chiếu Fact."
        )

    logger.info(
        f"-> Fact_Interactions hoàn tất: {len(df_fact):,} tương tác hợp lệ."
    )
    return df_fact


def transform_all(
    raw_data: dict[str, pd.DataFrame]
) -> dict[str, pd.DataFrame]:
    """Hàm tổng hợp biến đổi toàn bộ kho dữ liệu theo Star Schema."""
    logger.info("================ BẮT ĐẦU TRANSFORM TOÀN BỘ DWH ================")

    df_orders = raw_data["orders"]
    df_order_items = raw_data["order_items"]
    df_customers = raw_data["customers"]
    df_products = raw_data["products"]
    df_translation = raw_data.get("category_translation")
    df_reviews = raw_data.get("reviews")

    # 1. Transform Dim_Category
    dim_category = transform_dim_category(df_products, df_translation)
    valid_categories = set(dim_category["category_id"])

    # 2. Transform Dim_User
    dim_user = transform_dim_user(df_customers, df_orders)
    valid_users = set(dim_user["user_id"])

    # 3. Transform Dim_Product
    dim_product = transform_dim_product(
        df_products, df_order_items, df_translation, valid_categories
    )
    valid_products = set(dim_product["product_id"])

    # 4. Transform Dim_Time
    dim_time = transform_dim_time(df_orders["order_purchase_timestamp"])
    valid_times = set(dim_time["time_id"])

    # 5. Transform Fact_Interactions
    fact_interactions = transform_fact_interactions(
        df_orders=df_orders,
        df_order_items=df_order_items,
        df_customers=df_customers,
        df_reviews=df_reviews,
        valid_user_ids=valid_users,
        valid_product_ids=valid_products,
        valid_time_ids=valid_times,
    )

    logger.info("================ KẾT THÚC TRANSFORM THÀNH CÔNG ================")
    return {
        "dim_category": dim_category,
        "dim_user": dim_user,
        "dim_product": dim_product,
        "dim_time": dim_time,
        "fact_interactions": fact_interactions,
    }
