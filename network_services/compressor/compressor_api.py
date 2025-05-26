
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
from PIL import Image
import gzip
import requests
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

DECOMPRESSOR_URL = "http://grayscaler-service:8012/process" 

@app.post("/upload")
async def receive_image(file: UploadFile = File(...)):
    try:
        # Read image bytes from upload
        img_data = await file.read()
        
        # Convert to PIL and back to bytes (to validate and reformat)
        image = Image.open(BytesIO(img_data))
        image_bytes = BytesIO()
        image.save(image_bytes, format="PNG")
        image_bytes.seek(0)

        # Compress the image bytes
        compressed = BytesIO()
        with gzip.GzipFile(fileobj=compressed, mode="wb") as gz:
            gz.write(image_bytes.read())
        compressed.seek(0)

        # Send to decompressor
        files = {
            "file": ("image.gz", compressed, "application/octet-stream")
        }
        resp = requests.post(DECOMPRESSOR_URL, files=files)

        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        return StreamingResponse(BytesIO(resp.content), media_type="image/png")

    except Exception as e:
        logging.error(f"Compressor error: {e}")
        raise HTTPException(status_code=500, detail="Compressor failed")

