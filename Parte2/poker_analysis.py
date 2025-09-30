import os
import warnings
from typing import Tuple, List

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from collections import Counter
from sklearn.model_selection import StratifiedKFold, train_test_split, cross_validate
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix, ConfusionMatrixDisplay
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

warnings.filterwarnings("ignore", category=UserWarning)

DATA_URL_TRAIN = "https://archive.ics.uci.edu/ml/machine-learning-databases/poker/poker-hand-training-true.data"
DATA_URL_TEST  = "https://archive.ics.uci.edu/ml/machine-learning-databases/poker/poker-hand-testing.data"

OUTPUTS_DIR = "outputs"
RANDOM_STATE = 42

def ensure_outputs():
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

def load_poker_data(sample_n: int = None) -> Tuple[pd.DataFrame, pd.Series]:
    colnames = ["S1","R1","S2","R2","S3","R3","S4","R4","S5","R5","y"]
    df_tr = pd.read_csv(DATA_URL_TRAIN, header=None, names=colnames)
    try:
        df_te = pd.read_csv(DATA_URL_TEST, header=None, names=colnames)
    except Exception:
        df_te = pd.DataFrame(columns=colnames)
    df = pd.concat([df_tr, df_te], axis=0, ignore_index=True)
    if sample_n is not None and sample_n > 0 and sample_n < len(df):
        df = df.sample(n=sample_n, random_state=RANDOM_STATE).reset_index(drop=True)
    X = df.drop(columns=["y"]).copy()
    y = df["y"].copy().astype(int)
    return X, y

def make_hand_features(df_cards: pd.DataFrame) -> pd.DataFrame:
    ranks = df_cards[["R1","R2","R3","R4","R5"]].values
    suits = df_cards[["S1","S2","S3","S4","S5"]].values

    feats = {
        "unique_ranks": [], "unique_suits": [], "max_count_rank": [], "max_count_suit": [],
        "num_pairs": [], "has_three": [], "has_four": [], "is_flush": [],
        "is_straight": [], "straight_high_rank": [],
        "rank_sum": [], "rank_mean": [], "rank_std": [],
        "top1_rank": [], "top2_rank": [], "top3_rank": [],
        "rank_gap12": [], "rank_gap23": [], "rank_gap34": [], "rank_gap45": [],
    }

    def is_sequence(sorted_ranks: List[int]):
        diffs = np.diff(sorted_ranks)
        if np.all(diffs == 1):
            return True, int(sorted_ranks[-1])
        return False, 0

    for i in range(df_cards.shape[0]):
        r = ranks[i, :].astype(int)
        s = suits[i, :].astype(int)
        r_sorted = np.sort(r)
        uniq_r = np.unique(r_sorted)
        uniq_s = np.unique(s)
        from collections import Counter as C
        cnt_r = C(r_sorted)
        cnt_s = C(s)
        counts_r_sorted = sorted(cnt_r.values(), reverse=True)
        max_cnt_r = counts_r_sorted[0] if counts_r_sorted else 0
        num_pairs = sum(1 for v in cnt_r.values() if v == 2)
        has_three = 1 if any(v == 3 for v in cnt_r.values()) else 0
        has_four = 1 if any(v == 4 for v in cnt_r.values()) else 0
        max_cnt_s = max(cnt_s.values()) if cnt_s else 0
        is_flush = 1 if max_cnt_s == 5 else 0
        straight, high = is_sequence(r_sorted)

        gaps = np.diff(r_sorted)
        gap12, gap23, gap34, gap45 = (int(gaps[0]), int(gaps[1]), int(gaps[2]), int(gaps[3]))

        feats["unique_ranks"].append(len(uniq_r))
        feats["unique_suits"].append(len(uniq_s))
        feats["max_count_rank"].append(max_cnt_r)
        feats["max_count_suit"].append(max_cnt_s)
        feats["num_pairs"].append(num_pairs)
        feats["has_three"].append(has_three)
        feats["has_four"].append(has_four)
        feats["is_flush"].append(is_flush)
        feats["is_straight"].append(1 if straight else 0)
        feats["straight_high_rank"].append(high)
        feats["rank_sum"].append(int(r_sorted.sum()))
        feats["rank_mean"].append(float(r_sorted.mean()))
        feats["rank_std"].append(float(r_sorted.std()))
        feats["top1_rank"].append(int(r_sorted[-1]))
        feats["top2_rank"].append(int(r_sorted[-2]))
        feats["top3_rank"].append(int(r_sorted[-3]))
        feats["rank_gap12"].append(gap12)
        feats["rank_gap23"].append(gap23)
        feats["rank_gap34"].append(gap34)
        feats["rank_gap45"].append(gap45)

    return pd.DataFrame(feats, index=df_cards.index)

def build_dataset(sample_n: int = None) -> Tuple[pd.DataFrame, pd.Series]:
    X_raw, y = load_poker_data(sample_n=sample_n)
    X_feat = make_hand_features(X_raw)
    X_all = pd.concat([X_raw, X_feat], axis=1)
    return X_all, y

