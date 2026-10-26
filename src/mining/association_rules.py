"""Khai phá luật kết hợp giỏ hàng (Market Basket Analysis) dùng FP-Growth & Apriori."""

import logging
import sys
from pathlib import Path
from typing import List, Optional, Union

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules, fpgrowth
from mlxtend.preprocessing import TransactionEncoder
from sqlalchemy import text

from src.database import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("Mining.MBA")


def get_transactions_from_dwh(
    engine_instance=None,
    item_column: str = "product_name",
    min_basket_size: int = 2,
) -> List[List[str]]:
    """Truy vấn DWH để lấy danh sách các giỏ hàng (transactions).

    Args:
        engine_instance: SQLAlchemy Engine.
        item_column: 'product_id', 'product_name' hoặc 'category_id'.
        min_basket_size: Kích thước giỏ hàng tối thiểu (mặc định 2 để loại giỏ đơn).

    Returns:
        List các list (mỗi phần tử con là danh sách các sản phẩm trong 1 giỏ).
    """
    logger.info(f"Đang trích xuất giỏ hàng từ DWH theo trường '{item_column}'...")
    if engine_instance is None:
        engine_instance = engine

    sql_query = f"""
    SELECT 
        f.user_id,
        f.time_id,
        f.product_id,
        p.product_name,
        p.category_id
    FROM fact_interactions f
    JOIN dim_product p ON f.product_id = p.product_id
    WHERE f.event_type IN ('purchase', 'review');
    """

    df = pd.DataFrame()
    try:
        with engine_instance.connect() as conn:
            df = pd.read_sql_query(text(sql_query), conn)
    except Exception as exc:
        logger.warning(f"Không thể truy vấn trực tiếp từ database: {exc}. Đang đọc từ Staging...")

    if df.empty:
        project_root = Path(__file__).resolve().parent.parent.parent
        processed_dir = project_root / "data" / "processed"

        fact_path = processed_dir / "fact_interactions.parquet"
        prod_path = processed_dir / "dim_product.parquet"
        if not fact_path.exists():
            fact_path = processed_dir / "fact_interactions.csv"
            prod_path = processed_dir / "dim_product.csv"

        if fact_path.exists() and prod_path.exists():
            df_fact = pd.read_parquet(fact_path) if fact_path.suffix == ".parquet" else pd.read_csv(fact_path)
            df_prod = pd.read_parquet(prod_path) if prod_path.suffix == ".parquet" else pd.read_csv(prod_path)
            df = df_fact.merge(df_prod, on="product_id", how="inner")
        else:
            raise FileNotFoundError("Không tìm thấy dữ liệu Fact và Dim_Product để khai phá luật kết hợp.")

    # Xác định giỏ hàng (basket) dựa trên user_id (nhóm các sản phẩm user cùng tương tác)
    df["basket_id"] = df["user_id"].astype(str)
    
    # Nhóm sản phẩm theo giỏ hàng
    grouped = (
        df.groupby("basket_id")[item_column]
        .apply(lambda s: list(set(s.dropna())))
        .reset_index()
    )

    # Lọc giỏ hàng có số lượng mặt hàng >= min_basket_size
    if min_basket_size > 1:
        filtered = grouped[grouped[item_column].apply(len) >= min_basket_size]
        logger.info(
            f"Tổng số giỏ hàng DWH: {len(grouped):,} | "
            f"Số giỏ hàng có >= {min_basket_size} sản phẩm: {len(filtered):,}."
        )
        transactions = filtered[item_column].tolist()
    else:
        transactions = grouped[item_column].tolist()

    # Bổ sung các mẫu giỏ hàng từ DummyJSON Carts API
    try:
        from src.etl.extract.dummyjson_api import fetch_dummyjson_carts
        df_dummy_carts = fetch_dummyjson_carts(limit=50)
        if not df_dummy_carts.empty:
            dummy_baskets = (
                df_dummy_carts.groupby("cart_id")["product_title"]
                .apply(lambda s: list(set(s.dropna())))
                .tolist()
            )
            dummy_baskets = [b for b in dummy_baskets if len(b) >= min_basket_size]
            if dummy_baskets:
                logger.info(f"-> Đã bổ sung {len(dummy_baskets)} giỏ hàng từ DummyJSON Carts API.")
                transactions.extend(dummy_baskets)
    except Exception as exc:
        logger.debug(f"Không thể nạp DummyJSON carts: {exc}")

    return transactions


