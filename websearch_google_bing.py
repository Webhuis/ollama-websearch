#!/opt/projects/ollama-websearch/.venv/bin/python3
"""
Ollama Web Search - Example 3: Google Custom Search + Bing Search APIs
Streaming version - real-time output, no timeouts
Model: llama3.1
Author: Martin Simons
"""

import json
import os
import requests
import sys

OLLAMA_API = "http://localhost:11434/api/chat"
MODEL = "llama3.1:latest"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "your-google-api-key")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "your-custom-search-engine-id")
BING_API_KEY = os.getenv("BING_API_KEY", "your-bing-api-key")
SEARCH_BACKEND = os.getenv("SEARCH_BACKEND", "google")

def web_search_google(query: str, num_results: int = 5) -> str:
    try:
        response = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID, "q": query, "num": num_results},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])
        if not items:
            return "No results found."
        formatted = []
        for i, item in enumerate(items):
            formatted.append(
                f"[{i+1}] {item.get('title', 'No title')}\n"
                f"    URL: {item.get('link', '')}\n"
                f"    {item.get('snippet', 'No snippet')}"
            )
        return "\n\n".join(formatted)
    except requests.RequestException as e:
        return f"Google search error: {str(e)}"

def web_search_bing(query: str, num_results: int = 5) -> str:
    try:
        response = requests.get(
            "https://api.bing.microsoft.com/v7.0/search",
            headers={"Ocp-Apim-Subscription-Key": BING_API_KEY},
            params={"q": query, "count": num_results, "mkt": "en-US"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("webPages", {}).get("value", [])
        if not items:
            return "No results found."
        formatted = []
        for i, item in enumerate(items):
            formatted.append(
                f"[{i+1}] {item.get('name', 'No title')}\n"
                f"    URL: {item.get('url', '')}\n"
                f"    {item.get('snippet', 'No snippet')}"
            )
        return "\n\n".join(formatted)
    except requests.RequestException as e:
        return f"Bing search error: {str(e)}"

def web_search(query: str, num_results: int = 5) -> str:
    if SEARCH_BACKEND == "bing":
        print(f"🔍 Searching Bing for: {query}", flush=True)
        return web_search_bing(query, num_results)
    else:
        print(f"🔍 Searching Google for: {query}", flush=True)
        return web_search_google(query, num_results)

def stream_response(messages: list, tools: list = None) -> tuple[str, list]:
    payload = {"model": MODEL, "messages": messages, "stream": True}
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
                if message.get("tool_calls"):
                    tool_calls.extend(message["tool_calls"])
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
    tools = [{"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web for current, real-time information",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "The search query"}
        }, "required": ["query"]}
    }}]

    messages = [{"role": "user", "content": user_message}]
    print(f"\n❓ Question: {user_message}")
    print(f"🔧 Backend: {SEARCH_BACKEND.upper()}\n")
    print("🤔 Thinking...", flush=True)

    _, tool_calls = stream_response(messages, tools)

    if not tool_calls:
        print("\n⚠️  Model answered without searching.")
        return

    messages.append({"role": "assistant", "content": "", "tool_calls": tool_calls})

    for tool_call in tool_calls:
        if tool_call["function"]["name"] == "web_search":
            query = tool_call["function"]["arguments"].get("query", "")
            search_result = web_search(query)
            print(f"📄 Found {search_result.count('[')  } results\n", flush=True)
            messages.append({"role": "tool", "content": search_result})

    print("💬 Answer:\n", flush=True)
    stream_response(messages)
    print("\n")

if __name__ == "__main__":
    if SEARCH_BACKEND == "google" and GOOGLE_API_KEY == "your-google-api-key":
        print("❌ Set GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables")
        print("   export GOOGLE_API_KEY=your-key")
        print("   export GOOGLE_CSE_ID=your-cse-id")
        sys.exit(1)
    if SEARCH_BACKEND == "bing" and BING_API_KEY == "your-bing-api-key":
        print("❌ Set BING_API_KEY environment variable")
        print("   export BING_API_KEY=your-key")
        sys.exit(1)
    question = sys.argv[1] if len(sys.argv) > 1 else "What is the latest version of Ollama?"
    chat_with_search(question)
