import os
import subprocess
import logging
from flask import Flask, request, send_file, jsonify

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

@app.route("/", methods=["GET"])
def home():
    return "FFmpeg API is running!"

@app.route("/process-video", methods=["POST"])
def process_video():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded!"}), 400

    file = request.files["file"]
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    output_path = os.path.join(PROCESSED_FOLDER, f"modified_{file.filename}")

    file.save(input_path)
    logging.info(f"File saved: {input_path}")

    # Cek FFmpeg
    ffmpeg_path = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True).stdout.strip()
    if not ffmpeg_path:
        ffmpeg_path = "ffmpeg"

    # Jalankan FFmpeg dengan pengaturan agar sulit dideteksi
    command = [
        ffmpeg_path, "-y",
        "-i", input_path,
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2, noise=alls=10:allf=t, eq=brightness=0.02",
        "-r", "23.976",
        "-c:v", "libx264", "-preset", "medium", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k",
        output_path
    ]

    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    logging.info(f"FFmpeg Output:\n{result.stdout}")
    logging.error(f"FFmpeg Error:\n{result.stderr}")

    if result.returncode != 0 or not os.path.exists(output_path):
        return jsonify({"error": "FFmpeg failed!"}), 500

    response = send_file(output_path, as_attachment=True)

    # Hapus file untuk hemat storage
    os.remove(input_path)
    os.remove(output_path)

    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
