"""Module làm giàu dữ liệu sản phẩm qua Open Food Facts API.

Tài liệu tham khảo: https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/
Cung cấp thông tin bổ sung: ingredients_text (thành phần dinh dưỡng) và brands (nhãn hàng)
cho Top 100 sản phẩm phổ biến nhất trong tập dữ liệu.
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ETL.Extract.OpenFoodFacts")

# Header tuân thủ chính sách của Open Food Facts API (bắt buộc User-Agent hợp lệ)
DEFAULT_HEADERS = {
    "User-Agent": "ECommerceDWH-StudentAnalytics/1.0 (contact@student.dwh.edu.vn)",
    "Accept": "application/json",
}

BASE_OFF_URL = "https://world.openfoodfacts.org"


def fetch_product_details(
    barcode_or_name: str,
    timeout: int = 5,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    """Tra cứu chi tiết một sản phẩm qua Open Food Facts API.

    Hỗ trợ:
      - Mã vạch barcode (chuỗi số EAN-13, UPC): gọi trực tiếp endpoint /api/v2/product/{barcode}.json
      - Tên sản phẩm: gọi endpoint tìm kiếm /api/v2/search hoặc fallback v0

    Args:
        barcode_or_name: Mã vạch hoặc từ khóa tên sản phẩm.
        timeout: Thời gian chờ tối đa (giây).
        session: requests.Session tái sử dụng connection pool.

    Returns:
        dict chứa: code, product_name, brands, ingredients_text
    """
    client = session or requests
    query = str(barcode_or_name).strip()
    is_barcode = query.isdigit() and len(query) >= 8

    # 1. Trường hợp là Mã vạch Barcode
    if is_barcode:
        url = f"{BASE_OFF_URL}/api/v2/product/{query}.json"
        params = {"fields": "code,product_name,brands,ingredients_text"}
        try:
            res = client.get(url, params=params, headers=DEFAULT_HEADERS, timeout=timeout)
            if res.status_code == 200:
                data = res.json()
                prod = data.get("product", {})
                if prod:
                    return {
                        "code": prod.get("code", query),
                        "product_name": prod.get("product_name") or "",
                        "brands": prod.get("brands") or "",
                        "ingredients_text": prod.get("ingredients_text") or "",
                    }
        except Exception as exc:
            logger.debug(f"Không thể lấy barcode {query}: {exc}")

    # 2. Trường hợp là Tên sản phẩm (Search API)
    search_url = f"{BASE_OFF_URL}/api/v2/search"
    search_params = {
        "search_terms": query,
        "fields": "code,product_name,brands,ingredients_text",
        "page_size": 1,
        "json": 1,
    }

    try:
        res = client.get(search_url, params=search_params, headers=DEFAULT_HEADERS, timeout=timeout)
        if res.status_code == 200:
            data = res.json()
            products = data.get("products", [])
            if products:
                prod = products[0]
                return {
                    "code": prod.get("code", ""),
                    "product_name": prod.get("product_name") or query,
                    "brands": prod.get("brands") or "",
                    "ingredients_text": prod.get("ingredients_text") or "",
                }
    except Exception as exc:
        logger.debug(f"Search API gặp lỗi cho '{query}': {exc}")

    # Fallback kết quả mặc định nếu không tìm thấy hoặc API bận
    return {
        "code": query,
        "product_name": query,
        "brands": "",
        "ingredients_text": "",
    }


def enrich_top_products(
    top_products_list: List[Dict[str, str]],
    top_n: int = 100,
    delay_between_requests: float = 0.2,
    cache_to_local: bool = True,
) -> pd.DataFrame:
    """Làm giàu thông tin Open Food Facts cho Top N sản phẩm phổ biến nhất.

    Vì API công cộng có rate-limit, hàm giới hạn chỉ gọi cho tối đa top_n sản phẩm
    và có thời gian giãn cách giữa các lượt gọi.

    Args:
        top_products_list: Danh sách dict [{'product_id': '...', 'product_name': '...'}]
        top_n: Số lượng sản phẩm tối đa cần làm giàu (mặc định 100).
        delay_between_requests: Thời gian chờ giữa 2 lượt gọi (giây).
        cache_to_local: Tự động lưu cache parquet vào data/raw/openfoodfacts/.

    Returns:
        pd.DataFrame chứa: product_id, product_name, brands, ingredients_text
    """
    logger.info(f"Bắt đầu làm giàu dữ liệu Open Food Facts cho Top {min(len(top_products_list), top_n)} sản phẩm...")
    project_root = Path(__file__).resolve().parents[3]
    cache_dir = project_root / "data" / "raw" / "openfoodfacts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"enriched_top_{top_n}.parquet"

    if cache_file.exists():
        logger.info(f"-> Đã tìm thấy bản cache Open Food Facts: {cache_file.name}. Đang nạp...")
        return pd.read_parquet(cache_file)

    session = requests.Session()
    enriched_records = []
    targets = top_products_list[:top_n]

    for idx, item in enumerate(targets):
        pid = item.get("product_id", "")
        name = item.get("product_name", "")

        # Ưu tiên tìm theo tên hoặc barcode
        details = fetch_product_details(barcode_or_name=name or pid, session=session)
        enriched_records.append({
            "product_id": pid,
            "product_name": name,
            "brands": details.get("brands", ""),
            "ingredients_text": details.get("ingredients_text", ""),
        })

        if (idx + 1) % 20 == 0 or (idx + 1) == len(targets):
            logger.info(f"  * Tiến độ: {idx + 1}/{len(targets)} sản phẩm đã xử lý.")

        time.sleep(delay_between_requests)

    df = pd.DataFrame(enriched_records)
    logger.info(f"-> Hoàn tất làm giàu Open Food Facts cho {len(df):,} sản phẩm.")

    if cache_to_local and not df.empty:
        df.to_parquet(cache_file, index=False)
        logger.info(f"-> Đã lưu bản đệm vào {cache_file}")

    return df


if __name__ == "__main__":
    # Thử nghiệm với mã vạch mẫu thực tế (Nutella)
    sample_code = "3017620422003"
    print(f"Tra cứu sản phẩm mã vạch: {sample_code}")
    res = fetch_product_details(sample_code)
    print("Kết quả:", res)