def encode_transactions(transactions: List[List[str]]) -> pd.DataFrame:
    """Chuyển đổi danh sách giỏ hàng thành ma trận One-Hot Encoding."""
    logger.info("Đang chuyển đổi giỏ hàng sang ma trận nhị phân (One-Hot Encoding)...")
    te = TransactionEncoder()
    te_ary = te.fit(transactions).transform(transactions)
    matrix_df = pd.DataFrame(te_ary, columns=te.columns_)
    logger.info(f"-> Ma trận giỏ hàng: {matrix_df.shape[0]:,} đơn hàng x {matrix_df.shape[1]:,} mặt hàng.")
    return matrix_df


def mine_frequent_itemsets(
    matrix_df: pd.DataFrame,
    algorithm: str = "fpgrowth",
    min_support: float = 0.01,
) -> pd.DataFrame:
    """Sinh tập phổ biến (Frequent Itemsets) bằng FP-Growth hoặc Apriori."""
    logger.info(f"Đang chạy thuật toán {algorithm.upper()} với min_support={min_support}...")

    if algorithm.lower() == "fpgrowth":
        frequent_itemsets = fpgrowth(matrix_df, min_support=min_support, use_colnames=True)
    elif algorithm.lower() == "apriori":
        frequent_itemsets = apriori(matrix_df, min_support=min_support, use_colnames=True)
    else:
        raise ValueError("Thuật toán chỉ hỗ trợ 'fpgrowth' hoặc 'apriori'.")

    frequent_itemsets["length"] = frequent_itemsets["itemsets"].apply(len)
    frequent_itemsets = frequent_itemsets.sort_values(by="support", ascending=False).reset_index(drop=True)

    logger.info(f"-> Đã tìm thấy {len(frequent_itemsets):,} tập mục phổ biến.")
    return frequent_itemsets


def extract_rules(
    frequent_itemsets: pd.DataFrame,
    metric: str = "lift",
    min_threshold: float = 1.0,
) -> pd.DataFrame:
    """Trích xuất các luật kết hợp (Association Rules) từ tập mục phổ biến."""
    logger.info(f"Đang trích xuất luật kết hợp với {metric} >= {min_threshold}...")

    if frequent_itemsets.empty:
        logger.warning("Tập mục phổ biến rỗng, không thể trích xuất luật.")
        return pd.DataFrame()

    rules = association_rules(frequent_itemsets, metric=metric, min_threshold=min_threshold)
    if rules.empty:
        logger.warning(f"Không có luật nào thỏa mãn {metric} >= {min_threshold}.")
        return rules

    # Sắp xếp luật theo Lift giảm dần, sau đó theo Confidence giảm dần
    rules = rules.sort_values(by=["lift", "confidence"], ascending=[False, False]).reset_index(drop=True)

    logger.info(f"-> Đã trích xuất thành công {len(rules):,} luật kết hợp.")
    return rules


def recommend_cross_sell(
    item_query: str,
    rules_df: pd.DataFrame,
    top_k: int = 5,
) -> pd.DataFrame:
    """Gợi ý sản phẩm mua kèm khi khách hàng chọn 1 sản phẩm (Cross-selling).

    Args:
        item_query: Mã hoặc tên sản phẩm khách hàng đang xem/mua.
        rules_df: Bảng luật kết hợp trích xuất từ association_rules.
        top_k: Số lượng sản phẩm đề xuất tối đa.

    Returns:
        DataFrame chứa các sản phẩm mua kèm gợi ý, độ tin cậy và Lift.
    """
    if rules_df.empty:
        return pd.DataFrame(columns=["recommended_item", "confidence", "lift", "support"])

    matched_records = []
    query_lower = item_query.lower()

    for _, row in rules_df.iterrows():
        antecedents_list = [str(x) for x in row["antecedents"]]
        # Kiểm tra nếu item_query nằm trong antecedents
        is_matched = any(query_lower in ant.lower() for ant in antecedents_list)

        if is_matched:
            consequents_list = [str(x) for x in row["consequents"]]
            for rec_item in consequents_list:
                matched_records.append(
                    {
                        "recommended_item": rec_item,
                        "confidence": round(row["confidence"], 4),
                        "lift": round(row["lift"], 4),
                        "support": round(row["support"], 4),
                    }
                )

    if not matched_records:
        return pd.DataFrame(columns=["recommended_item", "confidence", "lift", "support"])

    rec_df = (
        pd.DataFrame(matched_records)
        .sort_values(by=["lift", "confidence"], ascending=[False, False])
        .drop_duplicates(subset=["recommended_item"])
        .head(top_k)
        .reset_index(drop=True)
    )
    return rec_df


