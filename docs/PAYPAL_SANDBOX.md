# PayPal Sandbox Integration

Proxy uses the PayPal Payouts API for the demo scenario where a user sends funds to a recipient's PayPal email. Payouts is distinct from buyer checkout through the Orders API and requires the PayPal account/app to be eligible for Payouts.

Official references:
- [PayPal Payouts overview](https://developer.paypal.com/payouts/overview/)
- [Create payout request](https://developer.paypal.com/api/payments.payouts-batch/v1/definitions/create_payout_request/)
- [Show payout batch details](https://developer.paypal.com/api/payments.payouts-batch/v1/payouts-get/)
- [REST API requests and idempotency](https://developer.paypal.com/api/make-api-requests/)

## Configuration

Copy `.env.example` to `.env` and set sandbox-only values:

```dotenv
PAYPAL_MODE=sandbox
PAYPAL_CLIENT_ID=your_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_sandbox_client_secret
```

Never commit `.env`. Use credentials from the PayPal Developer Dashboard and confirm Payouts is enabled for the sandbox app/account.

## Current flow

1. Backend reserves the payment intent in `processing` after a human has approved the exact fingerprint.
2. Adapter obtains an OAuth 2.0 client-credentials access token from the Sandbox host.
3. It submits one payout item with a stable idempotency key and sender batch ID.
4. It fetches payout batch details and checks the specific item status.
5. Only an item-level `SUCCESS` with a PayPal transaction ID is recorded as `succeeded`.

An acknowledged/pending batch is not proof of settlement. If a network/provider error or non-terminal status occurs, the intent remains `processing` and requires reconciliation. Do not blindly retry with a new key. The stable sender batch ID is part of duplicate-payout protection.

## Important limitations

- This adapter has not yet been validated against live PayPal Sandbox credentials in this repository.
- PayPal may return a pending batch before the item settles. A future reconciliation worker/webhook path must check the batch and item statuses and update the local state.
- The adapter performs a bounded number of status checks (three by default, one second apart). If the item is still pending, it fails closed and leaves the intent in an ambiguous processing state. This is not a substitute for durable background reconciliation.
- Durable background reconciliation, webhook signature verification, provider error taxonomy, rate limits, and integration testing against a configured Sandbox account remain follow-up tasks.
- This is not production-ready financial infrastructure.
