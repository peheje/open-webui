# S23 Open WebUI working handoff

Last updated: 2026-08-04 (Europe/Copenhagen).

This is the starting point for a new Codex session working on Peter's private
Samsung S23 Ultra Open WebUI server. Read this file before changing code or
runtime state. It records architecture and operational decisions; Git history
is authoritative for individual code changes.

## Repositories and authority

- Product fork: <https://github.com/peheje/open-webui>, branch `s23-custom`.
  This repository is authoritative for the modified Open WebUI source.
- Operations/recovery: <https://github.com/peheje/ai-scripts>, branch `main`,
  directory `s23-open-webui`. It owns S23/S26 scripts, provider curation,
  tests, service definitions, recovery notes, and build/deploy logic. The
  fast-deploy work from this session was merged at `4cf98ba`.
- Upstream base: `open-webui/open-webui` dev commit
  `d1aa812d80389f90e31f0629ace3ca4205892951`.
- Never commit provider keys, admin credentials, SSH private keys,
  `WEBUI_SECRET_KEY`, chats, uploads, databases, or decrypted backups.

Clone both repositories on a new controller:

```bash
git clone --branch s23-custom https://github.com/peheje/open-webui.git
git clone https://github.com/peheje/ai-scripts.git
```

Then read:

- this file;
- `ai-scripts/s23-open-webui/docs/CURRENT-STATE.md`;
- `ai-scripts/s23-open-webui/docs/BUILD-AND-DEPLOY.md`;
- `ai-scripts/s23-open-webui/docs/OPENROUTER.md`;
- `ai-scripts/s23-open-webui/docs/PDF-FILES-AND-MODELS.md`;
- `ai-scripts/s23-open-webui/docs/RECOVERY.md`.

## Runtime topology

- Server: Samsung Galaxy S23 Ultra, Android 16, roughly 10 GB RAM.
- Runtime: Ubuntu 24.04 ARM64 through Termux `proot-distro`.
- Service supervision: native Termux runit; do not replace it with an
  ad-hoc background process.
- Production URL: `http://100.117.57.15:8080` over Tailscale only.
- SSH: `u0_a351@100.117.57.15:8022`, public keys only; normal host alias is
  `s23u`.
- LAN address `192.168.0.71:8080` must continue to refuse connections.
- Vite/HMR development URL: `http://100.117.57.15:5173`, started explicitly
  and also inaccessible through the LAN address.
- Venv: `/opt/open-webui-dev-d1aa812d/venv`.
- Data: `/srv/open-webui/data`.
- Protected environment: `/etc/open-webui/open-webui.env` (mode `0600`).
- Runit service: `$PREFIX/var/service/open-webui`.
- Log: `$PREFIX/var/log/sv/open-webui/current`.

As last verified, production returned HTTP 200, its LAN endpoint refused
connections, the development server was stopped, and runit was healthy.

## Current deployed revisions

The deployed frontend and backend are deliberately tracked separately:

- frontend: `64ec6565df1111ae1c5f57b1a6dc8fbb47f1cdcf`;
- backend: `cfd6217fd4be4c862e880f2f872e9916859ca749`.

The backend advanced without a frontend rebuild for the final Gemini gateway
recovery. Live state is recorded in:

```text
/opt/open-webui-dev-d1aa812d/deployment-state.json
```

Do not infer deployed code only from the fork's current HEAD. Inspect that
state file and `build/_app/version.json` first.

## Build and deployment workflow

S26 is currently the controller; S23 native Termux is the canonical build
worker. A laptop may act as controller once it has its own authorized SSH key
and Tailscale access. Never copy another device's private key.

Choose the smallest safe path:

| Change | Workflow |
| --- | --- |
| UI/CSS/Svelte/TypeScript/static/frontend config | Vite/HMR, then one `owui-build && owui-deploy` after approval |
| Modified existing Python files below `backend/open_webui` | `owui-fast-deploy s23-custom check`, then `owui-fast-deploy` |
| Dependencies, new/deleted/renamed backend files, or non-Python backend files | Full installation/recovery path; fast deploy refuses these |
| Documentation/tests only | Commit/push; normally no runtime deployment |

The fast deploy path byte-compiles changed modules, creates timestamped
backups, rolls back if health fails, and verifies production/LAN/dev ports.
It was regression-tested and an installed no-op deployment took about 7.7
seconds including Git, SSH, and network checks.

