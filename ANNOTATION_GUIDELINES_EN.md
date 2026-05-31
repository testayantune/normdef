````markdown
# Annotation Guide — NormDef-FR

Version: 1.0.0  
Language: French  
Domain: French legal codes  
Resource: NormDef-FR

## 1. Purpose of the guide

This document describes the annotation rules used to build NormDef-FR, a corpus of normative definitions extracted from French legal codes published on Légifrance.

The aim of the annotation is to identify, validate and standardise term–definition pairs found in legal articles. A NormDef-FR annotation does not merely seek to identify a sentence containing a definitional marker; it aims to determine whether a legal text actually assigns a legally operative meaning to a term, expression or category.

## 2. Definition of a normative definition

In NormDef-FR, a normative definition is a textual relationship through which a legal text establishes the meaning of a term, expression or category within a given legal context.

A normative definition may:

- introduce a legal category;
- specify the conditions for falling within a regime;
- establish a legal assimilation;
- determine the scope of a term within an article, chapter, title, book or code;
- delimit the content of a concept used by other provisions.

General example:

```text
Au sens du présent article, on entend par « X » ...
````
In this case, `X` is the term being defined, and the following text constitutes the definition if it actually specifies its legal meaning.

## 3. Annotated unit

The main annotated unit is the pair:

```text
defined term — definition
```

Each instance may also contain:

```text
article_id
source_code
article_number
term
definition
definition_type
pattern
scope_text
scope_label
label
```
The term refers to the expression whose meaning is established by the text.
The definition refers to the section that specifies that meaning.
The scope indicates, where explicitly stated, the scope of application of the definition.

## 4. Main labels

The annotation uses three main labels:

```text
valid_definition
partial
invalid
```

For binary experiments, the labels are grouped as follows:

```text
accepted = valid_definition + partial
invalid = invalid
```

This grouping reflects how the pipeline works in practice: a partial candidate may be useful after correction, whereas an invalid candidate must be rejected.

## 5. `valid_definition` label

The `valid_definition` label is assigned when an entry contains a genuine, usable normative definition.

An entry is `valid_definition` when:

* the term being defined is identifiable;
* the definition effectively establishes the legal meaning of the term;
* the term–definition pair is sufficiently complete;
* the boundaries of the term and the definition are correct or require only minor standardisation;
* the segment is not merely a condition, a procedure, a sanction, a reference or a vague qualification.

Schematic example:
```text
On entend par « service numérique » tout service fourni au moyen d’un système de communication électronique.
```
Annotation :

```json
{
  "term": "service numérique",
  "definition": "tout service fourni au moyen d’un système de communication électronique",
  "label": "valid_definition"
}
```
Reason: the text explicitly assigns a legal meaning to the term `service numérique`.

## 6. `partial` label

The `partial` label is assigned when a candidate contains a valid definitional relationship, but the extracted pair requires correction or particular caution.

A candidate is `partial` when:

* the definition is valid, but the term is partially truncated;
* the definition is valid, but the definitional segment is incomplete;
* the boundaries of the term or definition need to be corrected;
* the candidate contains a definition that can be used after human review;
* the definitional marker is correct, but the automatic extraction has not perfectly isolated the term–definition pair.

Schematic example:
```text
Pour l’application du présent chapitre, on entend par « installation de traitement » une installation destinée à...
```
If the extractor only offers:
```json
{
  "term": "traitement",
  "definition": "une installation destinée à...",
  "label": "partial"
}
```

Reason: the definitional relationship exists, but the extracted term is incomplete. The correct term would probably be  `installation de traitement`.

The `partial` label does not therefore mean that the candidate is legally useless. It means that the candidate must be corrected before being incorporated as the final gold instance.

## 7. `invalid` label

The `invalid` label is assigned when a candidate does not constitute a usable normative definition.

A candidate is `invalid` when:

* the detected marker does not introduce a definition;
* the segment corresponds to a procedure, an obligation, a sanction or a condition;
* the text contains a qualifier that cannot be used as a definition;
* the term or definition cannot be reliably identified;
* the segment is too noisy, too truncated or out of scope;
* the text refers to an external definition without defining the term itself.

Schematic example
```text
Le président désigne les membres de la commission.
```
Although the verb `désigne` can be identified by a broad pattern, this segment does not define a term. It describes an institutional action.

Annotation :

```json
{
  "term": null,
  "definition": null,
  "label": "invalid"
}
```
Reason: the text does not define the legal meaning of a term.
## 8. Types of definitions

Accepted instances can be associated with a definition type.

### 8.1 `explicit`

The `explicit` type corresponds to direct and complete definitions.

Examples of common patterns:


```text
on entend par
s’entend de
défini comme
terme : définition
```

Exemple :

```text
On entend par « producteur » toute personne qui...
```
### 8.2 `explicit_subitem`

The `explicit_subitem` type corresponds to a definition located within an item, a sub-item, a list or an internal subdivision.

Schematic example:
```text
1° « Acheteur » : toute personne qui acquiert...
2° « Vendeur » : toute personne qui cède...
```

Each item may be annotated as a separate instance if the term and definition are identifiable.

### 8.3 `explicit_qualification`

The `explicit_qualification` type applies to cases where the text defines a category by legal qualification.

Schematic example:
```text
Sont qualifiés de services essentiels les services qui...
```

These cases should only be annotated if the classification actually determines membership of a legal category.

### 8.4 `explicit_internal`

The `explicit_internal` type corresponds to definitions that are internal to a sentence or a broader provision.

Schematic example:

```text
La notification, entendue comme la transmission formelle d’une décision, est réalisée par...
```

The definition is present, but embedded within a more complex sentence.



### 8.5 `explicit_enumerative`

The `explicit_enumerative` type corresponds to definitions constructed by enumeration.

Schematic example:
```text
Sont considérés comme des déchets dangereux les déchets présentant l’une des propriétés suivantes : ...
```
These cases must be annotated if the list actually determines the legal content of the category.

## 9. Common definitional patterns

The following patterns may introduce normative definitions:
```text
on entend par
s’entend de
est défini comme
sont définis comme
est considéré comme
sont considérés comme
est réputé
sont réputés
constitue
terme : définition
au sens de
pour l’application de
aux fins de
```

Not all of these patterns are equally reliable.

The patterns that are generally more accurate are:


```text
on entend par
s’entend de
terme : définition
défini comme
```
The most talked-about bosses are:
```text
constitue
est réputé
est considéré comme
sont qualifiés de
désigne
```


A vague provision should not automatically be rejected. It is always necessary to check whether the text actually establishes a legal category or whether it merely describes a condition, an effect or a procedure.

## 10. Scope of the definition

The scope indicates the legal context within which the definition applies.

Examples of scope:

```text
au sens du présent article
pour l’application du présent chapitre
aux fins du présent titre
au sens du présent code
```

The scope labels used are:

```text
article
section
chapitre
titre
livre
code
unspecified
```
If the scope is explicit, it must be specified in `scope_text` and normalised in `scope_label`.

Example:

```text
Pour l’application du présent chapitre, on entend par « X » ...
```

Annotation :

```json
{
  "scope_text": "Pour l’application du présent chapitre",
  "scope_label": "chapitre"
}
```
If no explicit scope is specified, use:
```json
{
  "scope_label": "unspecified"
}
```
In some cases, a scope may be inferred by default from the article, but this inference must be distinguished from the scope explicitly stated in the text.

## 11. Rules for segmenting the term

The term must correspond to the expression defined in the text.

To do:

* include necessary adjectives and modifiers;
* retain complete legal expressions;
* avoid truncating the term;
* remove quotation marks if the corpus format allows for this;
* do not include the definitional marker within the term.

Example:

```text
On entend par « installation agrivoltaïque » une installation de production d’électricité...
```

Correct term :

```text
installation agrivoltaïque
```

Incorrect term :

```text
installation
```
Reason: the text does not define all installations, but a specific category.

## 12. Rules for segmenting the definition

The definition must correspond to the segment that establishes the meaning of the term.

To do:

* include the conditions necessary for the definition;
* include important restrictive elements;
* retain lists if they form part of the definition;
* do not include the following sentences if they merely describe effects, penalties or procedures;
* do not include the introductory marker.

Example:

```text
On entend par « X » toute personne qui exerce l’activité Y dans les conditions prévues par le présent article.
```

Correcte defintion :

```text
toute personne qui exerce l’activité Y dans les conditions prévues par le présent article

