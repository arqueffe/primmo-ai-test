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

1. **D'interroger la base documentaire via un LLM** -- un utilisateur doit pouvoir poser des questions en langage naturel et obtenir des reponses basees sur les documents du dossier.

2. **D'evaluer le cout et la pertinence des reponses** -- un endpoint ou un outil permettant de mesurer et suivre la qualite et le cout des interactions.

La conception de l'API (endpoints, format des requetes/reponses, architecture) est libre -- c'est au candidat de proposer le design qu'il juge le plus adapte.

## Contraintes techniques

- Python 3.11+
- FastAPI
- LLM : **Claude** (cle API fournie, budget plafonne a ~$5)
- Toute lib RAG/embedding/vectorstore autorisee
- Le code doit tourner avec `docker compose up` ou `make run`
- `README.md` expliquant les choix techniques et d'architecture

## Regles metier -- verification d'un dossier notarial

L'agent doit connaitre les regles de base qu'un collaborateur d'etude notariale applique lors de la verification d'un dossier de vente. Voici les principales :

### Pieces d'identite (CNI, passeport)
- Une CNI francaise est valide **15 ans** pour les majeurs (depuis 2014 ; 10 ans pour les CNI emises avant 2014).
- La piece d'identite doit etre **en cours de validite** a la date prevue de signature de l'acte authentique.
- Les **nom, prenom et date de naissance** doivent correspondre exactement aux informations mentionnees dans le compromis de vente.
### Justificatifs de domicile
- Le justificatif doit dater de **moins de 3 mois** a la date de la transaction (certaines etudes tolerent 6 mois).
- L'adresse doit correspondre a celle declaree par la partie dans le compromis.
- Documents acceptes : facture d'electricite, de gaz, d'eau, de telephone fixe/internet, avis d'imposition, quittance de loyer.

### Diagnostic de Performance Energetique (DPE)
- Le DPE est **obligatoire** pour toute vente immobiliere.
- Il doit concerner **le bien objet de la vente** (meme adresse).
- Il est valide **10 ans** a compter de sa date d'etablissement.
- La **surface** indiquee dans le DPE doit etre coherente avec celle du compromis.

### Compromis de vente
- Le compromis identifie les parties (vendeur, acquereur), le bien (adresse, surface, references cadastrales) et le prix.
- Il contient l'**origine de propriete** (comment le vendeur a acquis le bien).
- Les informations du compromis servent de **reference** pour verifier la coherence des autres pieces du dossier.

### Verification croisee
- L'agent doit etre capable de **croiser les informations** entre documents pour detecter d'eventuelles incoherences.

## Exemples de questions que l'agent doit savoir traiter

*(Ces exemples illustrent le type de questions attendues -- l'agent doit pouvoir repondre a des questions similaires, pas uniquement a celles-ci)*

- Qui sont les acheteurs et les vendeurs ?
- Quel est le bien concerne par la transaction de Paris ?
- Les pieces d'identite sont-elles en ordre ?
- Le DPE est-il present et correspond-il au bien ?
- Les justificatifs de domicile sont-ils conformes ?
- Y a-t-il des incoherences entre les documents d'un meme dossier ?

## Criteres d'evaluation

- L'agent repond de facon pertinente sur la base documentaire fournie
- Le cout et la pertinence des reponses sont mesurables
- Le code est lisible et bien structure
- Le projet se lance en une commande
- Les choix techniques sont documentes dans le README

## Duree

A determiner -- rendu par repo Git.
