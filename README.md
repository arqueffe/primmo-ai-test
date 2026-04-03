# Test technique -- Lead IA/LLM

## Contexte

Tu rejoins une startup qui developpe un outil pour les etudes notariales. L'equipe souhaite mettre en place un agent conversationnel capable de repondre aux questions des notaires et collaborateurs a partir des pieces d'un dossier de vente.

## Base documentaire

Le dossier `documents/` contient les resultats OCR (format Google Vision API) des pieces de **3 dossiers de vente immobiliere** :

| Dossier | Nombre de pieces |
|---------|-----------------|
| `dossier_1/` | 9 documents |
| `dossier_2/` | 6 documents |
| `dossier_3/` | 6 documents |

Chaque dossier contient :

| Type | Exemples | Format |
|------|----------|--------|
| Pieces d'identite | CNI | JSON (OCR Google Vision) |
| Compromis de vente | Compromis sous seing prive | JSON (OCR Google Vision) |
| Justificatifs de domicile | Facture EDF, avis d'imposition | JSON (OCR Google Vision) |
| DPE | Diagnostic de performance energetique | JSON (OCR Google Vision) |

**~21 fichiers au total.**

Les fichiers JSON suivent le format de reponse de l'API Google Cloud Vision (`fullTextAnnotation` avec `pages`, `blocks`, `words`, `symbols` et scores de `confidence`).

## Objectif

Developper une API permettant :

1. **D'interroger la base documentaire via un LLM** -- un utilisateur doit pouvoir poser des questions en langage naturel et obtenir des reponses basees sur les documents des dossiers.

2. **D'evaluer le cout, latence et la pertinence des reponses** -- un endpoint ou un outil permettant de mesurer et suivre la qualite, le cout et la latence des interactions.

La conception de l'API (endpoints, format des requetes/reponses, architecture) est libre -- c'est au candidat de proposer le design qu'il juge le plus adapte.

## Contraintes techniques

- Python 3.11+
- FastAPI
- LLM : **OpenRouter** (clé API fournie, budget plafonné a €20)
- Toute lib RAG/embedding/vectorstore autorisee
- Le code doit tourner avec `docker compose up` ou `make run`
- `README.md` expliquant les choix techniques et d'architecture

## Regles metier -- verification d'un dossier notarial

L'agent doit connaitre les regles de base qu'un collaborateur d'etude notariale applique lors de la verification d'un dossier de vente. Les règles ci-dessous sont partielles.

### 1. Toute information doit être ancrée dans un document au dossier, une déclaration d'une partie, ou un texte de droit

Un collaborateur ne travaille jamais à partir d’hypothèses.

### 2. Le dossier doit être complet à l’étape où il se situe

À chaque étape, tous les éléments requis doivent être présents

### 3. Chaque document doit être valide en lui-même

Avant même de croiser les documents :
- document officiel
- à jour
- lisible
- complet

### 4. Les informations clés doivent être parfaitement cohérentes partout

Le collaborateur passe son temps à croiser :

- identités
- bien
- montants
- dates

### 5. Le vendeur doit pouvoir juridiquement vendre

Vérification centrale.

- titulaire des droits
- nature des droits correcte
- absence de blocage (indivision, usufruit…)

### 6. Le bien doit être défini de manière unique et stable
un seul bien
une seule définition
aucune ambiguïté

### 7. Les obligations réglementaires sont non négociables
diagnostics
urbanisme
obligations légales

### 8. La chronologie doit être logique
compromis avant acte
conditions levées avant signature
documents valides au bon moment

### 9. Les montants doivent s’équilibrer
prix
financement
frais

### 10. Le doute doit être explicitement traité

Un collaborateur ne “devine” pas. Ce qui n’est pas certain doit être traité comme un risque

## Règles specifiques par type de document les plus fréquents

Les règles ci-dessous sont partielles.

# ### Pièce d’identité

## Vérifications de validité

* Document officiel accepté (CNI, passeport, titre de séjour)
* Non expiré *(tolérance parfois sur CNI française prolongée, mais à vérifier)*
* Lisible (photo, numéro, dates)
* Correspond à la personne (nom, prénom, date de naissance)

