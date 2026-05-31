````markdown
# Dataset Card — NormDef-FR 1.0.0

## Dataset details

| Field | Value |
|---|---:|
| Dataset name | NormDef-FR |
| Version | 1.0.0 |
| Language | French (`fr`) |
| Domain | French legal codes |
| Source | Légifrance / LEGI |
| Task | Normative term-definition extraction |
| Format | JSONL |
| Definitions | 693 |
| Source articles | 363 |
| Source code entries | 50 |
| Annotation schema version | 1.0.0 |

## Dataset description

NormDef-FR is a manually validated dataset of normative legal definitions extracted from French legal codes published on Légifrance.

The dataset focuses on **normative definitions**, that is, textual relations through which a legal text assigns an operative legal meaning to a term, expression, category, or regime within a given legal scope.

Each record links:

- a legal, administrative, technical, or regulatory term;
- its normative definition;
- the article and source code where the definition appears;
- the explicit scope of the definition when available;
- an inferred scope when no explicit scope is present;
- the linguistic pattern used to identify the candidate definition;
- the normalized type of definition;
- legal metadata associated with the article version.

NormDef-FR is intended for research in legal NLP, legal information extraction, terminology extraction, legal text mining, and the construction of legal knowledge resources.

## Intended uses

NormDef-FR can be used for:

- training or evaluating definition extraction systems;
- studying definitional patterns in French legal language;
- legal terminology mining;
- term-definition alignment;
- candidate validation for legal information extraction;
- article-level detection of definitional provisions;
- evaluating rule-based, classical machine-learning, and neural approaches to legal NLP;
- building definition-oriented search indexes;
- supporting retrieval-augmented generation systems for legal information retrieval.

## Out-of-scope uses

NormDef-FR should not be used as:

- legal advice;
- an authoritative substitute for current legal codes;
- a complete inventory of all definitions in French law;
- a source for making legal decisions without consulting official legal texts;
- evidence that a legal definition is currently in force without checking the official version on Légifrance.

The dataset is a research resource. Users must consult the official legal sources for any legal or professional use.

## Data fields

| Field | Description |
|---|---|
| `definition_id` | Unique annotation identifier |
| `source_code` | Name of the French legal code or source entry |
| `article_number` | Legal article number |
| `article_id` | LEGI article identifier when available |
| `article_key` | Normalized article key used for grouping and split construction |
| `etat` | Legal status of the article version |
| `date_debut` | Start date of the article version |
| `date_fin` | End date of the article version |
| `item_number` | Numbered item where applicable |
| `term` | Defined term |
| `defined_subject` | Subject being qualified, for qualification definitions |
| `definition` | Definition text span |
| `scope_text` | Explicit scope expression, when present |
| `scope_label` | Normalized explicit scope label |
| `inferred_scope` | Scope inferred by default or context |
| `pattern` | Linguistic pattern associated with the definition |
| `definition_type` | Normalized definition type |
| `raw_body` | Source text supporting the annotation |
| `source_file` | Source XML path when available |
| `annotation_source` | Annotation origin or processing batch |
| `manual_label` | Manual validation label when available |
| `correction_notes` | Manual correction notes when available |

## Annotation schema

NormDef-FR uses a three-class annotation schema for candidate validation.

| Label | Meaning | Binary mapping |
|---|---|---|
| `valid_definition` | Correct and directly exploitable normative definition | `accepted` |
| `partial` | Real definitional relation requiring correction or normalization | `accepted` |
| `invalid` | No exploitable normative definition | `invalid` |

The binary mapping is used in the candidate validation experiments:

