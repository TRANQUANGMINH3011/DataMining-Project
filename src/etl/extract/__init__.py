"""Package ETL Extract - Module trích xuất dữ liệu đa nguồn:
1. Amazon Reviews 2023 (Hugging Face)
2. DummyJSON REST API (Users & Carts)
3. Open Food Facts API (Nutritional Ingredients & Brands)
"""

from src.etl.extract.amazon_loader import (
    extract_amazon_metadata,
    extract_amazon_reviews,
)
from src.etl.extract.dummyjson_api import (
    fetch_dummyjson_carts,
    fetch_dummyjson_users,
)
from src.etl.extract.openfoodfacts_api import (
    enrich_top_products,
    fetch_product_details,
)

__all__ = [
    "extract_amazon_reviews",
    "extract_amazon_metadata",
    "fetch_dummyjson_users",
    "fetch_dummyjson_carts",
    "fetch_product_details",
    "enrich_top_products",
]
