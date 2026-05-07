# UnblurBrief Content OS

> Open-source, local-first content research and carousel workflow console for UnblurBrief-style news/current-affairs content.

## Public repository note

This GitHub version is sanitized. It does not include live API keys, Canva OAuth tokens, generated output, daily caches, or personal local file paths. Configure your own `api_keys.json` and `workflow_config.json` before running. See `GITHUB_SETUP.md`.

---


# UnblurBrief Content OS V7 — API Connectors

## Fast start

Double-click:

```text
START_HERE.bat
```

It will run the full OS and open the localhost console.

## What V7 adds

This version adds API connectors on top of V6:

```text
Guardian API
NewsAPI
Mediastack
GDELT
Official sources
Manual article override
```

## API key setup

Open:

```text
api_keys.json
```

Paste keys where available:

```json
{
  "guardian_api_key": "",
  "newsapi_key": "",
  "mediastack_key": ""
}
```

Leave a key blank to skip that API.

## Source roles

```text
primary_official     = RBI, SEBI, PIB, ISRO
publisher_api        = Guardian API
discovery_api        = NewsAPI, Mediastack
discovery_crosscheck = GDELT
discovery_only       = Google News, Wikipedia Current Events
manual_verified      = manual article text override
```

## Production rule

```text
APIs discover stories.
Only reliable full article/official/manual/publisher text creates final posts.
```

## New files

```text
api_keys.json
api_common.py
collect_guardian_sources.py
collect_newsapi_sources.py
collect_mediastack_sources.py
collect_gdelt_sources.py
```

## Recommended API order

1. Guardian API: best next production/publisher source.
2. GDELT: broad free discovery/cross-checking.
3. NewsAPI: structured discovery.
4. Mediastack: optional discovery supplement.

## Manual article override

If an article is blocked:

1. Open the article manually.
2. Copy the full article body.
3. Paste it into a `.txt` file inside:

```text
manual_overrides/
```

4. Run `START_HERE.bat` again.

## Download exports

After pasting ChatGPT output and clicking `Separate output`, the console gives:

```text
Download JSON package
Download Markdown
Download quick text pack
```

Use JSON package with:

```bash
python export_canva_pack.py unblurbrief_post_package_your-topic.json
```

## Daily workflow

1. Run `START_HERE.bat`.
2. Use only Verified / Usable with caution candidates.
3. Copy content prompt to ChatGPT.
4. Paste output back into the console.
5. Download JSON package.
6. Create Canva review pack.
7. Review and publish manually.


## V8 Three-Section Viewer

This version simplifies the localhost app into the exact workflow:

1. **Content Prompt**
2. **Final Image Prompt**
3. **Caption + Hashtags**

### How it works

- Copy the candidate's **Content Prompt**
- Paste it into ChatGPT
- Paste the full ChatGPT output back into the app
- Click **Separate outputs**
- The app automatically:
  - builds the final **image-generation prompt**
  - combines **caption + hashtags**

### What changed

The viewer no longer tries to show too many repeated sections. It now focuses on the 3 outputs you actually need for production.


## V9 Dynamic Design Routes

This version upgrades the prompt engine so the design language is not repetitive.

### What changed

- every candidate now gets a **creative route**
- the route is woven directly into the content prompt and image-prompt instructions
- prompts now rotate between multiple editorial systems inspired by the design references you fed earlier
- the app still keeps the UnblurBrief brand intact while making each post feel fresher

### Included creative routes

- Obsidian Terminal Briefing
- Editorial Swiss Grid
- Museum Label Editorial
- Gallery Product Briefing
- Kinetic Portfolio News
- Manifesto Monochrome
- Institutional Dashboard
- Atmospheric Gradient Briefing

### Effect

Instead of repeating the same safe layout language every time, the generator now tells ChatGPT to build each carousel with a selected creative route, fresh composition logic, and stronger visual distinctness while preserving the brand system.


## V10 Design-Principle Prompt Engine

This version upgrades prompt generation using the Creative OS knowledge base and the design books/principles you asked me to retain.

### Embedded principles

- Don Norman — human-centered clarity, signifiers, mental models, feedback
- Universal Principles of Design — hierarchy, chunking, consistency, figure-ground, accessibility, signal-to-noise
- John Maeda — reduction, organization, trust, simplicity
- Steve Krug — self-evident communication, remove needless words, scan-friendly design
- About Face — goal-directed structure and purposeful slide progression
- Nir Eyal — ethical hook and low-friction progression
- Ellen Lupton + Bringhurst — typographic hierarchy, rhythm, measure, spacing
- Müller-Brockmann — grids, alignment, modular structure
- Wheeler + Airey — brand coherence and identity discipline
- Austin Kleon — remix, do not copy references literally

