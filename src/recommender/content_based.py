"""Content-Based Filtering dung TF-IDF va Cosine Similarity tren du lieu san pham."""
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Recommender.CB")


# ===========================================================================
# 1. LOAD DU LIEU SAN PHAM TU DWH / STAGING
# ===========================================================================

def load_product_data(engine_instance=None) -> pd.DataFrame:
    """Load du lieu san pham (Dim_Product + Dim_Category) tu DWH hoac Staging CSV/Parquet."""
    project_root = Path(__file__).resolve().parent.parent.parent
    processed_dir = project_root / "data" / "processed"

    if engine_instance is not None:
        try:
            from sqlalchemy import text
            sql = """SELECT p.product_id, p.product_name, p.category_id, p.description,
                            p.price, p.brand, p.ingredients_text, c.category_name
                     FROM dim_product p LEFT JOIN dim_category c ON p.category_id = c.category_id"""
            with engine_instance.connect() as conn:
                df = pd.read_sql_query(text(sql), conn)
                logger.info("Da tai %d san pham tu DWH.", len(df))
                return df
        except Exception as exc:
            logger.warning("Khong ket noi DWH: %s. Chuyen sang Staging.", exc)

    prod_path = processed_dir / "dim_product.csv"
    cat_path = processed_dir / "dim_category.csv"
    if not prod_path.exists():
        prod_path = processed_dir / "dim_product.parquet"
        cat_path = processed_dir / "dim_category.parquet"

    if not prod_path.exists():
        raise FileNotFoundError(str(prod_path))

    df_prod = pd.read_parquet(prod_path) if str(prod_path).endswith(".parquet") else pd.read_csv(prod_path)
    if cat_path.exists():
        df_cat = pd.read_parquet(cat_path) if str(cat_path).endswith(".parquet") else pd.read_csv(cat_path)
        df_prod = df_prod.merge(df_cat[["category_id", "category_name"]], on="category_id", how="left")
    else:
        df_prod["category_name"] = "unknown"

    logger.info("Da tai %d san pham tu Staging.", len(df_prod))
    return df_prod


# ===========================================================================
# 2. TIEN XU LY - TAO FEATURE VAN BAN
# ===========================================================================

def _fill_col(s: pd.Series, default: str = "") -> pd.Series:
    return s.fillna(default).astype(str).str.strip()


def build_text_features(df: pd.DataFrame) -> pd.DataFrame:
    """Tao cot 'text_features' bang cach ghep cac truong van ban cua san pham.

    So do trong so: category_name (x3) > product_name (x2) > brand (x1) > ingredients (x1) > description (x1).
    """
    df = df.copy()
    cat = _fill_col(df.get("category_name", pd.Series([""] * len(df))), "unknown")
    name = _fill_col(df.get("product_name", pd.Series([""] * len(df))), "")
    brand = _fill_col(df.get("brand", pd.Series([""] * len(df))), "")
    desc = _fill_col(df.get("description", pd.Series([""] * len(df))), "")
    ingredients = _fill_col(df.get("ingredients_text", pd.Series([""] * len(df))), "")

    # Lam sach: giu lai ky tu alphanumeric va khoang trang
    import re
    def clean(s: str) -> str:
        return re.sub(r"[^a-zA-Z0-9\s]", " ", s).lower().strip()

    df["text_features"] = (
        (cat.apply(clean) + " ") * 3
        + (name.apply(clean) + " ") * 2
        + brand.apply(clean) + " "
        + ingredients.apply(clean) + " "
        + desc.str[:500].apply(clean)
    )
    df["text_features"] = df["text_features"].str.replace(r"\s+", " ", regex=True).str.strip()
    logger.info("Da tao text_features cho %d san pham.", len(df))
    return df


# ===========================================================================
# 3. MO HINH CONTENT-BASED FILTERING
# ===========================================================================

