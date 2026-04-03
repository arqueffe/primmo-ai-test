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

L'agent doit connaitre les regles de base qu'un collaborateur d'etude notariale applique lors de la verification d'un dossier de vente. 

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
- Les choix techniques sont documentes dans le README

## Duree

A determiner -- rendu par repo Git.