```text
accepted = valid_definition + partial
invalid = invalid
````

This reflects the practical use of the pipeline: a `partial` candidate may still be useful after human correction, whereas an `invalid` candidate should be rejected.

## Scope labels

The following normalized scope labels are used when a definition explicitly specifies its legal scope:

```text
article
section
chapitre
titre
livre
code
unspecified
```

If no explicit scope expression is present, `scope_label` is set to:

```text
unspecified
```

## Inferred scope

The `inferred_scope` field provides a normalized scope inferred from the context when no explicit scope is available.

Possible values are:

```text
article
section
chapitre
titre
livre
code
```

In the current release, most definitions are inferred at article level when no broader explicit scope is present.

## Definition types

The following definition types are used:

```text
explicit
explicit_subitem
explicit_qualification
explicit_internal
explicit_enumerative
```

| Definition type          | Description                                          |
| ------------------------ | ---------------------------------------------------- |
| `explicit`               | Direct explicit definition                           |
| `explicit_subitem`       | Definition located in an item, list, or subparagraph |
| `explicit_qualification` | Definition expressed through legal qualification     |
| `explicit_internal`      | Definition embedded inside a larger sentence         |
| `explicit_enumerative`   | Definition constructed through enumeration           |

## Linguistic patterns

NormDef-FR preserves the French legal surface patterns found in the source texts. These expressions are not translated in the dataset because they correspond to the actual forms used by the extraction scripts and by the legal texts.

Frequent definitional patterns include:

```text
on entend par
s'entend de
défini comme
définis comme
est considéré comme
sont considérés comme
sont qualifiés de
terme_colon_definition
au sens du présent chapitre, on entend par
pour l'application du présent code, on entend par
aux fins du présent article, on entend par
```

Some patterns are more precise than others. For example, `on entend par`, `s'entend de`, and `terme_colon_definition` often introduce explicit definitions. Broader patterns such as `est considéré comme`, `sont qualifiés de`, or similar qualification patterns may be noisier and require manual validation.

## Annotation process

The dataset was created through a hybrid pipeline combining pattern-based retrieval, rule-based candidate extraction, manual validation, correction, and deduplication.

The construction process followed these steps:

1. French legal code articles in force were collected from the LEGI database published through Légifrance.
2. Candidate articles were retrieved using definition-oriented French legal patterns.
3. Candidate term-definition pairs were extracted with rule-based heuristics.
4. Draft annotations were manually reviewed.
5. Terms, definitions, scopes, patterns, and definition types were corrected when needed.
6. Invalid candidates were rejected.
7. Accepted and partial candidates were normalized.
8. Gold annotations were merged across batches.
9. Duplicate annotations were removed using article-level and span-level information.
10. A final audit corrected incomplete, truncated, or inconsistent annotations.
11. Experimental datasets were derived from the validated gold corpus.

The final public release is NormDef-FR 1.0.0.

## Quality control

Quality control included:

* schema validation;
* uniqueness checks for `definition_id`;
* verification of source article metadata;
* deduplication using article-level and span-level keys;
* manual review of draft definitions;
* correction of truncated definitions;
* correction of incomplete term boundaries;
* validation of `defined_subject` for qualification definitions;
* verification of candidate labels;
* construction of manually verified true negatives for article-level evaluation;
* train/dev/test splits grouped by article key to prevent article leakage.

## Deduplication

Gold files were merged using a deduplication strategy based on article and content information.

The main deduplication key used:

```text
article_id + normalized term + normalized definition
```

When `article_id` was unavailable, the fallback key was:

```text
source_code + article_number + normalized term + normalized definition
```

This strategy avoids removing distinct definitions that occur in different articles while eliminating duplicate annotations from successive annotation batches.

## Dataset statistics

### Core statistics

| Element                                        | Count |
| ---------------------------------------------- | ----: |
| Gold definitions                               |   693 |
| Unique source articles                         |   363 |
| Source code entries                            |    50 |
| Candidate validation examples                  |   449 |
| Accepted candidates                            |   306 |
| Invalid candidates                             |   143 |
| Article-level benchmark examples               |   600 |
| Definition articles in article-level benchmark |   300 |
| Manually verified true negatives               |   300 |

## Source code distribution

The dataset covers 50 source code entries as represented in the metadata. Some entries correspond to annexes or source labels that are treated separately in LEGI metadata.

