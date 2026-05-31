````markdown
# Guide d’annotation — NormDef-FR

Version : 1.0.0  
Langue : français  
Domaine : codes juridiques français  
Ressource : NormDef-FR

## 1. Objectif du guide

Ce document décrit les règles d’annotation utilisées pour construire NormDef-FR, un corpus de définitions normatives extraites des codes juridiques français publiés sur Légifrance.

L’objectif de l’annotation est d’identifier, de valider et de normaliser des couples terme–définition présents dans des articles juridiques. Une annotation NormDef-FR ne vise pas seulement à repérer une phrase contenant un marqueur définitionnel ; elle vise à déterminer si un texte juridique attribue réellement à un terme, une expression ou une catégorie un sens juridiquement opératoire.

## 2. Définition d’une définition normative

Dans NormDef-FR, une définition normative est une relation textuelle par laquelle un texte juridique fixe le sens d’un terme, d’une expression ou d’une catégorie dans un périmètre juridique donné.

Une définition normative peut :

- introduire une catégorie juridique ;
- préciser les conditions d’appartenance à un régime ;
- établir une assimilation juridique ;
- fixer la portée d’un terme dans un article, un chapitre, un titre, un livre ou un code ;
- délimiter le contenu d’une notion utilisée par d’autres dispositions.

Exemple général :

