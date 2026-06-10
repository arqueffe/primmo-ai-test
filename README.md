# KG-RAG Notarial

## Motivation

L'objectif de ce projet est de developper un outil d'interrogation de dossiers notariaux. Les règles notariales sont complexes mais précises, et peuvent être formalisées sur de la donnée structurée.
Cette démonstration à deux buts 
1. Limiter les risques d'hallucination en s'appuyant sur des données structurées extraites de documents, permettant à un agent de parcourir et d'interroger une base documentaire de manière plus fiable.
2. Augmenter la fiabilité et la proactivité d'un système notarial en utilisant un système hybride combinant LLM et raisonnement symbolique sur un graphe de connaissance construit à partir de documents.

Ce prototype présente cette approche, en intégrant les besoins décrits dans le cahier des charges. La mesure de la pertinence n'est pas traitée ici, mais le projet inclut un suivi léger des latences, des tokens et des coûts d'exécution pour observer le comportement de la pipeline.

## Generation Graphe de Connaissance

Après une étude de l'état de l'art en matière de génération automatique de graphes de connaissance, j'ai identifié une librairie prometteuse, [KGGen](https://github.com/stair-lab/kg-gen), publié à NeurIPS 2025. Cette librairie, encore en développement, propose une approche pour la génération de graphes de connaissance à partir de données non structurées. Cette méthode me permet d'ingester les données OCR des documents notariaux et de les aggréger ensemble dans un graphe de connaissance, facilitant ainsi les requêtes et le raisonnement sur les données.

Voir `ingestor.py` pour plus de détails sur l'ingestion et la construction du graphe de connaissance.

### Limitation du prototype

- La génération des graphes est entièrement basée sur les données extraites des documents. Une étape importante pour améliorer la qualité des graphes serait de formaliser les besoins en fonction des documents et des dossiers. Par exemple, il serait utile de prédéfinir un ensemble de relations comme "est_vendeur", "est_acheteur", ... pour guider la génération du graphe vers une structure plus formalisée et adaptée aux besoins de l'application.
- Le graphe n'est pas post-traité pour corriger les entitiés, et les relations ou encore s'assurer de la connectivité du graphe. Avec de meilleurs prompts, quelques algorithme de post-traitement et une légère intéraction humaine, la qualité du graphe pourrait être grandement améliorée.
- Les graphes des différents dossiers sont fusionnés en un seul graphe global pour permettre les requêtes inter-dossiers. Cependant, cela peut introduire du bruit et des incohérences. Une approche plus robuste serait de maintenir des graphes séparés pour chaque dossier, avec des liens explicites entre les graphes pour les entités communes. Ainsi que de permettre à l'agent de naviguer entre les graphes, et de fournir un embedding de chaque graphe pour faciliter la recherche d'information.
- Le graphe de connaissance n'identifie pas le type de chaque entité (personne, bien, document, etc.) ni les types de relations. Cela limite la capacité de l'agent à raisonner sur les données. L'ajout de types d'entités et de relations permettrait d'améliorer la précision des réponses et de faciliter le raisonnement symbolique.

## Agent

L'agent fonctionne en deux temps.

1. Une étape de planification par LLM classe la question (recherche de role, transaction, document, incohérence, etc.) et choisit une première stratégie d'exploration.
2. L'agent exécute ensuite cette stratégie avec des outils d'inspection, en s'appuyant uniquement sur les éléments retournés par ces outils pour construire sa réponse.

Pour les questions de roles, de transaction ou de documents, l'agent commence d'abord par rechercher un sous-graphe de preuve.

- Evidence Subgraph: outil principal pour partir de la question complète en langage naturel. Il retourne des entités candidates, leurs relations incidentes, du contexte sémantique, et éventuellement des indices issus des documents OCR.
- Exact Entity Lookup: outil de vérification, utilisé uniquement quand l'agent dispose déjà d'un nom exact d'entité, soit parce qu'il apparaît explicitement dans la question, soit parce qu'un autre outil l'a proposé.
- Semantic Retrieve: permet de récupérer des ancres sémantiques pertinentes dans le graphe à partir de la question complète.
- Node Incident Edges: permet de vérifier précisément les relations attachées à une entité candidate.
- Neighbor Traversal: permet d'explorer le voisinage local d'une entité lorsqu'un contexte plus large est nécessaire.
- Relation List / Relation Filter: permettent d'inspecter directement les relations du graphe quand l'agent veut vérifier une hypothèse structurée.
- Dossier Catalog: permet à l'agent d'identifier les dossiers disponibles et de choisir lui-même le bon périmètre.
- Document Catalog / Document Evidence Search: permettent à l'agent d'inspecter les documents source et de retrouver des extraits OCR utiles pour les questions documentaires.

