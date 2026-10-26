"""Pipeline ETL tự động hóa toàn diện từ 3 nguồn dữ liệu lớn vào Kho Dữ Liệu Star Schema:

1. Extract:
   - Amazon Reviews 2023 (Hugging Face)
   - DummyJSON Users (REST API)
   - Open Food Facts (REST API)
2. Transform:
   - Làm sạch, khử trùng lặp, chuẩn hóa kiểu dữ liệu
   - Ghép nối nhân khẩu học vào Dim_User (Round-robin)
   - Tích hợp thành phần dinh dưỡng vào Dim_Product & Dim_Category
   - Phân rã lịch thời gian vào Dim_Time
   - Ánh xạ khóa ngoại chuẩn xác vào Fact_Interactions
3. Validate:
   - Kiểm định 100% tính toàn vẹn tham chiếu và tỷ lệ Missing Data
4. Load:
   - Bulk-loading nạp vào PostgreSQL / MySQL / SQLite DWH với chunksize=5000, method='multi'
"""

import argparse
import logging
import sys
import time
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.database import engine, init_db, test_connection
from src.etl.extract import (
    enrich_top_products,
    extract_amazon_metadata,
    extract_amazon_reviews,
    fetch_dummyjson_users,
)
from src.etl.load import load_dwh, save_processed_staging
from src.etl.transform import transform_all
from src.etl.validate import run_data_quality_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ETL.Pipeline")


