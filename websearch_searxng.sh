#!/bin/bash
# =============================================================================
# Ollama Web Search - Shell/curl version: SearXNG (self-hosted, private)
# Author: Martin Simons
#
# Usage:
#   ./websearch_searxng.sh "What is the latest version of Ollama?"
#   SEARXNG_URL=http://myserver:8080 ./websearch_searxng.sh "your question"
# =============================================================================

OLLAMA_API="${OLLAMA_API:-http://localhost:11434/api/chat}"
SEARXNG_URL="${SEARXNG_URL:-http://localhost:8080/search}"
MODEL="${MODEL:-llama3.1:latest}"
NUM_RESULTS="${NUM_RESULTS:-5}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Functions ---

check_dependencies() {
    for cmd in curl jq; do
        if ! command -v "$cmd" &>/dev/null; then
            echo -e "${RED}❌ Required command not found: $cmd${NC}"
            echo "   Install with: sudo apt install $cmd"
            exit 1
        fi
    done
}

check_ollama() {
    if ! curl -sf "$OLLAMA_API/../tags" &>/dev/null; then
        echo -e "${RED}❌ Ollama not reachable at $OLLAMA_API${NC}"
        exit 1
    fi
}

check_searxng() {
    if ! curl -sf "${SEARXNG_URL}?q=test&format=json" &>/dev/null; then
        echo -e "${RED}❌ SearXNG not reachable at $SEARXNG_URL${NC}"
        echo "   Start with: docker run -d --name searxng -p 8080:8080 searxng/searxng:latest"
        exit 1
    fi
}

web_search() {
    local query="$1"
    local encoded_query
    encoded_query=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$query'))")

    local result
    result=$(curl -sf "${SEARXNG_URL}?q=${encoded_query}&format=json&language=en&safesearch=0")

    if [ -z "$result" ]; then
        echo "No results found."
        return
    fi

    # Format top N results
    echo "$result" | jq -r --argjson n "$NUM_RESULTS" '
        .results[:$n] | to_entries[] |
        "[\(.key+1)] \(.value.title // "No title")\n" +
        "    URL: \(.value.url // "")\n" +
        "    Sources: \((.value.engines // []) | join(", "))\n" +
        "    \(.value.content // "No snippet")"
    '
}

ollama_chat() {
    local messages="$1"
    local tools="$2"
    local payload

    if [ -n "$tools" ]; then
        payload=$(jq -n \
            --arg model "$MODEL" \
            --argjson messages "$messages" \
            --argjson tools "$tools" \
            '{model: $model, messages: $messages, tools: $tools, stream: false}')
    else
        payload=$(jq -n \
            --arg model "$MODEL" \
            --argjson messages "$messages" \
            '{model: $model, messages: $messages, stream: false}')
    fi

    curl -sf "$OLLAMA_API" \
        -H "Content-Type: application/json" \
        -d "$payload"
}

stream_final_answer() {
    local messages="$1"

    curl -sf "$OLLAMA_API" \
        -H "Content-Type: application/json" \
        -d "$(jq -n \
            --arg model "$MODEL" \
            --argjson messages "$messages" \
            '{model: $model, messages: $messages, stream: true}')" \
    | while IFS= read -r line; do
        content=$(echo "$line" | jq -r '.message.content // empty' 2>/dev/null)
        if [ -n "$content" ]; then
            printf "%s" "$content"
        fi
    done
    echo
}

# --- Main ---

main() {
    local question="${1:-What is the latest version of Ollama?}"

    check_dependencies
    check_ollama
    check_searxng

    echo -e "\n${YELLOW}❓ Question: ${question}${NC}\n"
    echo -e "${BLUE}🤔 Asking model to search...${NC}"

    # Define tool
    local tools
    tools=$(jq -n '[{
        type: "function",
        function: {
            name: "web_search",
            description: "Search the web for current, real-time information",
            parameters: {
                type: "object",
                properties: {
                    query: {
                        type: "string",
                        description: "The search query"
                    }
                },
                required: ["query"]
            }
        }
    }]')

    # Initial messages
    local messages
    messages=$(jq -n --arg q "$question" '[{role: "user", content: $q}]')

    # First call — get tool call from model
    local response
    response=$(ollama_chat "$messages" "$tools")

    if [ -z "$response" ]; then
        echo -e "${RED}❌ No response from Ollama${NC}"
        exit 1
    fi

    # Check for tool calls
    local tool_name
    tool_name=$(echo "$response" | jq -r '.message.tool_calls[0].function.name // empty')

    if [ -z "$tool_name" ]; then
        echo -e "${YELLOW}⚠️  Model answered without searching:${NC}"
        echo "$response" | jq -r '.message.content'
        exit 0
    fi

    # Extract query from tool call
    local search_query
    search_query=$(echo "$response" | jq -r '.message.tool_calls[0].function.arguments.query')
    echo -e "${BLUE}🔍 Searching SearXNG for: ${search_query}${NC}"

    # Execute search
    local search_results
    search_results=$(web_search "$search_query")
    local result_count
    result_count=$(echo "$search_results" | grep -c "^\[" || echo "0")
    echo -e "${GREEN}📄 Found ${result_count} results${NC}\n"

    # Build updated messages with tool result
    local assistant_message
    assistant_message=$(echo "$response" | jq '.message')

    messages=$(echo "$messages" | jq \
        --argjson asst "$assistant_message" \
        --arg results "$search_results" \
        '. + [$asst, {role: "tool", content: $results}]')

    # Final streaming answer
    echo -e "${GREEN}💬 Answer:${NC}\n"
    stream_final_answer "$messages"
    echo
}

main "$@"
