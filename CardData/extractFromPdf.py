import argparse
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract

def extract_text_from_scanned_pdf(pdf_path: str | Path, dpi: int = 300) -> list[str]:
    """
    Extract text from an image-only (scanned) PDF using Tesseract OCR.

    Args:
        pdf_path: Path to the PDF file.
        dpi: Resolution for page-to-image conversion (higher = slower but better).

    Returns:
        A list of recognized text, one entry per page, with internal
        newlines collapsed so each entry is a single line.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Convert all pages to images
    pages = convert_from_path(str(pdf_path), dpi=dpi)

    page_lines = []
    for page_image in pages:
        # Run OCR on each page image, flattened to a single line
        text = pytesseract.image_to_string(page_image)
        page_lines.append(" ".join(text.strip().split()))

    return page_lines


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract text from a PDF, one line per page."
    )
    parser.add_argument("pdf_file", type=Path, help="Path to the input PDF file.")
    parser.add_argument(
        "output_file", type=Path, help="Path to the output text file."
    )
    args = parser.parse_args()

    page_lines = extract_text_from_scanned_pdf(args.pdf_file)

    with open(args.output_file, "w") as f:
        for line in page_lines:
            f.write(line + "\n\n")