Full builds reuse `node_modules` when `package-lock.json` is unchanged and a
content-addressed 61 MB Pyodide cache under
`~/.cache/open-webui-build/pyodide`. Cache-only verification:

```bash
owui-build s23-custom prepare-only
```

Cache adoption/reuse took about 4-5 seconds including SSH/Git. This removes
redundant preparation but does not make Vite's complete production traversal
incremental. Use HMR for the inner UI loop:

```bash
owui-dev-start
owui-dev-sync
owui-dev-logs
owui-dev-stop
```

Production stays on 8080 while HMR uses 5173. Do not leave the dev server
running after approval/deployment.

## Product behavior added by this fork

### Provider-aware chat controls

- Curated model aliases keep the model picker usable; provider prefixes such
  as `di/`, `ds`, and `or/` identify DeepInfra, direct DeepSeek, and
  OpenRouter without exposing the full provider catalogue.
- Reasoning-capable aliases expose one compact `r0`/`r1`/`r2` per-chat
  control. Provider metadata translates those levels to the provider's real
  parameters. Do not create three duplicate aliases per model again.
- Tapping cycles the compact control; holding opens the full menu.
- Web-search on/off remains visible instead of disappearing when enabled.
  Holding opens provider/depth choices where the selected provider supports
  them.
- Android sticky-hover/selection CSS is intentionally overridden so the blue
  active state is repainted consistently. Regression-test repeated toggles,
  not only the first click.
- Composer suggestions were removed. Voice/dictation clutter was reduced;
  keyboard dictation is the expected phone path.
- Routine disconnect/reconnect notifications disappear after about one
  second. History/sidebar disappearance has occurred in both Firefox and
  Chrome; do not assume it is browser-specific if it returns.
- Model-family PNG avatars use existing OWUI image paths rather than a new
  serving subsystem.

Primary UI files include:

```text
src/lib/components/chat/MessageInput.svelte
src/lib/components/chat/MessageInput/IntegrationsMenu.svelte
src/lib/components/chat/Messages/ResponseMessage.svelte
src/lib/openrouter.ts
src/lib/reasoning.ts
```

### Providers and web access

Configured provider families include direct DeepSeek, DeepInfra, and
OpenRouter. Local web search uses Brave by default with Serper retained as an
alternate; Firecrawl is the local page loader. Keys are stored only in the
protected S23 configuration/database and are updated with `owui-keys`.

Local Brave/Serper search intentionally has no artificial maximum-search
promise in the UI. Earlier Quick/Normal/Deep hard limits did not reliably
bound native model tool calls and were removed. Provider choice remains.

OpenRouter is a provider-aware integration, not just another generic base
URL:

- curated aliases force the official inference provider and disable
  fallbacks;
- unified reasoning is translated in `backend/open_webui/utils/openrouter.py`;
- `reasoning_details` must survive and be replayed in multi-turn chats;
- prompt-cache mode and hashed per-chat `session_id` are supported;
- an `OR` action below OpenRouter responses links to the OpenRouter Sessions
  view;
- OpenRouter server search exposes Auto/Native/Exa/Parallel/Perplexity/
  Firecrawl plus one user-facing Quick/Balanced/Deep depth choice;
- local Brave/Serper injection is suppressed for OpenRouter searches to avoid
  two search systems firing from one toggle;
- image generation is a separate composer mode and switches to a curated
  image-model picker. It does not charge or route through an arbitrary chat
  model first.

Curated OpenRouter chat models include first-party OpenAI, Anthropic, and xAI
routes. Image models include the curated Nano Banana, GPT Image, Grok
Imagine, Seedream, and FLUX paths. The exact catalogue belongs in the
ai-scripts curator; do not hard-code a second independent catalogue here.

### Gemini on OpenRouter

Gemini aliases hide the generic web-search control. They keep a conservative
managed Exa server tool available and let Gemini decide whether to call it.
This replaced an unreliable Google-native search route. The backend retries
without the failed search tool for known provider/gateway failures, including
the later HTTP 500 shape fixed at `cfd6217fd`.

Before changing this path, run the OpenRouter unit tests and live-test both:

1. a simple prompt that should need zero searches;
2. an explicit current-information prompt that should search and return
   citations;
3. the gateway-error recovery path.

Relevant backend files:

```text
backend/open_webui/utils/openrouter.py
backend/open_webui/routers/openai.py
backend/open_webui/utils/middleware.py
backend/tests/test_openrouter.py
```

### Files, PDFs, images, and OCR

