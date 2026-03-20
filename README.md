# Ollama Web Search — The Complete Guide

> A production-tested guide to adding web search to local LLMs via Ollama.
> Every example was tested on a real Debian 13 server. No fluff.

**Author:** Martin Simons  
**Tested on:** Ollama 0.18.2, Debian 13 Trixie, Python 3.11, Node.js 22  
**Date:** March 2026

---

## Why This Guide Exists

Most tutorials about Ollama web search are wrong in at least one of these ways:

- They use DuckDuckGo's free API — which returns **empty results**
- They don't handle streaming — leading to **60-second timeouts**
- They don't document **which models** actually support tool calling
- They skip **production concerns** like auto-restart, error handling, and privacy

This guide fixes all of that. Every code example was run on a real server.

---

## The Hard Truth About DuckDuckGo's Free API

The most commonly recommended approach — DuckDuckGo's free API — simply does not work:
```bash
curl "https://api.duckduckgo.com/?q=ollama+latest+version&format=json&no_html=1"
```

Result:
```json
{
  "Abstract": "",
  "AbstractText": "",
  "RelatedTopics": [],
  "Results": []
}
```

Empty. Every time. For almost every query.  
**Do not use DuckDuckGo's free API for Ollama web search.**

---

## Search Backend Comparison

| Backend | API Key | Real Results | Privacy | Cost | Verdict |
|---|---|---|---|---|---|
| DuckDuckGo free API | ❌ None | ❌ Empty | ✅ | Free | ❌ Don't use |
| SearXNG self-hosted | ❌ None | ✅ Real | ✅ Full | Free | ✅ Best overall |
| Google Custom Search | ✅ Required | ✅ Excellent | ❌ Cloud | 100/day free | ✅ Best results |
| Bing Search API | ✅ Required | ✅ Excellent | ❌ Cloud | 1000/month free | ✅ Good alternative |
| OpenClaw built-in | ❌ None | ✅ Real | ⚠️ Depends | Free | ⚠️ GPU recommended |

---

## Model Comparison for Tool Calling

Tested on Ollama 0.18.2, CPU-only server, 32GB RAM:

| Model | Tool Calling | Thinking Mode | Web Search Speed | Recommended |
|---|---|---|---|---|
| `qwen3:8B` | ✅ Excellent | On by default | 16+ min on CPU | ⚠️ GPU only |
| `llama3.1:8B` | ✅ Good | None | 2-5 min on CPU | ✅ CPU servers |
| `mistral-nemo:12b` | ⚠️ Moderate | None | 3-7 min on CPU | ⚠️ Sometimes |
| `deepseek-r1:14b` | ⚠️ Limited | Always on | Very slow | ❌ Not for search |

> ⚠️ **qwen3 thinking mode warning:** qwen3 enables extended reasoning by default.
> On CPU-only servers this causes 16+ minute response times for web search queries.
> A GPU with 16GB+ VRAM is strongly recommended for qwen3.

---

## Prerequisites

### System Requirements
- Ollama 0.17.1+ (tested on 0.18.2)
- Python 3.10+ or Node.js 22+
- Docker (for SearXNG)
- 16GB+ RAM recommended

### Install Ollama
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Pull a recommended model
```bash
ollama pull llama3.1        # Best for CPU-only servers
ollama pull qwen3           # Best quality (GPU recommended)
```

### Set up Python environment
```bash
mkdir -p /opt/projects/ollama-websearch
cd /opt/projects/ollama-websearch
python3 -m venv .venv
source .venv/bin/activate
pip install requests ollama
```

### Install Node.js 22 (via nvm)
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 22
nvm use 22
nvm alias default 22
```

---

## Option 1: SearXNG (Recommended — Private, Free, No API Key)

### Setup SearXNG with Docker
```bash
# Create config directory
mkdir -p /opt/projects/ollama-websearch/docker/searxng

# Start SearXNG
docker run -d \
  --name searxng \
  --restart always \
  -p 8080:8080 \
  -e BASE_URL=http://localhost:8080 \
  searxng/searxng:latest
```

### Enable JSON format (required)
```bash
# Copy default config
docker cp searxng:/etc/searxng/settings.yml \
  /opt/projects/ollama-websearch/docker/searxng/settings.yml
```

Edit `settings.yml` — find the `search:` section and add:
```yaml
search:
  safe_search: 0
  autocomplete: ""
  formats:
    - html
    - json

server:
  secret_key: "change-this-to-a-random-string"
  limiter: false
```

Restart with config mounted:
```bash
docker stop searxng && docker rm searxng

docker run -d \
  --name searxng \
  --restart always \
  -p 8080:8080 \
  -e BASE_URL=http://localhost:8080 \
  -v /opt/projects/ollama-websearch/docker/searxng/settings.yml:/etc/searxng/settings.yml \
  searxng/searxng:latest
