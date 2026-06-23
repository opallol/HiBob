# References

Baseline date: 2026-06-23

This blueprint intentionally uses official documentation as primary references where possible.

## Agent and model layer

- OpenAI Agents SDK / Responses / tools documentation: https://developers.openai.com/api/docs/guides/agents
- Model Context Protocol introduction: https://modelcontextprotocol.io/docs/getting-started/intro
- Hermes Agent (Nous Research, MIT license): https://github.com/NousResearch/hermes-agent - reference implementation only, not a runtime dependency; see `07_LOCAL_FIRST_STACK.md` §5.13

## Local and UI layer

- Ollama GitHub repository and documentation: https://github.com/ollama/ollama
- Open WebUI documentation: https://docs.openwebui.com/
- AnythingLLM documentation: https://docs.anythingllm.com/

## Retrieval and ingestion

- Qdrant documentation: https://qdrant.tech/documentation/
- Unstructured documentation: https://docs.unstructured.io/
- Crawl4AI documentation: https://docs.crawl4ai.com/

## Browser and automation

- Playwright MCP repository: https://github.com/microsoft/playwright-mcp
- Activepieces documentation: https://www.activepieces.com/docs

## Observability and evals

- Arize Phoenix documentation: https://arize.com/docs/phoenix
- DeepEval documentation: https://deepeval.com/docs/getting-started

## Developer workflow

- Cline documentation: https://docs.cline.bot/
- Aider documentation: https://aider.chat/docs/
- Docker Desktop WSL2 backend documentation: https://docs.docker.com/desktop/features/wsl/

## Notes

Technologies in this document should be periodically reviewed. Hibob's architecture is designed so these tools can be replaced if better models, protocols, vector stores, or agent runtimes emerge.
