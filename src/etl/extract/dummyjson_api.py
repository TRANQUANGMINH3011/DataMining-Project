"""Module trích xuất dữ liệu người dùng và giỏ hàng từ DummyJSON REST API.

Tài liệu tham khảo: https://dummyjson.com/docs
Cung cấp dữ liệu nhân khẩu học (Age, Gender, City, Country) để làm giàu Dim_User
và dữ liệu giỏ hàng mẫu để kiểm thử phân tích kết hợp.
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ETL.Extract.DummyJSON")

DUMMYJSON_BASE_URL = "https://dummyjson.com"


def _get_retry_session(
    retries: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: tuple = (500, 502, 503, 504, 429),
) -> requests.Session:
    """Tạo requests Session có cấu hình tự động thử lại (Retry) khi gặp lỗi mạng/máy chủ."""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch_dummyjson_users(
    limit: int = 100,
    skip: int = 0,
    timeout: int = 10,
    cache_to_local: bool = True,
) -> pd.DataFrame:
    """Gọi DummyJSON REST API để lấy danh sách hồ sơ người dùng làm giàu nhân khẩu học.

    Endpoint: https://dummyjson.com/users?limit={limit}&skip={skip}

    Returns:
        pd.DataFrame với các cột: dummy_user_id, age, gender, city, country, email, username
    """
    logger.info(f"Đang gọi DummyJSON Users API (limit={limit}, skip={skip})...")
    project_root = Path(__file__).resolve().parents[3]
    cache_dir = project_root / "data" / "raw" / "dummyjson"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"users_limit_{limit}.parquet"

    url = f"{DUMMYJSON_BASE_URL}/users"
    params = {"limit": limit, "skip": skip}
    session = _get_retry_session()

    try:
        response = session.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        raw_users = data.get("users", [])

        records = []
        for u in raw_users:
            addr = u.get("address", {}) or {}
            records.append({
                "dummy_user_id": u.get("id"),
                "age": int(u.get("age", 0) or 0),
                "gender": str(u.get("gender", "unknown")),
                "city": str(addr.get("city", "Unknown City")),
                "country": str(addr.get("country", "United States")),
                "email": str(u.get("email", "")),
                "username": str(u.get("username", "")),
            })

        df = pd.DataFrame(records)
        logger.info(f"-> Đã lấy thành công {len(df):,} người dùng từ DummyJSON API.")

        if cache_to_local and not df.empty:
            df.to_parquet(cache_file, index=False)
            logger.info(f"-> Đã lưu bản đệm vào {cache_file}")

        return df

    except requests.exceptions.RequestException as exc:
        logger.error(f"Lỗi khi gọi DummyJSON Users API: {exc}")
        if cache_file.exists():
            logger.info(f"-> Sử dụng bản cache có sẵn: {cache_file}")
            return pd.read_parquet(cache_file)
        # Trả về DataFrame rỗng nếu gặp lỗi mạng và chưa có cache
        return pd.DataFrame(columns=["dummy_user_id", "age", "gender", "city", "country", "email", "username"])


def fetch_dummyjson_carts(
    limit: int = 50,
    skip: int = 0,
    timeout: int = 10,
    cache_to_local: bool = True,
) -> pd.DataFrame:
    """Gọi DummyJSON REST API để lấy các mẫu giỏ hàng phục vụ Market Basket Analysis.

    Endpoint: https://dummyjson.com/carts?limit={limit}&skip={skip}

    Returns:
        pd.DataFrame chi tiết từng mặt hàng trong giỏ: cart_id, user_id, product_id,
        product_title, price, quantity, total, discounted_total
    """
    logger.info(f"Đang gọi DummyJSON Carts API (limit={limit}, skip={skip})...")
    project_root = Path(__file__).resolve().parents[3]
    cache_dir = project_root / "data" / "raw" / "dummyjson"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"carts_limit_{limit}.parquet"

    url = f"{DUMMYJSON_BASE_URL}/carts"
    params = {"limit": limit, "skip": skip}
    session = _get_retry_session()

    try:
        response = session.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        raw_carts = data.get("carts", [])

        records = []
        for cart in raw_carts:
            c_id = cart.get("id")
            u_id = cart.get("userId")
            products = cart.get("products", [])
            for p in products:
                records.append({
                    "cart_id": c_id,
                    "dummy_user_id": u_id,
                    "dummy_product_id": p.get("id"),
                    "product_title": str(p.get("title", "")),
                    "price": float(p.get("price", 0.0) or 0.0),
                    "quantity": int(p.get("quantity", 1) or 1),
                    "total": float(p.get("total", 0.0) or 0.0),
                    "discounted_total": float(p.get("discountedTotal", 0.0) or 0.0),
                })

        df = pd.DataFrame(records)
        logger.info(f"-> Đã lấy thành công {len(df):,} dòng chi tiết giỏ hàng từ DummyJSON API.")

        if cache_to_local and not df.empty:
            df.to_parquet(cache_file, index=False)
            logger.info(f"-> Đã lưu bản đệm vào {cache_file}")

        return df

    except requests.exceptions.RequestException as exc:
        logger.error(f"Lỗi khi gọi DummyJSON Carts API: {exc}")
        if cache_file.exists():
            logger.info(f"-> Sử dụng bản cache có sẵn: {cache_file}")
            return pd.read_parquet(cache_file)
        return pd.DataFrame(columns=[
            "cart_id", "dummy_user_id", "dummy_product_id", "product_title",
            "price", "quantity", "total", "discounted_total"
        ])


if __name__ == "__main__":
    df_u = fetch_dummyjson_users(limit=5)
    print("\n--- SAMPLE USERS ---")
    print(df_u)

    df_c = fetch_dummyjson_carts(limit=5)
    print("\n--- SAMPLE CARTS ---")
    print(df_c.head())