def save_rules_to_csv(rules_df: pd.DataFrame, frequent_itemsets: pd.DataFrame):
    """Lưu tập phổ biến và luật kết hợp ra file CSV trong data/processed/."""
    project_root = Path(__file__).resolve().parent.parent.parent
    processed_dir = project_root / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    if not frequent_itemsets.empty:
        itemsets_export = frequent_itemsets.copy()
        itemsets_export["itemsets"] = itemsets_export["itemsets"].apply(lambda s: ", ".join(list(s)))
        itemsets_export.to_csv(processed_dir / "frequent_itemsets.csv", index=False, encoding="utf-8")

    if not rules_df.empty:
        rules_export = rules_df.copy()
        rules_export["antecedents"] = rules_export["antecedents"].apply(lambda s: ", ".join(list(s)))
        rules_export["consequents"] = rules_export["consequents"].apply(lambda s: ", ".join(list(s)))
        out_path = processed_dir / "association_rules.csv"
        rules_export.to_csv(out_path, index=False, encoding="utf-8")
        logger.info(f" Đã lưu luật kết hợp vào: {out_path.resolve()}")


def run_market_basket_analysis(
    item_column: str = "category_id",
    algorithm: str = "fpgrowth",
    min_support: float = 0.005,
    min_lift: float = 1.0,
) -> pd.DataFrame:
    """Chạy toàn bộ pipeline Khai phá luật kết hợp giỏ hàng."""
    print("\n" + "=" * 90)
    print(" BẮT ĐẦU KHAI PHÁ LUẬT KẾT HỢP GIỎ HÀNG (MARKET BASKET ANALYSIS)")
    print("=" * 90)

    # 1. Trích xuất transactions
    transactions = get_transactions_from_dwh(
        item_column=item_column,
        min_basket_size=2,
    )

    if not transactions:
        logger.warning("Không có đủ giao dịch đa mục để trích xuất luật.")
        return pd.DataFrame()

    # 2. Tạo ma trận One-Hot
    matrix_df = encode_transactions(transactions)

    # 3. Sinh tập phổ biến
    frequent_itemsets = mine_frequent_itemsets(
        matrix_df, algorithm=algorithm, min_support=min_support
    )

    # 4. Trích xuất luật kết hợp
    rules = extract_rules(frequent_itemsets, metric="lift", min_threshold=min_lift)

    # 5. Lưu kết quả
    save_rules_to_csv(rules, frequent_itemsets)

    # 6. In Top 10 luật có Lift cao nhất
    if not rules.empty:
        print("\n" + "-" * 90)
        print(" TOP 10 LUẬT KẾT HỢP CÓ ĐỘ NÂNG (LIFT) CAO NHẤT:")
        print("-" * 90)
        print(f" {'TIỀN ĐỀ (Antecedents)':<35} => {'HỆ QUẢ (Consequents)':<30} | {'Support':<8} | {'Confidence':<10} | {'Lift':<6}")
        print("-" * 90)
        for _, r in rules.head(10).iterrows():
            ant = ", ".join(list(r["antecedents"]))
            con = ", ".join(list(r["consequents"]))
            print(f" {ant:<35} => {con:<30} | {r['support']:<8.4f} | {r['confidence']:<10.4f} | {r['lift']:<6.2f}")
        print("=" * 90 + "\n")

    return rules


if __name__ == "__main__":
    # Chạy khai phá theo danh mục sản phẩm (category_id)
    rules_result = run_market_basket_analysis(
        item_column="category_id",
        algorithm="fpgrowth",
        min_support=0.005,
        min_lift=1.1,
    )

    # Demo hàm gợi ý sản phẩm mua kèm
    if not rules_result.empty:
        first_ant = list(rules_result.iloc[0]["antecedents"])[0]
        print(f"\n [DEMO] GỢI Ý MUA KÈM CHO MẶT HÀNG: '{first_ant}':")
        recs = recommend_cross_sell(first_ant, rules_result, top_k=5)
        print(recs.to_string(index=False))
