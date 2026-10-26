"""Module trích xuất dữ liệu từ Amazon Reviews 2023 trên Hugging Face.

Hỗ trợ streaming trực tiếp từ Hugging Face qua thư viện `datasets` hoặc qua direct HTTP streaming,
kết hợp cơ chế lưu đệm (cache) vào thư mục cục bộ data/raw/amazon/ để tăng tốc cho các lần chạy sau.
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Optional, Union
import urllib.request

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ETL.Extract.Amazon")

BASE_HF_URL = "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw"


def _clean_price(price_val: Any) -> float:
    """Chuyển đổi giá trị price (chuỗi ký tự dạng '$12.99' hoặc số) về dạng float."""
    if price_val is None:
        return 0.0
    if isinstance(price_val, (int, float)):
        return 0.0 if pd.isna(price_val) else float(price_val)
    if isinstance(price_val, (list, tuple)):
        return 0.0
    if isinstance(price_val, str):
        cleaned = re.sub(r"[^\d.]", "", price_val.strip())
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0
    return 0.0


def _clean_description(desc_val: Any) -> str:
    """Chuẩn hóa trường description từ list các đoạn văn bản thành một chuỗi duy nhất."""
    if desc_val is None:
        return ""
    if isinstance(desc_val, (list, tuple)):
        return " ".join([str(item).strip() for item in desc_val if str(item).strip()])
    try:
        if pd.isna(desc_val):
            return ""
    except Exception:
        pass
    return str(desc_val).strip()


def extract_amazon_reviews(
    category: str = "All_Beauty",
    sample_size: int = 50000,
    local_path: Optional[Union[str, Path]] = None,
    cache_to_local: bool = True,
) -> pd.DataFrame:
    """Trích xuất mẫu đánh giá người dùng (Reviews) từ Amazon Reviews 2023.

    Args:
        category: Danh mục sản phẩm (ví dụ: 'All_Beauty', 'Appliances', 'Grocery_and_Gourmet_Food').
        sample_size: Số lượng bản ghi mẫu cần lấy (mặc định 50,000 dòng).
        local_path: Đường dẫn tới file .parquet hoặc .jsonl cục bộ (nếu có sẵn).
        cache_to_local: Tự động lưu bản sao parquet vào data/raw/amazon/ sau khi tải.

    Returns:
        pd.DataFrame chứa các cột: user_id, parent_asin, rating, timestamp, text, helpful_vote.
    """
    logger.info(f"Bắt đầu trích xuất Amazon Reviews cho ngành hàng '{category}' (sample={sample_size:,})...")

    project_root = Path(__file__).resolve().parents[3]
    cache_dir = project_root / "data" / "raw" / "amazon"
    cache_dir.mkdir(parents=True, exist_ok=True)
    default_cache_file = cache_dir / f"reviews_{category}_{sample_size}.parquet"

    # 1. Kiểm tra cache cục bộ trước để tránh tải lại
    if local_path and Path(local_path).exists():
        logger.info(f"-> Đọc trực tiếp từ file chỉ định: {local_path}")
        df = pd.read_parquet(local_path) if str(local_path).endswith(".parquet") else pd.read_json(local_path, lines=True)
        return df.head(sample_size)
    elif default_cache_file.exists():
        logger.info(f"-> Đã tìm thấy bản sao cache cục bộ: {default_cache_file.name}. Đang nạp...")
        return pd.read_parquet(default_cache_file).head(sample_size)

    # 2. Tải trực tiếp từ Hugging Face
    records = []
    hf_jsonl_url = f"{BASE_HF_URL}/review_categories/{category}.jsonl"

    try:
        # Thử phương thức streaming qua thư viện `datasets`
        logger.info(f"-> Đang streaming dữ liệu qua HuggingFace datasets từ: {hf_jsonl_url}")
        from datasets import load_dataset
        ds = load_dataset("json", data_files=hf_jsonl_url, split="train", streaming=True)
        for i, item in enumerate(ds):
            records.append({
                "user_id": item.get("user_id", ""),
                "parent_asin": item.get("parent_asin", ""),
                "rating": float(item.get("rating", 0.0) or 0.0),
                "timestamp": item.get("timestamp", 0),
                "text": str(item.get("text", "") or ""),
                "helpful_vote": int(item.get("helpful_vote", 0) or 0),
            })
            if (i + 1) >= sample_size:
                break
    except Exception as exc:
        logger.warning(f"-> Streaming qua datasets gặp lỗi ({exc}). Đang chuyển sang HTTP direct stream...")
        req = urllib.request.Request(hf_jsonl_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            count = 0
            for line in response:
                if not line.strip():
                    continue
                item = json.loads(line.decode("utf-8"))
                records.append({
                    "user_id": item.get("user_id", ""),
                    "parent_asin": item.get("parent_asin", ""),
                    "rating": float(item.get("rating", 0.0) or 0.0),
                    "timestamp": item.get("timestamp", 0),
                    "text": str(item.get("text", "") or ""),
                    "helpful_vote": int(item.get("helpful_vote", 0) or 0),
                })
                count += 1
                if count >= sample_size:
                    break

    df = pd.DataFrame(records)
    logger.info(f"-> Đã trích xuất thành công {len(df):,} bản ghi reviews từ Amazon.")

    # 3. Lưu cache cục bộ nếu được bật
    if cache_to_local and not df.empty:
        df.to_parquet(default_cache_file, index=False)
        logger.info(f"-> Đã lưu bản đệm vào {default_cache_file}")

    return df


def extract_amazon_metadata(
    category: str = "All_Beauty",
    sample_size: int = 50000,
    local_path: Optional[Union[str, Path]] = None,
    cache_to_local: bool = True,
) -> pd.DataFrame:
    """Trích xuất thông tin sản phẩm (Metadata) từ Amazon Reviews 2023.

    Args:
        category: Danh mục sản phẩm (ví dụ: 'All_Beauty', 'Appliances', 'Grocery_and_Gourmet_Food').
        sample_size: Số lượng sản phẩm cần lấy.
        local_path: Đường dẫn tới file metadata cục bộ.
        cache_to_local: Tự động lưu cache sau khi tải.

    Returns:
        pd.DataFrame chứa các cột: parent_asin, title, price, main_category, description.
    """
    logger.info(f"Bắt đầu trích xuất Amazon Metadata cho ngành hàng '{category}' (sample={sample_size:,})...")

    project_root = Path(__file__).resolve().parents[3]
    cache_dir = project_root / "data" / "raw" / "amazon"
    cache_dir.mkdir(parents=True, exist_ok=True)
    default_cache_file = cache_dir / f"meta_{category}_{sample_size}.parquet"

    if local_path and Path(local_path).exists():
        logger.info(f"-> Đọc trực tiếp từ file chỉ định: {local_path}")
        df = pd.read_parquet(local_path) if str(local_path).endswith(".parquet") else pd.read_json(local_path, lines=True)
        return df.head(sample_size)
    elif default_cache_file.exists():
        logger.info(f"-> Đã tìm thấy bản sao cache metadata: {default_cache_file.name}. Đang nạp...")
        return pd.read_parquet(default_cache_file).head(sample_size)

    records = []
    hf_jsonl_url = f"{BASE_HF_URL}/meta_categories/meta_{category}.jsonl"

    try:
        from datasets import load_dataset
        ds = load_dataset("json", data_files=hf_jsonl_url, split="train", streaming=True)
        for i, item in enumerate(ds):
            records.append({
                "parent_asin": item.get("parent_asin", ""),
                "title": str(item.get("title", "") or "Sản phẩm Amazon"),
                "price": _clean_price(item.get("price")),
                "main_category": str(item.get("main_category", category) or category),
                "description": _clean_description(item.get("description")),
            })
            if (i + 1) >= sample_size:
                break
    except Exception as exc:
        logger.warning(f"-> Streaming metadata qua datasets gặp lỗi ({exc}). Đang dùng HTTP direct stream...")
        req = urllib.request.Request(hf_jsonl_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            count = 0
            for line in response:
                if not line.strip():
                    continue
                item = json.loads(line.decode("utf-8"))
                records.append({
                    "parent_asin": item.get("parent_asin", ""),
                    "title": str(item.get("title", "") or "Sản phẩm Amazon"),
                    "price": _clean_price(item.get("price")),
                    "main_category": str(item.get("main_category", category) or category),
                    "description": _clean_description(item.get("description")),
                })
                count += 1
                if count >= sample_size:
                    break

    df = pd.DataFrame(records)
    # Khử trùng lặp theo parent_asin
    df = df.drop_duplicates(subset=["parent_asin"]).reset_index(drop=True)
    logger.info(f"-> Đã trích xuất thành công {len(df):,} sản phẩm metadata duy nhất từ Amazon.")

    if cache_to_local and not df.empty:
        df.to_parquet(default_cache_file, index=False)
        logger.info(f"-> Đã lưu bản đệm metadata vào {default_cache_file}")

    return df


if __name__ == "__main__":
    df_reviews = extract_amazon_reviews(category="All_Beauty", sample_size=100)
    print("\n--- SAMPLE REVIEWS ---")
    print(df_reviews.head(3))

    df_meta = extract_amazon_metadata(category="All_Beauty", sample_size=100)
    print("\n--- SAMPLE METADATA ---")
    print(df_meta.head(3))
