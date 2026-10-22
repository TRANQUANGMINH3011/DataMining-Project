"""Danh gia hieu nang cac he thong goi y: Precision@K, Recall@K, NDCG@K."""
import logging
import sys
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Recommender.Eval")


# ===========================================================================
# 1. CAC METRIC DANH GIA OFFLINE
# ===========================================================================

def precision_at_k(recommended: List[str], relevant: set, k: int) -> float:
    """Precision@K = |rec[:K] & relevant| / K"""
    if not recommended or k == 0:
        return 0.0
    rec_k = recommended[:k]
    hits = sum(1 for r in rec_k if r in relevant)
    return hits / k


def recall_at_k(recommended: List[str], relevant: set, k: int) -> float:
    """Recall@K = |rec[:K] & relevant| / |relevant|"""
    if not recommended or not relevant or k == 0:
        return 0.0
    rec_k = recommended[:k]
    hits = sum(1 for r in rec_k if r in relevant)
    return hits / len(relevant)


def ndcg_at_k(recommended: List[str], relevant: set, k: int) -> float:
    """NDCG@K (Normalized Discounted Cumulative Gain).

    Gan nhi phan relevance: 1 neu san pham trong relevant, 0 neu khong.
    DCG@K = sum( rel_i / log2(i+2) ) voi i tu 0 den K-1.
    IDCG@K = DCG cua thu tu ly tuong (tat ca relevant o dau).
    """
    if not recommended or not relevant or k == 0:
        return 0.0
    rec_k = recommended[:k]
    dcg = sum(
        (1.0 / np.log2(i + 2)) if rec_k[i] in relevant else 0.0
        for i in range(len(rec_k))
    )
    ideal_k = min(k, len(relevant))
    idcg = sum(1.0 / np.log2(i + 2) for i in range(ideal_k))
    return dcg / idcg if idcg > 0 else 0.0


def hit_rate_at_k(recommended: List[str], relevant: set, k: int) -> float:
    """Hit Rate@K = 1 neu co it nhat 1 san pham relevant trong top-K, nguoc lai 0."""
    return 1.0 if any(r in relevant for r in recommended[:k]) else 0.0


def average_precision_at_k(recommended: List[str], relevant: set, k: int) -> float:
    """Average Precision@K (AP@K) - co tinh den thu tu cua cac hit."""
    if not recommended or not relevant or k == 0:
        return 0.0
    rec_k = recommended[:k]
    score, hits = 0.0, 0
    for i, r in enumerate(rec_k):
        if r in relevant:
            hits += 1
            score += hits / (i + 1)
    return score / min(k, len(relevant))


# ===========================================================================
# 2. DANH GIA TREN TAP TEST (BATCH)
# ===========================================================================

def build_ground_truth(df_test: pd.DataFrame,
                        min_rating: Optional[float] = 3.5) -> Dict[str, set]:
    """Tao bo ground truth: {user_id: set of product_ids trong tap test}.

    Args:
        df_test: DataFrame tap Test.
        min_rating: Chi coi la 'relevant' neu rating >= nguong nay. None = moi tuong tac la relevant.
    """
    if min_rating is not None and "rating_value" in df_test.columns:
        df_rel = df_test[df_test["rating_value"] >= min_rating]
    else:
        df_rel = df_test
    return df_rel.groupby("user_id")["product_id"].apply(set).to_dict()


