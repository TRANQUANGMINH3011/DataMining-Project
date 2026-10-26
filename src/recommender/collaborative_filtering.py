"""Collaborative Filtering voi Matrix Factorization (SVD) - Explicit Rating & Implicit Feedback."""
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Recommender.CF")

# ===========================================================================
# 1. LOAD DU LIEU TU DWH / STAGING
# ===========================================================================

def load_interactions(engine_instance=None) -> pd.DataFrame:
    project_root = Path(__file__).resolve().parent.parent.parent
    processed_dir = project_root / "data" / "processed"

    if engine_instance is not None:
        try:
            from sqlalchemy import text
            sql = """SELECT f.user_id, f.product_id,
                            COALESCE(f.rating_score, 4.0) AS rating_value,
                            19.99 AS total_amount,
                            t.full_timestamp, f.event_type
                     FROM fact_interactions f JOIN dim_time t ON f.time_id = t.time_id"""
            with engine_instance.connect() as conn:
                df = pd.read_sql_query(text(sql), conn)
                df["full_timestamp"] = pd.to_datetime(df["full_timestamp"])
                logger.info("Da tai %d tuong tac tu DWH.", len(df))
                return df
        except Exception as exc:
            logger.warning("Khong ket noi DWH: %s. Chuyen sang Staging.", exc)

    fact_path = processed_dir / "fact_interactions.csv"
    time_path = processed_dir / "dim_time.csv"
    if not fact_path.exists():
        fact_path = processed_dir / "fact_interactions.parquet"
        time_path = processed_dir / "dim_time.parquet"
    if not fact_path.exists():
        raise FileNotFoundError(str(fact_path))

    df_fact = pd.read_parquet(fact_path) if str(fact_path).endswith(".parquet") else pd.read_csv(fact_path)
    df_time = pd.read_parquet(time_path) if str(time_path).endswith(".parquet") else pd.read_csv(time_path, parse_dates=["full_timestamp"])
    df = df_fact.merge(df_time[["time_id", "full_timestamp"]], on="time_id", how="left")
    if "rating_value" not in df.columns and "rating_score" in df.columns:
        df["rating_value"] = df["rating_score"]
    if "total_amount" not in df.columns:
        df["total_amount"] = 19.99
    logger.info("Da tai %d tuong tac tu Staging.", len(df))
    return df


# ===========================================================================
# 2. CHIA TRAIN / TEST THEO THOI GIAN
# ===========================================================================

def temporal_train_test_split(df: pd.DataFrame, test_ratio: float = 0.2,
                               min_interactions_per_user: int = 2) -> Tuple[pd.DataFrame, pd.DataFrame]:
    logger.info("Chia Train/Test theo thoi gian (test_ratio=%.2f)...", test_ratio)
    df = df.sort_values("full_timestamp").copy()
    user_counts = df.groupby("user_id").size()
    active_users = user_counts[user_counts >= min_interactions_per_user].index
    df_active = df[df["user_id"].isin(active_users)].copy()
    logger.info("Users du dieu kien: %d", len(active_users))

    train_rows, test_rows = [], []
    for uid, group in df_active.groupby("user_id"):
        g = group.sort_values("full_timestamp")
        n_test = max(1, int(len(g) * test_ratio))
        train_rows.append(g.iloc[:-n_test])
        test_rows.append(g.iloc[-n_test:])

    df_train = pd.concat(train_rows, ignore_index=True)
    df_test = pd.concat(test_rows, ignore_index=True)
    inactive = df[~df["user_id"].isin(active_users)]
    df_train = pd.concat([df_train, inactive], ignore_index=True)
    logger.info("Train: %d | Test: %d", len(df_train), len(df_test))
    return df_train, df_test


# ===========================================================================
# 3. XAY DUNG MA TRAN USER-ITEM
# ===========================================================================

def build_user_item_matrix(df: pd.DataFrame, rating_col: str = "rating_value",
                            use_implicit: bool = False) -> Tuple[csr_matrix, np.ndarray, np.ndarray]:
    df_clean = df.dropna(subset=["user_id", "product_id"]).copy()
    df_clean = df_clean.groupby(["user_id", "product_id"])[rating_col].mean().reset_index()
    if use_implicit:
        df_clean[rating_col] = 1.0
    users = df_clean["user_id"].unique()
    items = df_clean["product_id"].unique()
    user2idx = {u: i for i, u in enumerate(users)}
    item2idx = {it: i for i, it in enumerate(items)}
    row = df_clean["user_id"].map(user2idx).values
    col = df_clean["product_id"].map(item2idx).values
    data = df_clean[rating_col].fillna(0).values
    matrix = csr_matrix((data, (row, col)), shape=(len(users), len(items)))
    logger.info("Ma tran User-Item: %d x %d | Density: %.4f%%",
                matrix.shape[0], matrix.shape[1], 100.0 * matrix.nnz / (matrix.shape[0] * matrix.shape[1]))
    return matrix, users, items


# ===========================================================================
# 4. MO HINH SVD
# ===========================================================================

