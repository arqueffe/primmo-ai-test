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

## Verification croisee
- L'agent doit etre capable de **croiser les informations** entre documents pour detecter d'eventuelles incoherences.

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
