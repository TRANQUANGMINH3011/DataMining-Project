"""Phân cụm khách hàng RFM (Recency, Frequency, Monetary) kết hợp K-Means Clustering."""

import logging
import sys
from pathlib import Path
from typing import Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text

from src.database import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("Mining.RFM")


def calculate_rfm_from_dwh(engine_instance=None) -> pd.DataFrame:
    """Truy vấn DWH để tính các chỉ số RFM cho từng khách hàng.

    Recency: Số ngày kể từ lần mua gần nhất đến ngày chốt mốc dữ liệu.
    Frequency: Tổng số giao dịch mua hàng của người dùng.
    Monetary: Tổng số tiền người dùng đã chi tiêu.
    """
    logger.info("Đang tính toán chỉ số RFM từ Data Warehouse...")
    if engine_instance is None:
        engine_instance = engine

    sql_query = """
    SELECT 
        f.user_id,
        MAX(t.full_timestamp) AS last_purchase_date,
        COUNT(f.product_id) AS frequency,
        SUM(COALESCE(p.price, 19.99)) AS monetary
    FROM fact_interactions f
    JOIN dim_time t ON f.time_id = t.time_id
    LEFT JOIN dim_product p ON f.product_id = p.product_id
    GROUP BY f.user_id;
    """

    rfm_df = pd.DataFrame()
    try:
        with engine_instance.connect() as conn:
            rfm_df = pd.read_sql_query(text(sql_query), conn)
    except Exception as exc:
        logger.warning(f"Không thể truy vấn trực tiếp từ database: {exc}. Đang đọc từ Staging...")

    # Dự phòng đọc từ Staging Parquet/CSV nếu database chưa có dữ liệu
    if rfm_df.empty:
        project_root = Path(__file__).resolve().parent.parent.parent
        processed_dir = project_root / "data" / "processed"

        fact_path = processed_dir / "fact_interactions.parquet"
        time_path = processed_dir / "dim_time.parquet"
        prod_path = processed_dir / "dim_product.parquet"
        if not fact_path.exists():
            fact_path = processed_dir / "fact_interactions.csv"
            time_path = processed_dir / "dim_time.csv"
            prod_path = processed_dir / "dim_product.csv"

        if fact_path.exists() and time_path.exists():
            logger.info("Đang nạp dữ liệu từ Staging để tính RFM...")
            df_fact = pd.read_parquet(fact_path) if fact_path.suffix == ".parquet" else pd.read_csv(fact_path)
            df_time = pd.read_parquet(time_path) if time_path.suffix == ".parquet" else pd.read_csv(time_path)

            merged = df_fact.merge(df_time, on="time_id", how="inner")
            if prod_path.exists():
                df_prod = pd.read_parquet(prod_path) if prod_path.suffix == ".parquet" else pd.read_csv(prod_path)
                merged = merged.merge(df_prod[["product_id", "price"]], on="product_id", how="left")
            else:
                merged["price"] = 19.99

            merged["full_timestamp"] = pd.to_datetime(merged["full_timestamp"])
            merged["monetary"] = pd.to_numeric(merged.get("total_amount", merged["price"]), errors="coerce").fillna(19.99)

            rfm_df = merged.groupby("user_id").agg(
                last_purchase_date=("full_timestamp", "max"),
                frequency=("product_id", "count"),
                monetary=("monetary", "sum"),
            ).reset_index()
        else:
            raise FileNotFoundError("Không tìm thấy dữ liệu Fact và Dim_Time để tính RFM.")

    # Tính toán Recency so với ngày snapshot (ngày cuối cùng + 1 ngày)
    rfm_df["last_purchase_date"] = pd.to_datetime(rfm_df["last_purchase_date"])
    snapshot_date = rfm_df["last_purchase_date"].max() + pd.Timedelta(days=1)
    rfm_df["recency"] = (snapshot_date - rfm_df["last_purchase_date"]).dt.days

    rfm_df["frequency"] = rfm_df["frequency"].astype(int)
    rfm_df["monetary"] = rfm_df["monetary"].round(2)

    result = rfm_df[["user_id", "recency", "frequency", "monetary"]].copy()
    logger.info(f"-> Đã tính toán xong chỉ số RFM cho {len(result):,} khách hàng.")
    return result


