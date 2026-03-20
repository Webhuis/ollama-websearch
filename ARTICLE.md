---
title: The Only Honest Guide to Web Search in Ollama
tags: ollama, llm, web-search, self-hosted, python
canonical_url: https://github.com/Webhuis/ollama-websearch
cover_image: 
description: Every tutorial about Ollama web search gets it wrong. DuckDuckGo's free API returns empty results. Here's what actually works — tested on a real Debian 13 server.
---

# The Only Honest Guide to Web Search in Ollama

*Every other tutorial gets this wrong. Here's what actually works.*

---

I wanted to add web search to my local Ollama setup. I found a Medium article
that looked promising. It used DuckDuckGo's free API. I followed it exactly.

It returned empty results. Every time. For every query.

So I spent two days testing every approach on a real Debian 13 server with
Ollama 0.18.2. This is what I found.

---

## First: The DuckDuckGo Lie

Every tutorial recommends this:
```python
response = requests.get(
    "https://api.duckduckgo.com/",
    params={"q": query, "format": "json"}
)
```

Here's what it actually returns:
```json
{
  "Abstract": "",
  "AbstractText": "",
  "RelatedTopics": [],
  "Results": []
}
```

Empty. I verified it with curl:
```bash
curl "https://api.duckduckgo.com/?q=ollama+latest+version&format=json&no_html=1"
```

The meta section reveals why — it's a test endpoint in "development" state,
marked offline. **DuckDuckGo's free API is not a real search API.**

---

## What Actually Works

After testing every option, here's the honest comparison:

| Backend | API Key | Real Results | Private | Cost |
|---|---|---|---|---|
| DuckDuckGo free API | ❌ | ❌ Empty | ✅ | Free |
| **SearXNG self-hosted** | ❌ | ✅ | ✅ Full | Free |
| Google Custom Search | ✅ | ✅ Excellent | ❌ | 100/day free |
| Bing Search API | ✅ | ✅ | ❌ | 1000/month free |
| OpenClaw built-in | ❌ | ✅ | ⚠️ | Free |

**Winner: SearXNG.** Self-hosted, private, no API key, real results from
multiple engines simultaneously.

---

## The Timeout Problem Nobody Mentions

The second mistake most tutorials make: no streaming.
```python
# This will timeout on any real query
response = requests.post(OLLAMA_API, json=payload, timeout=60)
```

Ollama needs time to think, search, and generate. 60 seconds isn't enough.
The solution is streaming — you start receiving output immediately:
```python
with requests.post(OLLAMA_API, json=payload, stream=True) as response:
    for line in response.iter_lines():
        chunk = json.loads(line)
        content = chunk.get("message", {}).get("content", "")
        if content:
            print(content, end="", flush=True)
```

No timeout. Real-time output. Works every time.

---

## Which Model Should You Use?

Not all Ollama models support tool calling. Tested on Ollama 0.18.2:

| Model | Tool Calling | Speed on CPU |
|---|---|---|
| `llama3.1:8B` | ✅ Reliable | ~2-5 min |
| `qwen3:8B` | ✅ Excellent | ⚠️ 16+ min* |
| `mistral-nemo:12b` | ⚠️ Moderate | ~3-7 min |
| `deepseek-r1:14b` | ⚠️ Limited | Very slow |

*qwen3 enables extended reasoning (thinking mode) by default. On a CPU-only
server this caused a **16-minute hang** for a simple web search query, consuming
21GB RAM. On a GPU it's the best choice. On CPU, use llama3.1.

---

## Setting Up SearXNG
```bash
# Start SearXNG
docker run -d \
  --name searxng \
  --restart always \
  -p 8080:8080 \
  -e BASE_URL=http://localhost:8080 \
  searxng/searxng:latest
```

SearXNG needs JSON format enabled — it's off by default:
```bash
docker cp searxng:/etc/searxng/settings.yml ./settings.yml
```

Add to the `search:` section:
```yaml
search:
  formats:
    - html
    - json

server:
  limiter: false
```