### Creative OS style grounding

Prompt routes are now also grounded in your earlier design-reference learning from Apple, ElevenLabs, Resend, Monopo, Sociotype, Locomotive, Kai Fox, and similar references — as transformed design language, not direct copying.

### Effect

Prompt generation should now create more unique and better-structured visual directions while staying readable, premium, and on-brand.


## V11 Stronger Visual Variation

This version specifically addresses repetitive image outputs.

### What changed

- Added route-specific layout construction rules.
- Added route-specific hero metaphor rules.
- Added route-specific slide progression rules.
- Added a hard anti-template rule against repeating the same:
  - top document icon
  - huge lower-left headline
  - identical rounded panels
  - same dashboard/card structure
  - same visual hero across posts
- The app now prepends a **Visual Non-Repetition Directive** to the final image prompt.
- Pixel/document/cursor motifs are now treated as subtle brand texture unless intentionally used once as a hero.

### Goal

Keep UnblurBrief recognizable, but make every carousel look like a fresh editorial design rather than a repeated template.


## V12 Brand Constants + Variable Layout Engine

This version separates UnblurBrief design logic into two layers:

### 1. Fixed brand constants

These stay consistent:
- palette
- tone
- subtle motifs
- footer/logo zone
- publication identity

### 2. Variable composition system

These change from post to post:
- layout family
- hero metaphor
- slide-flow pattern
- composition logic
- scale relationships
- card geometry
- headline placement

### New prompt-engine outputs

Each candidate now gets:
- selected design route
- selected layout family
- selected hero metaphor
- selected slide-flow pattern

### Goal

Keep UnblurBrief recognizable like a publication, while preventing the model from collapsing everything into one repeated template.


## V13 Colorful Image-Led Engine

This version changes the visual direction away from the repeated dark dashboard look.

### What changed

- Brand constants no longer force a dark navy/black background.
- The image prompt now explicitly asks for colorful, image-led, eye-catching editorial visuals.
- New color moods are selected per candidate:
  - Electric Editorial
  - Light Institutional Pop
  - Gradient Spectrum Brief
  - Poster Pop Explainer
  - Data Colorburst
- New image-led styles are selected per candidate:
  - 3D symbolic editorial object
  - bold vector/editorial illustration
  - collage-style cutout object
  - isometric metaphor scene
  - cinematic symbolic object
  - magazine-cover object

### Goal

Keep UnblurBrief recognizable, but make posts more colorful, visual, and scroll-stopping instead of dark, text-heavy, and repetitive.


## V14 Text-Only Visual Prompt Safety

This version fixes the issue where pasting the content prompt into ChatGPT could trigger image generation immediately.

### What changed

- The output heading is now `VISUAL_PROMPT_FOR_LATER_USE`, not a direct image-generation command.
- The prompt explicitly says:
  - do not generate images
  - do not call image tools
  - write reusable prompt text only
  - the user will copy it into ChatGPT Images later
- The app parser supports both:
  - `VISUAL_PROMPT_FOR_LATER_USE`
  - old `IMAGE_GENERATION_PROMPT`

### Workflow

1. Copy Content Prompt.
2. Paste into normal ChatGPT.
3. ChatGPT returns text-only post package.
4. Paste that output back into the app.
5. App separates:
   - Final Image Prompt for Later
   - Caption + Hashtags


## Separate Slide Output Patch

This patched version updates the final visual/image prompt so image tools are instructed to generate:

```text
5 separate square slide images
one image per Instagram carousel slide
```

It explicitly forbids:

```text
single combined preview
contact sheet
collage
grid
storyboard
mockup
Canva/editor preview
multiple slides on one canvas
```


## V15 No Image Section in Content Prompt

This version fixes the issue where pasting the content prompt into ChatGPT triggered image generation.

### What changed

The Content Prompt no longer asks ChatGPT to return:

```text
IMAGE_GENERATION_PROMPT
VISUAL_PROMPT_FOR_LATER_USE
```

The text step now returns only:

```text
CAROUSEL_TITLE
SLIDE_COPY
VISUAL_DIRECTION
CAPTION
HASHTAGS
VERIFICATION_CHECKLIST
```

The localhost app then builds the final image prompt separately from:

```text
SLIDE_COPY + VISUAL_DIRECTION
```

This prevents the normal ChatGPT text step from accidentally triggering image generation.


## V16 Text-Only Content Prompt Patch

