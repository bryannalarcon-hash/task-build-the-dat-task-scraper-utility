# DAT Task Scraper

A minimal Python desktop utility that converts messy HTML task files into clean,
AI-readable Markdown. It strips navigation/boilerplate, preserves questions and
form fields, and saves the result as `cleaned_task_N.md` in the project root.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| [Docker](https://docs.docker.com/get-docker/) ≥ 24 | Required to build and run the container |
| [Docker Compose](https://docs.docker.com/compose/) v2 | Usually bundled with Docker Desktop |
| X11 display server | **Linux**: built-in. **macOS**: install [XQuartz](https://www.xquartz.org/). **Windows**: install [VcXsrv](https://sourceforge.net/projects/vcxsrv/) or [X410](https://x410.dev/). |

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/bryannalarcon-hash/task-build-the-dat-task-scraper-utility.git
cd task-build-the-dat-task-scraper-utility
```

### 2. Place your HTML file in the project root

Copy or rename your input file to `raw_task.html` in the project root:

```bash
cp /path/to/your/task.html ./raw_task.html
```

### 3. Set up your X11 display

#### Linux

```bash
xhost +local:docker
export UID=$(id -u)
export GID=$(id -g)
```

> Run `xhost +local:docker` once per login session. The `UID`/`GID` exports
> ensure output files are owned by your user, not root.

#### macOS (XQuartz)

1. Install XQuartz:
   ```bash
   brew install --cask xquartz
   ```
2. Open XQuartz, go to **Preferences → Security**, and enable
   **"Allow connections from network clients"**.
3. Restart XQuartz, then run:
   ```bash
   xhost +localhost
   export DISPLAY=host.docker.internal:0
   export UID=$(id -u)
   export GID=$(id -g)
   ```

#### Windows (VcXsrv)

1. Install [VcXsrv](https://sourceforge.net/projects/vcxsrv/) and launch
   **XLaunch** with *"Disable access control"* checked.
2. In your terminal set the display variable (replace `<your-LAN-IP>` with your
   actual LAN IP address):
   ```powershell
   $env:DISPLAY = "<your-LAN-IP>:0"
   ```

### 4. Launch the application

```bash
docker compose up
```

Docker builds the image on first run (subsequent runs are instant). A small GUI
window will open on your desktop.

### 5. Use the GUI

1. Click the **Process** button.
2. The status label updates to **✓ Success** and the output file (e.g.
   `cleaned_task_1.md`) appears in the project root.
3. Each successive click increments the filename:
   `cleaned_task_1.md`, `cleaned_task_2.md`, …
4. If anything goes wrong (missing file, parse error, etc.) the label shows
   **✗ Error** with a short description.

---

## Output file naming

| Run | Output filename |
|-----|-----------------|
| 1st | `cleaned_task_1.md` |
| 2nd | `cleaned_task_2.md` |
| … | … |

The utility **never overwrites** an existing output file.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `cannot open display` / blank window | Check `$DISPLAY` is set and X11 access is granted (`xhost +local:docker`). |
| `raw_task.html not found` | Ensure the file is in the **project root** (same directory as `docker-compose.yaml`). |
| Output files owned by root | Set `UID` and `GID` environment variables before running (see Step 3). |
| `docker compose` not found | You may need the v1 syntax: `docker-compose up`. |
| macOS: window does not appear | Confirm XQuartz is running and "Allow connections from network clients" is enabled in XQuartz Preferences → Security. |

---

## Project structure

```
.
├── Dockerfile            # Container image definition
├── docker-compose.yaml   # Compose config with X11 forwarding + volume mounts
├── requirements.txt      # Python pip dependencies
├── main.py               # Tkinter GUI — Process button and status label
├── scraper.py            # HTML parsing, boilerplate stripping, Markdown output
├── raw_task.html         # <- YOU place this file here before running
└── cleaned_task_N.md     # <- Generated output file(s) appear here
```

---

## How it works

1. **Read** — loads `raw_task.html` from the mounted project root (`/workspace`).
2. **Strip boilerplate** — removes `<nav>`, `<header>`, `<footer>`, `<aside>`,
   `<script>`, `<style>`, `<noscript>`, and `<iframe>` elements.
3. **Convert form fields** — replaces `<input>`, `<select>`, and `<textarea>`
   elements with labeled Markdown placeholders such as `**Field: label:** ___`
   so an AI agent can identify and respond to each question.
4. **Markdown conversion** — runs `markdownify` on the cleaned HTML tree,
   preserving headings, paragraphs, lists, and tables.
5. **Write output** — saves the result as `cleaned_task_N.md`, auto-incrementing
   `N` to avoid overwriting previous outputs.

---

## License

MIT