Restart with config mounted:
```bash
docker stop searxng && docker rm searxng
docker run -d --name searxng --restart always \
  -p 8080:8080 \
  -e BASE_URL=http://localhost:8080 \
  -v $(pwd)/settings.yml:/etc/searxng/settings.yml \
  searxng/searxng:latest
```

Verify:
```bash
curl "http://localhost:8080/search?q=ollama&format=json" | jq .results[0].title
```

---

## The Working Python Example
```python
import json, requests, sys

OLLAMA_API = "http://localhost:11434/api/chat"
SEARXNG_URL = "http://localhost:8080/search"
MODEL = "llama3.1:latest"

def web_search(query: str) -> str:
    response = requests.get(SEARXNG_URL,
        params={"q": query, "format": "json", "language": "en"},
        timeout=10)
    results = response.json().get("results", [])[:5]
    return "\n\n".join(
        f"[{i+1}] {r['title']}\n    {r.get('content', '')}"
        for i, r in enumerate(results)
    ) or "No results found."

def stream_response(messages, tools=None):
    payload = {"model": MODEL, "messages": messages, "stream": True}
    if tools: payload["tools"] = tools
    tool_calls = []
    with requests.post(OLLAMA_API, json=payload, stream=True, timeout=30) as r:
        for line in r.iter_lines():
            if not line: continue
            chunk = json.loads(line)
            msg = chunk.get("message", {})
            if msg.get("tool_calls"): tool_calls.extend(msg["tool_calls"])
            if msg.get("content"): print(msg["content"], end="", flush=True)
            if chunk.get("done"): break
    return tool_calls

def chat(question: str):
    tools = [{"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web for current information",
        "parameters": {"type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]}
    }}]
    messages = [{"role": "user", "content": question}]
    print(f"\n❓ {question}\n🤔 Thinking...")
    tool_calls = stream_response(messages, tools)
    if not tool_calls: return
    messages.append({"role": "assistant", "content": "", "tool_calls": tool_calls})
    for tc in tool_calls:
        query = tc["function"]["arguments"].get("query", "")
        print(f"\n\n🔍 Searching: {query}")
        messages.append({"role": "tool", "content": web_search(query)})
    print("\n💬 Answer:\n")
    stream_response(messages)

chat(sys.argv[1] if len(sys.argv) > 1 else "What is the latest version of Ollama?")
```

Run it:
```bash
python3 websearch_searxng.py "What is the weather in Nijmegen today?"
```

Output:
```
❓ What is the weather in Nijmegen today?
🤔 Thinking...
🔍 Searching SearXNG for: Nijmegen weather today
📄 Found 5 results
💬 Answer:
According to AccuWeather, it will be cloudy with a chance of rain today...
```

It works. Unlike every other tutorial.

---

## What About Ollama's Built-in Web Search?

Ollama 0.18 introduced OpenClaw integration with built-in web search.
The reality is more nuanced than the release notes suggest:

- Web search lives inside **OpenClaw** — a coding assistant, not a standalone feature
- Requires **Node.js 22.12+** (not documented)
- Must install openclaw under **nvm's npm**, not system npm
- Requires **psmisc** package for the `--force` flag (`sudo apt install psmisc`)
- Gateway must be started before `ollama launch`
- **Not recommended for CPU-only servers** — session auto-resume causes runaway inference

For developers who want web search in their **own applications**, the API +
SearXNG approach gives full control. OpenClaw is a UI tool, not a programmable API.

---

## The Full Code

All examples — Python, Node.js, and shell/curl — are on GitHub:
**[github.com/Webhuis/ollama-websearch](https://github.com/Webhuis/ollama-websearch)**

Includes:
- SearXNG setup with Docker
- Google Custom Search API integration
- Bing Search API integration  
- Streaming responses in all three languages
- Production tips for multi-user servers
- systemd service for SearXNG auto-start

---

*Tested on a real Debian 13 server. No VMs, no Docker-in-Docker, no assumptions.*
*If something doesn't work, open an issue.*
