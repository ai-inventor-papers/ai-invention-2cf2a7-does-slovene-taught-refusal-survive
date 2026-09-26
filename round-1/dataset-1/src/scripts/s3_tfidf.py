#!/usr/bin/env python3
"""Step 3 ($0, CPU): TF-IDF hazard vote (ported unchanged from iter_3 stage0b/hazard_dose_cpu.py:
char_wb 2-5 + word 1-2 TF-IDF, LogisticRegression(C=4.0, class_weight='balanced', max_iter=2000)),
trained per language on RefusEU lang_{en,sl}/TRAIN only. Reports 5-fold CV and gold TEST accuracy, then
predicts a 14-class probability vector for eval items, gold test items, HARD items (EN originals; SL MT if present)
and dose rows. Gold TRAIN calibration items are in-sample for this classifier, so they get no TF-IDF vote."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.common import CATS, DS, LABELS, OUT, WORK, setup_logging  # noqa: E402

setup_logging("s3_tfidf")
R = DS / "NASK-PIB__RefusEU"


def user_text(conv) -> str:
    return [t["content"] for t in conv if t["role"] == "user"][0]


def featurize(train_text, *others):
    cv = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True, max_features=200000)
    wv = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=100000)
    Xtr = hstack([cv.fit_transform(train_text), wv.fit_transform(train_text)]).tocsr()
    return Xtr, [hstack([cv.transform(o), wv.transform(o)]).tocsr() for o in others]


@logger.catch(reraise=True)
def main() -> None:
    ev = pd.read_parquet(WORK / "eval_items.parquet")
    calib = pd.read_parquet(WORK / "calib_items.parquet")
    hard = pd.read_parquet(WORK / "hard_items.parquet")
    dose = pd.read_parquet(WORK / "dose_rows.parquet")
    mt_path = WORK / "hard_mt.parquet"
    hard_mt = pd.read_parquet(mt_path) if mt_path.exists() else None
    rx_path = WORK / "refuseu_x_mt.parquet"
    rx = pd.read_parquet(rx_path) if rx_path.exists() else None
    report, preds = {}, []
    for lang in ["en", "sl"]:
        tr = pd.read_parquet(R / f"lang_{lang}/train-00000-of-00001.parquet")
        te = pd.read_parquet(R / f"lang_{lang}/test-00000-of-00001.parquet")
        ttext, y = tr.chosen.map(user_text).values, tr.category.values
        targets = {"eval": ev[ev.lang == lang], "calib_test": calib[(calib.lang == lang) & (calib.gold_split == "test")],
                   "dose": dose[dose.language == lang]}
        if lang == "en":
            targets["hard"] = hard
        elif hard_mt is not None:
            targets["hard"] = hard_mt.rename(columns={"prompt_sl": "prompt_x"}).assign(prompt=lambda d: d.prompt_x)
        if lang == "sl" and rx is not None:
            targets["refuseu_x"] = rx.assign(prompt=rx.prompt_sl)
        text_col = {"dose": "user"}
        Xtr, Xo = featurize(ttext, te.chosen.map(user_text).values,
                            *[targets[k][text_col.get(k, "prompt")].fillna("").values for k in targets])
        clf = LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced")
        cvp = cross_val_predict(clf, Xtr, y, cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")
        classes = np.array(sorted(set(y)))
        yhat = classes[cvp.argmax(1)]
        clf.fit(Xtr, y)
        assert list(clf.classes_) == list(classes)
        pte = clf.predict_proba(Xo[0])
        yte = clf.classes_[pte.argmax(1)]
        report[lang] = {"train_n": len(y), "classes_in_train": list(classes), "cv5_acc": round(accuracy_score(y, yhat), 4),
                        "cv5_macroF1": round(f1_score(y, yhat, average="macro"), 4),
                        "test_n": len(te), "classes_in_test": sorted(set(te.category)),
                        "test_acc": round(accuracy_score(te.category, yte), 4),
                        "test_macroF1": round(f1_score(te.category, yte, average="macro"), 4),
                        "test_top2_acc": round(float(np.mean([t in clf.classes_[np.argsort(-p)[:2]] for t, p in zip(te.category, pte)])), 4),
                        "test_confusion": {"labels": CATS, "matrix": confusion_matrix(te.category, yte, labels=CATS).tolist()}}
        logger.info(f"{lang}: {json.dumps({k: v for k, v in report[lang].items() if 'confusion' not in k and 'classes' not in k})}")
        for (name, df), X in zip(targets.items(), Xo[1:]):
            P = clf.predict_proba(X)
            idcol = {"dose": "row_key"}.get(name, "item_id")
            full = np.zeros((len(P), 14))
            for j, c in enumerate(clf.classes_):
                full[:, CATS.index(c)] = P[:, j]
            srt = np.argsort(-full, 1)
            preds.append(pd.DataFrame({"key": df[idcol].values, "set": name, "lang": lang,
                                       "tfidf_top": [CATS[i] for i in srt[:, 0]], "tfidf_runner_up": [CATS[i] for i in srt[:, 1]],
                                       "tfidf_pmax": full.max(1), "tfidf_probs": [list(np.round(r, 5)) for r in full]}))
    out = pd.concat(preds, ignore_index=True)
    LABELS.mkdir(exist_ok=True)
    out.to_parquet(LABELS / "tfidf_votes.parquet")
    (OUT / "tfidf_report.json").write_text(json.dumps(report, indent=1))
    logger.info(f"saved {len(out)} tfidf votes: {out.groupby(['set', 'lang']).size().to_dict()}")


if __name__ == "__main__":
    main()
