#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data.json"
BACKUP = ROOT / "data-last-good.json"
OVERLAY = ROOT / "pet-overlay.json"
REQUIRED = ("deals", "coupons", "claims", "subscriptions", "instore")

private_code = re.compile(r"(?:CUSTR-|REDACTED|PERSONALI[ZS]ED)", re.I)
internal_ref = re.compile(r"(?:mail\.google\.com|\bGmail\b|message/thread\s+[0-9a-f]{8,}|\bthread\s+[0-9a-f]{8,})", re.I)
email_re = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)


def load(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def stable_key(kind, item):
    if kind == "deals":
        return item.get("dealId") or item.get("deal")
    if kind == "coupons":
        return item.get("couponId") or item.get("dealId") or "|".join(str(item.get(k, "")) for k in ("brand", "coupon", "expiry"))
    if kind == "claims":
        return item.get("claimId") or item.get("dealId") or item.get("product")
    if kind == "subscriptions":
        return item.get("dealId") or "|".join(str(item.get(k, "")) for k in ("brand", "product"))
    if kind == "instore":
        return item.get("dealId") or "|".join(str(item.get(k, "")) for k in ("brand", "product", "retailer"))
    return None


def clean_text(value):
    if not isinstance(value, str):
        return value
    value = email_re.sub("", value)
    if internal_ref.search(value):
        return ""
    return value.strip()


def sanitize_item(kind, item):
    item = dict(item)
    if kind == "deals" and private_code.search(str(item.get("code", ""))):
        return None
    for k, v in list(item.items()):
        if isinstance(v, str):
            if k in ("dealLink", "terms", "claimUrl") and v and not re.match(r"^https?://", v, re.I):
                item.pop(k, None)
                continue
            cleaned = clean_text(v)
            if cleaned:
                item[k] = cleaned
            else:
                item.pop(k, None)
    return item


def merge_list(kind, base_items, upserts, removals):
    removal_set = set(removals or [])
    out = []
    index = {}
    for raw in base_items:
        item = sanitize_item(kind, raw)
        if not item:
            continue
        key = stable_key(kind, item)
        if key in removal_set:
            continue
        if key and key in index:
            out[index[key]] = item
        else:
            if key:
                index[key] = len(out)
            out.append(item)
    for raw in upserts or []:
        item = sanitize_item(kind, raw)
        if not item:
            continue
        key = stable_key(kind, item)
        if not key:
            raise ValueError(f"{kind} upsert lacks stable key: {item}")
        if key in index:
            out[index[key]] = item
        else:
            index[key] = len(out)
            out.append(item)
    return out


def validate(candidate, base, overlay):
    for name in REQUIRED:
        if name not in candidate or not isinstance(candidate[name], list):
            raise ValueError(f"missing/invalid top-level array: {name}")
        seen = set()
        for item in candidate[name]:
            key = stable_key(name, item)
            if key and key in seen:
                raise ValueError(f"duplicate {name} stable key: {key}")
            if key:
                seen.add(key)
            text = json.dumps(item, ensure_ascii=False)
            if internal_ref.search(text) or email_re.search(text):
                raise ValueError(f"private/internal text survived in {name}: {key}")
            if kind_has_private_code(name, item):
                raise ValueError(f"personalised code survived in {name}: {key}")
    # This pet merge must never wipe the unrelated public feed.
    if len(candidate["deals"]) < max(0, len(base.get("deals", [])) - 3):
        raise ValueError("sudden deal-count drop; refusing publish")
    expected = overlay.get("expected", {})
    for deal_id in expected.get("dealIds", []):
        if not any(x.get("dealId") == deal_id for x in candidate["deals"]):
            raise ValueError(f"expected deal missing after merge: {deal_id}")
    for deal_id in expected.get("subscriptionDealIds", []):
        if not any(x.get("dealId") == deal_id for x in candidate["subscriptions"]):
            raise ValueError(f"expected subscription missing after merge: {deal_id}")


def kind_has_private_code(kind, item):
    return kind == "deals" and private_code.search(str(item.get("code", ""))) is not None


def main():
    base = load(DATA)
    overlay = load(OVERLAY)
    for name in REQUIRED:
        base.setdefault(name, [])
    # Save the exact currently-working public feed before changing it.
    BACKUP.write_text(json.dumps(base, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    candidate = dict(base)
    candidate["version"] = max(int(base.get("version", 0)) + 1, int(overlay.get("version", 0)))
    candidate["generatedAt"] = overlay.get("generatedAt") or base.get("generatedAt")
    candidate["source"] = "Coupon Hunt HQ public feed"

    for name in REQUIRED:
        candidate[name] = merge_list(
            name,
            base.get(name, []),
            overlay.get(name, []),
            overlay.get("remove", {}).get(name, []),
        )

    for override in overlay.get("dealStatusOverrides", []):
        target_id = override.get("dealId")
        target_name = override.get("deal")
        for item in candidate["deals"]:
            if (target_id and item.get("dealId") == target_id) or (target_name and item.get("deal") == target_name):
                item["status"] = override["status"]

    validate(candidate, base, overlay)
    DATA.write_text(json.dumps(candidate, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({
        "version": candidate["version"],
        "deals": len(candidate["deals"]),
        "coupons": len(candidate["coupons"]),
        "claims": len(candidate["claims"]),
        "subscriptions": len(candidate["subscriptions"]),
        "instore": len(candidate["instore"]),
    }))


if __name__ == "__main__":
    main()