def preprocess_rfm(rfm_df: pd.DataFrame) -> Tuple[np.ndarray, StandardScaler]:
    """Xử lý phân phối lệch bằng Log transform và chuẩn hóa bằng StandardScaler."""
    features = rfm_df[["recency", "frequency", "monetary"]].copy()

    # Log transform để giảm độ lệch phải (Right-skewness)
    features_log = np.log1p(features)

    # Chuẩn hóa về mean=0, std=1
    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(features_log)
    return scaled_data, scaler


def find_optimal_k(scaled_data: np.ndarray, k_range=range(2, 9)) -> dict:
    """Đánh giá và tìm K tối ưu qua phương pháp Elbow (Inertia) và Silhouette score."""
    logger.info("Đang đánh giá số cụm K tối ưu qua Elbow và Silhouette...")
    metrics = {"k": [], "inertia": [], "silhouette": []}

    print("\n--- BẢNG ĐÁNH GIÁ SỐ CỤM K TỐI ƯU ---")
    print(f" {'K':<4} | {'Inertia (WCSS)':<16} | {'Silhouette Score':<16} ")
    print("-" * 42)

    best_k = 4
    best_silhouette = -1.0

    for k in k_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(scaled_data)
        inertia = kmeans.inertia_
        sil = silhouette_score(scaled_data, labels, sample_size=10000, random_state=42)

        metrics["k"].append(k)
        metrics["inertia"].append(round(inertia, 2))
        metrics["silhouette"].append(round(sil, 4))

        print(f" {k:<4} | {inertia:<16.2f} | {sil:<16.4f}")

        if sil > best_silhouette:
            best_silhouette = sil
            best_k = k

    print("-" * 42)
    logger.info(f"-> Gợi ý số cụm K tốt nhất theo Silhouette: K={best_k} (Score: {best_silhouette:.4f})")
    metrics["best_k"] = best_k
    return metrics


def assign_business_segments(cluster_summary: pd.DataFrame) -> dict:
    """Gán nhãn nghiệp vụ (Business Segment Labels) dựa trên hồ sơ trung bình của từng cụm.

    Nhãn:
      - Champions (VIP): R thấp nhất (mới mua), F cao, M cao
      - Loyal Customers: F khá, M khá, R vừa
      - Potential Loyalists: R mới, F thấp, M trung bình
      - At Risk: R cao (đã lâu không mua), trước đây có F hoặc M khá
      - Lost: R rất cao, F thấp, M thấp
    """
    sorted_by_r = cluster_summary.sort_values(by="recency_mean", ascending=True).index.tolist()
    sorted_by_m = cluster_summary.sort_values(by="monetary_mean", ascending=False).index.tolist()

    label_map = {}
    used_clusters = set()

    # Cụm VIP / Champions: Monetary cao nhất và Recency tương đối tốt
    champ_cluster = sorted_by_m[0]
    label_map[champ_cluster] = "Champions (VIP)"
    used_clusters.add(champ_cluster)

    # Cụm mua gần đây nhất (Recent Buyers / Potential)
    for c in sorted_by_r:
        if c not in used_clusters:
            label_map[c] = "Potential Loyalists"
            used_clusters.add(c)
            break

    # Cụm có nguy cơ rời bỏ (At Risk)
    for c in reversed(sorted_by_r):
        if c not in used_clusters:
            label_map[c] = "At Risk / Inactive"
            used_clusters.add(c)
            break

    # Các cụm còn lại
    remaining = [c for c in cluster_summary.index if c not in used_clusters]
    for idx, c in enumerate(remaining):
        if idx == 0:
            label_map[c] = "Loyal Customers"
        else:
            label_map[c] = "Standard Customers"

    return label_map


