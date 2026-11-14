import sys
from pypdf import PdfReader

reader = PdfReader(sys.argv[1])
text = "\n".join(page.extract_text() for page in reader.pages)
sys.stdout.buffer.write(text.encode("utf-8"))
