#!/usr/bin/env node
/**
 * Ollama Web Search - Example 3: Google Custom Search + Bing Search APIs
 * Streaming version - real-time output, no timeouts
 * Model: llama3.1
 * Author: Martin Simons
 *
 * Setup:
 *   Google: export GOOGLE_API_KEY=your-key GOOGLE_CSE_ID=your-cse-id
 *   Bing:   export BING_API_KEY=your-key SEARCH_BACKEND=bing
 */

const OLLAMA_API = "http://localhost:11434/api/chat";
const MODEL = "llama3.1:latest";

const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY || "your-google-api-key";
const GOOGLE_CSE_ID = process.env.GOOGLE_CSE_ID || "your-custom-search-engine-id";
const BING_API_KEY = process.env.BING_API_KEY || "your-bing-api-key";
const SEARCH_BACKEND = process.env.SEARCH_BACKEND || "google";

async function webSearchGoogle(query, numResults = 5) {
  const params = new URLSearchParams({
    key: GOOGLE_API_KEY,
    cx: GOOGLE_CSE_ID,
    q: query,
    num: numResults
  });

  const response = await fetch(`https://www.googleapis.com/customsearch/v1?${params}`);
  if (!response.ok) throw new Error(`Google API error: ${response.status}`);

  const data = await response.json();
  const items = data.items || [];
  if (items.length === 0) return "No results found.";

  return items.map((item, i) =>
    `[${i+1}] ${item.title || "No title"}\n` +
    `    URL: ${item.link || ""}\n` +
    `    ${item.snippet || "No snippet"}`
  ).join("\n\n");
}

async function webSearchBing(query, numResults = 5) {
  const params = new URLSearchParams({ q: query, count: numResults, mkt: "en-US" });

  const response = await fetch(`https://api.bing.microsoft.com/v7.0/search?${params}`, {
    headers: { "Ocp-Apim-Subscription-Key": BING_API_KEY }
  });
  if (!response.ok) throw new Error(`Bing API error: ${response.status}`);

  const data = await response.json();
  const items = data.webPages?.value || [];
  if (items.length === 0) return "No results found.";

  return items.map((item, i) =>
    `[${i+1}] ${item.name || "No title"}\n` +
    `    URL: ${item.url || ""}\n` +
    `    ${item.snippet || "No snippet"}`
  ).join("\n\n");
}

async function webSearch(query, numResults = 5) {
  if (SEARCH_BACKEND === "bing") {
    console.log(`\n🔍 Searching Bing for: ${query}`);
    return webSearchBing(query, numResults);
  } else {
    console.log(`\n🔍 Searching Google for: ${query}`);
    return webSearchGoogle(query, numResults);
  }
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
        if (message.tool_calls) toolCalls.push(...message.tool_calls);
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
      description: "Search the web for current, real-time information",
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

  console.log(`\n❓ Question: ${userMessage}`);
  console.log(`🔧 Backend: ${SEARCH_BACKEND.toUpperCase()}\n`);
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

// Validate API keys
if (SEARCH_BACKEND === "google" && GOOGLE_API_KEY === "your-google-api-key") {
  console.error("❌ Set GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables");
  console.error("   export GOOGLE_API_KEY=your-key");
  console.error("   export GOOGLE_CSE_ID=your-cse-id");
  process.exit(1);
}
if (SEARCH_BACKEND === "bing" && BING_API_KEY === "your-bing-api-key") {
  console.error("❌ Set BING_API_KEY environment variable");
  console.error("   export BING_API_KEY=your-key");
  process.exit(1);
}

const question = process.argv[2] || "What is the latest version of Ollama?";
chatWithSearch(question).catch(console.error);