This patch makes the ChatGPT text step safer by removing visual-generation instructions from the content prompt.

### Content Prompt now returns only:

```text
CAROUSEL_TITLE
SLIDE_COPY
CAPTION
HASHTAGS
VERIFICATION_CHECKLIST
```

It does **not** ask for:

```text
VISUAL_DIRECTION
IMAGE_GENERATION_PROMPT
VISUAL_PROMPT_FOR_LATER_USE
FINAL_IMAGE_PROMPT
```

### Final Image Prompt

The localhost app now builds the image prompt itself from:

```text
SLIDE_COPY
candidate visual_style
candidate visual_elements
design_route
layout_family
hero_metaphor
color_mood
image_led_style
image_safety_note
```

This reduces the chance that normal ChatGPT triggers image generation during the content/copy step.


## V17 Brave Profile + Post Folder Packager

This version adds local workflow helpers.

### New files

```text
workflow_config.json
workflow_helper.py
OPEN_CHATGPT_BRAVE_PROFILE.bat
OPEN_CANVA_BRAVE_PROFILE.bat
OPEN_BOTH_BRAVE_PROFILE.bat
IMPORT_LATEST_5_SLIDES.bat
OPEN_GENERATED_POSTS_FOLDER.bat
```

### Configure first

Open:

```text
workflow_config.json
```

Set:

```json
{
  "brave_exe": "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
  "brave_profile_directory": "Profile 2",
  "download_folder": "C:\\UnblurBrief\\ChatGPT Slides",
  "generated_posts_folder": "C:\\UnblurBrief\\Generated Posts"
}
```

To find your real Brave profile directory:

```text
Open the UnblurBrief Brave profile
Go to brave://version
Find Profile Path
Use the last folder name, for example Profile 2
```

### Workflow

1. Run your OS normally.
2. Use `OPEN_CHATGPT_BRAVE_PROFILE.bat` to open ChatGPT in the correct Brave profile.
3. Generate and download the 5 images.
4. Run `IMPORT_LATEST_5_SLIDES.bat`.

The importer will:

```text
- find the latest 5 images from your download folder
- create a new per-post folder
- move/copy files into slides/
- rename them slide_01.png to slide_05.png
- create source/copy/exports folders
- create canva_upload_manifest.json
```


## V18 Instagram 4:5 Aspect Ratio Patch

This patch updates the final image prompt so ChatGPT Images generates each carousel slide as a **portrait 4:5 Instagram post** instead of square 1:1.

### New behavior

The final image prompt now explicitly says:

```text
Generate 5 separate full-size 4:5 portrait images
Use 4:5 aspect ratio for every slide (recommended 1080×1350)
Do NOT create square 1:1 slides unless explicitly requested
```

This helps the generated slides fit the standard portrait Instagram post format better.


## V19 Aspect Ratio Toggle

This version adds an output-format selector inside the app.

### New options
- 4:5 portrait post (1080×1350)
- 1:1 square post (1080×1080)
- 9:16 story / reel cover (1080×1920)

The final image prompt now follows the selected format automatically.


## V20 Localhost opens in Brave Profile 2

This version changes the main app runner so when you run:

```text
START_HERE.bat
```

the local console site (`http://localhost:PORT/console.html`) opens automatically in **Brave using the profile from `workflow_config.json`**.

### Default behavior
```json
{
  "brave_profile_directory": "Profile 2"
}
```

### Files changed
- `run_unblurbrief_os.py`
- `README.md`

### Optional launcher
- `OPEN_LOCAL_APP_BRAVE_PROFILE.bat`

If your Brave profile is different, edit:

```text
workflow_config.json
```


## V21 Canva API Foundation

This version adds a first Canva Connect API integration.

### New files

```text
canva_client.py
SEND_LATEST_POST_TO_CANVA.bat
IMPORT_LATEST_5_SLIDES_AND_SEND_TO_CANVA.bat
```

### Updated files

```text
workflow_config.json
workflow_helper.py
run_unblurbrief_os.py
console.html
README.md
```

### Configure Canva

Open:

```text
workflow_config.json
```

Set:

```json
{
  "canva_enabled": true,
  "canva_access_token": "PASTE_YOUR_CANVA_ACCESS_TOKEN_HERE",
  "canva_parent_folder_id": "uploads",
  "canva_create_folder": true,
  "canva_move_assets_to_folder": true,
  "canva_create_design": true,
  "canva_design_width": 1080,
  "canva_design_height": 1350,
  "canva_open_design_after_create": true
}
```

Required Canva scopes:

```text
asset:write
asset:read
folder:write
design:content:write
```