def eda_plots(X_raw: pd.DataFrame, y: pd.Series):
    ensure_outputs()
    plt.figure()
    y.value_counts().sort_index().plot(kind="bar")
    plt.title("Distribución de etiquetas (mano de póker)")
    plt.xlabel("Clase (0..9)")
    plt.ylabel("Frecuencia")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUTS_DIR, "labels_distribution.png"))
    plt.close()

    for col in ["R1","R2","R3","R4","R5"]:
        plt.figure()
        X_raw[col].plot(kind="hist", bins=13)
        plt.title(f"Histograma {col}")
        plt.xlabel("Rango (1..13)")
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUTS_DIR, f"hist_{col}.png"))
        plt.close()

    for col in ["S1","S2","S3","S4","S5"]:
        plt.figure()
        X_raw[col].plot(kind="hist", bins=4)
        plt.title(f"Histograma {col}")
        plt.xlabel("Traje (1..4)")
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUTS_DIR, f"hist_{col}.png"))
        plt.close()

def evaluate_models(X: pd.DataFrame, y: pd.Series, cv_splits: int = 5, fast: bool = False) -> pd.DataFrame:
    ensure_outputs()
    logreg = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs"))
    ])

    rf = RandomForestClassifier(
        n_estimators=200 if not fast else 120,
        max_depth=20 if not fast else 12,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        class_weight="balanced_subsample"
    )

    folds = 3 if fast else cv_splits
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=RANDOM_STATE)
    scoring = {"accuracy": "accuracy", "f1_macro": "f1_macro"}

    # Ejecutar CV en un solo proceso para evitar problemas con backends/GC
    cv_logreg = cross_validate(logreg, X, y, scoring=scoring, cv=skf, return_train_score=False, n_jobs=1)
    cv_rf     = cross_validate(rf,    X, y, scoring=scoring, cv=skf, return_train_score=False, n_jobs=1)

    results = pd.DataFrame({
        "model": ["LogisticRegression"] * folds + ["RandomForest"] * folds,
        "fold": list(range(1, folds+1)) * 2,
        "accuracy": np.concatenate([cv_logreg["test_accuracy"], cv_rf["test_accuracy"]]),
        "f1_macro": np.concatenate([cv_logreg["test_f1_macro"], cv_rf["test_f1_macro"]]),
    })

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)
    logreg.fit(X_tr, y_tr)
    rf.fit(X_tr, y_tr)

    preds_lr = logreg.predict(X_te)
    preds_rf = rf.predict(X_te)

    acc_lr = accuracy_score(y_te, preds_lr)
    f1_lr  = f1_score(y_te, preds_lr, average="macro")
    acc_rf = accuracy_score(y_te, preds_rf)
    f1_rf  = f1_score(y_te, preds_rf, average="macro")

    with open(os.path.join(OUTPUTS_DIR, "classification_report_logreg.txt"), "w", encoding="utf-8") as f:
        f.write(classification_report(y_te, preds_lr, digits=4))
        f.write(f"\nAccuracy: {acc_lr:.4f}  Macro-F1: {f1_lr:.4f}\n")

    with open(os.path.join(OUTPUTS_DIR, "classification_report_randomforest.txt"), "w", encoding="utf-8") as f:
        f.write(classification_report(y_te, preds_rf, digits=4))
        f.write(f"\nAccuracy: {acc_rf:.4f}  Macro-F1: {f1_rf:.4f}\n")

    for name, preds in [("logreg", preds_lr), ("randomforest", preds_rf)]:
        cm = confusion_matrix(y_te, preds, labels=sorted(y.unique()))
        disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=sorted(y.unique()))
        fig, ax = plt.subplots()
        disp.plot(ax=ax, xticks_rotation=45, colorbar=False)
        ax.set_title(f"Matriz de confusión - {name}")
        fig.tight_layout()
        fig.savefig(os.path.join(OUTPUTS_DIR, f"confusion_{name}.png"))
        plt.close(fig)

    importances = pd.Series(rf.feature_importances_, index=X.columns).sort_values(ascending=False)
    topk = importances.head(20)
    plt.figure()
    topk[::-1].plot(kind="barh")
    plt.title("Top 20 Importancias - Random Forest")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUTS_DIR, "feature_importance_rf_top20.png"))
    plt.close()

    results.to_csv(os.path.join(OUTPUTS_DIR, "cv_results.csv"), index=False)
    summary = results.groupby("model")[["accuracy","f1_macro"]].agg(["mean","std"])
    summary.to_csv(os.path.join(OUTPUTS_DIR, "cv_summary.csv"))
    print("Resumen CV:")
    print(summary)
    print("\nHoldout (20%)\n - LogReg:  acc={:.4f}, f1_macro={:.4f}\n - RF:      acc={:.4f}, f1_macro={:.4f}".format(acc_lr, f1_lr, acc_rf, f1_rf))
    return results

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=100000, help="Tamaño de muestra máximo a usar. Usa -1 para todo.")
    parser.add_argument("--fast", action="store_true", help="Modo rápido: CV con 3 folds y RF más ligero.")
    args = parser.parse_args()

    ensure_outputs()

    sample_n = None if args.sample == -1 else args.sample
    print("Cargando datos...")
    X_raw, y = load_poker_data(sample_n=sample_n)
    print(f"Dataset shape (raw): {X_raw.shape}, y: {y.shape}")

    print("Generando EDA...")
    eda_plots(X_raw, y)

    print("Ingeniería de características...")
    X_feat = make_hand_features(X_raw)
    X_all = pd.concat([X_raw, X_feat], axis=1)
    X_all.to_csv(os.path.join(OUTPUTS_DIR, "dataset_with_features.csv"), index=False)

    print("Evaluando modelos...")
    _ = evaluate_models(X_all, y, cv_splits=5, fast=args.fast)

    print("Listo. Resultados en la carpeta 'outputs/' para gráficos y métricas.")

if __name__ == "__main__":
    main()
