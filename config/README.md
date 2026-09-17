# Safe Open WebUI configuration backup

`owui-settings.safe.json` is generated from an explicit allowlist. It contains
feature flags, UI defaults, tool defaults, and selected model behavior settings.
It never exports provider connections, URLs, prompts, headers, credentials,
tokens, passwords, cookies, webhooks, user data, or chat data.

Create or refresh the deterministic backup:

```sh
python scripts/owui-safe-config.py backup \
  --database /srv/open-webui/data/webui.db \
  --output config/owui-settings.safe.json
```

Validate a restore without changing the database:

```sh
python scripts/owui-safe-config.py restore \
  --database /srv/open-webui/data/webui.db \
  --input config/owui-settings.safe.json
```

After reviewing the dry-run output, stop Open WebUI, add `--apply` to restore,
and then start it again so its in-memory configuration is refreshed. Existing
model records are updated by ID; missing models are reported and skipped.
Unlisted object fields in the database are preserved. Allowlisted list settings,
such as model tags and default feature IDs, are restored as complete lists.
