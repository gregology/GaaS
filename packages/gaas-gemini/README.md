# gaas-gemini

Web research using Google's Gemini API with Google Search grounding. Unlike email or GitHub, this isn't an event-driven poller. It's a callable service that other integrations trigger from automation `then` clauses.

## Prerequisites

- A Google AI API key ([aistudio.google.com](https://aistudio.google.com/))

## Installation

Gemini is an optional dependency:

```bash
uv sync --extra gemini
```

## Config

```yaml
integrations:
  - type: gemini
    name: default
    api_key: !secret gemini_api_key
    # model: gemini-2.0-flash       # Optional, uses SDK default if omitted
```

`api_key` is required. `model` is optional.

## Calling from automations

You can trigger the service from any integration's automation rules:

```yaml
# In an email integration's automations:
automations:
  - when:
      classification.user_agreement_update: true
    then:
      - archive
      - service:
          call: gemini.default.web_research
          inputs:
            prompt: "research $domain terms of service changes"
```

The `call` format is `{type}.{name}.{service_name}`. If you named your Gemini integration `research` instead of `default`, the call would be `gemini.research.web_research`.

`$field` references in `inputs` get resolved against the automation context at runtime, same as script inputs.

### Input schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | Yes | The research query |
| `output_schema` | object | No | JSON schema for structured output (triggers a second pass to reformat results) |

Without `output_schema` you get free-text research results plus source URLs. With it, the service makes a second Gemini call to restructure the research into your schema.

## Safety

The `web_research` service is declared `reversible: true` in its manifest because it only reads. No side effects. That means it can be triggered from LLM-provenance automations without `!yolo`.

A future service with write side effects would need `reversible: false` (the default) and would require `!yolo` when triggered from non-deterministic conditions.
