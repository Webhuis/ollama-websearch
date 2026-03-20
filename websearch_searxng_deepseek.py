#!/opt/projects/ollama-websearch/.venv/bin/python3
"""
Ollama Web Search - DeepSeek-r1 with SearXNG (manual injection)
Note: deepseek-r1 does not support tool calling — Ollama returns:
"deepseek-r1:14b does not support tools"
Workaround: search SearXNG first, inject results into system prompt
DeepSeek-r1 does not support tool calling (returns HTTP 400)
Workaround: search SearXNG first, inject results into prompt
Author: Martin Simons
"""

import json
import requests
import sys

OLLAMA_API = "http://localhost:11434/api/chat"
SEARXNG_URL = "http://localhost:8080/search"
MODEL = "deepseek-r1:14b"


def web_search(query: str, num_results: int = 5) -> str:
    """Search SearXNG and return formatted results."""
    try:
        response = requests.get(
            SEARXNG_URL,
            params={"q": query, "format": "json", "language": "en"},
            timeout=10
        )
        response.raise_for_status()
        results = response.json().get("results", [])[:num_results]
        if not results:
            return "No results found."
        formatted = []
        for i, r in enumerate(results):
            formatted.append(
                f"[{i+1}] {r.get('title', 'No title')}\n"
                f"    URL: {r.get('url', '')}\n"
                f"    {r.get('content', 'No snippet')}"
            )
        return "\n\n".join(formatted)
    except requests.RequestException as e:
        return f"Search error: {str(e)}"


def stream_response(messages: list) -> str:
    """Stream response from Ollama — no tools for DeepSeek."""
    payload = {"model": MODEL, "messages": messages, "stream": True}
    full_content = ""

    with requests.post(OLLAMA_API, json=payload, stream=True, timeout=120) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
                content = chunk.get("message", {}).get("content", "")
                if content:
                    print(content, end="", flush=True)
                    full_content += content
                if chunk.get("done"):
                    break
            except json.JSONDecodeError:
                continue

    return full_content


def chat_with_search(user_message: str) -> None:
    """
    DeepSeek-r1 workaround:
    1. Search SearXNG manually
    2. Inject results into system prompt
    3. Ask DeepSeek to reason over them
    """
    print(f"\n❓ Question: {user_message}\n")

    # Step 1 — search first, without asking the model
    print(f"🔍 Searching SearXNG for: {user_message}", flush=True)
    search_results = web_search(user_message)
    result_count = search_results.count("[")
    print(f"📄 Found {result_count} results\n", flush=True)

    # Step 2 — inject results into system prompt
    system_prompt = f"""You are a helpful assistant with access to current web search results.
Use the following search results to answer the user's question accurately.
Always cite which source you used.

SEARCH RESULTS:
{search_results}

Answer based on these results. If the results don't contain enough information, say so."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]

    # Step 3 — stream DeepSeek's reasoning
    print("💬 Answer:\n", flush=True)
    stream_response(messages)
    print("\n")


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "What is the latest version of Ollama?"
    chat_with_search(question)
