# VAFA - Classement des Athlètes

Application web pour gérer et afficher les classements des athlètes VAFA (Vendée Athlétisme Fédération d'Athlétisme).

## Fonctionnalités

- Affichage des classements des athlètes dans un tableau interactif
- Filtrage par catégorie
- Tri par différentes colonnes (Place, Nom/Prénom, Club, Catégorie, Performance)
- Interface responsive et moderne aux couleurs VAFA
- Synchronisation automatique avec Google Sheets

## Prérequis

- Python 3.x
- Compte Google avec accès à Google Sheets
- Fichier de credentials Google (service_account.json)

## Installation

1. Clonez le repository :
```bash
git clone [URL_DU_REPO]
cd app-athle
```

2. Installez les dépendances Python :
```bash
pip install -r requirements.txt
```

3. Configurez les credentials Google :
   - Créez un projet dans la Google Cloud Console
   - Activez l'API Google Sheets
   - Créez un compte de service et téléchargez le fichier JSON des credentials
   - Renommez le fichier en `service_account.json` et placez-le à la racine du projet
   - Ou définissez le chemin vers votre fichier de credentials via la variable d'environnement `SERVICE_ACCOUNT_PATH`

## Utilisation

### Application Web

1. Démarrez le serveur Flask :
```bash
python app.py
```

2. Accédez à l'application dans votre navigateur :
```
http://localhost:5000
```

### Script de Classement

Pour ajouter un nouveau classement :

1. Exécutez le script :
```bash
python classement.py
```

2. Entrez l'URL de la liste des engagés quand demandé
3. Le script va automatiquement :
   - Extraire les données des athlètes
   - Les trier par performance
   - Créer un nouvel onglet dans le Google Sheet
   - Y insérer les données

## Structure du Projet

- `app.py` : Application Flask principale
- `classement.py` : Script pour ajouter de nouveaux classements
- `templates/table.html` : Template HTML pour l'affichage des classements
- `static/` : Fichiers statiques (images, CSS, etc.)

## Configuration

- `SHEET_KEY` : Clé du Google Sheet dans `app.py` et `classement.py`
- `SERVICE_ACCOUNT_PATH` : Chemin vers le fichier de credentials Google
- Les couleurs VAFA sont définies dans les variables CSS de `table.html`

## Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :
1. Fork le projet
2. Créer une branche pour votre fonctionnalité
3. Commiter vos changements
4. Pousser vers la branche
5. Ouvrir une Pull Request

## Licence

[À définir selon vos besoins] 