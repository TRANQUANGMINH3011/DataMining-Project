"""Module nạp (Load) dữ liệu vào PostgreSQL Data Warehouse theo đúng thứ tự Star Schema."""

import logging
import time
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ETL.Load")


def load_table(
    df: pd.DataFrame,
    table_name: str,
    engine: Engine,
    if_exists: str = "append",
    chunksize: int = 5000,
) -> int:
    """Nạp một DataFrame vào bảng cơ sở dữ liệu sử dụng bulk loading.

    Args:
        df: DataFrame chứa dữ liệu đã làm sạch.
        table_name: Tên bảng đích (viết thường).
        engine: SQLAlchemy Engine kết nối tới DWH.
        if_exists: 'append' hoặc 'replace'.
        chunksize: Số lượng bản ghi mỗi batch (mặc định 5000).

    Returns:
        Số lượng bản ghi đã nạp thành công.
    """
    # Bản đồ khóa chính để chống trùng lặp khi chạy lại pipeline
    pk_map = {
        "dim_category": "category_id",
        "dim_user": "user_id",
        "dim_product": "product_id",
        "dim_time": "time_id",
    }
    table_lower = table_name.lower()
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

    total_rows = len(insert_df)
    if total_rows == 0:
        logger.info(f"Bảng '{table_name}' đã cập nhật đầy đủ (không có bản ghi mới).")
        return 0

    start_time = time.time()
    # Tự động điều chỉnh chunksize cho SQLite để tránh vượt quá giới hạn 999 biến SQL
    actual_chunksize = min(chunksize, 100) if engine.dialect.name == "sqlite" else chunksize
    logger.info(
        f"Bắt đầu nạp bảng '{table_name}': {total_rows:,} dòng "
        f"(chunksize={actual_chunksize}, method='multi')..."
    )

    try:
        # Sử dụng bulk insert của Pandas với method='multi' tối ưu cho PostgreSQL
        insert_df.to_sql(
            name=table_lower,
            con=engine,
            if_exists=if_exists,
            index=False,
            chunksize=actual_chunksize,
            method="multi",
        )
        elapsed = time.time() - start_time
        speed = total_rows / elapsed if elapsed > 0 else total_rows
        logger.info(
            f"-> Nạp '{table_name}' thành công! "
            f"Thời gian: {elapsed:.2f}s | Tốc độ: {speed:,.0f} dòng/s."
        )
        return total_rows

    except Exception as exc:
        logger.error(f"Lỗi khi nạp vào bảng '{table_name}': {exc}")
        raise exc


def truncate_tables(engine: Engine):
    """Xóa trắng dữ liệu cũ theo thứ tự Fact trước, Dim sau để tránh lỗi FK."""
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
                conn.execute(text(f"TRUNCATE TABLE {tbl} CASCADE;"))
            except Exception:
                # Nếu bảng chưa tồn tại hoặc database là SQLite thì dùng DELETE
                try:
                    conn.execute(text(f"DELETE FROM {tbl};"))
                except Exception:
                    pass
        conn.commit()
    logger.info("-> Dọn dẹp dữ liệu cũ hoàn tất.")


def save_processed_staging(tables: dict[str, pd.DataFrame], output_dir: Optional[Path] = None):
    """Lưu bản sao dữ liệu sạch vào data/processed/ làm tầng Staging (ưu tiên Parquet, fallback CSV)."""
    project_root = Path(__file__).resolve().parent.parent.parent
    if output_dir is None:
        output_dir = project_root / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    for tbl_name, df in tables.items():
        try:
            file_path = output_dir / f"{tbl_name}.parquet"
            df.to_parquet(file_path, index=False)
            logger.debug(f"Đã lưu staging Parquet: {file_path.name} ({len(df):,} dòng)")
        except (ImportError, Exception):
            file_path = output_dir / f"{tbl_name}.csv"
            df.to_csv(file_path, index=False, encoding="utf-8")
            logger.debug(f"Đã lưu staging CSV: {file_path.name} ({len(df):,} dòng)")


def load_dwh(
    tables: dict[str, pd.DataFrame],
    engine: Engine,
    truncate_first: bool = False,
    chunksize: int = 5000,
) -> dict[str, int]:
    """Điều phối nạp dữ liệu vào toàn bộ Star Schema theo đúng thứ tự phân cấp.

    Thứ tự nạp nghiêm ngặt:
      1. Dim_Category
      2. Dim_Product
      3. Dim_User
      4. Dim_Time
      5. Fact_Interactions
    """
    logger.info("================ BẮT ĐẦU LOAD VÀO DATA WAREHOUSE ================")

    if truncate_first:
        truncate_tables(engine)

    # Lưu bản sao staging Parquet
    save_processed_staging(tables)

    # Ánh xạ tên key với tên bảng chuẩn trong SQL
    ordered_tables = [
        ("dim_category", tables["dim_category"]),
        ("dim_product", tables["dim_product"]),
        ("dim_user", tables["dim_user"]),
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

    logger.info("================ KẾT THÚC LOAD THÀNH CÔNG ================")
    return loaded_counts
