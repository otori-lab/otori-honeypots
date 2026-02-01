# LLM SSH Honeypot

Honeypot SSH intelligent utilisant un LLM (Ollama) pour generer des reponses realistes.

## Fonctionnalites

- **Shell interactif SSH** avec authentification par mot de passe
- **Reponses generees par IA** pour les commandes inconnues
- **Filesystem virtuel** persistant par session
- **Architecture hybride**:
  - Commandes triviales (whoami, pwd, id, date) → reponses deterministes
  - Operations filesystem (cd, ls, cat, mkdir, rm) → moteur FS interne
  - Autres commandes → LLM avec validation
- **Logging complet** en JSONL pour analyse

## Quick Start

```bash
# Avec Docker Compose (Ollama inclus)
docker compose up -d

# Test
ssh -p 2222 admin@localhost
# Password: admin123
```

## Configuration

Toute la configuration se fait via variables d'environnement:

```bash
docker run -d -p 2222:2222 \
  -e OLLAMA_URL="http://host.docker.internal:11434/api/generate" \
  -e OLLAMA_MODEL="mistral:latest" \
  -e FAKE_USER="admin" \
  -e FAKE_PASS="secretpass" \
  -e FAKE_HOSTNAME="prod-web-01" \
  -e EXTRA_CONTEXT="Serveur web de production pour acme.com" \
  -v ./logs:/app/logs \
  ghcr.io/otori-lab/otori-honeypots/honeypot-llm:latest
```

## Architecture

```
llm/
├── src/
│   ├── honeypot_ssh.py    # Serveur SSH principal
│   ├── llm_adapter.py     # Interface avec Ollama
│   ├── fs_engine.py       # Filesystem virtuel
│   └── utils.py           # Utilitaires (logging)
├── config/
│   ├── system_prompt.txt  # Prompt systeme pour le LLM
│   └── default_context.json
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Comment ca marche

1. **Connexion SSH** → Paramiko gere l'authentification
2. **Commande recue** → Pipeline de traitement:
   ```
   quick_command() → handle_fs_ops() → LLM fallback
   ```
3. **Post-validation** → Assure la coherence (whoami retourne toujours le bon user)
4. **Generation dynamique** → Si `cat` sur un fichier inexistant, le LLM genere du contenu et le persiste

## Logs

Format JSONL dans `logs/honeypot_sessions.jsonl`:

```json
{"ts":"2024-01-22T10:12:01Z","sid":"uuid","ip":"10.0.0.5","type":"command","cmd":"ls -la","cwd":"/home/admin"}
{"ts":"2024-01-22T10:12:02Z","sid":"uuid","ip":"10.0.0.5","type":"output","out":"notes.txt scripts .ssh\n","code":0}
```

Sessions completes dans `logs/sessions/{session_id}.json`.

## Developpement

```bash
# Build local
docker build -t honeypot-llm:dev .

# Test avec Ollama local
ollama serve &
ollama pull mistral
docker run -d -p 2222:2222 \
  -e OLLAMA_URL="http://host.docker.internal:11434/api/generate" \
  honeypot-llm:dev
```
