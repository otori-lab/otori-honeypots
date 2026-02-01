# Otori Honeypots

Collection de honeypots SSH pour la detection d'intrusions.

## Types de honeypots

| Type | Description | Image Docker |
|------|-------------|--------------|
| **LLM** | Honeypot SSH avec reponses generees par IA (Ollama) | `ghcr.io/otori-lab/otori-honeypots/honeypot-llm` |
| **Cowrie** | Honeypot SSH classique avec filesystem simule | `cowrie/cowrie` (officiel) |

## Quick Start (LLM Honeypot)

### Option 1: Docker Compose (recommande)

```bash
cd llm
docker compose up -d
```

Cela demarre le honeypot ET Ollama automatiquement.

### Option 2: Docker seul (Ollama sur l'hote)

1. Installer Ollama: https://ollama.ai
2. Pull le modele: `ollama pull mistral`
3. Lancer le honeypot:

```bash
docker run -d -p 2222:2222 \
  -e OLLAMA_URL="http://host.docker.internal:11434/api/generate" \
  -e FAKE_HOSTNAME="mon-serveur" \
  ghcr.io/otori-lab/otori-honeypots/honeypot-llm:latest
```

### Test de connexion

```bash
ssh -p 2222 admin@localhost
# Password: admin123
```

## Configuration

### Variables d'environnement

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://host.docker.internal:11434/api/generate` | URL de l'API Ollama |
| `OLLAMA_MODEL` | `mistral:latest` | Modele LLM a utiliser |
| `FAKE_USER` | `admin` | Nom d'utilisateur SSH accepte |
| `FAKE_PASS` | `admin123` | Mot de passe SSH accepte |
| `FAKE_HOSTNAME` | `srv-prod-01` | Hostname affiche dans le prompt |
| `SSH_PORT` | `2222` | Port SSH interne |
| `EXTRA_CONTEXT` | _(vide)_ | Contexte additionnel pour le LLM |

### Personnalisation du contexte

Le systeme prompt est integre dans l'image. Pour ajouter du contexte specifique:

```bash
docker run -d -p 2222:2222 \
  -e EXTRA_CONTEXT="Ce serveur appartient a ACME Corp. Il heberge WordPress et MySQL." \
  ghcr.io/otori-lab/otori-honeypots/honeypot-llm:latest
```

## Architecture

```
otori-honeypots/
├── llm/                    # Honeypot SSH avec LLM
│   ├── src/                # Code Python
│   ├── config/             # Prompts et config
│   ├── Dockerfile
│   └── docker-compose.yml
├── cowrie/                 # Honeypot Cowrie classique
│   ├── config/
│   ├── honeyfs/            # Fake filesystem
│   └── scripts/
└── .github/workflows/      # CI/CD
```

## Logs

Les logs sont stockes dans `/app/logs/` (monte sur `./logs/` par defaut):

- `honeypot_sessions.jsonl` - Tous les evenements en JSONL
- `sessions/` - Etat complet de chaque session (filesystem, historique)

## Documentation

- [LLM Honeypot](./llm/README.md)
- [Cowrie Honeypot](./cowrie/README.md)

## Integration avec otori-cli

Ce repo fournit les images Docker utilisees par [otori-cli](https://github.com/otori-lab/otori-cli).

## License

MIT
