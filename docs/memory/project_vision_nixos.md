---
name: Vision long terme — déploiement NixOS / serveur centralisé
description: L'objectif final est de supprimer Docker et le venv Python au profit d'une intégration native sur NixOS, accessible via URL (modèle Citrix XenApp)
type: project
---

L'objectif à long terme est de déployer PULSE OS sur un serveur NixOS où le client n'installe rien — il se connecte simplement à une URL.

**Why:** Docker et le venv Python sont des intermédiaires utiles pour le développement portable sur Windows, mais dans un produit final, ils ajoutent de la friction. NixOS permet une intégration native déclarative sans ces couches, et le modèle "client = navigateur + URL" élimine toute gestion côté utilisateur.

**How to apply:** Ne pas sur-ingénierer l'abstraction Docker/venv actuelle — elle est temporaire. Quand on approche de la production, orienter les choix d'architecture (chemins, configs, services) vers ce qui sera facilement déclarable dans un fichier Nix. Éviter les dépendances Windows-spécifiques dans le code applicatif lui-même.
