````markdown
# Experimental scripts — NormDef-FR

This directory contains the scripts used to build the experimental datasets and reproduce the baseline experiments reported for NormDef-FR.

The experimental pipeline starts from the manually validated NormDef-FR gold corpus and produces:

- term-definition extraction datasets;
- candidate validation datasets;
- article-level definition detection datasets;
- rule-based extraction metrics;
- TF-IDF baseline results;
- CamemBERT baseline results;
- 5-fold cross-validation results;
- candidate validation error analysis.

The scripts in this directory are intended for experimental reproducibility. They are separate from the annotation scripts used to build the gold corpus.

---

## 1. Expected inputs

The main expected inputs are:

```text
data/normdef_fr_gold.jsonl
data/candidates/candidate_true_negative.jsonl
````

Depending on the local organization of the repository, file names may also include historical version suffixes such as:

```text
normdef_fr_v0_6_gold.jsonl
candidate_true_negative.jsonl
```

The gold corpus contains the manually validated NormDef-FR definitions.
The true negative file contains manually verified non-definition articles used to build the article-level benchmark.

---

## 2. Recommended execution order

The recommended order is:

```text
1. prepare_experiment_dataset.py
2. create_experiment_splits.py
3. build_certified_article_classification_dataset.py
4. rule_based_extraction_baseline.py
5. train_tfidf_certified_article_classifier.py
6. train_camembert_certified_article_classifier.py
7. train_tfidf_candidate_validator.py
8. train_camembert_candidate_validator.py
9. cross_validate_tfidf_candidate_validator.py
10. error_analysis_candidate_validation.py
```

The exact command-line arguments may depend on your local paths. Run each script with:

```bash
python scripts/experiments/<script_name>.py --help
```

if argument parsing is implemented.

---

## 3. Script descriptions

### `prepare_experiment_dataset.py`

Builds the main experimental datasets from the NormDef-FR gold corpus.

It creates datasets for:

* term-definition extraction;
* candidate validation;
* article-level classification;
* experiment summary metadata.

Typical outputs:

```text
data/experiments/normdef_gold_instances.jsonl
data/experiments/normdef_term_definition_extraction.jsonl
data/experiments/normdef_candidate_validation.jsonl
data/experiments/normdef_article_classification.jsonl
data/experiments/normdef_experiment_summary.json
```

This script is the main entry point for transforming the validated gold corpus into experimental files.

---

### `create_experiment_splits.py`

Creates train/dev/test splits for the experimental datasets.

The splits are grouped by article key to avoid leakage between training and evaluation data.

Expected split sizes:

```text
Term-definition extraction:
- train: 509
- dev: 88
- test: 96
- total: 693

Candidate validation:
- train: 322
- dev: 79
- test: 48
- total: 449
```

For article-level classification, the final verified benchmark is built separately by `build_certified_article_classification_dataset.py`.

---

### `build_certified_article_classification_dataset.py`

Builds the manually verified article-level definition detection benchmark.

This script combines:

* positive examples sampled from gold definition articles;
* manually verified true negative articles.

Expected final benchmark:

```text
Total examples: 600
Definition articles: 300
Manually verified true negatives: 300
```

Expected split:

```text
Train: 420 | labels: {0: 210, 1: 210}
Dev:    90 | labels: {0: 45, 1: 45}
Test:   90 | labels: {0: 45, 1: 45}
```

The script also checks that there is no article overlap between train, dev, and test splits.

---

### `rule_based_extraction_baseline.py`

Evaluates the rule-based term-definition extraction baseline.

The script applies explicit French legal definitional patterns, including:

```text
terme_colon_definition
on entend par
s'entend de
défini comme
est considéré comme
```

It evaluates predicted terms and definitions against the gold test split.

Main metrics:

* term exact match;
* definition exact match;
* term + definition exact match;
* term token F1;
* definition token F1;
* no prediction rate.

Expected headline results:

```text
n: 96
term exact match: 0.635
definition exact match: 0.865
both exact match: 0.604
term token F1: 0.902
definition token F1: 0.961
no prediction rate: 0.010
```

Typical output:

```text
results/rule_based_extraction_metrics.json
```

---

### `train_tfidf_certified_article_classifier.py`

Trains and evaluates TF-IDF baselines for article-level definition detection on the manually verified benchmark.

Models evaluated:

* TF-IDF word + Logistic Regression;
* TF-IDF word + Linear SVM;
* TF-IDF char + Linear SVM.

Typical outputs:

```text
results/article_classification_certified_tfidf_metrics.json
results/article_classification_certified_tfidf_predictions.jsonl
```

Expected best model:

```text
TF-IDF char + Linear SVM
Test macro-F1: 0.989
Definition-F1: 0.989
True-negative-F1: 0.989
```

---

### `train_camembert_certified_article_classifier.py`

Fine-tunes CamemBERT for article-level definition detection on the manually verified benchmark.

Input:

```text
article text
```

Output labels:

```text
0 = true negative
1 = definition article
```

Typical outputs:

```text
results/article_classification_certified_camembert_metrics.json
results/article_classification_certified_camembert_predictions.jsonl
models/camembert_article_classification/
```

Expected result:

```text
Dev macro-F1: 0.989
Test macro-F1: 1.000
Definition-F1: 1.000
True-negative-F1: 1.000
Confusion matrix: [[45, 0], [0, 45]]
```

This result should be interpreted as performance on a balanced manually verified benchmark, not as proof that article-level detection is solved in all uncontrolled settings.

---

### `train_tfidf_candidate_validator.py`

Trains and evaluates TF-IDF baselines for candidate validation.

Input:

```text
candidate term-definition pair
```

Output labels:

```text
0 = invalid
1 = accepted
```

The accepted class groups:

```text
valid_definition + partial
```

Models evaluated:

* TF-IDF word + Logistic Regression;
* TF-IDF word + Linear SVM;
* TF-IDF char + Linear SVM.

Typical outputs:

```text
results/candidate_validation_tfidf_metrics.json
results/candidate_validation_tfidf_predictions.jsonl
```

Expected best test result:

```text
TF-IDF word + Logistic Regression
Test macro-F1: 0.747
Accepted-F1: 0.895
Invalid-F1: 0.600
Confusion matrix: [[6, 6], [2, 34]]
```

The confusion matrix follows the order:

```text
[[TN_invalid, FP_invalid_to_accepted],
 [FN_accepted_to_invalid, TP_accepted]]
