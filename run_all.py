"""Master Run Script - Khởi chạy toàn bộ hệ thống Kho Dữ Liệu & Khai Phá Dữ Liệu bằng một lệnh duy nhất.

Tuân thủ yêu cầu bắt buộc của Học phần INT1422 (Bài 12, Slide 12):
"Chạy lại được từ đầu bằng một lệnh là yêu cầu bắt buộc."

Quy trình tự động hóa (End-to-End Execution):
  Bước 1: Kiểm tra kết nối CSDL & Khởi tạo Lược đồ hình sao (Star Schema DDL).
  Bước 2: Chạy Multi-Source ETL Pipeline (Amazon Reviews, DummyJSON, Open Food Facts).
  Bước 3: Khởi tạo các View phân tích BI & Khối đa chiều OLAP Cubes (GROUP BY CUBE, ROLLUP).
  Bước 4: Chạy Khai phá dữ liệu (K-Means RFM Clustering & FP-Growth Association Rules).
  Bước 5: Huấn luyện và đánh giá mô hình Gợi ý sản phẩm (Collaborative & Content-Based).
  Bước 6: Khởi chạy Streamlit BI & Analytics Dashboard.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# Đảm bảo mã hóa UTF-8 trên Windows PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def print_banner(step_num: int, title: str):
    print("\n" + "=" * 80)
    print(f" [BƯỚC {step_num}/6] {title.upper()}")
    print("=" * 80)


def step1_init_database():
    print_banner(1, "Kiểm tra Kết nối CSDL & Áp dụng Lược đồ hình sao (Star Schema)")
    from src.database import engine, init_db, test_connection

    is_connected = test_connection()
    if is_connected:
        print("-> [OK] Kết nối Data Warehouse thành công (Docker PostgreSQL / SQLite).")
    else:
        print("-> [WARNING] Không thể kết nối PostgreSQL. Hệ thống sẽ tự động sử dụng SQLite dự phòng.")

    # Khởi tạo bảng DDL theo schema.sql
    init_db(drop_first=False)
    print("-> [OK] Đã xác nhận cấu trúc 5 bảng Star Schema: Dim_Category, Dim_User, Dim_Product, Dim_Time, Fact_Interactions.")


def step2_run_etl(sample_size: int, category: str, top_off: int):
    print_banner(2, "Trích xuất & Biến đổi dữ liệu đa nguồn (Multi-Source ETL)")
    from src.etl.pipeline import run_etl_pipeline

    summary = run_etl_pipeline(
        sample_size=sample_size,
        category=category,
        top_off=top_off,
        truncate_first=False,
    )
    print("-> [OK] ETL hoàn tất. Đã nạp thành công dữ liệu đa nguồn vào Kho Dữ Liệu.")


def step3_apply_bi_and_cubes():
    print_banner(3, "Xây dựng các View BI & Tính toán trước Khối đa chiều (OLAP Cubes)")
    from src.database import engine
    from sqlalchemy import text

    sql_files = ["sql/bi_views.sql", "sql/olap_cubes.sql"]
    with engine.connect() as conn:
        for sql_file in sql_files:
            file_path = PROJECT_ROOT / sql_file
            if file_path.exists():
                sql_content = file_path.read_text(encoding="utf-8")
                statements = [s.strip() for s in sql_content.split(";") if s.strip()]
                for s in statements:
                    conn.execute(text(s))
                print(f"-> [OK] Đã biên dịch & tính toán xong: {sql_file}")
        conn.commit()


def step4_run_data_mining():
    print_banner(4, "Khai phá dữ liệu: K-Means RFM Phân cụm & FP-Growth Luật kết hợp")
    from src.mining.rfm_clustering import run_rfm_pipeline
    from src.mining.association_rules import run_market_basket_analysis

    print("1. Đang phân cụm khách hàng RFM...")
    rfm_df, profiles = run_rfm_pipeline(n_clusters=4, evaluate_k=False)
    print("-> [OK] K-Means hoàn thành với 4 cụm. Đã gán nhãn rfm_segment vào Dim_User.")

    print("\n2. Đang khai phá luật kết hợp giỏ hàng FP-Growth...")
    rules_df = run_market_basket_analysis(item_column="category_id", algorithm="fpgrowth", min_support=0.005, min_lift=1.1)
    print(f"-> [OK] FP-Growth tìm thấy {len(rules_df):,} luật kết hợp mua kèm có Lift > 1.1x.")


def step5_evaluate_recommender():
    print_banner(5, "Huấn luyện & Đánh giá Offline Mô hình Gợi ý")
    from src.recommender.run_phase4 import run_cf_pipeline, run_cb_pipeline, run_full_evaluation

    cf_model, df_train, df_test = run_cf_pipeline(n_components=50, top_k=10)
    cb_model = run_cb_pipeline(top_k=10)
    df_eval = run_full_evaluation(cf_model, cb_model, df_train, df_test, k_values=[5, 10, 20])

    out_csv = PROJECT_ROOT / "data" / "processed" / "evaluation_results.csv"
    df_eval.to_csv(out_csv, index=False, encoding="utf-8")
    print(f"-> [OK] Đã lưu kết quả đo lường Offline vào {out_csv.name}.")


def step6_launch_dashboard():
    print_banner(6, "Khởi chạy Streamlit BI & OLAP Analytics Dashboard")
    cmd = [sys.executable, "-m", "streamlit", "run", "src/ui/dashboard.py", "--server.port", "8501"]
    print(f"Đang mở giao diện Streamlit tại: http://localhost:8501\n")
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n[INFO] Đã dừng ứng dụng Streamlit.")


def main():
    parser = argparse.ArgumentParser(description="Chạy toàn bộ dự án Kho dữ liệu & Khai phá dữ liệu.")
    parser.add_argument("--sample", type=int, default=10000, help="Số lượng bản ghi Amazon Reviews (mặc định: 10000)")
    parser.add_argument("--category", type=str, default="All_Beauty", help="Ngành hàng Amazon (mặc định: All_Beauty)")
    parser.add_argument("--top-off", type=int, default=50, help="Số sản phẩm làm giàu Open Food Facts (mặc định: 50)")
    parser.add_argument("--skip-etl", action="store_true", help="Bỏ qua bước ETL nếu DWH đã có sẵn dữ liệu")
    parser.add_argument("--no-ui", action="store_true", help="Chỉ chạy pipeline mà không bật giao diện Streamlit")

    args = parser.parse_args()
    start_time = time.time()

    print("=" * 80)
    print(" HỌC VIỆN CÔNG NGHỆ BƯU CHÍNH VIỄN THÔNG - KHOA CNTT 1")
    print(" BÀI TẬP LỚN MÔN: KHO DỮ LIỆU VÀ KHAI PHÁ DỮ LIỆU (INT1422)")
    print(" Đề tài: Hệ thống Kho Dữ Liệu & Phân Tích BI Thương Mại Điện Tử Đa Nguồn")
    print("=" * 80)

    # Thực thi tuần tự các bước
    step1_init_database()

    if not args.skip_etl:
        step2_run_etl(args.sample, args.category, args.top_off)
    else:
        print("\n-> [SKIP] Bỏ qua bước ETL theo yêu cầu tham số --skip-etl.")

    step3_apply_bi_and_cubes()
    step4_run_data_mining()
    step5_evaluate_recommender()

    elapsed = time.time() - start_time
    print("\n" + "=" * 80)
    print(f" TẤT CẢ CÁC BƯỚC ĐÃ HOÀN TẤT THÀNH CÔNG TRONG {elapsed:.2f} GIÂY!")
    print("=" * 80)

    if not args.no_ui:
        step6_launch_dashboard()


if __name__ == "__main__":
    main()
