# Otori Honeypots

Collection de honeypots SSH pour la detection d'intrusions. Projet de Fin d'Etudes (PFE) - ECE Paris 2025.

## Types de honeypots

| Type | Description | Image Docker |
|------|-------------|--------------|
| **Classic (Cowrie)** | Honeypot SSH/Telnet avec filesystem simule | `cowrie/cowrie` |
| **LLM** | Honeypot SSH avec reponses generees par IA | `ghcr.io/otori-lab/otori-honeypots/honeypot-llm` |

## Quick Start

### Utilisation recommandee : via otori-cli

```bash
# Installer otori-cli
git clone https://github.com/otori-lab/otori-cli.git
cd otori-cli && make install

# Deployer un honeypot classic
otori init -t classic -s mon-serveur --monitoring-url "http://otori-monitoring:8000"
otori deploy
```

### Utilisation standalone : LLM Honeypot

```bash
cd llm
docker compose up -d

# Test
ssh -p 2222 admin@localhost
# Password: admin123
```

### Utilisation standalone : Cowrie

```bash
cd cowrie
docker compose up -d

# Test
ssh -p 2222 root@localhost
# Accepte n'importe quel mot de passe
```

## Configuration

### Variables d'environnement (LLM)

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://ollama:11434/api/generate` | URL de l'API Ollama |
| `OLLAMA_MODEL` | `mistral:latest` | Modele LLM |
| `FAKE_USER` | `admin` | Utilisateur SSH |
| `FAKE_PASS` | `admin123` | Mot de passe SSH |
| `FAKE_HOSTNAME` | `srv-prod-01` | Hostname du prompt |
| `MONITORING_URL` | _(vide)_ | URL du serveur monitoring |
| `EXTRA_CONTEXT` | _(vide)_ | Contexte business pour le LLM |

### Variables d'environnement (Cowrie Shipper)

| Variable | Default | Description |
|----------|---------|-------------|
| `MONITORING_URL` | _(vide)_ | URL du serveur monitoring |
| `PROFILE_NAME` | `classic` | Nom du profil |
| `FAKE_HOSTNAME` | `svr04` | Nom du sensor |
| `LOG_FILE` | `/logs/cowrie.json` | Fichier de logs a surveiller |

## Integration Monitoring

Les honeypots envoient automatiquement les evenements au serveur de monitoring via un shipper sidecar :

```yaml
# docker-compose.yml
shipper:
  build: ./shipper
  environment:
    MONITORING_URL: "http://otori-monitoring:8000"
  networks:
    - otori-network
```

Le reseau `otori-network` permet la communication avec le monitoring sur la meme machine.

Pour un monitoring distant, utiliser l'IP :
```yaml
MONITORING_URL: "http://192.168.1.100:8000"
```

## Architecture

```
otori-honeypots/
├── llm/                    # Honeypot LLM
│   ├── src/
│   │   ├── honeypot_ssh.py    # Serveur SSH Paramiko
│   │   ├── llm_adapter.py     # Integration Ollama
│   │   ├── fs_engine.py       # Filesystem virtuel
│   │   └── log_shipper.py     # Envoi vers monitoring
│   ├── config/
│   │   └── system_prompt.txt  # Prompt systeme
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── cowrie/                 # Honeypot Cowrie
│   ├── config/
│   │   ├── cowrie.cfg.default
│   │   └── userdb.txt.default
│   ├── honeyfs/            # Fake filesystem
│   ├── shipper/            # Log shipper
│   │   ├── Dockerfile
│   │   └── log_shipper.py
│   └── docker-compose.yml
│
└── .github/workflows/      # CI/CD
```

## Logs

### LLM Honeypot
- `logs/honeypot_sessions.jsonl` - Tous les evenements (JSONL)
- `logs/sessions/` - Snapshots complets par session

### Cowrie
- `/var/log/cowrie/cowrie.json` - Evenements JSON
- `/var/log/cowrie/cowrie.log` - Logs texte

## Format des evenements

```json
{
  "timestamp": "2025-01-31T14:32:15.123Z",
  "sensor": "srv-prod-01",
  "honeypot_type": "classic",
  "session_id": "abc123",
  "src_ip": "192.168.1.42",
  "event_type": "command",
  "command": "cat /etc/passwd"
}
```

## Documentation

- [LLM Honeypot](./llm/README.md)
- [Cowrie Honeypot](./cowrie/README.md)
- [Cowrie Shipper](./cowrie/shipper/)

## License

MIT
