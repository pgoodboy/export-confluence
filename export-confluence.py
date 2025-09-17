#!/usr/bin/env python3
import os
import time
import requests
from requests.utils import requote_uri
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv

# -----------------------------
# Load credentials from .env
# -----------------------------
load_dotenv()
USERNAME = os.getenv("CONFLUENCE_USER")
PASSWORD = os.getenv("CONFLUENCE_PASS")
BASE_URL = os.getenv("CONFLUENCE_BASE_URL")  # e.g., https://your-domain.atlassian.net/wiki

if not USERNAME or not PASSWORD or not BASE_URL:
    print("❌ Missing CONFLUENCE_USER, CONFLUENCE_PASS, or CONFLUENCE_BASE_URL in .env")
    exit(1)

EXPORT_DIR = "exported"
os.makedirs(EXPORT_DIR, exist_ok=True)

# -----------------------------
# Load pages from pages.txt
# -----------------------------
with open("pages.txt", "r") as f:
    pages = [line.strip() for line in f if line.strip()]

if not pages:
    print("❌ No pages found in pages.txt")
    exit(1)

# -----------------------------
# Setup session
# -----------------------------
session = requests.Session()
session.auth = (USERNAME, PASSWORD)

# -----------------------------
# Helpers
# -----------------------------
def sanitize_filename(name: str) -> str:
    """Make a safe filename from page title."""
    decoded = unquote(name)
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in decoded)
    return safe

def wait_for_task_completion(task_id, timeout=300, interval=5):
    """
    Poll the task progress API until completion or timeout.
    Returns the `result` URL when done.
    """
    progress_url = f"{BASE_URL}/wiki/services/api/v1/task/{task_id}/progress"
    elapsed = 0
    while elapsed < timeout:
        resp = session.get(progress_url, headers={"X-Atlassian-Token": "no-check"})
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch task progress (HTTP {resp.status_code})")
        data = resp.json()
        progress = data.get("progress", 0)
        state = data.get("state", "")
        print(f"⏳ Task {task_id}: {progress}% complete ({state})")
        if progress >= 100:
            return data.get("result")
        time.sleep(interval)
        elapsed += interval
    raise TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")

def download_pdf(s3_url, filename):
    """
    Download PDF from S3 presigned URL (no auth headers).
    """
    from requests.utils import requote_uri
    s3_url = requote_uri(s3_url)
    # Do NOT use session.auth here
    with requests.get(s3_url, stream=True,headers={"Sec-Fetch-Site": "cross-site"}) as r:
        if r.status_code in (200, 304):
            with open(filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"✅ Saved {filename}")
        else:
            raise RuntimeError(f"Failed to download PDF from S3 (HTTP {r.status_code})")


# -----------------------------
# Main loop
# -----------------------------
results = []

for page_url in pages:
    print(f"\n🔗 Processing: {page_url}")
    parsed = urlparse(page_url)

    # Extract pageId from URL
    try:
        page_id = parsed.path.split("/pages/")[1].split("/")[0]
    except IndexError:
        print(f"⚠️ Could not extract pageId from URL: {page_url}")
        results.append((page_url, None, "Missing pageId"))
        continue

    export_url = f"{BASE_URL}/wiki/spaces/flyingpdf/pdfpageexport.action?pageId={page_id}"

    try:
        # Step 1: Kick off PDF export
        resp = session.get(export_url, headers={"X-Atlassian-Token": "no-check"})
        if resp.status_code != 200:
            print(f"⚠️ Failed export request (HTTP {resp.status_code})")
            results.append((page_url, None, f"HTTP {resp.status_code}"))
            continue

        # Step 2: Extract taskId from meta tag
        soup = BeautifulSoup(resp.text, "html.parser")
        meta = soup.find("meta", {"name": "ajs-taskId"})
        if not meta or not meta.get("content"):
            print(f"⚠️ Could not find taskId in export HTML")
            results.append((page_url, None, "Missing taskId"))
            continue
        task_id = meta["content"]
        print(f"🆔 Found taskId: {task_id}")

        # Step 3: Poll task progress until PDF is ready
        result_url = wait_for_task_completion(task_id)
        if not result_url:
            print(f"⚠️ Task completed but no result URL returned")
            results.append((page_url, None, "Missing result URL"))
            continue
        if result_url.startswith("/"):
            result_url = BASE_URL + result_url

        # Step 4: Fetch S3 presigned URL from result
        resp = session.get(result_url, headers={"X-Atlassian-Token": "no-check"})
        if resp.status_code != 200:
            print(f"⚠️ Failed to fetch S3 URL (HTTP {result_url} {resp.status_code})")
            results.append((page_url, None, f"HTTP {resp.status_code}"))
            continue
        s3_url = resp.text.strip().strip('"')
        s3_url = requote_uri(s3_url)
        print(f"⬇️ Downloading PDF from S3: {s3_url}")

        # Step 5: Download PDF
        safe_title = sanitize_filename(parsed.path.split("/")[-1])
        filename = os.path.join(EXPORT_DIR, f"{safe_title}.pdf")
        download_pdf(s3_url,filename)

    except Exception as e:
        print(f"❌ Error processing {page_url}: {e}")
        results.append((page_url, None, str(e)))

# -----------------------------
# Summary
# -----------------------------
print("\n📊 Summary:")
for url, file, status in results:
    if file:
        print(f"✅ {url} -> {file}")
    else:
        print(f"❌ {url} -> {status}")
