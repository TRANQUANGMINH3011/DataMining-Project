import logging
import sys
from typing import Optional, Union

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ETL.Validate")


def validate_referential_integrity(
    source: Union[dict[str, pd.DataFrame], Engine]
) -> dict[str, dict]:
    """Kiểm tra tính toàn vẹn tham chiếu (Referential Integrity).

    Có thể kiểm tra trực tiếp trên Database Engine qua SQL hoặc trên dict DataFrame.
    """
    logger.info("Đang kiểm tra tính toàn vẹn tham chiếu (Referential Integrity)...")
    results = {}

    if isinstance(source, Engine):
        # Kiểm tra thông qua các câu truy vấn SQL trên PostgreSQL
        checks = [
            (
                "Fact -> Dim_User",
                """
                SELECT count(*) FROM fact_interactions f
                LEFT JOIN dim_user u ON f.user_id = u.user_id
                WHERE u.user_id IS NULL;
                """,
            ),
            (
                "Fact -> Dim_Product",
                """
                SELECT count(*) FROM fact_interactions f
                LEFT JOIN dim_product p ON f.product_id = p.product_id
                WHERE p.product_id IS NULL;
                """,
            ),
            (
                "Fact -> Dim_Time",
                """
                SELECT count(*) FROM fact_interactions f
                LEFT JOIN dim_time t ON f.time_id = t.time_id
                WHERE t.time_id IS NULL;
                """,
            ),
            (
                "Dim_Product -> Dim_Category",
                """
                SELECT count(*) FROM dim_product p
                LEFT JOIN dim_category c ON p.category_id = c.category_id
                WHERE p.category_id IS NOT NULL AND c.category_id IS NULL;
                """,
            ),
        ]

        with source.connect() as conn:
            for check_name, sql in checks:
                try:
                    orphans = conn.execute(text(sql)).scalar()
                    results[check_name] = {
                        "orphan_count": orphans,
                        "status": "PASSED" if orphans == 0 else "FAILED",
                    }
                except Exception as exc:
                    results[check_name] = {"error": str(exc), "status": "ERROR"}

    elif isinstance(source, dict):
        # Kiểm tra trên tập các DataFrame
        users = set(source["dim_user"]["user_id"])
        products = set(source["dim_product"]["product_id"])
        times = set(source["dim_time"]["time_id"])
        categories = set(source["dim_category"]["category_id"])
        fact = source["fact_interactions"]
        prod_df = source["dim_product"]

        orphan_users = (~fact["user_id"].isin(users)).sum()
        orphan_prods = (~fact["product_id"].isin(products)).sum()
        orphan_times = (~fact["time_id"].isin(times)).sum()
        orphan_cats = (~prod_df["category_id"].dropna().isin(categories)).sum()

        results["Fact -> Dim_User"] = {
            "orphan_count": int(orphan_users),
            "status": "PASSED" if orphan_users == 0 else "FAILED",
        }
        results["Fact -> Dim_Product"] = {
            "orphan_count": int(orphan_prods),
            "status": "PASSED" if orphan_prods == 0 else "FAILED",
        }
        results["Fact -> Dim_Time"] = {
            "orphan_count": int(orphan_times),
            "status": "PASSED" if orphan_times == 0 else "FAILED",
        }
        results["Dim_Product -> Dim_Category"] = {
            "orphan_count": int(orphan_cats),
            "status": "PASSED" if orphan_cats == 0 else "FAILED",
        }

    return results


