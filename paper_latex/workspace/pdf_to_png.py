import fitz  # pymupdf
import os

pdf_path = "paper.pdf"
out_dir = "page_screenshots"
os.makedirs(out_dir, exist_ok=True)

doc = fitz.open(pdf_path)
for i, page in enumerate(doc):
    pix = page.get_pixmap(dpi=150)
    out_path = os.path.join(out_dir, f"page_{i+1:02d}.png")
    pix.save(out_path)
    print(f"Saved {out_path} ({pix.width}x{pix.height})")

doc.close()
print(f"Done: {len(doc)} pages")
