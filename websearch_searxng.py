#!/opt/projects/ollama-websearch/.venv/bin/python3
"""
Ollama Web Search - Example 2: SearXNG (self-hosted, private)
Streaming version - real-time output, no timeouts
Model: llama3.1
Author: Martin Simons

Why SearXNG over DuckDuckGo API:
- DuckDuckGo free API returns empty results (proven in testing)
- SearXNG aggregates multiple engines: Brave, Wikipedia, Startpage, Wikidata
- Fully self-hosted - zero data leaves your machine
- No API key required
- Docker deployment in minutes
"""

import json
import requests
import sys

OLLAMA_API = "http://localhost:11434/api/chat"
SEARXNG_URL = "http://localhost:8080/search"
MODEL = "llama3.1:latest"


def web_search(query: str, num_results: int = 5) -> str:
    """
    Search using self-hosted SearXNG and return formatted results.
    Returns top N results with title, URL and content snippet.
    """
    try:
        response = requests.get(
            SEARXNG_URL,
            params={
                "q": query,
                "format": "json",
                "language": "en",
                "safesearch": "0"
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        if not results:
            return "No results found."

        # Format top N results for the model
        formatted = []
        for i, r in enumerate(results[:num_results]):
            title = r.get("title", "No title")
            url = r.get("url", "")
            content = r.get("content", "No snippet available")
            engines = ", ".join(r.get("engines", []))
            formatted.append(
                f"[{i+1}] {title}\n"
                f"    URL: {url}\n"
                f"    Source: {engines}\n"
                f"    {content}"
            )

        return "\n\n".join(formatted)

    except requests.RequestException as e:
        return f"Search error: {str(e)}"


def stream_response(messages: list, tools: list = None) -> tuple[str, list]:
    """
    Stream a response from Ollama.
    Returns (full_text, tool_calls)
    """
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": True
    }
    if tools:
        payload["tools"] = tools

    full_content = ""
    tool_calls = []

    with requests.post(OLLAMA_API, json=payload, stream=True, timeout=30) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
                message = chunk.get("message", {})

                # Collect tool calls
                if message.get("tool_calls"):
                    tool_calls.extend(message["tool_calls"])

                # Stream text content
                content = message.get("content", "")
                if content:
                    print(content, end="", flush=True)
                    full_content += content

                if chunk.get("done"):
                    break

            except json.JSONDecodeError:
                continue

    return full_content, tool_calls


def chat_with_search(user_message: str) -> None:
    """Send a message to Ollama with SearXNG web search, streaming the response."""

    tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current, real-time information using a private self-hosted search engine",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query - be specific for better results"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    messages = [{"role": "user", "content": user_message}]

    print(f"\n❓ Question: {user_message}\n")
    print("🤔 Thinking...", flush=True)

    # First call — let model decide to use the tool
    _, tool_calls = stream_response(messages, tools)

    if not tool_calls:
        print("\n⚠️  Model answered without searching.")
        return

    # Execute tool calls
    messages.append({
        "role": "assistant",
        "content": "",
        "tool_calls": tool_calls
    })

    for tool_call in tool_calls:
        if tool_call["function"]["name"] == "web_search":
            args = tool_call["function"]["arguments"]
            query = args.get("query", "")
            print(f"\n\n🔍 Searching SearXNG for: {query}", flush=True)
            search_result = web_search(query)

            # Show sources found
            result_count = search_result.count("[") 
            print(f"📄 Found {result_count} results\n", flush=True)

            messages.append({
                "role": "tool",
                "content": search_result
            })

    # Final streaming answer
    print("💬 Answer:\n", flush=True)
    stream_response(messages)
    print("\n")


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "What is the latest version of Ollama?"
    chat_with_search(question)
