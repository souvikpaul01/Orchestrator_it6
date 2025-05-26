import requests

image_path = "test.png"
endpoint = "http://localhost:30080/upload"

with open(image_path, "rb") as img_file:
    files = {"file": ("input.png", img_file, "image/png")}
    response = requests.post(endpoint, files=files)

    if response.status_code == 200:
        with open("grayscale_result.png", "wb") as out_file:
            out_file.write(response.content)
        print("✅ Grayscale image saved.")
    else:
        print("❌ Failed:", response.text)
