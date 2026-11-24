"""Writes, reads back and deletes a small test file through the configured attachment store (a deployment check)."""
from app.services.attachment_store import get_attachment_store

store = get_attachment_store()
key = "healthcheck/test.pdf"
data = b"%PDF-1.4 deployment check"
print("store:", type(store).__name__)
store.save(key, data, "application/pdf")
print("read back matches:", store.read(key) == data)
store.delete(key)
print("deleted: ok")
