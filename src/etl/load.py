"""Module nạp (Load) dữ liệu vào PostgreSQL / MySQL / SQLite Data Warehouse theo đúng chuẩn Star Schema."""

import logging
import time
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ETL.Load")


def truncate_tables(engine: Engine):
    """Xóa dữ liệu cũ theo thứ tự Fact trước, Dim sau để tuân thủ ràng buộc toàn vẹn khóa ngoại."""
    logger.info("Đang dọn dẹp dữ liệu cũ trong Data Warehouse...")
    tables_reverse_order = [
        "fact_interactions",
        "dim_product",
        "dim_category",
        "dim_user",
        "dim_time",
    ]
    with engine.connect() as conn:
        for tbl in tables_reverse_order:
            try:
                # PostgreSQL / MySQL TRUNCATE CASCADE
                conn.execute(text(f"TRUNCATE TABLE {tbl} CASCADE;"))
            except Exception:
                try:
                    conn.execute(text(f"DELETE FROM {tbl};"))
                except Exception:
                    pass
        conn.commit()
    logger.info("-> Dọn dẹp dữ liệu cũ hoàn tất.")


def load_table(
    df: pd.DataFrame,
    table_name: str,
    engine: Engine,
    if_exists: str = "append",
    chunksize: int = 5000,
) -> int:
    """Nạp một DataFrame vào bảng cơ sở dữ liệu với chunking và method='multi'.

    Args:
        df: DataFrame chứa dữ liệu sạch cần nạp.
        table_name: Tên bảng đích (viết thường).
        engine: SQLAlchemy Engine kết nối tới CSDL.
        if_exists: 'append' hoặc 'replace'.
        chunksize: Số lượng bản ghi mỗi batch (mặc định 5000 cho Fact_Interactions).

    Returns:
        Số lượng bản ghi đã nạp thành công.
    """
    table_lower = table_name.lower()
    total_rows = len(df)
    if total_rows == 0:
        logger.info(f"Bảng '{table_name}' không có dữ liệu để nạp.")
        return 0

    # Khử trùng lặp khóa chính nếu bảng đã có dữ liệu từ trước
    pk_map = {
        "dim_category": "category_id",
        "dim_user": "user_id",
        "dim_product": "product_id",
        "dim_time": "time_id",
    }
    pk_col = pk_map.get(table_lower)
    insert_df = df

    if pk_col and if_exists == "append":
        try:
            with engine.connect() as conn:
                existing_pks = set(pd.read_sql_query(f"SELECT {pk_col} FROM {table_lower};", conn)[pk_col])
            if existing_pks:
                insert_df = df[~df[pk_col].isin(existing_pks)].copy()
                skipped = len(df) - len(insert_df)
                if skipped > 0:
                    logger.info(f"Bỏ qua {skipped:,} bản ghi đã tồn tại trong '{table_lower}'.")
        except Exception:
            pass

    rows_to_insert = len(insert_df)
    if rows_to_insert == 0:
        logger.info(f"Bảng '{table_name}' đã đầy đủ dữ liệu (không cần nạp thêm).")
        return 0

    # Tự động điều chỉnh chunksize thích hợp: SQLite tối đa 999 biến tham số; PostgreSQL hỗ trợ 5000+
    dialect = engine.dialect.name.lower()
    actual_chunksize = min(chunksize, 150) if dialect == "sqlite" else chunksize

    start_time = time.time()
    logger.info(
        f"Bắt đầu nạp bảng '{table_name}': {rows_to_insert:,} dòng "
        f"(chunksize={actual_chunksize}, method='multi', dialect={dialect.upper()})..."
    )

    try:
        insert_df.to_sql(
            name=table_lower,
            con=engine,
            if_exists=if_exists,
            index=False,
            chunksize=actual_chunksize,
            method="multi",
        )
        elapsed = time.time() - start_time
        speed = rows_to_insert / elapsed if elapsed > 0 else rows_to_insert
        logger.info(
            f"-> Nạp '{table_name}' THÀNH CÔNG! "
            f"Đã nạp: {rows_to_insert:,} dòng | Thời gian: {elapsed:.2f}s | Tốc độ: {speed:,.0f} dòng/s."
        )
        return rows_to_insert

    except Exception as exc:
        logger.error(f"Lỗi khi nạp bảng '{table_name}': {exc}")
        raise exc


def save_processed_staging(tables: Dict[str, pd.DataFrame], output_dir: Optional[Path] = None):
    """Lưu trữ dữ liệu sạch vào data/processed/ làm tầng Staging (Parquet và CSV)."""
    project_root = Path(__file__).resolve().parents[2]
    if output_dir is None:
        output_dir = project_root / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    for tbl_name, df in tables.items():
        try:
            p_file = output_dir / f"{tbl_name}.parquet"
            df.to_parquet(p_file, index=False)
            logger.debug(f"Đã lưu Parquet staging: {p_file.name} ({len(df):,} dòng)")
        except Exception:
            pass

        try:
            c_file = output_dir / f"{tbl_name}.csv"
            df.to_csv(c_file, index=False, encoding="utf-8")
            logger.debug(f"Đã lưu CSV staging: {c_file.name} ({len(df):,} dòng)")
        except Exception:
            pass


def load_dwh(
    tables: Dict[str, pd.DataFrame],
    engine: Engine,
    truncate_first: bool = False,
    chunksize: int = 5000,
) -> Dict[str, int]:
    """Điều phối nạp dữ liệu vào toàn bộ Star Schema theo đúng thứ tự ràng buộc khóa ngoại.

    Thứ tự nạp nghiêm ngặt:
      1. Dim_Category
      2. Dim_User
      3. Dim_Product (có khóa ngoại category_id)
      4. Dim_Time
      5. Fact_Interactions (có khóa ngoại user_id, product_id, time_id)
    """
    logger.info("================ BẮT ĐẦU LOAD VÀO DATA WAREHOUSE (STAR SCHEMA) ================")

    if truncate_first:
        truncate_tables(engine)

    # Lưu bản sao staging vào data/processed/
    save_processed_staging(tables)

    # Thứ tự nạp tuân thủ chặt chẽ khóa ngoại
    ordered_tables = [
        ("dim_category", tables["dim_category"]),
        ("dim_user", tables["dim_user"]),
        ("dim_product", tables["dim_product"]),
        ("dim_time", tables["dim_time"]),
        ("fact_interactions", tables["fact_interactions"]),
    ]

    loaded_counts = {}
    for tbl_name, df in ordered_tables:
        count = load_table(
            df=df,
            table_name=tbl_name,
            engine=engine,
            if_exists="append",
            chunksize=chunksize,
        )
        loaded_counts[tbl_name] = count

    logger.info("================ TOÀN BỘ BẢNG ĐÃ ĐƯỢC NẠP THÀNH CÔNG VÀO DWH ================")
    return loaded_counts