def fit_rfm_kmeans(
    rfm_df: pd.DataFrame,
    n_clusters: int = 4,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, KMeans]:
    """Huấn luyện mô hình K-Means và tạo báo cáo hồ sơ các cụm (Cluster Profiles)."""
    logger.info(f"Đang phân cụm khách hàng với K={n_clusters}...")
    scaled_data, scaler = preprocess_rfm(rfm_df)

    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    rfm_result = rfm_df.copy()
    rfm_result["cluster"] = kmeans.fit_predict(scaled_data)

    # Thống kê hồ sơ các cụm (Cluster Profiles)
    profiles = (
        rfm_result.groupby("cluster")
        .agg(
            customer_count=("user_id", "count"),
            recency_mean=("recency", "mean"),
            recency_median=("recency", "median"),
            frequency_mean=("frequency", "mean"),
            monetary_mean=("monetary", "mean"),
            monetary_median=("monetary", "median"),
            total_revenue=("monetary", "sum"),
        )
        .round(2)
    )

    profiles["customer_percentage"] = (
        profiles["customer_count"] / len(rfm_result) * 100
    ).round(2)
    profiles["revenue_percentage"] = (
        profiles["total_revenue"] / rfm_result["monetary"].sum() * 100
    ).round(2)

    # Gán nhãn ngữ nghĩa nghiệp vụ
    labels_dict = assign_business_segments(profiles)
    profiles["segment_name"] = profiles.index.map(labels_dict)
    rfm_result["rfm_segment"] = rfm_result["cluster"].map(labels_dict)

    # In báo cáo đặc trưng các cụm
    print("\n" + "=" * 95)
    print(" BÁO CÁO HỒ SƠ PHÂN CỤM KHÁCH HÀNG (CUSTOMER CLUSTER PROFILES)")
    print("=" * 95)
    for c_id, row in profiles.iterrows():
        print(f" Cụm {c_id}: [{row['segment_name']}]")
        print(
            f"   - Quy mô         : {int(row['customer_count']):,} khách "
            f"({row['customer_percentage']}%) | Đóng góp DT: {row['revenue_percentage']}%"
        )
        print(
            f"   - Recency TB     : {row['recency_mean']:.1f} ngày (Trung vị: {row['recency_median']:.1f})"
        )
        print(f"   - Frequency TB   : {row['frequency_mean']:.2f} đơn hàng")
        print(
            f"   - Monetary TB    : ${row['monetary_mean']:,.2f} (Trung vị: ${row['monetary_median']:,.2f})"
        )
        print("-" * 95)

    return rfm_result, profiles, kmeans


def save_rfm_to_dwh(rfm_result: pd.DataFrame, engine_instance=None):
    """Lưu kết quả phân cụm RFM vào file staging và cập nhật vào Dim_User trong DWH."""
    project_root = Path(__file__).resolve().parent.parent.parent
    processed_dir = project_root / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    # 1. Lưu ra CSV
    out_csv = processed_dir / "rfm_clusters.csv"
    rfm_result.to_csv(out_csv, index=False, encoding="utf-8")
    logger.info(f"Đã lưu kết quả phân cụm RFM vào: {out_csv.resolve()}")

    # 2. Cập nhật trường rfm_segment trong bảng Dim_User
    if engine_instance is None:
        engine_instance = engine

    try:
        logger.info("Đang cập nhật nhãn phân khúc RFM vào bảng Dim_User trong DWH...")
        with engine_instance.connect() as conn:
            # Batch update qua bảng tạm để tối ưu tốc độ
            rfm_result[["user_id", "rfm_segment"]].to_sql(
                name="temp_rfm_update",
                con=conn,
                if_exists="replace",
                index=False,
                chunksize=5000,
                method="multi",
            )
            if engine_instance.dialect.name == "postgresql":
                update_sql = """
                UPDATE dim_user
                SET rfm_segment = temp_rfm_update.rfm_segment
                FROM temp_rfm_update
                WHERE dim_user.user_id = temp_rfm_update.user_id;
                """
            else:
                update_sql = """
                UPDATE dim_user
                SET rfm_segment = (
                    SELECT rfm_segment FROM temp_rfm_update 
                    WHERE temp_rfm_update.user_id = dim_user.user_id
                )
                WHERE user_id IN (SELECT user_id FROM temp_rfm_update);
                """
            conn.execute(text(update_sql))
            # Dọn dẹp bảng tạm
            conn.execute(text("DROP TABLE IF EXISTS temp_rfm_update;"))
            conn.commit()
            logger.info(" Cập nhật Dim_User.rfm_segment thành công!")
    except Exception as exc:
        logger.warning(f"Không thể cập nhật trực tiếp vào database: {exc}")


def run_rfm_pipeline(n_clusters: int = 4, evaluate_k: bool = True):
    """Chạy toàn bộ pipeline phân cụm khách hàng RFM."""
    rfm_df = calculate_rfm_from_dwh()
    scaled_data, _ = preprocess_rfm(rfm_df)

    if evaluate_k:
        find_optimal_k(scaled_data, k_range=range(2, 7))

    rfm_result, profiles, _ = fit_rfm_kmeans(rfm_df, n_clusters=n_clusters)
    save_rfm_to_dwh(rfm_result)
    return rfm_result, profiles


if __name__ == "__main__":
    run_rfm_pipeline(n_clusters=4, evaluate_k=True)
