# Natural-language proposal extraction

Proxy can use an OpenAI Chat Completions API to turn a natural-language payment description into a **draft proposal**. Configure `OPENAI_API_KEY` and optionally `OPENAI_MODEL` (default `gpt-4o-mini`).

## Endpoint

`POST /v1/agent/propose` requires the same signed bearer JWT as other API routes. Body:

```json
{ "text": "Prepare $85 USD for Jordan Lee at jordan@example.com for logo revisions after I receive the final source files." }
```

The endpoint returns extracted fields, the original text, an explanation, missing fields, and risk flags. It does **not** create a payment intent, approve a payment, call PayPal, or treat the condition as verified evidence. The user must review the proposal and submit it through the normal payment-intent flow. Backend limits and explicit approval still apply.

## Security constraints

- Source text is untrusted; instructions embedded in it must not override extraction.
- Provider output is parsed and validated locally; malformed amounts are not accepted.
- Missing values remain missing; the model must not invent recipient details or evidence.
- No payment side effect occurs in the proposal endpoint.
- The AI provider key is held only by the backend and must never be exposed to the browser or committed.
- Do not place card data, passwords, access tokens, or other secrets in proposal text.

This is a proposal-extraction adapter, not a financial adviser, fraud detector, or evidence-verification system. Risk flags are advisory and may be incomplete.