### What it does

```text
1. Finds latest generated post folder
2. Uploads all slide images to Canva assets
3. Creates a Canva folder for the post
4. Moves uploaded assets into that folder
5. Creates a 1080×1350 Canva design using slide_01
6. Opens the Canva edit URL
7. Saves results to exports/canva_api_result.json
```

### Limitation

The public Create Design endpoint can create a design and insert an image asset, but this first integration does not automatically create a full 5-page Canva carousel. It uploads all 5 slide assets and creates/opens a design with the first slide. Add remaining slides manually in Canva, or later use a Canva template/autofill workflow if your Canva plan supports it.


## V22 Canva OAuth Manager

This version adds proper Canva OAuth instead of relying on a manually pasted access token.

### New files

```text
canva_oauth.py
CONNECT_CANVA.bat
CHECK_CANVA_AUTH.bat
REFRESH_CANVA_TOKEN.bat
```

### Updated files

```text
canva_client.py
workflow_helper.py
run_unblurbrief_os.py
console.html
workflow_config.json
README.md
```

### Setup

Create a Canva Connect API integration and add these values to `workflow_config.json`:

```json
{
  "canva_enabled": true,
  "canva_client_id": "YOUR_CANVA_CLIENT_ID",
  "canva_client_secret": "YOUR_CANVA_CLIENT_SECRET",
  "canva_redirect_uri": "http://127.0.0.1:8787/canva/oauth/callback",
  "canva_scopes": "asset:write asset:read folder:write folder:read design:content:write design:meta:read"
}
```

Your Canva integration must have the same redirect URI registered:

```text
http://127.0.0.1:8787/canva/oauth/callback
```

### Workflow

1. Run `START_HERE.bat`
2. Click **Connect Canva** inside the app
3. Approve access in Canva
4. The local app saves:
   - access token
   - refresh token
   - expiry time
5. Future Canva uploads auto-refresh the access token when needed.

### BAT shortcuts

```text
CONNECT_CANVA.bat
CHECK_CANVA_AUTH.bat
REFRESH_CANVA_TOKEN.bat
```


## V23 Canva OAuth State Fix

This patch fixes the common `Canva OAuth state mismatch` issue.

### What changed

The OAuth callback server now starts **before** the Canva authorization URL is opened. This avoids stale callback/race-condition issues.

### If you still see state mismatch

1. Close all old Canva authorization tabs.
2. Stop `START_HERE.bat`.
3. Restart `START_HERE.bat`.
4. Click `Connect Canva` only once.
5. Complete the Canva authorization in the newly opened tab.


## V24 Open Existing OS Launcher

This version adds a launcher that opens the existing dashboard without regenerating candidates.

### New files

```text
open_existing_os.py
OPEN_EXISTING_OS.bat
```

### Use this when candidates already exist

Run:

```text
OPEN_EXISTING_OS.bat
```

This skips:

```text
scrape_sources.py
collect_gdelt_sources.py
collect_guardian_sources.py
collect_newsapi_sources.py
collect_mediastack_sources.py
generate_post_candidates.py
extract_research.py
```

It only:

```text
starts localhost
opens console.html in Brave/profile from workflow_config.json
keeps local workflow API buttons working
```

### Required file

The dashboard loads existing candidates from:

```text
output/top_post_candidates.json
```

If this file is missing, run `START_HERE.bat` once to generate candidates.


## V25 Public APIs + Dynamic Slides

This version adds more candidate diversity and dynamic carousel slide counts.

### New free public API lanes

```text
Hacker News API — tech/startup/AI/business-tech discovery
World Bank API — India economy/data/exam-relevant evergreen explainers
Wikipedia Current Events API — broad current-affairs discovery backup
```

These are used as discovery/data seeds. Discovery-only candidates still require source checking before publishing.

### Dynamic slide counts

Each candidate now gets:

```json
{
  "category_lane": "India / Technology / Business / Current Affairs",
  "recommended_slide_count": 3,
  "recommended_structure": ["What happened", "Why it matters", "Bottom line"]
}
```

Slide count rules:

```text
3 slides = quick update
4 slides = standard explainer
5 slides = full explainer
6 slides = deeper explainer
```

### UI additions

```text
Category filter
Slide count filter
Recommended slide count shown on candidate cards
Recommended structure shown in candidate view
Import Recommended Slides
Import Recommended + Send to Canva
Import Latest 3 / 4 / 5 / 6
```

### New scripts

```text
collect_public_api_sources_v25.py
enrich_candidates_v25.py
```

### New BAT files

