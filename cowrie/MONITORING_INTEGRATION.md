# Intégration Cowrie → Monitoring

> Document de spécification pour l'envoi des logs Cowrie vers le serveur Monitoring.
> Statut : À IMPLÉMENTER

---

## Objectif

Permettre au honeypot Cowrie (classique) d'envoyer automatiquement ses logs au serveur Monitoring Otori, de la même manière que le honeypot LLM.

---

## Architecture cible

```
┌─────────────────────────────────────────────┐
│           COWRIE CONTAINER (custom)         │
│                                             │
│  ┌─────────────┐      ┌──────────────────┐  │
│  │   Cowrie    │─────▶│   Log Shipper    │──────▶ Monitoring
│  │  (honeypot) │ JSON │   (Python)       │ HTTP   POST /ingest
│  └─────────────┘ logs └──────────────────┘  │
│                                             │
│  /cowrie/var/log/cowrie/cowrie.json         │
└─────────────────────────────────────────────┘
```

---

## Pourquoi une image custom ?

Cowrie n'a pas de plugin natif pour envoyer les logs en HTTP POST vers une URL custom. Les options disponibles (Elasticsearch, Splunk, MongoDB) ne correspondent pas à notre besoin.

**Solution retenue** : Créer une image Docker qui étend `cowrie/cowrie:latest` et ajoute un script Python (log shipper) qui :
1. S'enregistre auprès du monitoring au démarrage
2. Lit les logs JSON de Cowrie en temps réel (tail)
3. Convertit au format OtoriEventIn
4. Envoie via HTTP POST à `/ingest`
5. Buffer sur disque en cas d'échec (retry automatique)

---

## Fichiers à créer

### 1. `cowrie/Dockerfile`

```dockerfile
FROM cowrie/cowrie:latest

USER root

# Installer les dépendances pour le log shipper
RUN apt-get update && apt-get install -y python3-requests && rm -rf /var/lib/apt/lists/*

# Copier le log shipper
COPY src/log_shipper.py /cowrie/log_shipper.py
COPY src/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Variables d'environnement pour le monitoring
ENV MONITORING_URL=""
ENV PROFILE_NAME=""
ENV SENSOR_FILE="/cowrie/var/lib/cowrie/sensor.json"
ENV LOG_FILE="/cowrie/var/log/cowrie/cowrie.json"

USER cowrie

ENTRYPOINT ["/entrypoint.sh"]
```

### 2. `cowrie/src/entrypoint.sh`

```bash
#!/bin/bash

# Démarrer le log shipper en background (si MONITORING_URL est défini)
if [ -n "$MONITORING_URL" ]; then
    python3 /cowrie/log_shipper.py &
fi

# Démarrer Cowrie (commande originale)
exec /cowrie/cowrie-env/bin/python3 /cowrie/cowrie-git/bin/cowrie start -n
```

### 3. `cowrie/src/log_shipper.py`

Script Python adapté du LLM shipper avec les modifications suivantes :

#### Format des logs Cowrie (entrée)

```json
{
  "eventid": "cowrie.session.connect",
  "timestamp": "2024-01-22T10:12:01.123456Z",
  "src_ip": "192.168.1.100",
  "src_port": 54321,
  "dst_ip": "10.0.0.5",
  "dst_port": 2222,
  "session": "abc123def456",
  "protocol": "ssh"
}
```

```json
{
  "eventid": "cowrie.login.success",
  "timestamp": "2024-01-22T10:12:05.123456Z",
  "session": "abc123def456",
  "username": "root",
  "password": "admin123"
}
```

```json
{
  "eventid": "cowrie.command.input",
  "timestamp": "2024-01-22T10:12:10.123456Z",
  "session": "abc123def456",
  "input": "cat /etc/passwd"
}
```

```json
{
  "eventid": "cowrie.session.closed",
  "timestamp": "2024-01-22T10:15:00.123456Z",
  "session": "abc123def456",
  "duration": 179.5
}
```

#### Mapping eventid → event_type

| Cowrie eventid | OtoriEventIn event_type |
|----------------|-------------------------|
| `cowrie.session.connect` | `connect` |
| `cowrie.login.success` | `login_success` |
| `cowrie.login.failed` | `login_failed` |
| `cowrie.command.input` | `command` |
| `cowrie.session.closed` | `closed` |