## Quand requis

* Toujours, pour **toutes les parties**
* À chaque entrée dans le dossier (on ne réutilise pas aveuglément une ancienne)

---

# ### Justificatif de domicile

## Vérifications de validité

* Date récente (≤ 3 mois en pratique)
* Type acceptable (facture énergie, quittance, attestation…)
* Nom cohérent avec la pièce d’identité
* Adresse exploitable (pas tronquée, pas ambiguë)

## Quand requis

* Toujours pour les parties (LCB-FT / connaissance client)
* Re-demandé si dossier long ou doute sur actualité

---

# ### Compromis ou promesse de vente

## Vérifications de validité

* Identité des parties complète
* Désignation du bien précise
* Prix clairement défini
* Conditions suspensives présentes (notamment prêt)
* Signatures présentes

## Quand requis

* Dès qu’une vente est engagée (avant acte)
* Sert de **référence centrale** jusqu’à l’acte

---

# ### Titre de propriété

## Vérifications de validité

* Acte authentique identifiable
* Désignation du bien claire
* Titulaire des droits identifié
* Droits correctement qualifiés (pleine propriété, usufruit…)

## Quand requis

* Toujours côté vendeur
* Base de toute vérification de propriété

---

# ### Diagnostics techniques

## Vérifications de validité

* Présence des diagnostics requis (DPE, amiante, plomb, etc. en fonction de l'age de l'immeuble et de sa localisation)
* Dates de validité respectées (variables selon le diagnostic et ses conclusions)
* Rapport complet
* Correspondance avec le bien (adresse, type) et tous ses lots (cave, parking)
* Présence des attestations sur l'honneur, polices d'assurance et certifcat de compétence valide à la date de réalisation du diagnostic pour chaque diagnostiqueur intervenant dans la réalisation des diagnostics

## Quand requis

* Avant signature de l’acte (souvent dès compromis)
* Obligatoire selon type de bien / situation

---

# ### État hypothécaire

## Vérifications de validité

* Document récent
* Liste des inscriptions (hypothèques, privilèges) et des mutations relatives au bien
* Correspondance avec le bien

## Quand requis

* Avant acte de vente
* Indispensable pour vérifier :

  * absence de charges bloquantes
  * montants à purger
  * origine de propriété

---

# ### Règlement de copropriété

## Vérifications de validité

* Document complet
* Identification des lots
* Description des parties communes / privatives
* Cohérence avec le bien vendu

## Quand requis

* Si bien en copropriété
* Nécessaire pour comprendre :

  * droits attachés au lot
  * charges / règles applicables

---

# ### Acte de vente (acte authentique)

## Vérifications de validité

* Reprise fidèle des éléments du compromis
* Identité des parties
* Désignation du bien
* Prix et financement
* Mentions obligatoires
* Signatures

## Quand requis

* Étape finale
* Formalise juridiquement le transfert de propriété

## Exemples de questions que l'agent doit savoir traiter

*(Ces exemples illustrent le type de questions attendues -- l'agent doit pouvoir repondre a des questions similaires, pas uniquement a celles-ci)*

- Dans quel dossier monsieur ... est-il vendeur?
- Qui sont les acheteurs et les vendeurs sur le dossier ...?
- Quel est le bien concerne par la transaction de Paris ?
- Les pieces d'identite sont-elles en ordre ?
- Le DPE est-il present et correspond-il au bien ?
- Les justificatifs de domicile sont-ils conformes ?
- Y a-t-il des incoherences entre les documents du dossier ... ?

## Criteres d'evaluation

- L'agent repond de facon pertinente sur la base documentaire fournie
- Le cout, la latence et la pertinence des reponses sont mesurables
- Le code est lisible et bien structure
- Le projet se lance en une commande
- Les choix techniques sont documentes dans le README: y compris une explication des arbitrages réalisés compte tenu des délais impartis, et suggestions pour aller plus loin.

## Duree

A determiner -- rendu par repo Git.
