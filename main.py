import os
import subprocess
import logging
import tempfile
import re
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

    # Cek apakah FFmpeg tersedia
    ffmpeg_path = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True).stdout.strip()
    if not ffmpeg_path:
        ffmpeg_path = "ffmpeg"

    # Ambil durasi video
    duration_cmd = [ffmpeg_path, "-i", input_path]
    duration_result = subprocess.run(duration_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", duration_result.stderr)
    
    if match:
        hours, minutes, seconds = map(float, match.groups())
        duration = hours * 3600 + minutes * 60 + seconds - 1  # Kurangi 1 detik agar unik
    else:
        logging.error("Gagal mendapatkan durasi video!")
        os.remove(input_path)
        return jsonify({"error": "Failed to get video duration!"}), 500

    # Filter agar video mirip Reels dan sulit dideteksi
    command = [
        ffmpeg_path, "-y",
        "-ss", "0.5",  # Hilangkan 0.5 detik awal
        "-i", input_path,
        "-t", str(duration),  # Hilangkan 1 detik terakhir
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
               "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
               "eq=contrast=1.05:brightness=0.03:saturation=1.08,"
               "hue=h=2*t,"
               "noise=alls=6:allf=t,"
               "mpdecimate,"
               "rotate=0.01*sin(2*PI*t/8),"  # Rotasi kecil agar unik
               "chromashift=-2,"
               "boxblur=1:1",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-b:v", "3500k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-af", "asetrate=44100*1.02, atempo=0.98, volume=1.02, "
               "rubberband=pitch=0.99,"
               "afftdn",
        "-movflags", "+faststart",
        "-map_metadata", "-1",
        "-metadata", "title=Edited",
        "-metadata", "encoder=CustomEncoder",
        "-metadata", "comment=Processed by Custom Pipeline",
        "-metadata", "creation_time=now",
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
