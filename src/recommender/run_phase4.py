"""Phase 4 - Recommender System end-to-end pipeline."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None

from src.recommender.collaborative_filtering import run_cf_pipeline
from src.recommender.content_based import run_cb_pipeline
from src.recommender.evaluation import run_full_evaluation

if __name__ == "__main__":
    print("=" * 65)
    print(" PHASE 4: RECOMMENDER SYSTEM - END-TO-END PIPELINE")
    print("=" * 65)

    # 1. Collaborative Filtering (SVD)
    cf_model, df_train, df_test = run_cf_pipeline(n_components=50, top_k=20)

    # 2. Content-Based Filtering (TF-IDF)
    cb_model = run_cb_pipeline(top_k=20)

    # 3. Danh gia va so sanh
    df_result = run_full_evaluation(
        cf_model, cb_model, df_train, df_test,
        k_values=[5, 10, 20],
        min_rating=3.5,
    )

    # 4. Luu ket qua
    out_path = Path(__file__).resolve().parents[2] / "data" / "processed" / "evaluation_results.csv"
    df_result.to_csv(out_path, index=False, encoding="utf-8")
    print(f"\nKet qua danh gia da luu: {out_path}")
