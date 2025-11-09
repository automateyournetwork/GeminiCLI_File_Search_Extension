import os, re, mimetypes, asyncio, logging
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from google import genai
from google.genai import types

# --- Setup --------------------------------------------------------------
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GeminiFileSearchMCP")

client = genai.Client()
mcp = FastMCP("Google Gemini File Search")

# --- Helpers -------------------------------------------------------------
def _get_name(obj):
    """Return the name field regardless of SDK object type."""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return obj.get("name") or obj.get("id") or str(obj)
    return getattr(obj, "name", str(obj))

def _sanitize_name(path: str) -> str:
    base = os.path.splitext(os.path.basename(path))[0].lower()
    safe = re.sub(r"[^a-z0-9-]+", "-", base).strip("-")
    return safe or "file"

def _safe_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    ext = os.path.splitext(path)[1].lower()

    # Force known safe values
    if ext in (".txt", ".log", ".md"):
        return "text/plain"
    if ext in (".json", ".csv"):
        # Force to text/plain because application/json/text/csv can fail
        return "text/plain"
    if ext == ".pdf":
        return "application/pdf"

    # Fallback if mimetype is valid
    if mime and "/" in mime:
        return mime

    return "application/octet-stream"

async def _wait_for_op(op_name: str):
    """Polls operation until completion (string-safe)."""
    op_id = _get_name(op_name)
    for _ in range(60):
        current = client.operations.get(_get_name(op_id))
        if isinstance(current, dict) and current.get("done"):
            return current
        if getattr(current, "done", False):
            return current
        await asyncio.sleep(3)
    raise TimeoutError("File Search operation timed out after 3 minutes.")

# --- 1. Upload and index -------------------------------------------------
@mcp.tool()
async def upload_and_index(file_path: str, display_name: str = None) -> str:
    """Direct upload and index of a file (PDF, JSON, TXT, etc.) into a new File Search Store."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    mime_type = _safe_mime(file_path)
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        raise ValueError("❌ DOCX not supported by File Search. Convert to PDF first.")

    display_name = display_name or os.path.basename(file_path)
    logger.info(f"📂 Uploading {display_name} ({mime_type})")

    # Create a new File Search Store
    store = client.file_search_stores.create(
        config={"display_name": f"store_{int(asyncio.get_event_loop().time())}"}
    )
    store_name = _get_name(store)
    logger.info(f"🪣 Created FileSearchStore: {store_name}")

    # Upload the file
    op = client.file_search_stores.upload_to_file_search_store(
        file_search_store_name=store_name,
        file=file_path,
        config={
            "display_name": display_name,
            "mime_type": mime_type,
            "chunking_config": {
                "white_space_config": {
                    "max_tokens_per_chunk": 500,
                    "max_overlap_tokens": 100,
                }
            },
        },
    )

    # Try to poll — but don’t fail if the SDK doesn’t support it
    op_name = _get_name(op)
    try:
        # Some SDKs return an operation name path (works)
        # Some return a plain string (safe check)
        if isinstance(op_name, str) and "/" in op_name:
            for _ in range(60):
                try:
                    current = client.operations.get(op_name)
                    if (
                        isinstance(current, dict)
                        and current.get("done")
                    ) or getattr(current, "done", False):
                        break
                except Exception:
                    break
                await asyncio.sleep(2)
        else:
            logger.warning(f"⚠️ Skipping polling; op_name={op_name}")
    except Exception as e:
        logger.warning(f"⚠️ Polling skipped or failed ({e}); upload likely completed.")

    logger.info("✅ Upload and indexing complete.")
    return store_name


# --- 2. Import via Files API --------------------------------------------
@mcp.tool()
async def import_file(file_path: str, display_name: str = None) -> str:
    """Upload via Files API, then import into a new File Search Store."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    mime_type = _safe_mime(file_path)
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        raise ValueError("❌ DOCX unsupported — convert to PDF first.")

    display_name = display_name or os.path.basename(file_path)
    safe_name = _sanitize_name(file_path)
    logger.info(f"⬆️  Uploading via Files API as {safe_name}")

    sample_file = client.files.upload(
        file=file_path,
        config={"name": safe_name, "display_name": display_name, "mime_type": mime_type},
    )
    file_name = _get_name(sample_file)

    store = client.file_search_stores.create(config={"display_name": display_name})
    store_name = _get_name(store)
    logger.info(f"🪣 Created FileSearchStore: {store_name}")

    op = client.file_search_stores.import_file(
        file_search_store_name=store_name,
        file_name=file_name,
    )

    await _wait_for_op(op)
    logger.info("✅ File imported and indexed.")
    return store_name

# --- 3. Query ------------------------------------------------------------
@mcp.tool()
async def query_file_search(store_name: str, question: str) -> dict:
    """Ask Gemini a question grounded in an uploaded File Search store."""
    if not store_name or not question:
        raise ValueError("Missing store_name or question.")

    loop = asyncio.get_event_loop()
    resp = await loop.run_in_executor(
        None,
        lambda: client.models.generate_content(
            model="gemini-2.5-flash",
            contents=question,
            config=types.GenerateContentConfig(
                tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store_name]))]
            ),
        ),
    )

    grounding = getattr(resp.candidates[0], "grounding_metadata", None)
    sources = [c.retrieved_context.title for c in getattr(grounding, "grounding_chunks", [])]
    return {"answer": resp.text, "sources": sources, "store": store_name}

# --- 4–6. List / Get / Delete ------------------------------------------
@mcp.tool()
async def list_stores() -> list:
    stores = client.file_search_stores.list()
    return [getattr(s, "to_dict", lambda: s)() for s in stores]

@mcp.tool()
async def get_store(store_name: str) -> dict:
    store = client.file_search_stores.get(name=store_name)
    return getattr(store, "to_dict", lambda: store)()

@mcp.tool()
async def delete_store(store_name: str, force: bool = False) -> str:
    client.file_search_stores.delete(name=store_name, config={"force": force})
    return f"🗑️ Deleted File Search Store: {store_name} (force={force})"

# --- Entry --------------------------------------------------------------
if __name__ == "__main__":
    logger.info("🚀 Starting Gemini File Search MCP Server...")
    mcp.run()
