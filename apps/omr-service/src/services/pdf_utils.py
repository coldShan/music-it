from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium


def pdf_first_page_to_png(pdf_path: Path, output_png: Path) -> Path:
    pdf = pdfium.PdfDocument(str(pdf_path))
    if len(pdf) == 0:
        raise ValueError("PDF has no pages")

    page = pdf[0]
    bitmap = page.render(scale=2.0)
    pil_image = bitmap.to_pil()
    image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(output_png), image)
    return output_png
