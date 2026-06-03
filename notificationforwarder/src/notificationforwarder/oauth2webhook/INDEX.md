# oauth2webhook Forwarder

## Purpose

This module extends the `webhook` forwarder with **OAuth2 Client Credentials Grant** support (RFC 6749 §4.4). It is for APIs that refuse a static username/password or static Bearer token and instead require a short-lived access token that must be dynamically obtained from a separate token endpoint before each (logical) session.

The concrete trigger was the **ServiceNow Event Management API**, whose endpoint requires a Bearer token obtained from ServiceNow's own OAuth2 token service:

- Token endpoint: `https://<instance>.service-now.com/oauth/accesstoken/v2`
- API endpoint:   `https://<instance>.service-now.com/itsm/eventapi/v1/api/global/em/jsonv2`

The same pattern appears in many other enterprise SaaS platforms (Dynatrace, Salesforce, Azure APIs, PagerDuty, etc.), so the module was written generically rather than ServiceNow-specific.

---

## Design Decisions

### Why a new module rather than extending `webhook`?

Three options were considered:

1. **Extend `WebhookForwarder` in-place** — rejected because token lifecycle state and logic would tangle with the existing HTTP logic, making both harder to test and reason about.
2. **`oauth2webhook` subclass** (chosen) — keeps `WebhookForwarder` unchanged; adds only the OAuth2 concern as a thin layer on top.
3. **`webhookservicenow` dedicated module** — rejected because duplicating all HTTP request logic for one API is wasteful, and ServiceNow's token endpoint is standard OAuth2.

### Why file-based token caching instead of in-memory?

The notificationforwarder is **not a daemon**. It is spawned once per monitoring notification event (like a Nagios notification command) and exits immediately. Instance-level variables vanish with the process. A fresh token request on every notification call would:
- Hit rate limits on high-alert volumes (potentially thousands of calls per hour)
- Add latency to every notification
- Be unnecessary because tokens typically live 30–60 minutes

The solution is a JSON file in `$OMD_ROOT/var/tmp/` (same directory as the SQLite spool database), which persists across process invocations and is read/written atomically under a file lock.

### Why `fcntl.LOCK_EX` on token refresh?

Multiple monitoring notifications can fire simultaneously for the same forwarder (e.g. a mass outage). Without coordination, every concurrent process would see an expired or missing token and each would request a new one, wasting N token requests. With an exclusive lock:
- The first process acquires the lock, fetches the token, writes the cache file, releases the lock.
- All other processes then acquire the lock, find the cache valid, and return immediately without contacting the token endpoint.

The lock file is a sibling of the cache file (`.lock` suffix) and is never deleted — it is just a lock target. `LOCK_EX` is blocking; processes queue up and wait rather than failing.

### Why call `NotificationForwarder.__init__` directly instead of `super().__init__`?

`WebhookForwarder.__init__` contains:
```python
super(self.__class__, self).__init__(opts)
```

This is the Python 2 pattern for calling the parent. It is **broken for subclassing in Python 3** because `self.__class__` is the concrete class (`Oauth2WebhookForwarder`), not `WebhookForwarder`. When `Oauth2WebhookForwarder.__init__` calls `super().__init__()` → `WebhookForwarder.__init__()`, which then calls `super(Oauth2WebhookForwarder, self).__init__()` → `WebhookForwarder.__init__()` again → infinite recursion.

The fix: bypass `WebhookForwarder.__init__` entirely and call `NotificationForwarder.__init__(self, opts)` directly, then replicate the five attribute defaults from `WebhookForwarder` manually. This is safe because those defaults are a trivial, stable set. If `WebhookForwarder` ever adds new attributes with defaults, they need to be mirrored here too.

If `WebhookForwarder` is ever refactored to use `super(WebhookForwarder, self).__init__(opts)` or plain `super().__init__(opts)`, the `NotificationForwarder.__init__` direct call here can be replaced with `super().__init__(opts)`.

### Why sync `_webhook_module.logger` in `submit_one`?

Python resolves global names (like `logger`) in the module where the function is **defined**, not where it is called. `WebhookForwarder.submit_one` is defined in `notificationforwarder.webhook.forwarder`. When invoked via inheritance, Python looks for `logger` in `webhook.forwarder`'s module namespace.

The factory function (`baseclass.new`) only sets `logger` on the module it loaded — `oauth2webhook.forwarder` — not on `webhook.forwarder`. So before delegating to `super().submit_one()`, we explicitly copy our logger reference into the webhook module's namespace:
```python
_webhook_module.logger = logger
```

This must happen on every `submit_one` call because each forwarder invocation is a separate process and the module attribute starts as `None`.

### Class name: `Oauth2WebhookForwarder`

The factory derives the class name from the module name via `.title()` on each `_`-split word:
```python
"".join([x.title() for x in "oauth2webhook".split("_")]) + "Forwarder"
```
`"oauth2webhook".title()` = `"Oauth2Webhook"` — Python's `title()` capitalizes the character after any non-letter, including digits. So `2` causes the following `w` to capitalize. The class must therefore be `Oauth2WebhookForwarder`, not `Oauth2webhookForwarder`.

---

## Configuration Options

All options from `webhook` forwarder are inherited (`url`, `username`, `password`, `insecure`, `headers`, `mode`). Additional options:

