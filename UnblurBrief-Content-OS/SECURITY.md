# Security

Do not commit real API keys, Canva OAuth credentials, access tokens, refresh tokens, generated caches, or personal local paths.

If secrets are accidentally committed:

1. Revoke/rotate the exposed credentials immediately.
2. Remove the secret from the repository history before making the repository public.
3. Regenerate local config from `workflow_config.example.json` and `api_keys.example.json`.

This project stores local runtime output in `output/`, `daily_source_cache/`, `posts/`, and `canva_review_packs/`. These folders are ignored by `.gitignore` except for `.gitkeep` placeholders.
