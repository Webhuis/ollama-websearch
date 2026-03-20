#!/usr/bin/env node
/**
 * Ollama Web Search - Example 2: SearXNG (self-hosted, private)
 * Streaming version - real-time output, no timeouts
 * Model: llama3.1
 * Author: Martin Simons
 */

const OLLAMA_API = "http://localhost:11434/api/chat";
const SEARXNG_URL = "http://localhost:8080/search";
const MODEL = "llama3.1:latest";

async function webSearch(query, numResults = 5) {
  const params = new URLSearchParams({
    q: query,
    format: "json",
    language: "en",
    safesearch: "0"
  });

  const response = await fetch(`${SEARXNG_URL}?${params}`);
  if (!response.ok) throw new Error(`SearXNG error: ${response.status}`);

  const data = await response.json();
  const results = data.results || [];

  if (results.length === 0) return "No results found.";

  return results.slice(0, numResults).map((r, i) =>
    `[${i+1}] ${r.title || "No title"}\n` +
    `    URL: ${r.url || ""}\n` +
    `    Source: ${(r.engines || []).join(", ")}\n` +
    `    ${r.content || "No snippet"}`
  ).join("\n\n");
}

async function streamResponse(messages, tools = null) {
  const payload = { model: MODEL, messages, stream: true };
  if (tools) payload.tools = tools;

  const response = await fetch(OLLAMA_API, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) throw new Error(`Ollama error: ${response.status}`);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let fullContent = "";
  let toolCalls = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const lines = decoder.decode(value).split("\n").filter(Boolean);
    for (const line of lines) {
      try {
        const chunk = JSON.parse(line);
        const message = chunk.message || {};

        if (message.tool_calls) {
          toolCalls.push(...message.tool_calls);
        }

        if (message.content) {
          process.stdout.write(message.content);
          fullContent += message.content;
        }

        if (chunk.done) break;
      } catch {}
    }
  }

  return { fullContent, toolCalls };
}

async function chatWithSearch(userMessage) {
  const tools = [{
    type: "function",
    function: {
      name: "web_search",
      description: "Search the web for current, real-time information using a private self-hosted search engine",
      parameters: {
        type: "object",
        properties: {
          query: { type: "string", description: "The search query" }
        },
        required: ["query"]
      }
    }
  }];

  const messages = [{ role: "user", content: userMessage }];

  console.log(`\n❓ Question: ${userMessage}\n`);
  process.stdout.write("🤔 Thinking...");

  const { toolCalls } = await streamResponse(messages, tools);

  if (toolCalls.length === 0) {
    console.log("\n⚠️  Model answered without searching.");
    return;
  }

  messages.push({ role: "assistant", content: "", tool_calls: toolCalls });

  for (const toolCall of toolCalls) {
    if (toolCall.function.name === "web_search") {
      const query = toolCall.function.arguments.query || "";
      console.log(`\n\n🔍 Searching SearXNG for: ${query}`);

      const searchResult = await webSearch(query);
      const resultCount = (searchResult.match(/\[/g) || []).length;
      console.log(`📄 Found ${resultCount} results\n`);

      messages.push({ role: "tool", content: searchResult });
    }
  }

  console.log("💬 Answer:\n");
  await streamResponse(messages);
  console.log("\n");
}

// Main
const question = process.argv[2] || "What is the latest version of Ollama?";
chatWithSearch(question).catch(console.error);