def run_etl_pipeline(
    sample_size: int = 50000,
    category: str = "All_Beauty",
    top_off: int = 100,
    truncate_first: bool = False,
    skip_db_load: bool = False,
) -> dict:
    """Thực thi toàn bộ luồng ETL End-to-End từ 3 nguồn vào Data Warehouse.

    Args:
        sample_size: Số lượng bản ghi mẫu reviews từ Amazon (mặc định 50,000 dòng).
        category: Ngành hàng Amazon (mặc định 'All_Beauty').
        top_off: Số lượng sản phẩm phổ biến nhất cần làm giàu qua Open Food Facts (mặc định 100).
        truncate_first: Có xóa sạch dữ liệu cũ trong DWH trước khi nạp không.
        skip_db_load: Chỉ trích xuất, biến đổi và lưu Parquet staging (không insert vào DB).

    Returns:
        dict thống kê chi tiết thời gian và quy mô bản ghi từng giai đoạn.
    """
    total_start_time = time.time()
    summary = {
        "sample_size": sample_size,
        "category": category,
        "durations": {},
        "records": {},
    }

    print("\n" + "=" * 80)
    print(" BẮT ĐẦU THỰC THI MULTI-SOURCE ETL PIPELINE VÀO DATA WAREHOUSE")
    print(f" Cấu hình: Sample={sample_size:,} | Ngành hàng: {category} | Top OFF: {top_off}")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 1: EXTRACT (TRÍCH XUẤT TỪ 3 NGUỒN)
    # --------------------------------------------------------------------------
    t0 = time.time()
    logger.info(">>> GIAI ĐOẠN 1: EXTRACT (Đọc dữ liệu từ 3 nguồn: Amazon, DummyJSON, Open Food Facts)")

    # 1.1 Amazon Reviews
    raw_reviews = extract_amazon_reviews(category=category, sample_size=sample_size)
    summary["records"]["raw_amazon_reviews"] = len(raw_reviews)

    # 1.2 Amazon Metadata
    raw_meta = extract_amazon_metadata(category=category, sample_size=sample_size)
    summary["records"]["raw_amazon_metadata"] = len(raw_meta)

    # 1.3 DummyJSON Users
    raw_users = fetch_dummyjson_users(limit=100)
    summary["records"]["raw_dummyjson_users"] = len(raw_users)

    # 1.4 Open Food Facts (làm giàu cho Top N sản phẩm phổ biến)
    top_products_list = []
    if not raw_reviews.empty and not raw_meta.empty:
        top_asin_counts = raw_reviews["parent_asin"].value_counts().head(top_off).index.tolist()
        meta_subset = raw_meta[raw_meta["parent_asin"].isin(top_asin_counts)]
        for _, row in meta_subset.iterrows():
            top_products_list.append({
                "product_id": str(row["parent_asin"]),
                "product_name": str(row["title"]),
            })

    raw_off = enrich_top_products(top_products_list, top_n=top_off)
    summary["records"]["raw_off_enriched"] = len(raw_off)

    extract_duration = time.time() - t0
    summary["durations"]["extract"] = round(extract_duration, 2)
    logger.info(f" Hoàn tất Extract trong {extract_duration:.2f} giây.\n")

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 2: TRANSFORM & MERGE (GHÉP NỐI & CHUẨN HÓA STAR SCHEMA)
    # --------------------------------------------------------------------------
    t0 = time.time()
    logger.info(">>> GIAI ĐOẠN 2: TRANSFORM (Làm sạch, ghép nối nhân khẩu & phân rã Dim/Fact)")
    transformed_tables = transform_all(
        raw_reviews=raw_reviews,
        raw_metadata=raw_meta,
        raw_dummyjson_users=raw_users,
        raw_off_enriched=raw_off,
    )
    transform_duration = time.time() - t0
    summary["durations"]["transform"] = round(transform_duration, 2)
    for k, df in transformed_tables.items():
        summary["records"][k] = len(df)
    logger.info(f" Hoàn tất Transform trong {transform_duration:.2f} giây.\n")

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 3: VALIDATE (KIỂM ĐỊNH TOÀN VẸN THAM CHIẾU VÀ TỶ LỆ NULL)
    # --------------------------------------------------------------------------
    t0 = time.time()
    logger.info(">>> GIAI ĐOẠN 3: VALIDATE (Kiểm tra chất lượng trước khi nạp)")
    is_valid = run_data_quality_report(transformed_tables)
    validate_duration = time.time() - t0
    summary["durations"]["validate"] = round(validate_duration, 2)
    summary["quality_status"] = "PASSED" if is_valid else "WARNINGS"
    logger.info(f" Hoàn tất Validate trong {validate_duration:.2f} giây.\n")

    # Lưu trữ bản sao staging Parquet và CSV vào data/processed/
    save_processed_staging(transformed_tables)
    logger.info(" Đã lưu bản sao Parquet vào thư mục 'data/processed/'.\n")

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 4: LOAD (NẠP VÀO POSTGRESQL / MYSQL / SQLITE DWH)
    # --------------------------------------------------------------------------
    if not skip_db_load:
        t0 = time.time()
        logger.info(">>> GIAI ĐOẠN 4: LOAD (Bulk loading vào Data Warehouse)")
        is_connected = test_connection()

        if is_connected:
            # Khởi tạo bảng DDL nếu chưa có (nếu truncate thì drop tái tạo bảng mới)
            init_db(drop_first=truncate_first)
            loaded_counts = load_dwh(
                tables=transformed_tables,
                engine=engine,
                truncate_first=truncate_first,
                chunksize=5000,
            )
            load_duration = time.time() - t0
            summary["durations"]["load"] = round(load_duration, 2)
            summary["loaded_to_db"] = loaded_counts
            logger.info(f" Hoàn tất Load DWH trong {load_duration:.2f} giây.\n")
        else:
            logger.warning(" Không thể kết nối cơ sở dữ liệu. Dữ liệu đã lưu tại 'data/processed/'")
            summary["durations"]["load"] = 0.0
            summary["loaded_to_db"] = "DB Offline (Saved to Staging)"
    else:
        logger.info(" [Bỏ qua nạp DB theo cấu hình --skip-load]")
        summary["durations"]["load"] = 0.0
        summary["loaded_to_db"] = "Skipped"

    # --------------------------------------------------------------------------
    # BẢNG TỔNG KẾT HIỆU NĂNG THỰC THI (EXECUTIVE SUMMARY)
    # --------------------------------------------------------------------------
    total_duration = time.time() - total_start_time
    summary["durations"]["total"] = round(total_duration, 2)

    print("\n" + "=" * 80)
    print(" BẢNG TỔNG KẾT HIỆU NĂNG ETL PIPELINE (MULTI-SOURCE)")
    print("=" * 80)
    print(f" Ngành hàng xử lý   : {summary['category']}")
    print(f" Tổng thời gian chạy : {total_duration:.2f} giây")
    print(f"   * Extract        : {summary['durations']['extract']:.2f} s")
    print(f"   * Transform      : {summary['durations']['transform']:.2f} s")
    print(f"   * Validate       : {summary['durations']['validate']:.2f} s")
    print(f"   * Load DWH       : {summary['durations']['load']:.2f} s")
    print("-" * 80)
    print(" THỐNG KÊ BẢN GHI STAR SCHEMA:")
    print(f"   * Dim_Category       : {summary['records'].get('dim_category', 0):,} dòng")
    print(f"   * Dim_User           : {summary['records'].get('dim_user', 0):,} dòng")
    print(f"   * Dim_Product        : {summary['records'].get('dim_product', 0):,} dòng")
    print(f"   * Dim_Time           : {summary['records'].get('dim_time', 0):,} dòng")
    print(f"   * Fact_Interactions  : {summary['records'].get('fact_interactions', 0):,} dòng")
    print("=" * 80 + "\n")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Chạy Multi-Source ETL Pipeline cho Data Warehouse")
    parser.add_argument(
        "--sample",
        type=int,
        default=50000,
        help="Số lượng bản ghi reviews mẫu (mặc định: 50000, có thể chỉnh 1000 để test nhanh)",
    )
    parser.add_argument(
        "--category",
        type=str,
        default="All_Beauty",
        help="Ngành hàng Amazon Reviews (ví dụ: All_Beauty, Appliances, Grocery_and_Gourmet_Food)",
    )
    parser.add_argument(
        "--top-off",
        type=int,
        default=100,
        help="Số lượng sản phẩm phổ biến nhất làm giàu từ Open Food Facts (mặc định: 100)",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Xóa sạch dữ liệu cũ trong DWH trước khi nạp",
    )
    parser.add_argument(
        "--skip-load",
        action="store_true",
        help="Chỉ trích xuất, làm sạch và lưu Staging Parquet, không nạp vào DB",
    )
    args = parser.parse_args()

    run_etl_pipeline(
        sample_size=args.sample,
        category=args.category,
        top_off=args.top_off,
        truncate_first=args.truncate,
        skip_db_load=args.skip_load,
    )


if __name__ == "__main__":
    main()
