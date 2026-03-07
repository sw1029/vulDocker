SSRF guidance:

- Expose an endpoint that accepts a user-supplied URL from the request.
- Make a server-side HTTP request with that exact value using `requests` or `urllib`.
- Omit allowlisting and internal-address protections on the vulnerable path.
- Keep the vulnerable fetch path easy to spot in code: `requests.get(user_url)` is preferred over indirect helpers.
- Ensure the PoC verifies a benign baseline fetch and then an internal/metadata-style target or loopback-only SSRF variant.
- Prefer a same-container loopback lab: expose `/metadata` that returns `FLAG{SSRF_OK}` and let `/fetch?url=` request `http://127.0.0.1:5000/metadata`.
- Keep the indicator literal in code and/or response body: include `metadata` text or `169.254.169.254` commentary so SSRF semantic checks can anchor on it.
- Do not use `before_first_request`; initialize any runtime state explicitly before `app.run()` or behind a one-time request guard compatible with Flask 3.
