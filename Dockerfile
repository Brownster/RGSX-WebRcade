# syntax=docker/dockerfile:1.4
FROM webrcade/webrcade:latest

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 \
      python3-venv \
      python3-pip \
      cron \
      jq \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/rgsx

COPY scripts/build_feed.py ./build_feed.py
COPY scripts/system_mapping.json ./system_mapping.json
COPY scripts/run-feed.sh ./run-feed.sh
COPY cron/rgsx-feed /etc/cron.d/rgsx-feed

RUN chmod 0644 /etc/cron.d/rgsx-feed \
 && crontab /etc/cron.d/rgsx-feed \
 && chmod +x /opt/rgsx/run-feed.sh

COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV RGSX_DATA_PATH=/mnt/rgsx/saves/ports/RGSX \
    SYSTEM_MAPPING_PATH=/opt/rgsx/system_mapping.json \
    FEED_OUTPUT_PATH=/var/www/html/content/feeds/rgsx_feed.json \
    FEED_TITLE="RGSX Library" \
    FEED_DESCRIPTION="Feed generated from RGSX caches." \
    FEED_CATEGORY_PREFIX="" \
    FEED_RUN_ON_START=1 \
    NEOGEO_BIOS_URL="https://archive.org/download/neogeoaesmvscomplete/BIOS/neogeo.zip"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/home/start.sh"]