| Source code                                                     | Count |
| --------------------------------------------------------------- | ----: |
| Code des impositions sur les biens et services                  |    66 |
| Code général des impôts                                         |    66 |
| Code de la santé publique                                       |    61 |
| Code des postes et des communications électroniques             |    59 |
| Code de l'environnement                                         |    51 |
| Code rural (nouveau)                                            |    42 |
| Code monétaire et financier                                     |    39 |
| Code de la construction et de l'habitation                      |    38 |
| Code de la consommation                                         |    34 |
| Code des transports                                             |    30 |
| Code de l'énergie                                               |    24 |
| Code du travail                                                 |    19 |
| Code général des impôts, annexe III                             |    18 |
| Code de la défense                                              |    13 |
| Code de la sécurité intérieure                                  |    13 |
| Code général des collectivités territoriales                    |    11 |
| Code du cinéma et de l'image animée                             |    10 |
| Code de commerce                                                |     9 |
| Code général des impôts, annexe II                              |     8 |
| Code de la sécurité sociale                                     |     8 |
| Code de la propriété intellectuelle                             |     7 |
| Code des relations entre le public et l'administration          |     6 |
| Code de l'urbanisme                                             |     5 |
| Code du sport                                                   |     5 |
| Code de l'action sociale et des familles                        |     4 |
| Code de l'entrée et du séjour des étrangers et du droit d'asile |     4 |
| Code de la route                                                |     4 |
| Code des assurances                                             |     4 |
| Code du tourisme                                                |     3 |
| Code des communes de la Nouvelle-Calédonie                      |     3 |
| Code général de la propriété des personnes publiques            |     3 |
| Code général des impôts, annexe IV                              |     3 |
| Code de la commande publique                                    |     2 |
| Code de la recherche                                            |     2 |
| Code de la voirie routière                                      |     2 |
| Code de procédure civile                                        |     2 |
| unknown                                                         |     2 |
| Code civil                                                      |     1 |
| Code de justice administrative                                  |     1 |
| Code de l'artisanat                                             |     1 |
| Code de l'éducation                                             |     1 |
| Code de l'organisation judiciaire                               |     1 |
| Code de la mutualité                                            |     1 |
| Code des douanes                                                |     1 |
| Code des juridictions financières                               |     1 |
| Code du service national                                        |     1 |
| Code forestier (nouveau)                                        |     1 |
| Code général de la fonction publique                            |     1 |
| Code général des impôts, annexe I                               |     1 |
| Code rural et de la pêche maritime                              |     1 |

## Definition type distribution

| Definition type          | Count |
| ------------------------ | ----: |
| `explicit`               |   667 |
| `explicit_subitem`       |    11 |
| `explicit_qualification` |     9 |
| `explicit_internal`      |     3 |
| `explicit_enumerative`   |     3 |

## Scope label distribution

| Scope label   | Count |
| ------------- | ----: |
| `unspecified` |   620 |
| `chapitre`    |    29 |
| `code`        |    20 |
| `article`     |    12 |
| `titre`       |     6 |
| `section`     |     3 |
| `livre`       |     3 |

## Inferred scope distribution

| Inferred scope | Count |
| -------------- | ----: |
| `article`      |   632 |
| `chapitre`     |    29 |
| `code`         |    20 |
| `titre`        |     6 |
| `section`      |     3 |
| `livre`        |     3 |

## Pattern distribution

| Pattern                                              | Count |
| ---------------------------------------------------- | ----: |
| `terme_colon_definition`                             |   255 |
| `s'entend de`                                        |   201 |
| `on entend par`                                      |   134 |
| `défini comme`                                       |    51 |
| `au sens du présent chapitre, on entend par`         |    21 |
| `pour l'application du présent code, on entend par`  |    19 |
| `est considéré comme`                                |     5 |
| `sont considérés comme`                              |     2 |
| `aux fins du présent article, on entend par`         |     1 |
| `pour l'application du présent titre, on entend par` |     1 |
| `définis comme`                                      |     1 |
| `sont qualifiés de ... lorsqu'ils`                   |     1 |
| `sont qualifiés de`                                  |     1 |

## Derived experimental datasets

NormDef-FR 1.0.0 includes derived datasets for three experimental tasks.

