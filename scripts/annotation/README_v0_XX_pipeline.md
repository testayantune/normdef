# Annotation pipeline

NormDef-FR was built incrementally through successive annotation batches.

Each release `v0.XX` extends the previous gold release with an additional manually reviewed annotation batch. The historical scripts may keep the version suffix of the batch for which they were originally created.

The scripts involved in each annotation stage are:

1. `sample_annotation_batch_v0_XX.py`  
   Selects or prepares the annotation batch.

2. `draft_extract_definitions_from_batch_v0_XX_strict.py`  
   Extracts candidate term-definition pairs from the selected batch using strict rule-based patterns.

3. `review_draft_definitions_gui_v0_XX.py`  
   Provides the manual review interface used to validate, reject, or correct candidate definitions.

4. `build_gold_from_review_v0_XX.py`  
   Builds a gold file from the manually reviewed candidates.

5. `validate_normdef_schema.py`  
   Checks that the newly generated annotations follow the NormDef-FR schema.

6. `merge_gold_datasets.py`  
   Merges the previous gold release with the newly reviewed gold batch and removes duplicates.

7. `validate_normdef_schema.py`  
   Runs schema validation again on the merged gold release.

8. `build_metadata.py`  
   Builds metadata and descriptive statistics for the resulting release.

   This annotation pipeline documents how the gold corpus was created. The experimental pipeline used to create train/dev/test splits, article-level benchmarks, model training runs, and evaluation outputs is documented separately in `scripts/experiments/`.