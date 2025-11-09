import os
import mimetypes
import asyncio
import logging
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from google import genai
from google.genai import types

# --- Setup ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GeminiFileSearchMCP")

client = genai.Client()
mcp = FastMCP("Google Gemini File Search")

# --- Tool 1: Upload any file type and index it ---
@mcp.tool()
async def upload_and_index(file_path: str, display_name: str = None) -> str:
    """
    Upload *any* supported file (JSON, TXT, PDF, DOCX, CSV, etc.)
    to Gemini File Search for RAG augmentation.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} not found")

    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    display_name = display_name or os.path.basename(file_path)
    logger.info(f"📂 Uploading {display_name} ({mime_type})")

    store = client.file_search_stores.create(
        config={"display_name": f"store_{int(asyncio.get_event_loop().time())}"}
    )
    store_name = getattr(store, "name", str(store))
    logger.info(f"🪣 Created FileSearchStore: {store_name}")

    op = client.file_search_stores.upload_to_file_search_store(
        file_search_store_name=store_name,
        file=file_path,
        config={
            "display_name": display_name,
            "mime_type": mime_type,
            "chunking_config": {
                "white_space_config": {
                    "max_tokens_per_chunk": 500,
                    "max_overlap_tokens": 100
                }
            }
        }
    )

    op_name = getattr(op, "name", str(op))
    for _ in range(60):
        current = client.operations.get(op_name)
        if getattr(current, "done", False):
            logger.info("✅ Upload and indexing complete.")
            break
        await asyncio.sleep(3)

    return store_name

# --- Tool 2: Import via Files API (alternate flow) ---
@mcp.tool()
async def import_file(file_path: str, display_name: str = None) -> str:
    """
    Upload a file via Files API first, then import into File Search Store.
    This supports binary formats and metadata.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} not found")

    display_name = display_name or os.path.basename(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"

    sample_file = client.files.upload(
        file=file_path,
        config={"name": display_name, "mime_type": mime_type}
    )
    store = client.file_search_stores.create(config={"display_name": display_name})
    logger.info(f"🪣 Created FileSearchStore: {store.name}")

    op = client.file_search_stores.import_file(
        file_search_store_name=store.name,
        file_name=sample_file.name
    )

    op_name = getattr(op, "name", str(op))
    for _ in range(60):
        current = client.operations.get(op_name)
        if getattr(current, "done", False):
            logger.info("✅ File imported and indexed.")
            break
        await asyncio.sleep(3)

    return store.name

# --- Tool 3: Ask questions grounded in a File Search store ---
@mcp.tool()
async def query_file_search(store_name: str, question: str) -> dict:
    """
    Ask Gemini a natural-language question grounded in the uploaded file(s).
    """
    if not store_name or not question:
        raise ValueError("Missing store_name or question.")

    loop = asyncio.get_event_loop()
    resp = await loop.run_in_executor(
        None,
        lambda: client.models.generate_content(
            model="gemini-2.5-flash",
            contents=question,
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store_name]
                        )
                    )
                ]
            )
        )
    )

    grounding = getattr(resp.candidates[0], "grounding_metadata", None)
    sources = []
    if grounding and getattr(grounding, "grounding_chunks", None):
        sources = [c.retrieved_context.title for c in grounding.grounding_chunks]

    return {
        "answer": resp.text,
        "sources": sources,
        "store": store_name
    }

# --- Tool 4: List all File Search stores ---
@mcp.tool()
async def list_stores() -> list:
    """List all available File Search Stores."""
    stores = client.file_search_stores.list()
    return [s.to_dict() if hasattr(s, "to_dict") else s for s in stores]

# --- Tool 5: Get metadata for a specific store ---
@mcp.tool()
async def get_store(store_name: str) -> dict:
    """Retrieve metadata for a specific File Search Store."""
    store = client.file_search_stores.get(name=store_name)
    return store.to_dict() if hasattr(store, "to_dict") else dict(store)

# --- Tool 6: Delete a File Search store ---
@mcp.tool()
async def delete_store(store_name: str, force: bool = False) -> str:
    """Delete a File Search Store (optionally force-remove documents)."""
    client.file_search_stores.delete(name=store_name, config={"force": force})
    return f"🗑️ Deleted File Search Store: {store_name} (force={force})"

if __name__ == "__main__":
    logger.info("🚀 Starting Gemini File Search MCP Server...")
    mcp.run()
