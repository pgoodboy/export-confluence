# Confluence PDF Exporter

This script automates exporting Confluence pages to PDF using the FlyingPDF add-on and downloads the exported files from S3.

---

## Workflow

```text
+-------------------+       +-------------------+       +-----------------+
|  pages.txt URLs   | ----> |  Export PDF Task  | ----> | Task Progress   |
|                   |       |  via FlyingPDF    |       | Polling         |
+-------------------+       +-------------------+       +-----------------+
                                                             |
                                                             v
                                                 +------------------------+
                                                 |  Get S3 Presigned URL  |
                                                 +------------------------+
                                                             |
                                                             v
                                                 +------------------------+
                                                 |  Download PDF locally  |
                                                 |  into ./exported/      |
                                                 +------------------------+
```

---

## Prerequisites

1. **Python 3.8+**
2. Install required Python packages:

```bash
pip install requests beautifulsoup4 python-dotenv
```

3. FlyingPDF / PDF Export app must be installed in your Confluence instance.
4. The user must have permission to view and export pages.

---

## Setup

1. Create a `.env` file with your Confluence credentials:

```env
CONFLUENCE_USER=your_email@example.com
CONFLUENCE_PASS=your_api_token_or_password
CONFLUENCE_BASE_URL=https://your-domain.atlassian.net/
```

2. Create a `pages.txt` file with one Confluence page URL per line:

```text
https://your-domain.atlassian.net/wiki/spaces/IS/pages/3443196578/Secure+Code+Review+Process
https://your-domain.atlassian.net/wiki/spaces/IS/pages/1234567890/Another+Page
```

---

## Usage

Run the script:

```bash
python export_confluence.py
```

* All PDFs will be saved in the `exported/` directory.
* Progress is printed in the console for each page.
* After completion, a summary table shows success/failure for each page.

---

## Notes

* The script polls the Confluence task API until the PDF export is completed.
* S3 presigned URLs are downloaded **without sending authentication headers**, as required by AWS S3.

---

## Directory Structure

```text
.
├── .env
├── pages.txt
├── export_confluence.py
└── exported/
```

---

## Troubleshooting

* **module 'collections' has no attribute 'Callable'**

  * add these 2 lines into the top of `export_confluence.py`
  ```
    import collections
    collections.Callable = collections.abc.Callable
  ```

* **404 on export request:**

  * Ensure `CONFLUENCE_BASE_URL` ends with `/wiki`.
  * Check that FlyingPDF / PDF Export is installed.
  * Confirm the user has view/export permission.

* **400/401/403 on S3 download:**

  * Ensure the download uses the presigned URL **without any auth headers**.
  * Download immediately after generating the export to avoid URL expiration.

* **Timeout waiting for task completion:**

  * Increase the `timeout` parameter in `wait_for_task_completion()` if large pages take longer to export.

---