def validate_null_rates(
    source: Union[dict[str, pd.DataFrame], Engine]
) -> pd.DataFrame:
    """Kiểm tra tỷ lệ giá trị NULL trên các cột của từng bảng."""
    logger.info("Đang kiểm tra tỷ lệ giá trị NULL trên các bảng...")
    null_records = []

    if isinstance(source, dict):
        for table_name, df in source.items():
            total = len(df)
            for col in df.columns:
                null_cnt = int(df[col].isnull().sum())
                null_pct = (null_cnt / total * 100) if total > 0 else 0.0
                null_records.append(
                    {
                        "table": table_name,
                        "column": col,
                        "total_rows": total,
                        "null_count": null_cnt,
                        "null_percent": round(null_pct, 2),
                    }
                )

    elif isinstance(source, Engine):
        tables = [
            "dim_category",
            "dim_user",
            "dim_product",
            "dim_time",
            "fact_interactions",
        ]
        with source.connect() as conn:
            for tbl in tables:
                try:
                    df = pd.read_sql_query(f"SELECT * FROM {tbl} LIMIT 1000;", conn)
                    total = len(df)
                    for col in df.columns:
                        null_cnt = int(df[col].isnull().sum())
                        null_pct = (null_cnt / total * 100) if total > 0 else 0.0
                        null_records.append(
                            {
                                "table": tbl,
                                "column": col,
                                "total_rows": total,
                                "null_count": null_cnt,
                                "null_percent": round(null_pct, 2),
                            }
                        )
                except Exception:
                    pass

    return pd.DataFrame(null_records)


def run_data_quality_report(
    source: Union[dict[str, pd.DataFrame], Engine]
) -> bool:
    """Tạo báo cáo tổng hợp chất lượng dữ liệu sau ETL và in ra terminal."""
    logger.info("================ BÁO CÁO KIỂM ĐỊNH CHẤT LƯỢNG DỮ LIỆU ================")

    # 1. Báo cáo Referential Integrity
    ri_results = validate_referential_integrity(source)
    all_passed = True

    print("\n--- 1. KIỂM TRA TÍNH TOÀN VẸN THAM CHIẾU (REFERENTIAL INTEGRITY) ---")
    for check_name, res in ri_results.items():
        status = res.get("status", "UNKNOWN")
        orphans = res.get("orphan_count", "N/A")
        icon = "[OK]" if status == "PASSED" else "[FAIL]"
        print(f" {icon} {check_name:<30}: {orphans} bản ghi mồ côi | Trạng thái: {status}")
        if status != "PASSED":
            all_passed = False

    # 2. Báo cáo tỷ lệ NULL
    null_df = validate_null_rates(source)
    print("\n--- 2. TỶ LỆ NULL TRÊN CÁC CỘT QUAN TRỌNG ---")
    key_columns = [
        "user_id",
        "product_id",
        "time_id",
        "category_id",
        "event_type",
        "total_amount",
    ]
    key_nulls = null_df[null_df["column"].isin(key_columns)]
    if not key_nulls.empty:
        for _, row in key_nulls.iterrows():
            tbl_col = f"{row['table']}.{row['column']}"
            print(f" * {tbl_col:<35}: {row['null_count']} NULLs ({row['null_percent']}%)")
            if row["null_percent"] > 0 and row["column"] != "category_id":
                all_passed = False
    else:
        print(" Không có trường khóa nào chứa giá trị NULL.")

    print("\n=======================================================================")
    if all_passed:
        logger.info(" TẤT CẢ CÁC KIỂM TRA CHẤT LƯỢNG ĐÃ ĐẠT CHUẨN 100%!")
    else:
        logger.warning(" Phát hiện một số vi phạm chất lượng dữ liệu.")

    return all_passed


if __name__ == "__main__":
    from src.etl.extract.amazon_loader import extract_amazon_metadata, extract_amazon_reviews
    from src.etl.extract.dummyjson_api import fetch_dummyjson_users
    from src.etl.transform import (
        build_dim_category_and_product,
        build_dim_time,
        build_dim_user,
        build_fact_interactions,
        clean_amazon_reviews,
    )

    df_rev = clean_amazon_reviews(extract_amazon_reviews(sample_size=500))
    df_meta = extract_amazon_metadata(sample_size=500)
    df_users_dj = fetch_dummyjson_users()

    dim_cat, dim_prod = build_dim_category_and_product(df_rev, df_meta)
    dim_u = build_dim_user(df_rev, df_users_dj)
    dim_t = build_dim_time(df_rev)
    fact_i = build_fact_interactions(df_rev, dim_u, dim_prod, dim_t)

    transformed = {
        "dim_category": dim_cat,
        "dim_product": dim_prod,
        "dim_user": dim_u,
        "dim_time": dim_t,
        "fact_interactions": fact_i,
    }
    run_data_quality_report(transformed)