```

Verify it works:
```bash
curl "http://localhost:8080/search?q=ollama&format=json" | python3 -m json.tool | head -20
```

### Python Example
```bash
source .venv/bin/activate
./websearch_searxng.py "What is the latest version of Ollama?"
```

Expected output:
```
❓ Question: What is the latest version of Ollama?
🤔 Thinking...
🔍 Searching SearXNG for: Ollama latest version
📄 Found 5 results
💬 Answer:
The latest version of Ollama is 0.18.2.
```

### Node.js Example
```bash
node websearch_searxng.js "What is the latest version of Ollama?"
```

### Shell/curl Example
```bash
./websearch_searxng.sh "What is the latest version of Ollama?"
```

---

## Option 2: Google Custom Search API

### Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Enable **Custom Search API**
3. Create API key at [Credentials](https://console.cloud.google.com/apis/credentials)
4. Create search engine at [Programmable Search Engine](https://programmablesearchengine.google.com)
```bash
export GOOGLE_API_KEY=your-api-key
export GOOGLE_CSE_ID=your-search-engine-id

# Python
./websearch_google_bing.py "What is the latest version of Ollama?"

# Node.js
node websearch_google_bing.js "What is the latest version of Ollama?"

# Shell
./websearch_google_bing.sh "What is the latest version of Ollama?"
```

---

## Option 3: Bing Search API

### Setup
1. Go to [Azure Portal](https://portal.azure.com)
2. Create **Bing Search v7** resource (free tier: 1000 queries/month)
3. Copy API key
```bash
export BING_API_KEY=your-api-key
export SEARCH_BACKEND=bing

# Python
./websearch_google_bing.py "What is the latest version of Ollama?"

# Node.js
node websearch_google_bing.js "What is the latest version of Ollama?"

# Shell
./websearch_google_bing.sh "What is the latest version of Ollama?"
```

---

## Option 4: OpenClaw Built-in Web Search

Ollama 0.18+ ships with OpenClaw integration which includes built-in web search.

### Requirements
- Node.js 22.12+ (use nvm)
- npm installed under nvm (not system npm)
- `psmisc` package (`sudo apt install psmisc`)
- GPU recommended (CPU-only causes runaway inference)

### Setup
```bash
# Install psmisc (required for --force flag)
sudo apt install psmisc -y

# Install Node.js 22 via nvm
nvm install 22 && nvm use 22

# Install openclaw under nvm
/home/$USER/.nvm/versions/node/v22.22.1/bin/npm install -g openclaw
```

### Run as systemd service (recommended)
```bash
sudo cat > /etc/systemd/system/openclaw-gateway.service << 'SYSTEMD'
[Unit]
Description=OpenClaw Gateway
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=YOUR_USERNAME
Environment="PATH=/home/YOUR_USERNAME/.nvm/versions/node/v22.22.1/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/YOUR_USERNAME/.nvm/versions/node/v22.22.1/bin/openclaw gateway
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SYSTEMD

sudo systemctl daemon-reload
sudo systemctl enable openclaw-gateway
sudo systemctl start openclaw-gateway
```

Then launch:
```bash
ollama launch openclaw --model llama3.1:latest
```

> ⚠️ **Known issues on CPU-only servers:**
> - qwen3 thinking mode causes 16+ minute hangs — use llama3.1 instead
> - Set `"restart": false` in `~/.openclaw/openclaw.json` to prevent session auto-resume
> - Clear workspace after crashes: `rm -rf ~/.openclaw/workspace/* /tmp/openclaw`

---

## Production Tips

### Ollama on multi-user / Docker servers

By default Ollama only listens on `127.0.0.1`. If you run LiteLLM or other
tools in Docker, configure Ollama to listen on all interfaces:
```bash
sudo systemctl edit ollama
```

Add:
```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```
```bash
sudo systemctl daemon-reload && sudo systemctl restart ollama
```

### Choosing the right model
```bash
# Fast, reliable tool calling on CPU
ollama pull llama3.1

# Best quality, needs GPU for web search
ollama pull qwen3

# Disable thinking mode in qwen3 for interactive use
# In OpenClaw TUI: /think off
```

### Directory structure for multi-user servers
```bash
sudo mkdir -p /opt/projects/ollama-websearch
sudo chown youruser:devteam /opt/projects/ollama-websearch
sudo chmod 2775 /opt/projects/ollama-websearch
```

---

## Quick Reference
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check SearXNG is running
curl "http://localhost:8080/search?q=test&format=json" | jq .results[0].title

# Run Python example
source .venv/bin/activate && ./websearch_searxng.py "your question"

# Run Node.js example
node websearch_searxng.js "your question"

# Run shell example
./websearch_searxng.sh "your question"
```

---

## License

MIT — use freely, attribution appreciated.