| Task                               | Total | Train | Dev | Test |
| ---------------------------------- | ----: | ----: | --: | ---: |
| Term-definition extraction         |   693 |   509 |  88 |   96 |
| Candidate validation               |   449 |   322 |  79 |   48 |
| Article-level definition detection |   600 |   420 |  90 |   90 |

All train/dev/test splits are grouped by article key. No article appears in more than one split for a given task.

## Candidate validation dataset

The candidate validation dataset contains 449 examples.

| Binary label | Count |
| ------------ | ----: |
| `accepted`   |   306 |
| `invalid`    |   143 |

The train/dev/test split is:

| Split | Total | Accepted | Invalid |
| ----- | ----: | -------: | ------: |
| Train |   322 |      230 |      92 |
| Dev   |    79 |       40 |      39 |
| Test  |    48 |       36 |      12 |

## Article-level benchmark

The article-level benchmark contains 600 examples.

| Label                           | Count |
| ------------------------------- | ----: |
| Definition article              |   300 |
| Manually verified true negative |   300 |

The train/dev/test split is balanced:

| Split | Total | Definition article | True negative |
| ----- | ----: | -----------------: | ------------: |
| Train |   420 |                210 |           210 |
| Dev   |    90 |                 45 |            45 |
| Test  |    90 |                 45 |            45 |

## Manually verified true negatives

The article-level benchmark uses manually verified true negatives rather than weak negatives.

A true negative article is an article that does not contain:

* an internal normative definition;
* a legal assimilation used as a definition;
* a legal fiction;
* a definitional qualification;
* a terminological block;
* an exploitable term-definition pair.

Weak negatives, defined only by absence from the gold corpus, were not used in the final article-level benchmark because manual audit showed that some of them contained definitional or quasi-definitional constructions.

Typical true negative articles include procedural, organizational, transitional, sanction-related, administrative, or budgetary provisions that do not define a term internally.

## Inter-annotator agreement

A subset of 150 examples was independently annotated by a second annotator.

| Schema                                                        | Examples | Cohen's kappa |
| ------------------------------------------------------------- | -------: | ------------: |
| Three-class schema (`valid_definition`, `partial`, `invalid`) |      150 |         0.973 |
| Binary schema (`accepted`, `invalid`)                         |      150 |         0.980 |

Disagreements mainly concerned partial definitions, legal qualifications close to definitions, and ambiguous term or definition boundaries.

## Experimental baselines

NormDef-FR 1.0.0 includes baseline results for three tasks.

### Term-definition extraction

A rule-based extraction baseline was evaluated on the test set of 96 examples.

| Metric                        | Score |
| ----------------------------- | ----: |
| Term exact match              | 0.635 |
| Definition exact match        | 0.865 |
| Term + definition exact match | 0.604 |
| Term token F1                 | 0.902 |
| Definition token F1           | 0.961 |
| No prediction rate            | 0.010 |

### Article-level definition detection

The article-level benchmark was evaluated with TF-IDF baselines and CamemBERT.

| Model                             | Macro-F1 | Definition-F1 | TrueNegative-F1 |
| --------------------------------- | -------: | ------------: | --------------: |
| TF-IDF word + Logistic Regression |    0.955 |         0.953 |           0.957 |
| TF-IDF word + Linear SVM          |    0.956 |         0.955 |           0.957 |
| TF-IDF char + Linear SVM          |    0.989 |         0.989 |           0.989 |
| CamemBERT                         |    1.000 |         1.000 |           1.000 |

The CamemBERT score should be interpreted as performance on this balanced manually verified benchmark, not as evidence that article-level definition detection is solved in all uncontrolled settings.

### Candidate validation

Candidate validation was evaluated on the test set and with 5-fold cross-validation.

| Model                             | Test Macro-F1 | Test Accepted-F1 | Test Invalid-F1 |
| --------------------------------- | ------------: | ---------------: | --------------: |
| TF-IDF word + Logistic Regression |         0.747 |            0.895 |           0.600 |
| TF-IDF word + Linear SVM          |         0.686 |            0.849 |           0.522 |
| TF-IDF char + Linear SVM          |         0.625 |            0.875 |           0.375 |
| CamemBERT                         |         0.705 |            0.865 |           0.545 |