class ContentBasedRecommender:
    """Goi y san pham dua tren do tuong dong noi dung (TF-IDF + Cosine Similarity)."""

    def __init__(
        self,
        max_features: int = 5000,
        ngram_range: tuple = (1, 2),
        use_price: bool = True,
        price_weight: float = 0.15,
    ):
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.use_price = use_price
        self.price_weight = price_weight

        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            stop_words="english",
            sublinear_tf=True,
            min_df=1,
        )
        self.tfidf_matrix: Optional[np.ndarray] = None
        self.product_ids: Optional[np.ndarray] = None
        self.prod_idx: Dict[str, int] = {}
        self.df_products: Optional[pd.DataFrame] = None
        self.is_fitted = False

    def fit(self, df: pd.DataFrame):
        """Huan luyen mo hinh tren du lieu san pham."""
        logger.info("Dang huan luyen Content-Based Recommender (%d san pham)...", len(df))
        df = build_text_features(df)
        self.df_products = df.reset_index(drop=True)
        self.product_ids = self.df_products["product_id"].values
        self.prod_idx = {pid: i for i, pid in enumerate(self.product_ids)}

        # TF-IDF ma tran van ban
        tfidf_arr = self.vectorizer.fit_transform(self.df_products["text_features"]).toarray()
        feature_matrix = tfidf_arr

        # Them dac trung gia (numeric) - giam trong so de khong at dac trung van ban
        if self.use_price and "price" in self.df_products.columns:
            prices = self.df_products["price"].fillna(0).values.reshape(-1, 1).astype(float)
            prices_scaled = MinMaxScaler().fit_transform(prices)
            feature_matrix = np.hstack([
                tfidf_arr * (1 - self.price_weight),
                prices_scaled * self.price_weight,
            ])

        self.tfidf_matrix = feature_matrix.astype(np.float32)
        self.is_fitted = True
        logger.info(
            "Content-Based Recommender san sang. Ma tran dac trung: %s.",
            self.tfidf_matrix.shape,
        )
        return self

    def recommend_by_product(self, product_id: str, top_k: int = 10,
                              exclude_self: bool = True) -> pd.DataFrame:
        """Goi y cac san pham tuong tu voi san pham dau vao."""
        if not self.is_fitted:
            raise RuntimeError("Chua huan luyen. Goi .fit() truoc.")
        idx = self.prod_idx.get(product_id)
        if idx is None:
            logger.warning("Khong tim thay product_id=%s", product_id)
            return pd.DataFrame(columns=["product_id", "similarity_score"])

        query_vec = self.tfidf_matrix[idx].reshape(1, -1)
        sims = cosine_similarity(query_vec, self.tfidf_matrix)[0]

        if exclude_self:
            sims[idx] = -1.0

        top_idx = np.argsort(sims)[::-1][:top_k]
        result = pd.DataFrame({
            "product_id": self.product_ids[top_idx],
            "similarity_score": sims[top_idx].round(5),
        })
        # Gan them thong tin san pham
        if "product_name" in self.df_products.columns:
            name_map = dict(zip(self.product_ids, self.df_products["product_name"].values))
            result["product_name"] = result["product_id"].map(name_map)
        if "category_name" in self.df_products.columns:
            cat_map = dict(zip(self.product_ids, self.df_products["category_name"].values))
            result["category_name"] = result["product_id"].map(cat_map)
        return result

    def recommend_for_user(self, user_id: str, interaction_df: pd.DataFrame,
                            top_k: int = 10, n_seed_products: int = 3) -> pd.DataFrame:
        """Goi y san pham cho user dua tren lich su tuong tac cua ho.

        Lay trung binh weighted cac vector cua seed products (co rating cao nhat).
        """
        if not self.is_fitted:
            raise RuntimeError("Chua huan luyen. Goi .fit() truoc.")

        user_hist = interaction_df[interaction_df["user_id"] == user_id].copy()
        if user_hist.empty:
            return pd.DataFrame(columns=["product_id", "similarity_score"])

        # Chon seed products co rating cao nhat
        if "rating_value" in user_hist.columns:
            user_hist = user_hist.sort_values("rating_value", ascending=False)
        seeds = user_hist["product_id"].head(n_seed_products).tolist()
        seen = set(user_hist["product_id"])

        # Tinh trung binh vector dac trung cua seed products
        seed_vecs = []
        for pid in seeds:
            idx = self.prod_idx.get(pid)
            if idx is not None:
                seed_vecs.append(self.tfidf_matrix[idx])
        if not seed_vecs:
            return pd.DataFrame(columns=["product_id", "similarity_score"])

        user_profile = np.mean(seed_vecs, axis=0).reshape(1, -1)
        sims = cosine_similarity(user_profile, self.tfidf_matrix)[0]

        # Loai cac san pham da xem
        for pid in seen:
            idx = self.prod_idx.get(pid)
            if idx is not None:
                sims[idx] = -1.0

        top_idx = np.argsort(sims)[::-1][:top_k]
        result = pd.DataFrame({
            "product_id": self.product_ids[top_idx],
            "similarity_score": sims[top_idx].round(5),
        })
        if "product_name" in self.df_products.columns:
            name_map = dict(zip(self.product_ids, self.df_products["product_name"].values))
            result["product_name"] = result["product_id"].map(name_map)
        if "category_name" in self.df_products.columns:
            cat_map = dict(zip(self.product_ids, self.df_products["category_name"].values))
            result["category_name"] = result["product_id"].map(cat_map)
        return result

    def recommend_batch_for_users(self, user_ids: List[str], interaction_df: pd.DataFrame,
                                  top_k: int = 10, n_seed_products: int = 3) -> Dict[str, List[str]]:
        """Batch recommend - vectorized: tinh cosine similarity mot lan cho tat ca users.

        Thay vi goi cosine_similarity() tung user (cham), xay dung ma tran user profiles
        kich thuoc (n_users, n_features) roi tinh mot phep nhan ma tran duy nhat.
        """
        if not self.is_fitted:
            raise RuntimeError("Chua huan luyen. Goi .fit() truoc.")

        # Nhom interaction theo user
        user_hist_map = {uid: grp for uid, grp in interaction_df.groupby("user_id")}

        # Xay dung user profile matrix (n_users, n_features)
        valid_users = []
        profile_matrix = []
        seen_map: Dict[str, set] = {}

        for uid in user_ids:
            hist = user_hist_map.get(uid)
            if hist is None or hist.empty:
                continue
            if "rating_value" in hist.columns:
                hist = hist.sort_values("rating_value", ascending=False)
            seeds = hist["product_id"].head(n_seed_products).tolist()
            seen_map[uid] = set(hist["product_id"])

            vecs = [self.tfidf_matrix[self.prod_idx[p]] for p in seeds if p in self.prod_idx]
            if not vecs:
                continue
            profile_matrix.append(np.mean(vecs, axis=0))
            valid_users.append(uid)

        if not valid_users:
            return {}

        # Tinh cosine similarity: (n_valid_users, n_items) - mot phep nhan
        profiles = np.array(profile_matrix, dtype=np.float32)  # (n_u, k)
        # Normalize
        norms = np.linalg.norm(profiles, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        profiles_normed = profiles / norms

        # item_matrix da duoc normalize trong .fit()
        item_norms = np.linalg.norm(self.tfidf_matrix, axis=1, keepdims=True)
        item_norms[item_norms == 0] = 1.0
        items_normed = self.tfidf_matrix / item_norms

        sim_matrix = profiles_normed @ items_normed.T  # (n_u, n_items)
        logger.info("Da tinh cosine similarity batch: %s.", sim_matrix.shape)

        results: Dict[str, List[str]] = {}
        for i, uid in enumerate(valid_users):
            sims = sim_matrix[i].copy()
            for pid in seen_map.get(uid, set()):
                idx = self.prod_idx.get(pid)
                if idx is not None:
                    sims[idx] = -1.0
            top_idx = np.argsort(sims)[::-1][:top_k]
            results[uid] = list(self.product_ids[top_idx])

        return results


# ===========================================================================
# 4. PIPELINE
# ===========================================================================

def run_cb_pipeline(top_k: int = 10) -> ContentBasedRecommender:
    print("\n" + "=" * 65)
    print(" CONTENT-BASED FILTERING - TF-IDF + COSINE SIMILARITY")
    print("=" * 65)
    df_prod = load_product_data()
    model = ContentBasedRecommender(max_features=5000, use_price=True)
    model.fit(df_prod)
    return model


if __name__ == "__main__":
    cb_model = run_cb_pipeline()
    sample_pid = cb_model.product_ids[0]
    recs = cb_model.recommend_by_product(sample_pid, top_k=5)
    print(f"\n[DEMO] Top-5 san pham tuong tu voi product '{sample_pid[:12]}...':")
    print(recs[["product_id", "similarity_score"]].to_string(index=False))