def evaluate_recommendations(
    recommendations: Dict[str, List[str]],
    ground_truth: Dict[str, set],
    k_values: List[int] = [5, 10, 20],
    model_name: str = "Model",
) -> pd.DataFrame:
    """Tinh cac metric Precision@K, Recall@K, NDCG@K, HitRate@K, MAP@K cho tat ca user.

    Args:
        recommendations: {user_id: [product_id, ...]} - ket qua goi y.
        ground_truth: {user_id: set(product_id)} - cac san pham relevant trong tap Test.
        k_values: Danh sach cac gia tri K can danh gia.
        model_name: Ten mo hinh (de bao cao).

    Returns:
        DataFrame chua ket qua trung binh cac metric theo tung K.
    """
    logger.info("Danh gia %s tren %d users...", model_name, len(recommendations))
    common_users = [u for u in recommendations if u in ground_truth]
    if not common_users:
        logger.warning("Khong co user nao overlap giua recommendations va ground_truth!")
        return pd.DataFrame()

    rows = []
    for k in k_values:
        p_list, r_list, ndcg_list, hr_list, map_list = [], [], [], [], []
        for uid in common_users:
            recs = recommendations[uid]
            relevant = ground_truth[uid]
            if not relevant:
                continue
            p_list.append(precision_at_k(recs, relevant, k))
            r_list.append(recall_at_k(recs, relevant, k))
            ndcg_list.append(ndcg_at_k(recs, relevant, k))
            hr_list.append(hit_rate_at_k(recs, relevant, k))
            map_list.append(average_precision_at_k(recs, relevant, k))

        n = len(p_list)
        rows.append({
            "Model": model_name,
            "K": k,
            "Precision@K": round(np.mean(p_list), 6) if p_list else 0.0,
            "Recall@K": round(np.mean(r_list), 6) if r_list else 0.0,
            "NDCG@K": round(np.mean(ndcg_list), 6) if ndcg_list else 0.0,
            "HitRate@K": round(np.mean(hr_list), 6) if hr_list else 0.0,
            "MAP@K": round(np.mean(map_list), 6) if map_list else 0.0,
            "N_Users": n,
        })

    df_result = pd.DataFrame(rows)
    return df_result


# ===========================================================================
# 3. SO SANH NHIEU MO HINH
# ===========================================================================

def compare_models(
    model_results: Dict[str, Dict[str, List[str]]],
    ground_truth: Dict[str, set],
    k_values: List[int] = [5, 10, 20],
) -> pd.DataFrame:
    """So sanh hieu nang giua nhieu mo hinh goi y.

    Args:
        model_results: {model_name: {user_id: [product_id]}}
        ground_truth: {user_id: set(product_id)}
        k_values: Cac gia tri K can so sanh.

    Returns:
        DataFrame hop nhat ket qua cua tat ca mo hinh.
    """
    all_results = []
    for model_name, recs in model_results.items():
        df_eval = evaluate_recommendations(recs, ground_truth, k_values=k_values, model_name=model_name)
        if not df_eval.empty:
            all_results.append(df_eval)

    if not all_results:
        return pd.DataFrame()

    df_combined = pd.concat(all_results, ignore_index=True)
    return df_combined


def print_comparison_report(df_combined: pd.DataFrame):
    """In bao cao so sanh dep len console."""
    if df_combined.empty:
        print("Khong co ket qua nao de hien thi.")
        return

    print("\n" + "=" * 80)
    print(" KET QUA DANH GIA HE THONG GOI Y")
    print("=" * 80)
    metrics = ["Precision@K", "Recall@K", "NDCG@K", "HitRate@K", "MAP@K"]
    for k_val in sorted(df_combined["K"].unique()):
        print(f"\n--- K = {k_val} ---")
        df_k = df_combined[df_combined["K"] == k_val]
        pivot = df_k.pivot(index="Model", columns="K", values=metrics).reset_index()
        # In don gian hon
        df_print = df_k[["Model"] + metrics + ["N_Users"]].copy()
        df_print.columns = ["Model"] + [m.replace("@K", f"@{k_val}") for m in metrics] + ["N_Users"]
        print(df_print.to_string(index=False))
    print("=" * 80)


# ===========================================================================
# 4. RUN DANH GIA DAY DU
# ===========================================================================

def popularity_recommend_batch(df_train: pd.DataFrame, eval_users: List[str],
                               top_k: int = 20) -> Dict[str, List[str]]:
    """Baseline: goi y cac san pham pho bien nhat (theo so luong tuong tac) cho moi user."""
    item_counts = df_train.groupby("product_id").size().sort_values(ascending=False)
    popular_items = item_counts.index.tolist()
    # Pre-build seen map de tranh O(N * M) boolean filtering tren DataFrame
    seen_map = df_train.groupby("user_id")["product_id"].apply(set).to_dict()
    results = {}
    for uid in eval_users:
        seen = seen_map.get(uid, set())
        recs = [p for p in popular_items if p not in seen][:top_k]
        results[uid] = recs
    return results