## Données Structurées

Grace à l'usage d'un graphe de connaissance, de nombreux problèmes peuvent être traités de manière pro-active et fiable. En effet, le graphe de connaissance permet de formaliser les données extraites des documents, et de raisonner sur ces données de manière symbolique. Par exemple, on peut identifier des incohérences entre les documents d'un même dossier, ou encore identifier des pièces manquantes.

Je considère donc que pour ce project, le type de demandes tel que:

- Les pieces d'identite sont-elles en ordre dans le dossier [1/2/3] ?
- Dans le dossier [1/2/3], Le DPE est-il present et correspond-il au bien ?
- Les justificatifs de domicile sont-ils conformes dans le dossier [1/2/3] ?
- Y a-t-il des incoherences entre les documents du dossier [1/2/3] ?
- Y a-t-il des incohérences dans les informations relatives aux parties du dossier [1/2/3]?
- Fais un resume des pieces manquantes dans chacun des dossier

sont des demandes qui n'ont pas besoin d'un LLM pour être traitées, et peuvent être traitées de manière fiable et pro-active en amont pendant la construction du dossier. En effet, en formalisant les règles notariales et les exigences documentaires dans la construction du graphe de connaissance, on peut identifier les pièces manquantes, les incohérences entre les documents, et les non-conformités de manière automatique et fiable.

Pour construire ce genre de raisonnement symbolique, il est nécessaire de formaliser les règles notariales et les exigences documentaires dans la construction du graphe de connaissance. Par exemple, on peut formaliser des règles telles que:
- Un dossier doit contenir une pièce d'identité valide pour chaque partie.
- Un dossier doit contenir un DPE valide pour le bien concerné.
- Un dossier doit contenir un justificatif de domicile valide pour chaque partie.

Lors de la construction du dossier, les parties sont identifiées, les documents nécessaires sont inférés, et les incohérences ou les pièces manquantes sont identifiées et annotées dans le graphe de connaissance. Ainsi, un dossier, indépendamment d'un LLM, peut être automatiquement vérifié pour sa complétude et sa conformité.

Ceci est moins couteux et plus fiable que de demander à un LLM de faire ce travail, et permet à l'agent de se concentrer sur les questions d'information.

## Metrics

Le projet suit les performances pour l'ingestion et les requêtes agentiques.

- Les requêtes enregistrent la latence totale ainsi que les temps par étape (`graph_prepare`, `embedding`, `retrieval`, `chat`).
- Les appels modèles enregistrent aussi les tokens d'entrée/sortie et une estimation de coût USD pour les modèles connus.
- Les données sont persistées dans `data/metrics_store_state.json`.
- Le frontend affiche ces métriques dans un dashboard dédié.

## Validation


La génération du graphe est validée par une étape simple de `LLM as a judge` exécutée juste après l'extraction d'un graphe.

- Le juge reçoit le texte du document ainsi que le graphe généré sérialisé en JSON.
- Il retourne un verdict simple (`pass`, `needs_review`, `fail`), un score, un résumé court, et des points d'attention.
- Cette validation reste non bloquante pour l'ingestion: si elle échoue, le graphe est conservé mais l'erreur est tracée.
- Les latences, tokens et coûts de cette étape sont suivis dans les métriques sous l'opération `kg_judge`, et les revues sont consultables dans l'onglet `Judge Reviews` du frontend.

Cette vérification ne remplace pas une validation métier formelle, mais elle permet de repérer rapidement des graphes incomplets, bruités ou peu fidèles au document source.

### Améliorations possibles

Les erreurs détectées par le juge pourraient être utilisées pour améliorer la génération du graphe, soit via des règles de post-traitement, soit en réparant le graphe et en le resoumettant à nouveau à la validation.

Le juge peut aussi servir à vérifier si les relations ou le type d'entités sont corrects, et pas seulement la fidélité globale du graphe au document source.

## Utilisation du projet

1. Cloner le repo
2. Indiquer une clé OpenAI dans le fichier `.env` voir `.env.example`
3. A la racine: ```make run```
4. L'API est disponible sur `http://localhost:8000/api/v1`
5. Dans frontend: ```python -m http.server 3000```
6. Le frontend est disponible sur `http://localhost:3000`
7. Charger les documents des dossiers
8. Explorer le graphe de connaissance
9. Poser des questions à l'agent