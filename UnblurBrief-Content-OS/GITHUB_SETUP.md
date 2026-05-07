# UnblurBrief Content OS — GitHub Setup

This repository has been sanitized for public release. It does **not** include live API keys, Canva OAuth tokens, local cache files, generated posts, or personal output folders.

## 1. Install

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## 2. Configure API keys

Edit `api_keys.json` or copy from `api_keys.example.json`:

```json
{
  "guardian_api_key": "",
  "newsapi_key": "",
  "mediastack_key": ""
}
```

All keys are optional depending on which collectors you use. PIB-only mode does not require any API key.

## 3. Configure local paths and Canva

Edit `workflow_config.json` or copy from `workflow_config.example.json`.

Minimum local fields to set on Windows:

```json
{
  "brave_exe": "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
  "brave_profile_directory": "Profile 2",
  "download_folder": "C:\\UnblurBrief\\ChatGPT Slides",
  "generated_posts_folder": "C:\\UnblurBrief\\Generated Posts"
}
```

For Canva integration, set:

```json
{
  "canva_enabled": true,
  "canva_client_id": "YOUR_CANVA_CLIENT_ID",
  "canva_client_secret": "YOUR_CANVA_CLIENT_SECRET",
  "canva_redirect_uri": "http://127.0.0.1:8787/canva/oauth/callback"
}
```

Then run:

```bat
CONNECT_CANVA.bat
```

## 4. Common commands

### PIB-only, no API keys

```bat
RUN_PIB_ONLY.bat
```

This fetches PIB Delhi English All Releases and writes:

- `output/pib_all_releases.json`
- `output/pib_only_sources.json`
- PIB debug files if needed

### Open existing local console

```bat
OPEN_EXISTING_OS.bat
```

### Full daily pull

```bat
START_HERE.bat
```

Use this only when you want to pull all configured sources/API collectors.

## 5. Public release safety

Before pushing to GitHub, verify:

```bash
grep -RIn "access_token\|refresh_token\|client_secret\|guardian_api_key\|newsapi_key\|mediastack_key" .
```

Only placeholders should appear.