class SVDRecommender:
    """Matrix Factorization voi TruncatedSVD. Du doan: r_ui = U_i . V_j^T."""

    def __init__(self, n_components: int = 50, random_state: int = 42):
        self.n_components = n_components
        self.random_state = random_state
        self.model = TruncatedSVD(n_components=n_components, random_state=random_state)
        self.user_factors: Optional[np.ndarray] = None
        self.item_factors: Optional[np.ndarray] = None
        self.users: Optional[np.ndarray] = None
        self.items: Optional[np.ndarray] = None
        self.user2idx: Dict = {}
        self.item2idx: Dict = {}
        self.is_fitted = False
        self._popular_items = None

    def fit(self, matrix: csr_matrix, users: np.ndarray, items: np.ndarray):
        logger.info("Huan luyen SVD (n_components=%d)...", self.n_components)
        self.users = users
        self.items = items
        self.user2idx = {u: i for i, u in enumerate(users)}
        self.item2idx = {it: i for i, it in enumerate(items)}
        self.user_factors = self.model.fit_transform(matrix)
        self.item_factors = self.model.components_.T
        self.user_factors = normalize(self.user_factors, norm="l2")
        self.item_factors = normalize(self.item_factors, norm="l2")
        self.is_fitted = True
        item_freq = __import__('numpy').asarray(matrix.sum(axis=0)).flatten()
        self._popular_items = items[__import__('numpy').argsort(item_freq)[::-1]]
        ev = self.model.explained_variance_ratio_.sum()
        logger.info("SVD hoan tat. Explained Variance: %.4f (%.2f%%)", ev, ev * 100)
        return self

    def recommend(self, user_id: str, top_k: int = 10,
                  exclude_seen: Optional[set] = None) -> pd.DataFrame:
        if not self.is_fitted:
            raise RuntimeError("Chua huan luyen. Goi .fit() truoc.")
        idx = self.user2idx.get(user_id)
        if idx is None:
            pops = [p for p in self._popular_items if p not in (exclude_seen or set())][:top_k]
            return pd.DataFrame({"product_id": pops, "predicted_score": [0.0]*len(pops)})
        scores = self.item_factors @ self.user_factors[idx]
        if exclude_seen:
            for pid in exclude_seen:
                jdx = self.item2idx.get(pid)
                if jdx is not None:
                    scores[jdx] = -np.inf
        top_idx = np.argsort(scores)[::-1][:top_k]
        return pd.DataFrame({"product_id": self.items[top_idx],
                              "predicted_score": scores[top_idx].round(5)})

    def recommend_batch(self, user_ids: List[str], top_k: int = 10,
                        train_df=None):
        """Batch recommend voi cold-start popularity fallback."""
        if not self.is_fitted:
            raise RuntimeError("Chua huan luyen.")
        known = [u for u in user_ids if u in self.user2idx]
        unknown = [u for u in user_ids if u not in self.user2idx]
        if unknown:
            logger.info("Cold-start: %d users dung popularity fallback.", len(unknown))

        # Pre-build seen map de tranh O(N * M) filtering tren DataFrame
        seen_map = {}
        if train_df is not None:
            seen_map = train_df.groupby("user_id")["product_id"].apply(set).to_dict()

        results = {}
        if known:
            import numpy as _np
            idxs = _np.array([self.user2idx[u] for u in known])
            score_matrix = self.user_factors[idxs] @ self.item_factors.T
            for ii, uid in enumerate(known):
                sc = score_matrix[ii].copy()
                seen = seen_map.get(uid, set())
                for pid in seen:
                    jdx = self.item2idx.get(pid)
                    if jdx is not None:
                        sc[jdx] = -_np.inf
                top_idx = _np.argsort(sc)[::-1][:top_k]
                results[uid] = list(self.items[top_idx])
        for uid in unknown:
            seen = seen_map.get(uid, set())
            pops = [p for p in self._popular_items if p not in seen][:top_k]
            results[uid] = pops
        return results

# ===========================================================================
# 5. PIPELINE
# ===========================================================================

def run_cf_pipeline(n_components: int = 50, top_k: int = 10,
                    use_implicit: bool = False) -> Tuple["SVDRecommender", pd.DataFrame, pd.DataFrame]:
    print("\n" + "=" * 65)
    print(" COLLABORATIVE FILTERING - SVD MATRIX FACTORIZATION")
    print("=" * 65)
    df = load_interactions()
    df_train, df_test = temporal_train_test_split(df, test_ratio=0.2, min_interactions_per_user=2)
    rating_col = "rating_value" if not use_implicit else "total_amount"
    matrix, users, items = build_user_item_matrix(df_train, rating_col=rating_col, use_implicit=use_implicit)
    model = SVDRecommender(n_components=n_components)
    model.fit(matrix, users, items)
    return model, df_train, df_test


if __name__ == "__main__":
    mdl, tr, te = run_cf_pipeline(n_components=50)
    sample = te["user_id"].iloc[0]
    seen = set(tr[tr["user_id"] == sample]["product_id"])
    print(mdl.recommend(sample, top_k=5, exclude_seen=seen).to_string(index=False))
