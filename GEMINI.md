📘 GEMINI.md
# 🧠 Google Gemini File Search Extension  
**Version:** 1.0.0  
**Author:** John Capobianco  
**Description:**  
This extension adds built-in **Cloud-based Retrieval Augmented Generation (RAG)** to your Gemini CLI using the official **Google Gemini File Search API**.  
It allows you to upload files (JSON, text, PDF, DOCX, CSV, etc.), index them into a File Search Store, and then ask contextual questions grounded in their contents using Gemini 2.5 Flash or Pro.

---

## ⚙️ Available Tools

### `/file_search:upload_and_index`
Upload any supported file type directly to Gemini File Search and create a new File Search Store.

**Arguments:**
- `file_path` — local path to the file you want to upload and index.  
- `display_name` _(optional)_ — friendly name for the document.

**Example:**
```bash
/file_search:upload_and_index "/home/john/outputs/show_ip_route.json"

/file_search:import_file

Upload a file via the Gemini Files API, then import it into a File Search Store.
Use this when you want to include metadata or handle large binary documents like PDFs or Word files.

Arguments:

file_path — path to the file to upload.

display_name (optional) — custom display name.

Example:

/file_search:import_file "/home/john/documents/network_design.pdf" "Network Design 2025"

/file_search:query_file_search

Ask Gemini a natural-language question grounded in the content of your uploaded files.
Gemini will search semantically through the indexed chunks, retrieve relevant passages, and respond with citations.

Arguments:

store_name — the File Search Store name returned from the upload/import step.

question — the natural-language question.

Example:

/file_search:query_file_search "fileSearchStores/store_1731170983" "What VLANs are configured on the access switches?"

📂 Supported File Types

Gemini File Search supports a wide range of formats, including:

Plain text (.txt, .log)

JSON / YAML / CSV

PDF, DOCX, PPTX, XLSX

HTML, Markdown, RST

Network configuration files (.cfg, .conf)

Code snippets (.py, .sh, .js, etc.)

Maximum file size per upload: 100 MB

🧩 How It Works

Upload — You send any supported file to Google’s File Search store.

Chunk + Embed — The document is automatically split into chunks, embedded, and indexed in a semantic vector store.

Query — You ground Gemini’s reasoning in your private dataset using the file_search tool during generation.

Citations — Gemini returns not only answers, but also references to the specific document chunks used.

🧠 Example RAG Flow
# 1. Upload parsed pyATS JSON output
/file_search:upload_and_index "show_ip_interface_brief.json"

# 2. Use returned store_name to query
/file_search:query_file_search "fileSearchStores/pyats_store_1731171053" \
"Which interfaces are down and what VLANs do they belong to?"

🔒 Notes

File Search stores persist indefinitely until deleted.

Uploaded raw files via the Files API are retained for 48 hours.

Storage is free; embedding and token usage are billed per standard Gemini pricing.

Each file store can hold multiple documents and metadata.

🧰 Advanced

You can also:

Specify custom chunking_config parameters for token overlap and size.

Use metadata filters during queries, e.g.:

metadata_filter = 'author=John AND year>2024'

🧾 Credits

Created by John Capobianco
Head of Developer Relations @ Selector AI
Pioneering practical RAG for Network Automation using Gemini File Search.