## 13. Special cases

### 13.1 Definitions using a colon

Definitions using a colon are common and often reliable.

Example:
Annotation :

```json
{
  "term": "Produit reconditionné",
  "definition": "produit ayant fait l’objet d’une opération de remise en état",
  "label": "valid_definition"
}
```

Note: a colon may also introduce a list, a procedure or a non-definitional explanation. In this case, the candidate may be `invalid`.

### 13.2 Equivalences

An equivalence may be annotated if it establishes a legally enforceable equivalence.

Schematic example:
```text
Est assimilé à un producteur toute personne qui...
```
Indicate in the notes whether the text actually establishes membership of a legal category.
### 13.3 Qualifications

Qualifications should be treated with caution.

Example:

```text
Sont qualifiés de déchets dangereux les déchets qui...
```
Annotate only if the text defines the category `déchets dangereux`.

Do not annotate if the text merely assigns a status, a consequence or an administrative decision without defining a term.

### 13.4 External references

An article that refers to an external definition without defining the term itself must not be annotated as an internal definition.

Example:
```text
Les termes utilisés sont ceux définis par le règlement européen ...
```

Label :

```text
invalid
```

Reason: The article does not contain the definition; it refers to another source.

### 13.5 Conditions and procedures

Conditions, procedures and legal effects are not definitions, even if they contain important legal terms.