#### Format OtoriEventIn (sortie)

```json
{
  "timestamp": "2024-01-22T10:12:01.123456Z",
  "sensor": "abc123-192.168.1.50-cowrie-prod",
  "honeypot_type": "classic",
  "session_id": "abc123def456",
  "src_ip": "192.168.1.100",
  "src_port": 54321,
  "dst_ip": "10.0.0.5",
  "dst_port": 2222,
  "event_type": "connect",
  "username": null,
  "password": null,
  "command": null,
  "duration_sec": null
}
```

---

## Modifications CLI

### Template `classic/docker-compose.yml`

Remplacer l'image officielle par notre image custom :

```yaml
services:
  cowrie:
    image: ghcr.io/otori-lab/otori-honeypots/cowrie:latest
    # OU en local : build: .
    container_name: otori-classic
    ports:
      - "2222:2222"
    environment:
      MONITORING_URL: ""
      PROFILE_NAME: ""
    volumes:
      - ./cowrie.cfg:/cowrie/cowrie-git/etc/cowrie.cfg:ro
      - ./userdb.txt:/cowrie/cowrie-git/etc/userdb.txt:ro
      - ./honeyfs:/cowrie/cowrie-git/honeyfs:ro
      - cowrie-logs:/cowrie/var/log/cowrie
      - cowrie-data:/cowrie/var/lib/cowrie
    restart: unless-stopped

volumes:
  cowrie-logs:
  cowrie-data:
```

### `config/templates.go`

Ajouter une fonction `CustomizeClassicProfile()` similaire à `CustomizeIAProfile()` :
- Remplacer `MONITORING_URL: ""`
- Remplacer `PROFILE_NAME: ""`
- Personnaliser les noms de volumes et containers

---

## Ordre d'implémentation

1. **Créer `cowrie/src/log_shipper.py`**
   - Copier la base de `llm/src/log_shipper.py`
   - Adapter la fonction `_convert_event()` pour le format Cowrie
   - Changer les chemins par défaut (LOG_FILE, SENSOR_FILE)

2. **Créer `cowrie/src/entrypoint.sh`**
   - Script bash simple qui lance le shipper puis Cowrie

3. **Créer `cowrie/Dockerfile`**
   - Étendre `cowrie/cowrie:latest`
   - Copier les scripts
   - Définir les variables d'environnement

4. **Tester localement**
   ```bash
   cd cowrie
   docker build -t cowrie-custom:test .
   docker run -e MONITORING_URL=http://host.docker.internal:8000 cowrie-custom:test
   ```

5. **Mettre à jour le template CLI**
   - Modifier `internal/templates/data/classic/docker-compose.yml`
   - Ajouter `CustomizeClassicProfile()` dans `templates.go`

6. **CI/CD**
   - Ajouter le build de l'image Cowrie dans `.github/workflows/docker-publish.yml`

---

## Tests de validation

### Test unitaire

```python
def test_convert_cowrie_event():
    raw = {
        "eventid": "cowrie.command.input",
        "timestamp": "2024-01-22T10:12:10Z",
        "session": "abc123",
        "input": "whoami"
    }
    result = shipper._convert_event(raw)
    assert result["event_type"] == "command"
    assert result["command"] == "whoami"
    assert result["session_id"] == "abc123"
```

### Test end-to-end

1. Démarrer le monitoring : `cd otori-monitoring && make run`
2. Démarrer Cowrie custom : `docker run -e MONITORING_URL=http://localhost:8000 ...`
3. Se connecter : `ssh -p 2222 root@localhost`
4. Vérifier dans le dashboard que la session apparaît

---

## Estimation

- Création des fichiers : ~1h
- Tests et debug : ~30min
- Mise à jour CLI : ~30min
- **Total : ~2h**

---

## Notes

- L'image custom sera publiée sur `ghcr.io/otori-lab/otori-honeypots/cowrie:latest`
- L'image officielle `cowrie/cowrie` reste utilisable en mode standalone (sans monitoring)
- Le log shipper est optionnel : si `MONITORING_URL` est vide, Cowrie fonctionne normalement
