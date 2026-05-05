---
name: et-0012-validating-config-at-startup
description: Load and validate configuration at startup, not at first use.
when_to_use: Use when reading an environment variable / config file value at the point where it is first used; writing a configuration class whose fields are typed as `string?` because they may be missing; reviewing a diff that defers config parsing into a request handler / job runner / command body; deciding when to validate that required config (URLs, secrets, feature flags, durations) is present and well-formed.
user-invocable: false
---
<!-- generated from tenets/ET-0012-validating-config-at-startup.md by `uv run poe build` — do not edit by hand. -->

# ET-0012 — Load and validate configuration at startup, not at first use

_Type: best-practice · Tier: 1_

## Rule

All configuration the process needs — environment variables, config
files, command-line flags, secret-store values, feature flags — is
loaded, parsed, and validated **once** at startup, before the
process begins serving traffic, processing jobs, or accepting
commands. Missing or malformed configuration crashes the process
with a message naming the offending key and the constraint it
violated. Internal code consumes a typed `Config` value where every
field is non-optional and already in its parsed form (URL, port,
duration, enum, parsed secret), not raw strings looked up at the
call site. "Optional" here is a property of the value, not of the
loader: optional fields exist as `Option<T>` / `T?` *after* parsing,
not as missing keys.

## Why

Lazy config validation defers errors to the worst time — the first
request that touches the missing key, often hours after deploy,
often only on a code path that runs once a day. The production
symptom is "feature X mysteriously fails" rather than "process
refused to start", and rolling back is harder because the bad
version has already accepted traffic and produced state. Validating
at startup turns an N-hour-mean-time-to-detect bug into a
deploy-fails-fast bug; the deploy pipeline catches it instead of
the customer. The typed `Config` value also removes parsing scatter:
URL strings, durations, ports, and enums are parsed in one place,
once, by code that knows what to do when they are wrong.

## Bad Example

```ts
// BAD: env read at request time; missing variable surfaces as `undefined.toLowerCase()`.
app.get("/users/:id", async (req, res) => {
  const baseUrl = process.env.API_BASE_URL;
  const r = await fetch(`${baseUrl}/users/${req.params.id}`);
  res.json(await r.json());
});
```

```python
# BAD: parsed lazily; a missing TIMEOUT only blows up on the first slow customer.
def fetch(url: str) -> Response:
    timeout = float(os.environ["HTTP_TIMEOUT_SECONDS"])   # KeyError at first call
    return requests.get(url, timeout=timeout)
```

```csharp
// BAD: reads config inline, accepts string?, defers all validation to the call site.
public async Task<Order> LoadAsync(int id)
{
    var conn = _config["Db:ConnectionString"];   // may be null, may be malformed
    using var c = new SqlConnection(conn);
    // ...
}
```

## Good Example

```ts
// GOOD: parse + validate once at startup. The handler receives a typed Config.
const ConfigSchema = z.object({
  apiBaseUrl: z.string().url(),
  httpTimeoutMs: z.coerce.number().int().positive(),
});
type Config = z.infer<typeof ConfigSchema>;

function loadConfig(): Config {
  return ConfigSchema.parse({
    apiBaseUrl: process.env.API_BASE_URL,
    httpTimeoutMs: process.env.HTTP_TIMEOUT_MS,
  });    // throws on startup with a precise error path if anything is missing/wrong
}

// In main():
const config = loadConfig();
app.get("/users/:id", async (req, res) => {
  const r = await fetch(`${config.apiBaseUrl}/users/${req.params.id}`,
                        { signal: AbortSignal.timeout(config.httpTimeoutMs) });
  res.json(await r.json());
});
```

```python
# GOOD: pydantic / dataclass parser at startup; downstream code consumes typed Config.
@dataclass(frozen=True)
class Config:
    api_base_url: str
    http_timeout: timedelta

def load_config() -> Config:
    raw = {
        "api_base_url": os.environ["API_BASE_URL"],
        "http_timeout": os.environ["HTTP_TIMEOUT_SECONDS"],
    }
    return Config(
        api_base_url=parse_url(raw["api_base_url"]),
        http_timeout=timedelta(seconds=float(raw["http_timeout"])),
    )

# In main(): config = load_config()  →  pass `config` down through the composition root.
```

## Exceptions

- **Hot-reloaded configuration** (feature flags, dynamic limits)
  intentionally changes at runtime. It is still parsed and validated
  *each time* it is reloaded, in one place, into a typed value; the
  rule applies to each reload as if it were a startup. A reload that
  produces an invalid value rejects the new config and keeps the
  previous one rather than crashing the process.
- **Optional, fall-back configuration** with a documented default is
  fine — the loader supplies the default when the variable is absent
  and the field is non-optional after parsing. The exception is
  about *defaultable* config, not about leaving keys un-validated.
- **Tools and scripts** with a small, fixed argument list MAY read
  arguments inline (e.g. CLI tools whose only "config" is `argv`).
  Once a tool grows more than a couple of inputs, parse them into a
  typed value the same way.

## Rationalizations

- **"It's just one env var, parsing it at startup is overkill."**
  Until it's three, then ten; the migration from "inline reads" to
  "central loader" is much harder than starting central. The
  startup parser is one function and one type; you pay it once.
- **"What if the config file is huge?"** Then parse it once at
  startup into a typed value (the rule), not every request (the
  failure mode this rule prevents). Size is an argument *for*
  startup parsing, not against.
- **"I want config to be lazy so unused parts don't fail."** Then
  unused parts should not be required. Mark them `Optional[T]` in
  the typed config; the loader treats absence as `None`. "Lazy
  because it might be wrong" delays the error to the worst possible
  moment.