```text
IMPORT_LATEST_3_SLIDES.bat
IMPORT_LATEST_4_SLIDES.bat
IMPORT_LATEST_6_SLIDES.bat
IMPORT_3_AND_SEND_TO_CANVA.bat
IMPORT_4_AND_SEND_TO_CANVA.bat
IMPORT_6_AND_SEND_TO_CANVA.bat
```


## V26 Classifier + Scoring Fix

### Fixed India misclassification

V25 used overly broad India keywords. Generic words like `election` could incorrectly classify US politics as India news.

V26 changes this:

```text
India lane now requires India-specific entities:
India, Indian, New Delhi, RBI, SEBI, Lok Sabha, Rajya Sabha,
Election Commission of India, Supreme Court of India, Kerala, Odisha, etc.
```

Generic terms like these no longer trigger India classification:

```text
election
court
government
senate
politics
```

### Improved scoring

V26 replaces the old additive score with a more transparent score model.

Score components include:

```text
base
category relevance
trust role
source quality
reliability score
fact depth
recency
article body availability
exam value
India/tech/business relevance
source-check penalty
low-value topic penalty
limited previous-score carryover
```

The app now shows a score breakdown in the candidate detail view.


## V27 Daily Source Cache Workflow

V27 separates **data pulling** from **candidate generation**.

### Daily flow

Run this once per day:

```text
START_HERE.bat
```

It pulls fresh data and saves reusable source/research files into:

```text
daily_source_cache/YYYY-MM-DD/
```

### Rest-of-day flow

After patching or making a new version, do not pull APIs/scrapers again.

Use:

```text
REBUILD_FROM_TODAY_CACHE.bat
```

This restores today’s saved source files and rebuilds candidates locally.

If today’s cache is missing, use:

```text
REBUILD_FROM_LATEST_CACHE.bat
```

### Cached files

```text
output/unblurbrief_sources.json
output/unblurbrief_sources.csv
output/public_api_v25_sources.json
output/research_cache.json
```

### What rebuild does NOT do

```text
No scraping
No Guardian/GDELT/NewsAPI/Mediastack calls
No Hacker News / World Bank / Wikipedia API calls
```

It only runs:

```text
generate_post_candidates.py
enrich_candidates_v25.py
```


## V27.1 Cache Command Fix

Fixed `START_HERE.bat` failing on:

```text
python.exe: can't open file 'daily_cache_manager.py save-today'
```

Cause: the runner passed `daily_cache_manager.py save-today` as one filename instead of splitting it into script + argument.

Fix: `run_step()` now supports command arguments safely.


## V28 Source Verification Button

V28 adds a source-check workflow for candidates marked `source_check_required`.

### New button

Inside the app:

```text
Verify Selected Source
Extract / Verify This Source
```

### What it does

```text
1. Loads the selected candidate URL.
2. Runs the existing article extraction stack.
3. Saves extracted text into output/research_cache.json.
4. Updates the selected candidate with article_text/key_facts when extraction succeeds.
5. Regenerates candidates locally.
6. Re-enriches candidates with classifier/scoring + dynamic slide count.
7. Reloads the app candidate list.
```

### Important

This does not rerun the full scraper/API pipeline. It only fetches the selected article URL.

### Result states

```text
ok + 250+ words + 3+ facts -> usable_with_caution
partial / summary_only -> source_check_required remains
failed / empty -> source_check_required remains
```

Scraped articles are not automatically marked fully verified. They become `usable_with_caution` when extraction is strong enough.


## V28.1 Verify Button JS Fix

Fixed the issue where clicking **Verify Selected Source / Extract Verify This Source** appeared to do nothing.

Cause:
The button HTML was added, but the JavaScript function was not inserted in some builds because the patch checked for the string `verifySelectedSource` and found it inside the button `onclick`, then skipped adding the actual function.

Fix:
`console.html` now includes the actual `async function verifySelectedSource()` implementation.


## V28.2 Verified Prompt Population Fix

Fixed the issue where source extraction succeeded in the command window but the app still showed `source_check_required`.

### Cause
The selected article was extracted into `research_cache.json`, but `enrich_candidates_v25.py` was not applying the research cache back into the candidate before rebuilding the prompt. So the app kept treating the candidate as discovery-only metadata.

### Fix
V28.2 applies cached extraction by URL during enrichment:

```text
research_cache[url].excerpt -> candidate.article_text
research_cache[url].key_facts -> candidate.key_facts
```

Strong extraction now upgrades:

```text
status ok + 250+ words + 3+ facts
→ verified
→ publishable
→ prompt includes extracted article text and key facts
```