| Option | Required | Default | Description |
|---|---|---|---|
| `token_url` | yes | — | Full URL of the OAuth2 token endpoint |
| `client_id` | yes | — | OAuth2 client ID |
| `client_secret` | yes | — | OAuth2 client secret |
| `token_scope` | no | `None` | OAuth2 scope string; omitted from request if not set |
| `token_grant_type` | no | `client_credentials` | OAuth2 grant type; change only if the token server requires a non-standard value |
| `token_expiry_buffer` | no | `30` | Seconds before actual token expiry at which to treat the cached token as expired and refresh it proactively |

`username` and `password` are inherited from `WebhookForwarder` but are unused for the API call itself — the Authorization header is set to `Bearer <token>`. They could theoretically be used if the token endpoint itself required Basic Auth on top of `client_id`/`client_secret`, but that is not currently implemented.

---

## Token Cache

**File:** `$OMD_ROOT/var/tmp/notificationforwarder_<forwarder_name>_oauth2token.json`

`forwarder_name` = `oauth2webhook` (no tag) or `oauth2webhook_<tag>` (with `--forwardertag`). Each distinct tag gets its own cache file, which is correct because different tags typically point at different API instances with different credentials.

**Format:**
```json
{"access_token": "<token string>", "expires_at": 1746123456.0}
```

`expires_at` is a Unix timestamp (float, from `time.time()`). A token is considered valid if:
```
time.time() < expires_at - token_expiry_buffer
```

**Lock file:** same path with `.lock` appended. Never deleted; re-used across invocations as a stable lock target.

---

## Call Flow

```
forward(raw_event)                          [baseclass]
  └── format_event()                        [baseclass → formatter]
  └── forward_formatted(formatted_event)    [baseclass]
        └── submit(formatted_event)         [WebhookForwarder, inherited]
              └── submit_one(event)         [Oauth2WebhookForwarder — overrides here]
                    1. _webhook_module.logger = logger   (logger sync)
                    2. acquire_token()
                         a. acquire fcntl.LOCK_EX on lock file
                         b. if cache valid → return cached token
                         c. POST to token_url with client_id/client_secret
                         d. write new token + expires_at to cache file
                         e. release lock
                    3. inject "Authorization: Bearer <token>" into event.forwarderopts["headers"]
                    4. super().submit_one(event)          [WebhookForwarder]
                         POST to self.url with full headers + payload
```

On failure at step 2 (exception from `acquire_token`), `submit_one` returns `False`. The baseclass then spools the raw event to SQLite for retry on the next invocation.

---

## Usage Example

```bash
notificationforwarder \
  --forwarder oauth2webhook \
  --forwarderopt url=https://myinstance.service-now.com/itsm/eventapi/v1/api/global/em/jsonv2 \
  --forwarderopt token_url=https://myinstance.service-now.com/oauth/accesstoken/v2 \
  --forwarderopt client_id=my_client_id \
  --forwarderopt client_secret=my_client_secret \
  --formatter servicenow \
  --eventopt HOSTNAME='$HOSTNAME$' \
  --eventopt SERVICEDESC='$SERVICEDESC$' \
  --eventopt SERVICESTATE='$SERVICESTATE$' \
  --eventopt SERVICEOUTPUT='$SERVICEOUTPUT$'
```

For a non-ServiceNow API that uses the same OAuth2 Client Credentials flow:
```bash
notificationforwarder \
  --forwarder oauth2webhook \
  --forwarderopt url=https://api.example.com/events \
  --forwarderopt token_url=https://auth.example.com/oauth2/token \
  --forwarderopt client_id=abc \
  --forwarderopt client_secret=xyz \
  --forwarderopt token_scope="events:write" \
  --formatter example
```

---

## Tests

`tests/test_oauth2webhook.py` covers:

| Test | What it verifies |
|---|---|
| `test_token_acquired_and_used` | Fresh start: token is fetched from endpoint and sent as Bearer header |
| `test_cached_token_reused` | Valid cache: token endpoint is NOT contacted; cached value is used |
| `test_expired_cache_triggers_refresh` | Stale cache: expired token triggers a new request to the token endpoint |
| `test_token_failure_spools_event` | Token endpoint returns 404: `submit_one` returns False, event is spooled to SQLite |
| `test_tag_separates_token_cache` | Two instances with different tags have independent cache files |

Tests use a single in-process `http.server.HTTPServer` that handles both the token path (`/oauth/accesstoken/v2`) and the API path (`/api/...`) on the same port, keeping the test setup simple.

---

## Known Limitations and Future Work

- **No refresh token support.** The OAuth2 Client Credentials flow does not issue refresh tokens (the client simply re-authenticates with its credentials), so this is intentional.
- **Token endpoint Basic Auth.** Some token servers expect `client_id`/`client_secret` as HTTP Basic Auth instead of form body fields. This is not currently implemented. If needed, add a `token_auth_method` option (`body` vs `basic`) and conditionally use `requests.auth.HTTPBasicAuth` for the token POST.
- **SSL for token endpoint.** The `insecure` flag applies to both the API call (via `WebhookForwarder`) and the token endpoint call (via `acquire_token`). If the two endpoints have different SSL requirements, a separate `token_insecure` option would be needed.
- **Token file permissions.** The cache file is written with the process's default umask. In shared OMD environments, consider tightening permissions (e.g. `os.chmod(cache_path, 0o600)` after writing) to prevent other site users from reading the token.
- **`WebhookForwarder` super() pattern.** If `webhook/forwarder.py` is ever fixed to use `super(WebhookForwarder, self).__init__(opts)` or plain `super().__init__(opts)`, update `Oauth2WebhookForwarder.__init__` accordingly and remove the duplicated webhook attribute defaults.
