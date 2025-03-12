import os
import subprocess
import logging
import tempfile
from flask import Flask, request, send_file, jsonify

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "FFmpeg API is running!"

@app.route("/process-video", methods=["POST"])
def process_video():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded!"}), 400

    file = request.files["file"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_input:
        input_path = temp_input.name
        file.save(input_path)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_output:
        output_path = temp_output.name

    logging.info(f"Processing video: {input_path}")

    # Cek FFmpeg
    ffmpeg_path = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True).stdout.strip()
    if not ffmpeg_path:
        ffmpeg_path = "ffmpeg"

    # Perbaikan Scale & Randomisasi Encoding agar sulit dideteksi Snapchat
    command = [
        ffmpeg_path, "-y",
        "-i", input_path,
        "-vf", "scale=w=1280:h=720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,eq=contrast=1.07:brightness=0.015:saturation=1.15,noise=alls=20:allf=t",
        "-r", "23.976",
        "-c:v", "libx264",  # Gunakan H.264 agar kompatibel
        "-preset", "veryfast",
        "-crf", "26",  # Kualitas sedikit dikompresi
        "-b:v", "1000k",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        "-map_metadata", "-1",  # Hapus metadata sepenuhnya
        "-pix_fmt", "yuv420p",
        "-metadata", "title=Edited",  # Ubah metadata
        "-metadata", "encoder=CustomEncoder",  # Buat metadata unik
        "-metadata", "comment=Processed by Custom Pipeline",  # Tambahkan comment metadata
        "-metadata", "creation_time=now",  # Ubah waktu pembuatan
        output_path
    ]

    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    logging.info(f"FFmpeg Output:\n{result.stdout}")
    logging.error(f"FFmpeg Error:\n{result.stderr}")

    if result.returncode != 0 or not os.path.exists(output_path):
        os.remove(input_path)
        return jsonify({"error": "FFmpeg failed!"}), 500

    response = send_file(output_path, as_attachment=True)

    # Hapus file sementara
    os.remove(input_path)
    os.remove(output_path)

    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