```text
Au sens du présent article, on entend par « X » ...
````

Dans ce cas, `X` est le terme défini, et le segment qui suit constitue la définition si celui-ci précise effectivement son sens juridique.

## 3. Unité annotée

L’unité annotée principale est le couple :

```text
terme défini — définition
```

Chaque instance peut également contenir :

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

Le terme correspond à l’expression dont le sens est fixé par le texte.
La définition correspond au segment qui précise ce sens.
La portée indique, lorsque cela est explicite, le périmètre d’application de la définition.

## 4. Labels principaux

L’annotation utilise trois labels principaux :

```text
valid_definition
partial
invalid
```

Pour les expériences binaires, les labels sont regroupés ainsi :

```text
accepted = valid_definition + partial
invalid = invalid
```

Ce regroupement reflète le fonctionnement pratique du pipeline : un candidat partiel peut être utile après correction, alors qu’un candidat invalide doit être rejeté.

## 5. Label `valid_definition`

Le label `valid_definition` est attribué lorsqu’un candidat contient une vraie définition normative exploitable.

Un candidat est `valid_definition` lorsque :

* le terme défini est identifiable ;
* la définition fixe effectivement le sens juridique du terme ;
* le couple terme–définition est suffisamment complet ;
* les frontières du terme et de la définition sont correctes ou ne nécessitent qu’une normalisation mineure ;
* le segment n’est pas seulement une condition, une procédure, une sanction, un renvoi ou une qualification vague.

Exemple schématique :

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

Justification : le texte attribue explicitement un sens juridique au terme `service numérique`.

## 6. Label `partial`

Le label `partial` est attribué lorsqu’un candidat contient une relation définitionnelle réelle, mais que le couple extrait nécessite une correction ou une prudence particulière.

Un candidat est `partial` lorsque :

* la définition est réelle, mais le terme est partiellement tronqué ;
* la définition est réelle, mais le segment définitionnel est incomplet ;
* les frontières du terme ou de la définition doivent être corrigées ;
* le candidat contient une définition exploitable après révision humaine ;
* le marqueur définitionnel est correct, mais l’extraction automatique n’a pas parfaitement isolé le couple terme–définition.

Exemple schématique :

```text
Pour l’application du présent chapitre, on entend par « installation de traitement » une installation destinée à...
```

Si l’extracteur propose seulement :

```json
{
  "term": "traitement",
  "definition": "une installation destinée à...",
  "label": "partial"
}
```

Justification : la relation définitionnelle existe, mais le terme extrait est incomplet. Le terme correct serait probablement `installation de traitement`.

Le label `partial` ne signifie donc pas que le candidat est juridiquement inutile. Il signifie que le candidat doit être corrigé avant d’être intégré comme instance gold finale.

## 7. Label `invalid`

Le label `invalid` est attribué lorsqu’un candidat ne constitue pas une définition normative exploitable.

Un candidat est `invalid` lorsque :

* le marqueur détecté n’introduit pas une définition ;
* le segment correspond à une procédure, une obligation, une sanction ou une condition ;
* le texte contient une qualification non exploitable comme définition ;
* le terme ou la définition ne peut pas être identifié de façon fiable ;
* le segment est trop bruité, trop tronqué ou hors périmètre ;
* le texte renvoie à une définition externe sans définir lui-même le terme.

Exemple schématique :

```text
Le président désigne les membres de la commission.
```

Même si le verbe `désigne` peut être détecté par un patron large, ce segment ne définit pas un terme. Il décrit une action institutionnelle.

Annotation :

```json
{
  "term": null,
  "definition": null,
  "label": "invalid"
}
```

Justification : le texte ne fixe pas le sens juridique d’un terme.

## 8. Types de définitions

Les instances acceptées peuvent être associées à un type de définition.

### 8.1 `explicit`

Le type `explicit` correspond aux définitions directes et complètes.

Exemples de patrons fréquents :

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

Le type `explicit_subitem` correspond à une définition située dans un item, un alinéa, une liste ou une subdivision interne.

Exemple schématique :

```text
1° « Acheteur » : toute personne qui acquiert...
2° « Vendeur » : toute personne qui cède...
```

Chaque item peut être annoté comme une instance distincte si le terme et la définition sont identifiables.

### 8.3 `explicit_qualification`

Le type `explicit_qualification` correspond aux cas où le texte définit une catégorie par qualification juridique.

Exemple schématique :

```text
Sont qualifiés de services essentiels les services qui...
```

Ces cas doivent être annotés seulement si la qualification fixe réellement l’appartenance à une catégorie juridique.

### 8.4 `explicit_internal`

Le type `explicit_internal` correspond aux définitions internes à une phrase ou à une disposition plus large.

Exemple schématique :

```text
La notification, entendue comme la transmission formelle d’une décision, est réalisée par...
```

La définition est présente, mais insérée dans une phrase plus complexe.

### 8.5 `explicit_enumerative`

Le type `explicit_enumerative` correspond aux définitions construites par énumération.

Exemple schématique :

```text
Sont considérés comme des déchets dangereux les déchets présentant l’une des propriétés suivantes : ...
```

Ces cas doivent être annotés si l’énumération fixe effectivement le contenu juridique de la catégorie.

## 9. Patrons définitionnels fréquents

Les patrons suivants peuvent introduire des définitions normatives :

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

Tous ces patrons ne sont pas également fiables.

Les patrons généralement plus précis sont :

```text
on entend par
s’entend de
terme : définition
défini comme
```

Les patrons plus bruités sont :

```text
constitue
est réputé
est considéré comme
sont qualifiés de
désigne
```

Un patron bruité ne doit pas entraîner automatiquement un rejet. Il faut toujours vérifier si le texte fixe réellement une catégorie juridique ou s’il décrit seulement une condition, un effet ou une procédure.

## 10. Portée de la définition

La portée indique le périmètre juridique dans lequel la définition s’applique.

Exemples de portée :

```text
au sens du présent article
pour l’application du présent chapitre
aux fins du présent titre
au sens du présent code
```

Les labels de portée utilisés sont :

```text
article
section
chapitre
titre
livre
code
unspecified
```

Si la portée est explicite, elle doit être annotée dans `scope_text` et normalisée dans `scope_label`.

Exemple :

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

Si aucune portée explicite n’est présente, utiliser :

```json
{
  "scope_label": "unspecified"
}
```

Dans certains cas, une portée peut être inférée par défaut à partir de l’article, mais cette inférence doit être distinguée de la portée explicitement écrite dans le texte.

## 11. Règles de segmentation du terme

Le terme doit correspondre à l’expression définie par le texte.

À faire :

* inclure les adjectifs et compléments nécessaires ;
* conserver les expressions juridiques complètes ;
* éviter de tronquer le terme ;
* supprimer les guillemets si le format du corpus le prévoit ;
* ne pas inclure le marqueur définitionnel dans le terme.

Exemple :

```text
On entend par « installation agrivoltaïque » une installation de production d’électricité...
```

Terme correct :

```text
installation agrivoltaïque
```

Terme incorrect :

```text
installation
```

Justification : le texte ne définit pas toute installation, mais une catégorie spécifique.

## 12. Règles de segmentation de la définition

La définition doit correspondre au segment qui fixe le sens du terme.

À faire :

* inclure les conditions nécessaires à la définition ;
* inclure les éléments restrictifs importants ;
* conserver les énumérations si elles font partie de la définition ;
* ne pas inclure les phrases suivantes si elles décrivent seulement des effets, sanctions ou procédures ;
* ne pas inclure le marqueur introductif.

Exemple :

```text
On entend par « X » toute personne qui exerce l’activité Y dans les conditions prévues par le présent article.
```

Définition correcte :

```text
toute personne qui exerce l’activité Y dans les conditions prévues par le présent article
```

## 13. Cas particuliers

### 13.1 Définitions par deux-points

Les définitions par deux-points sont fréquentes et souvent fiables.

Exemple :

```text
Produit reconditionné : produit ayant fait l’objet d’une opération de remise en état.
```

Annotation :

```json
{
  "term": "Produit reconditionné",
  "definition": "produit ayant fait l’objet d’une opération de remise en état",
  "label": "valid_definition"
}
```

Attention : un deux-points peut aussi introduire une liste, une procédure ou une explication non définitionnelle. Dans ce cas, le candidat peut être `invalid`.

### 13.2 Assimilations

Une assimilation peut être annotée si elle fixe une équivalence juridique exploitable.

Exemple schématique :

```text
Est assimilé à un producteur toute personne qui...
```

Annoter comme définition si le texte établit réellement l’appartenance à une catégorie juridique.

### 13.3 Qualifications

Les qualifications doivent être traitées avec prudence.

Exemple :

```text
Sont qualifiés de déchets dangereux les déchets qui...
```

Annoter seulement si le texte définit la catégorie `déchets dangereux`.

Ne pas annoter si le texte attribue seulement un statut, une conséquence ou une décision administrative sans définir un terme.

### 13.4 Renvois externes

Un article qui renvoie à une définition externe sans définir lui-même le terme ne doit pas être annoté comme définition interne.

Exemple :

```text
Les termes utilisés sont ceux définis par le règlement européen ...
```

Label :

```text
invalid
```

Justification : l’article ne contient pas la définition, il renvoie à une autre source.

### 13.5 Conditions et procédures

Les conditions, procédures et effets juridiques ne sont pas des définitions, même s’ils contiennent des termes juridiques importants.

Exemple :

```text
Le comité se réunit au moins une fois par an.
```

Label :

```text
invalid
```

Justification : le texte décrit une règle de fonctionnement, pas le sens d’un terme.

## 14. Vrais négatifs pour la tâche article-level

Un article est considéré comme vrai négatif s’il ne contient pas :

* de définition normative interne ;
* d’assimilation juridique définitoire ;
* de fiction juridique ;
* de qualification définitoire ;
* de bloc terminologique ;
* de couple terme–définition exploitable.

Les vrais négatifs peuvent être des articles :

* procéduraux ;
* organisationnels ;
* sanctionnateurs ;
* transitoires ;
* budgétaires ;
* administratifs ;
* de renvoi externe sans définition interne.

Exemple schématique :

```text
Il est institué un comité d’audit. Le comité se réunit au moins une fois par an...
```

Label article-level :

```text
true_negative
```

Justification : l’article décrit une organisation et des procédures, mais ne définit pas un terme.

## 15. Différence entre négatif faible et vrai négatif

Un négatif faible est un article qui n’apparaît pas dans le corpus gold. Cela ne signifie pas nécessairement qu’il ne contient pas de définition. Il peut simplement contenir une définition non repérée ou non encore annotée.

Un vrai négatif est un article vérifié manuellement comme ne contenant aucune définition normative interne.

Pour les expériences finales de détection d’articles définitionnels, NormDef-FR utilise des vrais négatifs vérifiés manuellement afin d’éviter la contamination de la classe négative.

## 16. Décision finale d’annotation

Pour chaque candidat, l’annotateur doit se poser les questions suivantes :

1. Le texte fixe-t-il le sens juridique d’un terme ou d’une catégorie ?
2. Le terme défini est-il identifiable ?
3. La définition est-elle identifiable ?
4. Le couple terme–définition est-il complet et exploitable ?
5. Le segment est-il une vraie définition, ou seulement une procédure, une condition, une qualification faible, un effet ou un renvoi ?
6. Faut-il accepter le candidat directement, le corriger, ou le rejeter ?

Décision :

```text
valid_definition : définition correcte et exploitable
partial : définition réelle mais nécessitant correction
invalid : pas de définition exploitable
```

## 17. Résolution des désaccords

Les désaccords entre annotateurs concernent principalement :

* les cas `partial` ;
* les frontières exactes du terme ;
* les frontières exactes de la définition ;
* les qualifications proches de définitions ;
* les assimilations juridiques ;
* les patrons larges et bruités.

En cas de désaccord, la décision finale doit privilégier :

1. la présence réelle d’une relation définitionnelle ;
2. l’exploitabilité juridique du couple terme–définition ;
3. la possibilité de corriger le candidat ;
4. la distinction entre définition, qualification et simple effet juridique.

## 18. Résumé des labels

| Label              | Signification                     | Utilisation expérimentale |
| ------------------ | --------------------------------- | ------------------------- |
| `valid_definition` | Définition normative correcte     | `accepted`                |
| `partial`          | Définition réelle mais à corriger | `accepted`                |
| `invalid`          | Pas de définition exploitable     | `invalid`                 |

## 19. Citation

Si vous utilisez NormDef-FR, veuillez citer l’article associé au corpus :

```bibtex
@article{tetereou_normdef_fr,
  title = {NormDef-FR : un corpus annoté pour l'extraction et la validation des définitions normatives dans les codes juridiques français},
  author = {Tetereou, Aboudourazakou and Boudaa, Tarik and El Wardani, Dadi},
  journal = {Submitted},
  year = {à paraître}
}
```

## 20. Contact

Pour toute question concernant le corpus, les annotations ou les scripts de reproduction :

```text
Aboudourazakou Tetereou
SOVIA Team, LSA
Abdelmalek Essaadi University
aboudourazakou.tetereou@etu.uae.ac.ma
```

```
```
