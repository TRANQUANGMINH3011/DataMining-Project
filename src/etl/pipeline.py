import argparse
import logging
import sys
import time
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.database import engine, test_connection, init_db
from src.etl.extract import extract_raw_dataset
from src.etl.load import load_dwh, save_processed_staging
from src.etl.transform import transform_all
from src.etl.validate import run_data_quality_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ETL.Pipeline")


def run_etl_pipeline(
    sample_size: Optional[int] = None,
    truncate_first: bool = False,
    skip_db_load: bool = False,
) -> dict:
    """Chạy toàn bộ pipeline ETL end-to-end.

    Args:
        sample_size: Số lượng bản ghi lấy mẫu (None để chạy full dataset).
        truncate_first: Có xóa trắng dữ liệu cũ trong DWH trước khi nạp không.
        skip_db_load: Chỉ extract, transform và lưu file staging Parquet (không insert DB).

    Returns:
        dict thống kê thời gian và số lượng dòng của từng giai đoạn.
    """
    total_start_time = time.time()
    summary = {
        "sample_size": sample_size if sample_size else "FULL DATASET",
        "durations": {},
        "records": {},
    }

    print("\n" + "=" * 80)
    print(" BẮT ĐẦU THỰC THI ETL PIPELINE - HỆ THỐNG KHO DỮ LIỆU THƯƠNG MẠI ĐIỆN TỬ")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # BƯỚC 1: EXTRACT (TRÍCH XUẤT DỮ LIỆU NGUỒN)
    # --------------------------------------------------------------------------
    t0 = time.time()
    logger.info(">>> GIAI ĐOẠN 1: EXTRACT (Đọc dữ liệu nguồn)")
    raw_data = extract_raw_dataset(sample_size=sample_size)
    extract_duration = time.time() - t0
    summary["durations"]["extract"] = round(extract_duration, 2)
    for k, df in raw_data.items():
        summary["records"][f"raw_{k}"] = len(df)
    logger.info(f" Hoàn tất Extract trong {extract_duration:.2f} giây.\n")

    # --------------------------------------------------------------------------
    # BƯỚC 2: TRANSFORM (LÀM SẠCH VÀ TẠO BẢNG STAR SCHEMA)
    # --------------------------------------------------------------------------
    t0 = time.time()
    logger.info(">>> GIAI ĐOẠN 2: TRANSFORM (Làm sạch, phân rã Dim & Fact)")
    transformed_tables = transform_all(raw_data)
    transform_duration = time.time() - t0
    summary["durations"]["transform"] = round(transform_duration, 2)
    for k, df in transformed_tables.items():
        summary["records"][k] = len(df)
    logger.info(f" Hoàn tất Transform trong {transform_duration:.2f} giây.\n")

    # --------------------------------------------------------------------------
    # BƯỚC 3: VALIDATE (KIỂM ĐỊNH TOÀN VẸN THAM CHIẾU VÀ NULL)
    # --------------------------------------------------------------------------
    t0 = time.time()
    logger.info(">>> GIAI ĐOẠN 3: VALIDATE (Kiểm tra chất lượng trước khi nạp)")
    is_valid = run_data_quality_report(transformed_tables)
    validate_duration = time.time() - t0
    summary["durations"]["validate"] = round(validate_duration, 2)
    summary["quality_status"] = "PASSED" if is_valid else "WARNINGS"
    logger.info(f" Hoàn tất Validate trong {validate_duration:.2f} giây.\n")

    # Lưu trữ staging Parquet tại data/processed/
    save_processed_staging(transformed_tables)
    logger.info(" Đã lưu bản sao Parquet vào thư mục 'data/processed/'.\n")

    # --------------------------------------------------------------------------
    # BƯỚC 4: LOAD (NẠP DỮ LIỆU VÀO POSTGRESQL DATA WAREHOUSE)
    # --------------------------------------------------------------------------
    if not skip_db_load:
        t0 = time.time()
        logger.info(">>> GIAI ĐOẠN 4: LOAD (Bulk loading vào PostgreSQL DWH)")
        is_connected = test_connection()

        if is_connected:
            # Khởi tạo bảng nếu chưa có
            init_db()
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
            logger.warning(
                " Không thể kết nối tới PostgreSQL container. Dữ liệu sạch đã được "
                "bảo toàn trong 'data/processed/' để sẵn sàng nạp khi Docker bật."
            )
            summary["durations"]["load"] = 0.0
            summary["loaded_to_db"] = "PostgreSQL Offline (Saved to Parquet Staging)"
    else:
        logger.info(" [Bỏ qua nạp DB theo cấu hình --skip-load]")
        summary["durations"]["load"] = 0.0
        summary["loaded_to_db"] = "Skipped"

    # --------------------------------------------------------------------------
    # BẢNG TỔNG KẾT THỰC THI (EXECUTIVE SUMMARY)
    # --------------------------------------------------------------------------
    total_duration = time.time() - total_start_time
    summary["durations"]["total"] = round(total_duration, 2)

    print("\n" + "=" * 80)
    print(" BẢNG TỔNG KẾT HIỆU NĂNG ETL PIPELINE")
    print("=" * 80)
    print(f" Quy mô xử lý       : {summary['sample_size']}")
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
    parser = argparse.ArgumentParser(description="Chạy ETL Pipeline cho Data Warehouse")
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Giới hạn số dòng dữ liệu để thử nghiệm nhanh (ví dụ: --sample 5000)",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Xóa sạch dữ liệu cũ trong DWH trước khi nạp",
    )
    parser.add_argument(
        "--skip-load",
        action="store_true",
        help="Chỉ trích xuất, làm sạch và lưu Parquet, không nạp vào database",
    )
    args = parser.parse_args()

    run_etl_pipeline(
        sample_size=args.sample,
        truncate_first=args.truncate,
        skip_db_load=args.skip_load,
    )


if __name__ == "__main__":
    main()