```

---

### `train_camembert_candidate_validator.py`

Fine-tunes CamemBERT for candidate validation.

Input:

```text
candidate term-definition pair
```

Output labels:

```text
0 = invalid
1 = accepted
```

Typical outputs:

```text
results/candidate_validation_camembert_metrics.json
results/candidate_validation_camembert_predictions.jsonl
models/camembert_candidate_validation/
```

Expected result:

```text
Dev macro-F1: 0.924
Test macro-F1: 0.705
Accepted-F1: 0.865
Invalid-F1: 0.545
Confusion matrix: [[6, 6], [4, 32]]
```

CamemBERT does not outperform the best TF-IDF baseline on candidate validation in this release.

---

### `cross_validate_tfidf_candidate_validator.py`

Runs grouped 5-fold cross-validation for TF-IDF candidate validation models.

The 5-fold evaluation is used because the fixed test set is small, especially for the invalid class.

Models evaluated:

* TF-IDF word + Logistic Regression;
* TF-IDF word + Linear SVM;
* TF-IDF char + Linear SVM.

Typical outputs:

```text
results/candidate_validation_tfidf_5fold_metrics.json
results/candidate_validation_tfidf_5fold_predictions.jsonl
```

Expected best mean result:

```text
TF-IDF word + Linear SVM
macro-F1: 0.710 ± 0.019
accepted-F1: 0.845 ± 0.015
invalid-F1: 0.575 ± 0.030
```

---

### `error_analysis_candidate_validation.py`

Analyzes the errors of the best candidate validation model.

The analysis focuses on the TF-IDF word + Logistic Regression model on the candidate validation test set.

Expected summary:

```text
Selected predictions: 48
Errors total: 8
False positives invalid→accepted: 6
False negatives accepted→invalid: 2
```

False positive patterns:

```text
terme_colon_definition: 3
défini comme: 2
est considéré comme: 1
```

False negative patterns:

```text
défini comme: 1
terme_colon_definition: 1
```

Typical output:

```text
results/candidate_validation_error_analysis.json
```

This analysis is used to document why candidate validation is harder than article-level detection.

---

## 4. Reproducibility notes

All train/dev/test splits are grouped by article key.

This prevents examples from the same legal article from appearing in both training and evaluation splits.

The TF-IDF experiments should be deterministic when using the released splits and the same random seed.

The CamemBERT experiments may show small variations depending on:

* `transformers` version;
* PyTorch version;
* CUDA or CPU execution;
* hardware;
* random seed handling.

The reported experiments used:

```text
seed: 2026
base model: camembert-base
```

---

## 5. Expected results directory

A complete reproduction should generate files similar to:

```text
results/
├── rule_based_extraction_metrics.json
├── article_classification_certified_tfidf_metrics.json
├── article_classification_certified_tfidf_predictions.jsonl
├── article_classification_certified_camembert_metrics.json
├── article_classification_certified_camembert_predictions.jsonl
├── candidate_validation_tfidf_metrics.json
├── candidate_validation_tfidf_predictions.jsonl
├── candidate_validation_camembert_metrics.json
├── candidate_validation_camembert_predictions.jsonl
├── candidate_validation_tfidf_5fold_metrics.json
├── candidate_validation_tfidf_5fold_predictions.jsonl
└── candidate_validation_error_analysis.json
```

Model checkpoints may be written to:

```text
models/
├── camembert_article_classification/
└── camembert_candidate_validation/
```

---

## 6. Notes on legacy scripts

The repository may contain historical scripts outside this directory. Those scripts were used during earlier annotation or pilot stages and may keep suffixes such as:

```text
v0_2
v0_3
v0_4
v0_5
v0_6
```

These suffixes correspond to internal development stages and should not be interpreted as public dataset versions.

The public dataset release is:

```text
NormDef-FR 1.0.0
```

For reproducing the experiments reported in the paper, use the scripts in this `scripts/experiments/` directory.

```
```
