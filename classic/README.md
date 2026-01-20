# Module Honeypot Classique (Cowrie)

**Petite précision**
Les étapes à suivre ci-dessous sont pour exécuter le honeypot classique en local sur notre PC, avec Docker Desktop.
Pour le faire fonctionner ensuite avec notre CLI, c'est la prochaine étape à chercher.

Ce module déploie un honeypot SSH (Cowrie) pré-configuré pour simuler un serveur d'entreprise.

## 📁 Structure
* `cowrie/` : Contient les fichiers de configuration et les leurres (fichiers fake).
* `docker/` : Contient le fichier docker-compose pour lancer le service.

## 🚀 Installation & Lancement

### 1. Pré-requis
Avoir Docker Desktop installé et lancé.

### 2. Gestion des permissions (IMPORTANT)
Sur Windows, les permissions des fichiers sont souvent mal gérées par Docker Linux.

**Avant de lancer**, exécutez cette commande depuis le dossier `classic/docker` pour rendre les fichiers lisibles par le honeypot :

```powershell
docker run --rm -v "${PWD}/../cowrie/fs_template:/mnt" alpine sh -c "chmod -R 755 /mnt && chmod -R 644 /mnt/etc/passwd /mnt/home/admin/*.txt"
```


### 3. Démarrage
Toujours depuis le dossier classic/docker :

```Bash
docker-compose up -d
```


### 🧪 Tester l'accès (Attaquant)
Ouvrez un nouveau terminal et connectez-vous :

```Bash
ssh -p 2222 admin@localhost
```

Si vous avez un problème lors du lancement de cette commande, c'est que vous avez sûrement déjà un container qui utilise le port 2222.
Ce que vous devez faire:

**********
commande pour faire oublier la connexion d'un port :
```Bash
ssh-keygen -R [localhost]:2222
```
**********

Ensuite vous exécutez à nouveau:
```Bash
ssh -p 2222 admin@localhost
```

*Mot de passe : 123456*

Vous êtes censés voir que vous êtes connectés dans:
**admin@srv-confidential:**

Après vous pouvez vous balader, explorer en exécutant les commandes que vous voulez.

Preuve de fonctionnement : Une fois connecté, tapez: ```cat /etc/passwd```. Vous devriez voir la mention "JE_SUIS_LE_BOSS".

### 🛠 Commandes utiles
Voir les logs (debug) : ```docker logs -f cowrie-classic```
Arrêter et supprimer : ```docker-compose down```




### Petit +
Ensuite vous cliquez sur votre container qui correspond, dans Docker Desktop, vous allez dans "logs" pour analyser un peu les actions qui ont été faites, voir si vous les retrouvez.

**Exfiltrer les preuves** (Peut servir pour la partie de Fabio)
et pour avoir une preuve, en tant que fichier, vous exécutez la commande:

```Bash
docker cp 'nom_du_container':/cowrie/cowrie-git/var/log/cowrie/cowrie.json ./capture\_attaque.json
```

qui va créer un fichier json avec toutes les actions réalisées