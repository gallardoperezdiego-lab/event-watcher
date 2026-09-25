# Building and developing

## Releases (automatic)

Pushing a version tag builds both apps on GitHub's own Windows and Mac machines, runs the self-tests on each and publishes `EventWatcher.exe` and `EventWatcher-mac.zip` on the **Releases** page:

```bash
git tag v1.2.0
git push origin v1.2.0
```

The workflow is in [.github/workflows/release.yml](.github/workflows/release.yml). It can also be started by hand from the **Actions** tab ("Build apps" → Run workflow); the apps are then attached to that run as downloads. The Mac build targets Apple Silicon Macs.

## Running from source

Needs **Python 3.9 or newer** and nothing else:

- Mac / Linux: `python_backend/run.sh`
- Windows: double-click `python_backend\run.bat`

Self-tests (offline, using a temporary data folder):

```bash
cd python_backend && python3 -m unittest discover -s tests -v
```

## Changing the interface

The interface is React + TypeScript + Tailwind CSS in `web/src`. The ready-built version in `web/dist` is what the app serves, so **rebuild and commit `web/dist` after any change**:

```bash
python_backend/run.sh --background      # start the backend
cd web && npm install
npm run dev                              # live preview on http://127.0.0.1:5173
npm run lint && npm run build            # type-check, then rebuild web/dist
```

Rules the interface must keep: no external fonts, scripts or images (fonts are bundled via `@fontsource-variable/*`), and every colour comes from the design tokens in `web/src/index.css`, so light and dark mode both work.

## Building the apps by hand

Build on the system you are building for (PyInstaller cannot cross-compile).

Mac:

```bash
cd python_backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pyinstaller --noconfirm --distpath ../release EventWatcher.spec
```

Windows:

```cmd
cd python_backend
py -3 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pyinstaller --noconfirm --distpath ..\release EventWatcher.spec
```

The result is `release/EventWatcher.app` (about 25 MB) or `release\EventWatcher.exe` (about 9 MB). Neither contains personal data: data is created on first launch in `~/Library/Application Support/EventWatcher` (Mac) or `%APPDATA%\EventWatcher` (Windows).

## Adding a new kind of source

Add it to `SOURCE_TYPES` in `python_backend/database.py`, handle it in `extract()` in `python_backend/extractors.py`, add a test in `python_backend/tests/`, and add the option to `web/src/types.ts` and `TYPE_OPTIONS` in `web/src/components/ui.tsx`.
