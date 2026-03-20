#!/bin/bash
# =============================================================================
# Ollama Web Search - Shell/curl version: Google Custom Search + Bing
# Author: Martin Simons
#
# Usage:
#   export GOOGLE_API_KEY=your-key
#   export GOOGLE_CSE_ID=your-cse-id
#   ./websearch_google_bing.sh "What is the latest version of Ollama?"
#
#   # Or with Bing:
#   export BING_API_KEY=your-key
#   export SEARCH_BACKEND=bing
#   ./websearch_google_bing.sh "What is the latest version of Ollama?"
# =============================================================================

OLLAMA_API="${OLLAMA_API:-http://localhost:11434/api/chat}"
MODEL="${MODEL:-llama3.1:latest}"
NUM_RESULTS="${NUM_RESULTS:-5}"
SEARCH_BACKEND="${SEARCH_BACKEND:-google}"

GOOGLE_API_KEY="${GOOGLE_API_KEY:-your-google-api-key}"
GOOGLE_CSE_ID="${GOOGLE_CSE_ID:-your-custom-search-engine-id}"
BING_API_KEY="${BING_API_KEY:-your-bing-api-key}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

check_dependencies() {
    for cmd in curl jq python3; do
        if ! command -v "$cmd" &>/dev/null; then
            echo -e "${RED}❌ Required: $cmd${NC}"
            exit 1
        fi
    done
}

validate_keys() {
    if [ "$SEARCH_BACKEND" = "google" ]; then
        if [ "$GOOGLE_API_KEY" = "your-google-api-key" ]; then
            echo -e "${RED}❌ Set GOOGLE_API_KEY and GOOGLE_CSE_ID${NC}"
            echo "   export GOOGLE_API_KEY=your-key"
            echo "   export GOOGLE_CSE_ID=your-cse-id"
            exit 1
        fi
    elif [ "$SEARCH_BACKEND" = "bing" ]; then
        if [ "$BING_API_KEY" = "your-bing-api-key" ]; then
            echo -e "${RED}❌ Set BING_API_KEY${NC}"
            echo "   export BING_API_KEY=your-key"
            exit 1
        fi
    fi
}

web_search_google() {
    local query="$1"
    local encoded
    encoded=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$query'))")

    curl -sf "https://www.googleapis.com/customsearch/v1?key=${GOOGLE_API_KEY}&cx=${GOOGLE_CSE_ID}&q=${encoded}&num=${NUM_RESULTS}" \
    | jq -r '.items[:5] | to_entries[] |
        "[\(.key+1)] \(.value.title // "No title")\n" +
        "    URL: \(.value.link // "")\n" +
        "    \(.value.snippet // "No snippet")"'
}

web_search_bing() {
    local query="$1"
    local encoded
    encoded=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$query'))")

    curl -sf "https://api.bing.microsoft.com/v7.0/search?q=${encoded}&count=${NUM_RESULTS}&mkt=en-US" \
        -H "Ocp-Apim-Subscription-Key: ${BING_API_KEY}" \
    | jq -r '.webPages.value[:5] | to_entries[] |
        "[\(.key+1)] \(.value.name // "No title")\n" +
        "    URL: \(.value.url // "")\n" +
        "    \(.value.snippet // "No snippet")"'
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
        [ -n "$content" ] && printf "%s" "$content"
    done
    echo
}

ollama_chat() {
    local messages="$1"
    local tools="$2"
    curl -sf "$OLLAMA_API" \
        -H "Content-Type: application/json" \
        -d "$(jq -n \
            --arg model "$MODEL" \
            --argjson messages "$messages" \
            --argjson tools "$tools" \
            '{model: $model, messages: $messages, tools: $tools, stream: false}')"
}

main() {
    local question="${1:-What is the latest version of Ollama?}"

    check_dependencies
    validate_keys

    echo -e "\n${YELLOW}❓ Question: ${question}${NC}"
    echo -e "${BLUE}🔧 Backend: ${SEARCH_BACKEND^^}${NC}\n"
    echo -e "${BLUE}🤔 Asking model to search...${NC}"

    local tools
    tools=$(jq -n '[{
        type: "function",
        function: {
            name: "web_search",
            description: "Search the web for current information",
            parameters: {
                type: "object",
                properties: {
                    query: {type: "string", description: "The search query"}
                },
                required: ["query"]
            }
        }
    }]')

    local messages
    messages=$(jq -n --arg q "$question" '[{role: "user", content: $q}]')

    local response
    response=$(ollama_chat "$messages" "$tools")

    local search_query
    search_query=$(echo "$response" | jq -r '.message.tool_calls[0].function.arguments.query // empty')

    if [ -z "$search_query" ]; then
        echo -e "${YELLOW}⚠️  Model answered without searching:${NC}"
        echo "$response" | jq -r '.message.content'
        exit 0
    fi

    echo -e "${BLUE}🔍 Searching ${SEARCH_BACKEND^^} for: ${search_query}${NC}"

    local search_results
    if [ "$SEARCH_BACKEND" = "bing" ]; then
        search_results=$(web_search_bing "$search_query")
    else
        search_results=$(web_search_google "$search_query")
    fi

    local result_count
    result_count=$(echo "$search_results" | grep -c "^\[" || echo "0")
    echo -e "${GREEN}📄 Found ${result_count} results${NC}\n"

    local assistant_message
    assistant_message=$(echo "$response" | jq '.message')

    messages=$(echo "$messages" | jq \
        --argjson asst "$assistant_message" \
        --arg results "$search_results" \
        '. + [$asst, {role: "tool", content: $results}]')

    echo -e "${GREEN}💬 Answer:${NC}\n"
    stream_final_answer "$messages"
    echo
}

main "$@"
