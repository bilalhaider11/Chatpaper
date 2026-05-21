# Chatpaper — User Manual

Chatpaper lets you upload documents and ask questions about them in plain language. Answers are grounded in your documents and include numbered citations so you can verify exactly where each claim comes from.

---

## Supported File Types

| Format | Extensions |
|---|---|
| PDF | `.pdf` |
| Word document | `.docx`, `.doc` |
| Plain text | `.txt` |
| CSV spreadsheet | `.csv` |
| Excel spreadsheet | `.xlsx`, `.xls` |

Maximum file size: **200 MB** per upload (your administrator may have adjusted this).

> **Note:** Scanned PDFs (image-only, no embedded text) cannot be processed. The system will detect them and report a permanent failure. Convert to a searchable PDF using OCR software before uploading.

---

## Getting Started

### Creating an Account

1. Open the app in your browser (default: `http://localhost:5173`).
2. Click **Register** and enter your email address and a password.
3. Your account is created immediately — no email verification required.

If your organization has restricted open registration, ask your administrator to create an account for you.

### Logging In

Enter your email and password on the login page. Your session lasts 10 hours by default; after that you will be asked to log in again.

---

## Uploading Documents

1. Navigate to **Files** in the sidebar.
2. Click **Upload Document**.
3. Select a file from your computer.
4. Optionally enter a description to help identify the file later.
5. Click **Upload**.

After uploading, the document enters a background processing pipeline. This pipeline extracts the text, splits it into chunks, generates embeddings, and stores them for retrieval. This typically takes **30 seconds to a few minutes** depending on file size.

### Ingestion Status

Each document on the Files page shows a status badge:

| Status | Meaning |
|---|---|
| `QUEUED` | Waiting for a worker to pick it up |
| `STAGE_1` – `STAGE_7` | Actively being processed |
| `COMPLETE` | Ready — you can ask questions about this document |
| `FAILED_RETRYABLE` | A temporary error occurred; use **Re-ingest** to retry |
| `FAILED_PERMANENT` | A permanent error (e.g. scanned PDF); re-uploading will not help |

To see detailed status, click the document and select **Check Ingestion Status**.

### Re-ingesting a Document

If a file shows `FAILED_RETRYABLE`, open its detail page and click **Re-ingest**. This queues a fresh processing job. Documents that show `FAILED_PERMANENT` cannot be recovered without fixing the underlying issue (e.g. converting a scanned PDF first).

---

## Having a Conversation

### Starting a New Conversation

Click **New Conversation** in the sidebar. A new session is created. You can rename it at any time by clicking the title and typing a new name.

### Asking Questions

Type your question in the input box at the bottom and press **Enter** or click **Send**.

The system will:
1. Search your documents for the most relevant passages based on your question.
2. Combine those passages with your conversation history.
3. Generate an answer from the AI model.
4. Return the answer with numbered citations like `[1]`, `[2]`.

The cited passages appear below the answer, showing the source document name and the exact text used.

### Tips for Better Answers

- **Be specific.** "What methodology is described in Section 3 of the study?" works better than "Tell me about the study."
- **Follow-up questions work naturally.** You can ask "Can you expand on that?" or "What did they conclude there?" — the system uses your conversation history to understand references.
- **Scope to a specific document.** If you only want answers from one file, select it from the document picker before asking. Without a selection the system searches all your documents.
- **Rephrase if the answer is thin.** If the system says it could not find relevant information, try rewording your question. Retrieval is sensitive to phrasing.

---

## Managing Your Files

### Viewing All Files

The **Files** page lists all documents you have uploaded, with their ingestion status, upload date, and file size.

### Downloading a File

Open a file from the Files page and click **Download** to retrieve the original uploaded file.

### Deleting a File

Open a file and click **Delete**. This permanently removes:
- The file from disk
- All database records for that file
- All vector embeddings stored in ChromaDB

Conversations that referenced the deleted file remain in your history, but asking about that content again will no longer find relevant passages.

### File Privacy

Your files are private. Other users cannot see or access them. Administrators can view all files for platform management purposes.

---

## Understanding Citations

When the AI includes a citation like `[2]` in its answer, that number refers to a specific passage from your documents. The cited passages are shown below the answer with:
- The source document name
- The relevant text extract

If the AI generates an answer without any citation markers, it means the response was based on general knowledge rather than your documents — or the relevant passages were below the confidence threshold and excluded.

---

## Frequently Asked Questions

**Why is my document stuck in QUEUED?**
The background worker service (Celery) may not be running. Contact your administrator to check that the worker is active.

**My PDF failed with "likely scanned PDF." What does that mean?**
Your PDF contains images of text rather than actual text characters. There is no text to extract. Use OCR software (Adobe Acrobat, Tesseract, or an online service) to convert it to a searchable PDF, then re-upload.

**Can I upload the same document twice?**
The system detects duplicate content using a SHA-256 hash. If you upload a file with identical content under a different name, the second upload is flagged as a duplicate and skipped — it will not consume extra storage or compute.

**Why does the AI sometimes say it found nothing relevant?**
Each retrieved passage has a relevance score. Passages below the minimum threshold are excluded to prevent the AI from hallucinating answers based on unrelated content. Try rephrasing your question or making it more specific.

**How many documents can I upload?**
There is no hard limit on the number of documents. File size is capped at 200 MB per upload and 500 pages per document by default (your administrator may have adjusted these limits).

**My conversation history seems to affect answers from earlier questions. Is that intentional?**
Yes. The system includes your recent conversation turns when retrieving passages, which allows it to correctly interpret follow-up questions like "What did the paper say about that?" Without this, each question would be treated in isolation.