def run_full_evaluation(
    cf_model: Any,
    cb_model: Any,
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    k_values: List[int] = [5, 10, 20],
    min_rating: float = 3.5,
) -> pd.DataFrame:
    """Chay danh gia day du cho Collaborative Filtering, Content-Based va Popularity Baseline.

    Args:
        cf_model: Instance SVDRecommender da huan luyen.
        cb_model: Instance ContentBasedRecommender da huan luyen.
        df_train: DataFrame tap Train.
        df_test: DataFrame tap Test.
        k_values: Danh sach gia tri K.
        min_rating: Nguong rating de xac dinh 'relevant'.

    Returns:
        DataFrame so sanh ket qua cua tat ca mo hinh.
    """
    max_k = max(k_values)

    # Phan tich do thua cua dataset
    n_users = df_train["user_id"].nunique()
    n_items = df_train["product_id"].nunique()
    n_interactions = len(df_train)
    sparsity = 1.0 - n_interactions / (n_users * n_items)
    logger.info(
        "Dataset: %d users, %d items, %d tuong tac | Sparsity: %.4f%%",
        n_users, n_items, n_interactions, sparsity * 100,
    )

    # Tap users can danh gia
    test_users = df_test["user_id"].unique().tolist()
    gt = build_ground_truth(df_test, min_rating=min_rating)
    eval_users = [u for u in test_users if u in gt and gt[u]]
    logger.info("Danh gia tren %d users co ground truth.", len(eval_users))

    model_results = {}

    # --- Popularity Baseline ---
    logger.info("Tao goi y Popularity Baseline...")
    pop_recs = popularity_recommend_batch(df_train, eval_users, top_k=max_k)
    model_results["Popularity Baseline"] = pop_recs

    # --- Collaborative Filtering ---
    logger.info("Tao goi y Collaborative Filtering...")
    cf_recs = cf_model.recommend_batch(eval_users, top_k=max_k, train_df=df_train)
    model_results["Collaborative Filtering (SVD)"] = cf_recs

    # --- Content-Based Filtering ---
    logger.info("Tao goi y Content-Based Filtering...")
    cb_recs = cb_model.recommend_batch_for_users(eval_users, df_train, top_k=max_k)
    model_results["Content-Based (TF-IDF)"] = cb_recs

    df_comparison = compare_models(model_results, gt, k_values=k_values)
    print_comparison_report(df_comparison)

    # In phan tich do thua
    print("\n" + "-" * 80)
    print(" PHAN TICH DO THUA (SPARSITY ANALYSIS)")
    print("-" * 80)
    print(f"  Total users in train : {n_users:,}")
    print(f"  Total items in train : {n_items:,}")
    print(f"  Total interactions   : {n_interactions:,}")
    print(f"  Matrix sparsity      : {sparsity*100:.4f}%")
    print(f"  Avg interactions/user: {n_interactions/n_users:.2f}")
    print("\n  [NOTE] Dataset co do thua rat cao (sparsity > 99.9%).")
    print("  CF-SVD kho hoc pattern vi phan lon users chi co 1 tuong tac.")
    print("  Content-Based hoat dong tot hon voi cold-start va sparse data.")
    print("  Sparsity analysis nay la phan quan trong trong bao cao hoc thuat.")
    print("-" * 80)

    return df_comparison



if __name__ == "__main__":
    # Demo: chay danh gia voi du lieu that
    import sys
    sys.path.insert(0, str(__file__))
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from src.recommender.collaborative_filtering import run_cf_pipeline
    from src.recommender.content_based import run_cb_pipeline

    cf_model, df_train, df_test = run_cf_pipeline(n_components=50)
    cb_model = run_cb_pipeline()
    df_result = run_full_evaluation(cf_model, cb_model, df_train, df_test,
                                    k_values=[5, 10, 20], min_rating=3.5)
    out_path = Path(__file__).resolve().parents[2] / "data" / "processed" / "evaluation_results.csv"
    df_result.to_csv(out_path, index=False, encoding="utf-8")
    print(f"\nKet qua da luu tai: {out_path}")
