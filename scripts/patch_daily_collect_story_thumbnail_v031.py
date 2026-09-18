from __future__ import annotations

from pathlib import Path


PATCH_VERSION = "0.3.1"
TARGET = Path("scripts/daily_collect.py")


FETCH_BLOCK = '''        story_id = str(story.get("id") or "").strip()\n        media_type = str(story.get("media_type") or "").strip().upper()\n        media_url = str(story.get("media_url") or "").strip()\n\n        # Story representative still image\n        # IMAGE: the media itself is already an image.\n        # VIDEO: fetch Meta thumbnail_url once while the Story is active.\n        thumbnail_url = str(story.get("thumbnail_url") or "").strip()\n\n        if media_type == "IMAGE" and not thumbnail_url:\n            thumbnail_url = media_url\n\n        elif media_type == "VIDEO" and story_id and not thumbnail_url:\n            try:\n                detail = meta.get_instagram(\n                    story_id,\n                    params={\n                        "fields": "thumbnail_url",\n                    },\n                )\n                thumbnail_url = str(\n                    detail.get("thumbnail_url") or ""\n                ).strip()\n            except MetaAPIError as exc:\n                print(\n                    f"[WARN] Story thumbnail fetch failed "\n                    f"| story_id={story_id} | {exc}"\n                )\n\n'''

ROW_BLOCK = '''                "thumbnail_url": (\n                    thumbnail_url\n                ),\n\n'''


def main() -> None:
    print("=" * 78)
    print(f"Patch daily_collect Story Thumbnail v{PATCH_VERSION}")
    print("=" * 78)

    if not TARGET.exists():
        raise FileNotFoundError(f"Cannot find {TARGET}")

    text = TARGET.read_text(encoding="utf-8")

    if '"thumbnail_url": (' in text and 'Story representative still image' in text:
        print("[SKIP] daily_collect.py is already patched.")
        return

    backup = TARGET.with_name("daily_collect_pre_story_thumbnail_v063.py")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
        print(f"[BACKUP] {backup}")

    # Bump collector version only when the known version is present.
    text = text.replace('VERSION = "0.6.3"', 'VERSION = "0.6.4"', 1)

    # Insert thumbnail fetch logic immediately before rows.append() in collect_stories.
    story_section = text.find("def collect_stories(")
    if story_section < 0:
        raise RuntimeError("collect_stories() not found.")

    rows_append = text.find("        rows.append(\n", story_section)
    if rows_append < 0:
        raise RuntimeError("rows.append() inside collect_stories() not found.")

    text = text[:rows_append] + FETCH_BLOCK + text[rows_append:]

    # Insert thumbnail_url immediately after media_url field in the Story row.
    media_url_anchor = '''                "media_url": (\n                    story.get(\n                        "media_url"\n                    )\n                ),\n\n'''
    anchor_pos = text.find(media_url_anchor, rows_append)
    if anchor_pos < 0:
        raise RuntimeError("Story media_url row block not found. No file was overwritten.")

    insert_pos = anchor_pos + len(media_url_anchor)
    text = text[:insert_pos] + ROW_BLOCK + text[insert_pos:]

    TARGET.write_text(text, encoding="utf-8")

    print("[OK] scripts/daily_collect.py patched")
    print("     collector version: v0.6.4")
    print("     VIDEO -> thumbnail_url")
    print("     IMAGE -> media_url copied to thumbnail_url")
    print("=" * 78)
    print("PATCH COMPLETED")
    print("=" * 78)


if __name__ == "__main__":
    main()