Example:
```text
Le comité se réunit au moins une fois par an.
```

Label :

```text
invalid
```
Justification: the text describes a rule of procedure, not the meaning of a term.

## 14. True negatives for the article-level task

An article is considered a true negative if it does not contain:

* an internal normative definition;
* a legal definition by assimilation;
* a legal fiction;
* a defining qualification;
* a terminological block;
* a usable term–definition pair.

True negatives may be articles that are:

* procedural;
* organisational;
* punitive;
* transitional;
* budgetary;
* administrative;
* external references without an internal definition.

Schematic example:
```text
Il est institué un comité d’audit. Le comité se réunit au moins une fois par an...
```

Label article-level :

```text
true_negative
```
Reason: The article describes an organisation and procedures, but does not define a term.
## 15. Difference between a weak negative and a true negative

A weak negative is an article that does not appear in the gold corpus. This does not necessarily mean that it does not contain a definition. It may simply contain a definition that has not been identified or annotated yet.

A true negative is an article that has been manually verified as containing no internal normative definition.

For the final definition-detection experiments, NormDef-FR uses manually verified true negatives to avoid contamination of the negative class.

## 16. Final annotation decision

For each candidate, the annotator must ask themselves the following questions:

1. Does the text establish the legal meaning of a term or category?
2. Is the defined term identifiable?
3. Is the definition identifiable?
4. Is the term–definition pair complete and usable?
5. Is the segment a true definition, or merely a procedure, a condition, a weak qualification, an effect or a reference?
6. Should the candidate be accepted directly, corrected, or rejected?

Decision:

```text
valid_definition: correct and usable definition
partial: actual definition but requiring correction
invalid: no usable definition
```

## 17. Resolving disagreements

Disagreements between annotators mainly concern:

* `partial` cases;
* the exact boundaries of the term;
* the exact boundaries of the definition;
* qualifications that are close to definitions;
* legal assimilations;
* broad and noisy patterns.

In the event of a disagreement, the final decision must prioritise:

1. the actual presence of a definitional relationship;
2. the legal usability of the term–definition pair;
3. the possibility of correcting the candidate;
4. the distinction between definition, qualification and simple legal effect.

## 18. Summary of labels

| Label              | Meaning                     | Experimental use |
| ------------------ | --------------------------------- | ------------------------ - |
| `valid_definition` | Correct normative definition     | `accepted`                |
| `partial`          | Actual definition but requires correction | `accepted`                |
| `invalid`          | No usable definition     | `invalid`                 |

## 19. Citation

If you use NormDef-FR, please cite the article associated with the corpus:

```bibtex
@article{tetereou_normdef_fr,
  title = {NormDef-FR: an annotated corpus for the extraction and validation of normative definitions in French legal codes},
  author = {Tetereou, Aboudourazakou and Boudaa, Tarik and El Wardani, Dadi},
  journal = {Submitted},
  year = {forthcoming}
}
```

## 20. Contact

For any questions regarding the corpus, annotations or reproduction scripts:

```text
Aboudourazakou Tetereou
SOVIA Team, LSA
Abdelmalek Essaadi University
aboudourazakou.tetereou@etu.uae.ac.ma
```

```
```
