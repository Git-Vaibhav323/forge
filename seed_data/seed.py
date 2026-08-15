"""
Seeds the ForgeData backend with test data, against whatever is actually
live right now: project-service (M1) and file-service (M2), reached
through the gateway.

Only creates projects + uploads files -- that's all that's live. Everything
else (attributes, reviews, outputs) is still mock-only per the plan, so
those live in fixtures/attributes.json and fixtures/reviews.json for you
to load into frontend mocks or a future DB seed script once M4/M5 exist.

USAGE:
    python3 seed.py                      # seed everything in fixtures/projects.json
    python3 seed.py --base-url http://localhost:8000

The exact field names below (`name`, `goal`, `category` for project create;
`file` for the upload multipart field) are a best guess from the plan doc
-- they are NOT confirmed against shared/schemas.py. If a request 422s,
open http://localhost:8000/docs, check the real request schema, and adjust
the two spots marked `# ADJUST IF 422` below.
"""
import argparse
import json
import os
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures", "projects.json")
DATASHEETS = os.path.join(HERE, "datasheets")


def create_project(base_url, item):
    payload = {
        "name": item["name"],
        "goal": item["goal"],
        "category": item["category"],
    }  # ADJUST IF 422 -- match POST /api/projects body from /docs
    resp = requests.post(f"{base_url}/api/projects", json=payload, timeout=10)
    resp.raise_for_status()
    body = resp.json()
    project_id = body.get("id") or body.get("projectId") or body.get("project_id")
    if not project_id:
        print(f"  ! created but couldn't find an id field in response: {body}")
    return project_id, body


def upload_file(base_url, project_id, filepath):
    with open(filepath, "rb") as fh:
        files = {"file": (os.path.basename(filepath), fh, "application/pdf")}
        # ADJUST IF 422 -- match POST /api/projects/{id}/files from /docs
        resp = requests.post(
            f"{base_url}/api/projects/{project_id}/files", files=files, timeout=30
        )
    if resp.status_code == 409:
        print(f"    (duplicate, already uploaded: {os.path.basename(filepath)})")
        return None
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    with open(FIXTURES) as f:
        items = json.load(f)

    # quick health check first so failures are obvious
    try:
        h = requests.get(f"{args.base_url}/health", timeout=5)
        print(f"gateway health: {h.status_code} {h.text[:200]}")
    except requests.RequestException as e:
        print(f"Can't reach gateway at {args.base_url}: {e}")
        print("Is docker compose up and run-dev.sh running? See README.md.")
        sys.exit(1)

    created = {}
    for item in items:
        print(f"\n[{item['slug']}] creating project: {item['name']}")
        try:
            project_id, body = create_project(args.base_url, item)
        except requests.HTTPError as e:
            print(f"  ! project create failed: {e} -- {e.response.text[:300]}")
            continue
        created[item["slug"]] = project_id
        print(f"  -> project_id = {project_id}")

        for filename in item["files"]:
            filepath = os.path.join(DATASHEETS, filename)
            if not os.path.exists(filepath):
                print(f"  ! missing PDF: {filepath} (run make_datasheets.py first)")
                continue
            print(f"  uploading {filename} ...")
            try:
                result = upload_file(args.base_url, project_id, filepath)
                if result is not None:
                    doc_id = result.get("id") or result.get("documentId") or result
                    print(f"    -> document = {doc_id}")
            except requests.HTTPError as e:
                print(f"    ! upload failed: {e} -- {e.response.text[:300]}")

    print("\n--- summary ---")
    for slug, pid in created.items():
        print(f"  {slug:12s} -> {pid}")
    print(f"\n{len(created)}/{len(items)} projects created.")
    print("Everything past M2 (attributes, reviews, outputs) is still mock-only --")
    print("see fixtures/attributes.json and fixtures/reviews.json for that data.")


if __name__ == "__main__":
    main()