- OWUI normally extracts PDF text locally before inference. Native extraction
  is followed by per-page RapidOCR fallback for blank/image-based pages.
- Local scanned-PDF OCR is slow on this phone: roughly 73 seconds per page at
  150 DPI in the measured case. Treat it as fallback, not the default for all
  PDFs.
- Attachment UI modes are **Auto**, **Page images**, and capability-gated
  **Native PDF**. Page images are limited to 10 pages at 150 DPI and require
  every selected model to have live-tested vision capability.
- Never mark a model `vision` or `native_pdf` merely because marketing claims
  it. Run `owui-cap-test` with unique markers through the actual OWUI path.
- Providers vary: an OpenAI-compatible wrapper does not imply that raw PDF
  bytes reach or are accepted by the upstream model.
- Images, authenticated assets, model icons, TXT/CSV/XLSX/PPTX, text PDFs,
  scanned-PDF OCR, and page-image delivery have repeatable regression tests in
  ai-scripts.
- A past OpenRouter/DeepInfra error surfaced as `'NoneType' object is not
  iterable`; provider boundary and empty-tool behavior now have regressions.

Useful tests from a controller:

```bash
owui-cap-test di.sonnet5
owui-cap-test --quick ds.ds4f
owui-reason-test
```

Also run targeted fork tests for edited modules. Every discovered production
bug should gain a regression test before deployment.

## Model curation and defaults

The curated catalogue, aliases, provider routing metadata, icons, reasoning
maps, and capabilities are maintained by the ai-scripts curator. Avoid
showing every DeepInfra model; the intention is a useful shortlist plus a few
small experimental Qwen/Gemma models. Direct DeepSeek remains duplicated with
DeepInfra intentionally so direct credits can be consumed first.

A user's default model is normally changed directly in Open WebUI:

```text
Profile menu -> Settings -> Interface -> Default Model
```

That requires no code change or build. A reproducible server-wide default can
be added to the curator only when explicitly desired.

When adding a model, validate at least plain chat, advertised reasoning
levels, local/provider search behavior, image input, text PDF, scanned PDF,
page images, raw/native PDF claims, provider identity, and multi-turn replay.

## Operations, reboot, and backups

- Tailscale and Termux are configured unrestricted by Android battery
  optimization. Termux:Boot and runit handle post-boot startup.
- Android unexpectedly rebooted once while unattended. With a secure screen
  lock, the first physical unlock prevents truly remote recovery because
  Termux/Tailscale app data is credential-encrypted. The device currently has
  no screen PIN/locking mechanism to favor unattended recovery; reassess this
  tradeoff if physical-theft risk changes.
- A dedicated always-on host such as a small Mac/Linux mini-PC remains a
  reasonable future migration if phone reboot/security tradeoffs become a
  dealbreaker. LibreChat was previously shelved because of MongoDB friction;
  OWUI/SQLite remains the working deployment.
- OWUI live backups and recovery automation live in ai-scripts and must remain
  encrypted off-device. Do not commit archives or the age identity.
- Photos now sync from the Ubuntu desktop to S23 using Syncthing
  `receiveencrypted`. The encrypted S23 copy was fully caught up at 196.4 GB,
  and 11 representative decrypted files matched desktop SHA-256 hashes. The
  old plaintext S23 copy was deleted. The encryption password remains only in
  a mode-`0600` secret file on the desktop and in the user's password manager;
  do not print or copy it into either repository.

## Safe pickup checklist

1. Fetch both repositories and confirm a clean worktree.
2. Read live deployment-state, service status, recent log, and fork HEAD.
3. Confirm `100.117.57.15:8080` works and the LAN endpoint refuses access.
4. Reproduce the issue with the smallest targeted test before editing.
5. Work on a feature branch from `s23-custom`; preserve upstream and user
   changes.
6. For UI changes use HMR, obtain approval, then perform one production build.
7. For an existing Python module use the fast-deploy classifier first.
8. Add a regression, commit/push, merge into `s23-custom`, deploy only the
   necessary layer, and repeat health/security checks.

Useful controller commands:

```bash
ssh s23u 'sv status "$PREFIX/var/service/open-webui"'
ssh s23u 'tail -n 100 "$PREFIX/var/log/sv/open-webui/current"'
owui-status
owui-logs 100
owui-fast-deploy s23-custom check
termux-help
```

Do not reboot the S23 merely to test a change. Do not expose OWUI or Vite on
`0.0.0.0`. Do not reinstall provider/model state casually: the current
installation works, and minimal reversible changes are preferred.
