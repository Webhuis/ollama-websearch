#!/opt/projects/ollama-websearch/.venv/bin/python3
"""
Ollama Web Search - Example 1: DuckDuckGo (no API key required)
Streaming version - real-time output, no timeouts
Model: llama3.1
Author: Martin Simons
"""

import json
import requests
import sys

OLLAMA_API = "http://localhost:11434/api/chat"
MODEL = "llama3.1:latest"


def web_search(query: str) -> str:
    """Search DuckDuckGo and return results."""
    try:
        response = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        results = []
        if data.get("AbstractText"):
            results.append(data["AbstractText"])
        for item in data.get("RelatedTopics", [])[:3]:
            if "Text" in item:
                results.append(item["Text"])

        return "\n".join(results) if results else "No results found."

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

                # Done
                if chunk.get("done"):
                    break

            except json.JSONDecodeError:
                continue

    return full_content, tool_calls


def chat_with_search(user_message: str) -> None:
    """Send a message to Ollama with web search tool, streaming the response."""

    tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    messages = [{"role": "user", "content": user_message}]

    print(f"\n❓ Question: {user_message}\n")

    # First call — let model decide to use the tool
    print("🤔 Thinking...", flush=True)
    _, tool_calls = stream_response(messages, tools)

    if not tool_calls:
        print("\n⚠️  No tool was called — model answered directly.")
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
            print(f"\n\n🔍 Searching for: {query}", flush=True)
            search_result = web_search(query)
            print(f"📄 Results: {search_result[:200]}...\n", flush=True)

            messages.append({
                "role": "tool",
                "content": search_result
            })

    # Second call — stream the final answer
    print("💬 Answer:\n", flush=True)
    stream_response(messages)
    print("\n")


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "What is the latest version of Ollama?"
    chat_with_search(question)
