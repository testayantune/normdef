# NormDef-FR

NormDef-FR is a manually validated dataset for extracting and validating normative definitions in French legal codes.

The first public release contains 693 gold definitions from 363 source articles, with candidate-validation and article-level benchmarks.

The repository includes gold annotations, metadata, train/dev/test splits, verified true negatives, baseline scripts, and experimental results.

Documentation is provided in `DATA_CARD.md`, `MODEL_CARD.md`, `ANNOTATION_GUIDELINES_EN.md`, and `ANNOTATION_GUIDELINES_FR.md`.

Annotation scripts are in `scripts/annotation/`; experimental reproduction scripts are in `scripts/experiments/`.

Data files are organized under `data/`, including `annotation/`, `audit/`, `candidates/`, and `experiments/`.

Code is released under the MIT License; data and documentation are released under the Licence Ouverte 2.0 / Open Licence 2.0 (Etalab).

NormDef-FR is a research dataset and is not an official legal source or legal advice.