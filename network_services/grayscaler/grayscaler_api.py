from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
from PIL import Image
import gzip
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

@app.post("/process")
async def decompress_and_grayscale(file: UploadFile = File(...)):
    try:
        compressed_data = await file.read()

        # Decompress
        with gzip.GzipFile(fileobj=BytesIO(compressed_data), mode='rb') as gz:
            image_bytes = gz.read()

        # Convert to grayscale
        image = Image.open(BytesIO(image_bytes)).convert("L")

        output = BytesIO()
        image.save(output, format="PNG")
        output.seek(0)

        return StreamingResponse(output, media_type="image/png")

    except Exception as e:
        logging.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process image")
