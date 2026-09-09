#!/usr/bin/env bash
set -euo pipefail
rm -rf dist
mkdir dist
sed 's#</body>#<script src="engine-health.js?v=2"></script><script src="canonical-feed.js?v=1"></script></body>#' coupon-hunt-hq/index.html > dist/index.html
cp coupon-hunt-hq/manifest.webmanifest dist/manifest.webmanifest
cp coupon-hunt-hq/*.js dist/