5-fold cross-validation with TF-IDF models:

| Model                             |      Macro-F1 |   Accepted-F1 |    Invalid-F1 |
| --------------------------------- | ------------: | ------------: | ------------: |
| TF-IDF word + Logistic Regression | 0.705 ± 0.033 | 0.849 ± 0.014 | 0.561 ± 0.054 |
| TF-IDF word + Linear SVM          | 0.710 ± 0.019 | 0.845 ± 0.015 | 0.575 ± 0.030 |
| TF-IDF char + Linear SVM          | 0.678 ± 0.038 | 0.835 ± 0.022 | 0.522 ± 0.056 |

Candidate validation is the most difficult task in the benchmark. The invalid class remains harder to detect than the accepted class.

## Example record

```json
{
  "definition_id": "NORMDEF_FR_EXAMPLE_0001",
  "source_code": "Code de la consommation",
  "article_number": "L221-1",
  "article_id": "LEGIARTI_EXAMPLE",
  "term": "contrat de vente",
  "definition": "tout contrat en vertu duquel un professionnel transfère ou s'engage à transférer la propriété d'un bien à un consommateur et le consommateur en paie ou s'engage à en payer le prix",
  "scope_text": "Au sens du présent titre",
  "scope_label": "titre",
  "inferred_scope": "titre",
  "pattern": "on entend par",
  "definition_type": "explicit",
  "manual_label": "valid_definition"
}
```

The example above is illustrative. Users should refer to the JSONL files for the exact released records.

## Biases and limitations

NormDef-FR 1.0.0 has the following limitations:

* the corpus is not exhaustive;
* it over-represents articles where definitional markers are explicit;
* some French legal codes are more represented than others;
* the dataset reflects the article versions available at extraction time;
* the dataset focuses on codes in force and does not provide a diachronic view of legal definitions;
* the current release annotates term-definition pairs but does not provide exhaustive BIO token-level annotation;
* some rare definition types are underrepresented;
* the article-level benchmark uses manually verified true negatives, but their construction required human judgment;
* NormDef-FR should not be treated as legal advice.

## Ethical and legal considerations

NormDef-FR is derived from French legal texts published on Légifrance. The dataset is intended for research and evaluation in legal NLP.

Users should be aware that:

* legal texts may change over time;
* extracted definitions may become outdated if the underlying legal provisions are amended;
* official legal interpretation requires consulting the current official source;
* the dataset should not be used to provide legal advice or make legal decisions automatically.

## Maintenance

Future versions may include:

* more source articles;
* more manually validated definitions;
* expanded coverage across legal codes;
* more verified true negatives;
* token-level span annotations;
* BIO sequence-labeling datasets;
* diachronic versions of definitions;
* additional baselines, including generative or instruction-tuned models;
* improved error analysis for candidate validation.

## Citation

If you use NormDef-FR, please cite the associated paper:

```bibtex
@article{tetereou_normdef_fr,
  title = {NormDef-FR : un corpus annoté pour l'extraction et la validation des définitions normatives dans les codes juridiques français},
  author = {Tetereou, Aboudourazakou and Boudaa, Tarik and El Wardani, Dadi},
  journal = {Submitted},
  year = {forthcoming}
}
```

## License

NormDef-FR is intended for open research use. The final repository license must remain compatible with the applicable terms for French legal texts published on Légifrance and with the redistribution of derived annotation metadata.

Recommended release strategy:

* release annotation metadata, labels, terms, definitions, source identifiers, and experimental splits;
* include scripts to reproduce dataset construction and experiments;
* document the origin of legal source texts;
* avoid presenting the dataset as an official legal source.

## Contact

Maintainer:

```text
Aboudourazakou Tetereou
SOVIA Team, LSA
Abdelmalek Essaadi University
Tetouan, Morocco
aboudourazakou.tetereou@etu.uae.ac.ma
```

```
```
