from pathlib import Path

import cv2


def preprocess_image(src: Path, dst: Path, *, scale_factor: float = 1.0) -> Path:
    image = cv2.imread(str(src), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Cannot read image: {src}")
    if scale_factor <= 0:
        raise ValueError("scale_factor must be greater than 0")

    if scale_factor != 1.0:
        height, width = image.shape[:2]
        resized_width = max(1, int(width * scale_factor))
        resized_height = max(1, int(height * scale_factor))
        interpolation = cv2.INTER_CUBIC if scale_factor > 1 else cv2.INTER_AREA
        image = cv2.resize(
            image,
            (resized_width, resized_height),
            interpolation=interpolation,
        )

    blurred = cv2.GaussianBlur(image, (3, 3), 0)
    normalized = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        41,
        11,
    )

    cv2.imwrite(str(dst), normalized)
    return dst
