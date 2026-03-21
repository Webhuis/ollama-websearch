---
title: "Claude vs DeepSeek: A Real Code Review Battle (With and Without Web Search)"
tags: ollama, llm, deepseek, claude, python
canonical_url: https://github.com/Webhuis/ollama-websearch
description: Same code, same prompt, three conditions. Claude without search, DeepSeek without search, DeepSeek with SearXNG. Here's what actually happened.
---

# Claude vs DeepSeek: A Real Code Review Battle

*Same code. Same prompt. Three conditions. One honest verdict.*

---

This is Part 2 of my Ollama web search series. In Part 1, I proved that
DuckDuckGo's free API returns empty results and built a working SearXNG
integration. Now I'm using that same code as the subject of a code review
battle between Claude and DeepSeek.

The twist: DeepSeek gets to use web search. Claude doesn't.

---

## The Setup

I fed both models this prompt:
```
Analyze this Python code and suggest improvements across:
- Architecture
- Error handling
- Performance
- Production readiness
- Missing design patterns
```

The code: `websearch_searxng.py` from Part 1 — a 178-line Python streaming
web search implementation.

Three conditions:
1. **Claude** — no web search, analyzing cold
2. **DeepSeek-r1** — no web search
3. **DeepSeek-r1 + SearXNG** — web search enabled via manual injection

---

## Condition 1: Claude (No Web Search)

Claude found two actual bugs nobody asked about:

**Bug 1 — Tool call arguments may be a string, not a dict:**
```python
# This crashes on some Ollama model versions
args = tool_call["function"]["arguments"]
query = args.get("query", "")  # fails if args is a JSON string

# Fix:
args = tool_call["function"]["arguments"]
if isinstance(args, str):
    args = json.loads(args)
query = args.get("query", "")
```

**Bug 2 — result_count counts wrong:**
```python
# Counts ALL [ brackets including those in URLs
result_count = search_result.count("[")

# Fix:
result_count = len([r for r in search_result.split("\n") if r.startswith("[")])
```

Claude also correctly identified that `timeout=30` is wrong for streaming:
```python
# Wrong — streaming has no fixed duration
timeout=30

# Right — let streaming handle its own flow
timeout=None
```

Grade: **Found real bugs. Gave working fixes. Understood the streaming architecture.**

---

## Condition 2: DeepSeek-r1 (No Web Search)

First — an important discovery. DeepSeek-r1 does not support tool calling:
```bash
curl -s http://localhost:11434/api/chat \
  -d '{"model": "deepseek-r1:14b", "tools": [...]}' | jq .error
```
```json
"registry.ollama.ai/library/deepseek-r1:14b does not support tools"
```

This means DeepSeek-r1 **cannot use our web search implementation at all**
without a workaround. More on that in Condition 3.

Without web search, DeepSeek gave generic advice:
- "Add type hints"
- "Use python-dotenv"
- "Add unit tests"
- "PEP8 compliance"

Nothing specific to this code. No bugs found. No streaming-specific advice.

Grade: **Generic. Could apply to any Python script.**

---

## Condition 3: DeepSeek-r1 + SearXNG

Since DeepSeek-r1 doesn't support tool calling, web search requires a workaround
— search first, inject results into the system prompt:
```python
# Search SearXNG manually
search_results = web_search(user_message)

# Inject into system prompt
system_prompt = f"""You have access to these search results:
{search_results}
Answer based on these results."""

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_message}
]
```

With web search enabled, DeepSeek improved significantly:

- ✅ Proper code examples (not just bullet points)
- ✅ Strategy pattern with actual implementation
- ✅ Factory pattern (Claude missed this)
- ✅ Observer pattern (Claude missed this)
- ✅ Async example with `aiohttp`
- ✅ Custom exception classes

But still missed:
- ❌ The `args` string parsing bug
- ❌ The wrong `result_count`
- ❌ The `timeout=None` for streaming

And introduced a typo in its own code:
```python
# DeepSeek wrote OLLMAR instead of OLLAMA
OLLAMA_API = environ.get("OLLMAR_API", "http://localhost:11434/api/chat")
```

Grade: **Much better with web search. Still missed actual bugs.**

---

## The Verdict

| | Claude | DeepSeek | DeepSeek + Search |
|---|---|---|---|
| Found real bugs | ✅ 2 bugs | ❌ None | ❌ None |
| Working code fixes | ✅ Yes | ❌ No | ✅ Yes |
| Streaming-specific advice | ✅ Yes | ❌ No | ❌ No |
| Strategy pattern | ✅ Yes | ✅ Yes | ✅ Yes |
| Factory pattern | ❌ No | ❌ No | ✅ Yes |
| Generic advice | ⚠️ Some | ✅ Mostly | ⚠️ Some |
| Introduced bugs | ❌ No | ❌ No | ⚠️ Typo |
| Tool calling support | ✅ Yes | ❌ No | ❌ No |

---

## What Web Search Actually Changes

The improvement from Condition 2 to Condition 3 is dramatic:

**Without search:** Bullet points. No code. Generic advice.

**With search:** Structured response. Code examples. Additional patterns.

Web search doesn't make DeepSeek find bugs it missed — but it makes the
response dramatically more useful and actionable.

**The honest conclusion:**

> Web search closes the gap between models significantly for knowledge-based
> tasks. It does not close the gap for deep code comprehension tasks that
> require careful reading of the actual implementation.
>
> Claude found bugs because it read the code carefully.
> DeepSeek gave better advice because it searched for best practices.
> The ideal workflow uses both.

---

## The Tool Calling Gap

One finding deserves special attention:

**deepseek-r1:14b does not support tool calling.**

This means it cannot use our web search implementation natively. The manual
injection workaround works, but it's a fundamental architectural limitation:
```bash
# This fails with deepseek-r1
ollama run deepseek-r1:14b --tools web_search "latest ollama version"
# Error: deepseek-r1:14b does not support tools
```

For production web search pipelines, model selection matters:

| Model | Tool Calling | Web Search Ready |
|---|---|---|
| llama3.1:8B | ✅ | ✅ |
| qwen3:8B | ✅ | ✅ (GPU recommended) |
| mistral-nemo:12b | ⚠️ | ⚠️ |
| deepseek-r1:14b | ❌ | ❌ Native / ✅ Workaround |

---

## The COBOL Moment

One more finding that didn't make the main comparison.

Before running the structured test, I fed the Python code to DeepSeek via
the Ollama CLI — which had a lingering session history from an earlier test.

DeepSeek's response was a detailed COBOL improvement plan. Complete with:
- "Follow naming conventions for copybooks (e.g., -REC, -DAL)"
- "Ensure Compliance with COBOL 2002"
- "Use GnuCOBOL with the -std=cobol2002 flag"

This wasn't DeepSeek being stupid. It was DeepSeek being misled by session
context — and not noticing the contradiction. A subtle but important failure
mode for production use.

**Always start with a clean session for code review tasks.**

---

## The Full Code

Both approaches — tool calling (llama3.1) and manual injection (deepseek-r1) —
are on GitHub:

**[github.com/Webhuis/ollama-websearch](https://github.com/Webhuis/ollama-websearch)**

- `websearch_searxng.py` — llama3.1 with tool calling
- `websearch_searxng_deepseek.py` — deepseek-r1 with manual injection
- Full SearXNG Docker setup
- Python, Node.js, and shell examples

---

## What's Next

Part 3: Wiring Google and Bing APIs and comparing result quality across
all three search backends on the same queries.

---

*Tested on a real Debian 13 server. Ollama 0.18.2. No VMs, no assumptions.*
*If something doesn't work, open an issue.*
