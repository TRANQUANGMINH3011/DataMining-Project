"""Module trích xuất (Extract) dữ liệu thô từ CSV/JSON/Parquet."""

import logging
from pathlib import Path
from typing import Generator, Optional, Union

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ETL.Extract")


def read_raw_file(
    file_path: Union[str, Path],
    chunksize: Optional[int] = None,
    **kwargs,
) -> Union[pd.DataFrame, Generator[pd.DataFrame, None, None]]:
    """Đọc file dữ liệu thô (.csv, .parquet, .json) với hỗ trợ chunking.

    Args:
        file_path: Đường dẫn tới file dữ liệu.
        chunksize: Số dòng mỗi chunk nếu file lớn (chỉ áp dụng cho CSV/JSON).
        **kwargs: Các tham số bổ sung truyền cho hàm đọc pandas.

    Returns:
        pd.DataFrame hoặc Generator chứa các chunks.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file nguồn: {path.resolve()}")

    suffix = path.suffix.lower()
    logger.info(f"Đang đọc file: {path.name} (định dạng {suffix})")

    if suffix == ".csv":
        if chunksize is not None:
            return pd.read_csv(path, chunksize=chunksize, encoding="utf-8", **kwargs)
        return pd.read_csv(path, encoding="utf-8", **kwargs)

    elif suffix == ".parquet":
        return pd.read_parquet(path, **kwargs)

    elif suffix == ".json":
        if chunksize is not None:
            return pd.read_json(path, lines=True, chunksize=chunksize, **kwargs)
        return pd.read_json(path, **kwargs)

    else:
        raise ValueError(f"Định dạng file không được hỗ trợ: {suffix}")


def extract_raw_dataset(
    raw_dir: Optional[Union[str, Path]] = None,
    sample_size: Optional[int] = None,
) -> dict[str, pd.DataFrame]:
    """Trích xuất tất cả các tập dữ liệu thô từ thư mục data/raw/.

    Args:
        raw_dir: Thư mục chứa file dữ liệu thô (mặc định data/raw).
        sample_size: Giới hạn số dòng đọc để phục vụ test nhanh (None = đọc hết).

    Returns:
        dict chứa các DataFrame: orders, order_items, customers, products,
        category_translation, reviews.
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    if raw_dir is None:
        raw_dir = project_root / "data" / "raw"
    else:
        raw_dir = Path(raw_dir)

    logger.info(f"Bắt đầu trích xuất dữ liệu từ: {raw_dir.resolve()}")

    file_mapping = {
        "orders": "olist_orders_dataset.csv",
        "order_items": "olist_order_items_dataset.csv",
        "customers": "olist_customers_dataset.csv",
        "products": "olist_products_dataset.csv",
        "category_translation": "product_category_name_translation.csv",
        "reviews": "olist_order_reviews_dataset.csv",
    }

    extracted_data = {}

    # Nếu không sample thì đọc toàn bộ
    if sample_size is None:
        for key, filename in file_mapping.items():
            file_path = raw_dir / filename
            if file_path.exists():
                df = read_raw_file(file_path)
                logger.info(
                    f"-> Đã trích xuất '{key}': {len(df):,} dòng, {len(df.columns)} cột "
                    f"({file_path.stat().st_size / (1024 * 1024):.2f} MB)"
                )
                extracted_data[key] = df
            else:
                logger.warning(f"-> Không tìm thấy file '{filename}' trong {raw_dir}")
        return extracted_data

    # Khi có sample_size: đảm bảo các bảng liên kết quan hệ nhất quán với nhau
    logger.info(f"Đang lấy mẫu liên kết quan hệ ({sample_size:,} đơn hàng)...")

    # 1. Đọc orders mẫu
    orders_df = read_raw_file(raw_dir / file_mapping["orders"], nrows=sample_size)
    extracted_data["orders"] = orders_df
    sample_order_ids = set(orders_df["order_id"])
    sample_cust_ids = set(orders_df["customer_id"])

    # 2. Đọc order_items thuộc các đơn hàng mẫu
    items_df = read_raw_file(raw_dir / file_mapping["order_items"])
    extracted_data["order_items"] = items_df[items_df["order_id"].isin(sample_order_ids)].copy()

    # 3. Đọc customers của các đơn hàng mẫu
    cust_df = read_raw_file(raw_dir / file_mapping["customers"])
    extracted_data["customers"] = cust_df[cust_df["customer_id"].isin(sample_cust_ids)].copy()

    # 4. Đọc reviews của các đơn hàng mẫu
    rev_path = raw_dir / file_mapping["reviews"]
    if rev_path.exists():
        rev_df = read_raw_file(rev_path)
        extracted_data["reviews"] = rev_df[rev_df["order_id"].isin(sample_order_ids)].copy()

    # 5. Đọc danh mục và toàn bộ sản phẩm
    trans_path = raw_dir / file_mapping["category_translation"]
    if trans_path.exists():
        extracted_data["category_translation"] = read_raw_file(trans_path)

    prod_path = raw_dir / file_mapping["products"]
    if prod_path.exists():
        extracted_data["products"] = read_raw_file(prod_path)

    for k, v in extracted_data.items():
        logger.info(f"-> Mẫu '{k}': {len(v):,} dòng.")

    return extracted_data


if __name__ == "__main__":
    data = extract_raw_dataset(sample_size=1000)
    for name, df in data.items():
        print(f"[{name}] Kích thước: {df.shape}")
