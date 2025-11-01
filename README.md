# RGSX → webЯcade Stack

This layers the official [`webrcade/webrcade`](https://hub.docker.com/r/webrcade/webrcade) image together with an automated feed generator for RGSX libraries.

The resulting container:

* pulls the latest published webЯcade image during `docker build`
* installs Python and cron
* ships a helper script that converts the RGSX cache (`systems_list.json`, `games/*.json`) into a webЯcade feed
* runs the helper script on startup and every 30 minutes (adjustable)

## Directory Layout

```
rgsx-webrcade-stack/
├── Dockerfile                # Extends the official image with feed automation
├── docker-compose.yml        # Example stack definition
├── README.md
├── cron/
│   └── rgsx-feed             # Cron definition (defaults to every 30 minutes)
└── scripts/
    ├── build_feed.py         # Feed generator
    ├── entrypoint.sh         # Boots cron + runs initial feed build
    ├── run-feed.sh           # Thin wrapper used by cron/entrypoint
    └── system_mapping.json   # RGSX system -> webЯcade type map
```

Copy these files into a new repository (or keep them here temporarily) and update the mount paths in `docker-compose.yml` to point at your real data.

## Requirements

* A working RGSX deployment that produces the cache folder `saves/ports/RGSX/`
* Docker Engine (and optionally Docker Compose v2) on the host that will serve webЯcade
* HTTP/HTTPS reachable ROM storage (the feed will use the URLs stored in the RGSX cache, or a base URL you provide)

## Quick Start

1. Place these files in their own repository or directory on the host that will run webЯcade.
2. Create two host folders alongside the stack:
   * `content/` – webЯcade will write/read feed files here. You can pre-create `content/feeds`.
   * `rgsx-cache/` – bind-mount of your RGSX cache (copy or mount the real `saves/ports/RGSX` directory here).
3. Update the `volumes` section of `docker-compose.yml` so it points to the correct host paths. Example:
   ```yaml
   volumes:
     - ./content:/var/www/html/content
     - /srv/rgsx-cache:/mnt/rgsx/saves/ports/RGSX:ro
   ```
4. Build and start the container:
   ```bash
   docker compose build
   docker compose up -d
   ```
5. Visit `https://<host>:8443` (or `http://<host>:8080`) to reach webЯcade. The generated feed lives at `/content/feeds/rgsx_feed.json` inside the container, so expose it via the corresponding URL (for example, `https://<host>:8443/content/feeds/rgsx_feed.json`).
6. In the webЯcade UI, add the feed URL and you should see categories for each RGSX system.

## Feed Generator Configuration

Environment variables (set in `docker-compose.yml`) control the generator:

| Variable | Purpose | Default |
| --- | --- | --- |
| `RGSX_DATA_PATH` | Path to RGSX cache inside container | `/mnt/rgsx/saves/ports/RGSX` |
| `FEED_OUTPUT_PATH` | Output feed location | `/var/www/html/content/feeds/rgsx_feed.json` |
| `SYSTEM_MAPPING_PATH` | System → type map | `/opt/rgsx/system_mapping.json` |
| `FEED_TITLE` / `FEED_DESCRIPTION` | Feed metadata strings | `RGSX Library` / generated timestamp |
| `FEED_CATEGORY_PREFIX` | Prefix prepended to each category title | `""` |
| `ROM_PREFIX_URL` | Optional base URL if RGSX game entries only contain relative paths | unset |
| `FEED_RUN_ON_START` | Set to `0` to skip the initial run at container start | `1` |

Adjust the cron schedule by editing `cron/rgsx-feed`. For example, to run hourly change `*/30` to `0`.

## Local Testing

Use the sample `examples/rgsx-cache/` mount point referenced in `docker-compose.yml` as a placeholder while wiring things up. Once you have the real cache path, swap it in and rebuild the image:

```bash
docker compose build --no-cache
docker compose up -d
docker compose logs -f rgsx-webrcade
```

The logs will show whether the feed was generated successfully:

```
[rgsx-entrypoint] Running initial feed build...
2024-05-01 00:00:00 INFO Feed written to /var/www/html/content/feeds/rgsx_feed.json
[rgsx-entrypoint] Starting cron daemon.
[rgsx-entrypoint] Handing off to base image entrypoint.
```

## Continuous Rebuild Automation

Copy the workflow template at `.github/workflows/upstream-sync.yml` to the root of your new repository (preserving the path). The workflow:

* checks the upstream `webrcade/webrcade` main branch every hour (plus manual trigger)
* skips the build if the latest commit was already processed
* rebuilds the container, pushes tags to GitHub Container Registry, and publishes a GitHub release keyed to the upstream commit

Before enabling it, ensure that:

* repository → Settings → Actions → General allows GitHub Actions to create releases
* `GITHUB_TOKEN` has permission to write packages (default for public repos) so the workflow can push to `ghcr.io`
* if you rename the image or repository, update `IMAGE_ROOT` inside the workflow file accordingly

After committing, you can kick off the first run from the “Actions” tab via the `workflow_dispatch` trigger.

## Next Steps

* Expand `scripts/system_mapping.json` to cover every platform you use in RGSX.
* Host thumbnails/backgrounds referenced in your RGSX metadata so they load correctly in webЯcade.
* Optional: push the built image to your container registry and reference it from other compose stacks.
