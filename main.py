import os
import subprocess
import logging
import tempfile
from flask import Flask, request, send_file, jsonify

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "FFmpeg API for Reels is running!"

@app.route("/process-video", methods=["POST"])
def process_video():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded!"}), 400

    file = request.files["file"]

    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    input_path = temp_input.name
    file.save(input_path)

    temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    output_path = temp_output.name

    logging.info(f"Processing video: {input_path}")

    command = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
               "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
               "eq=contrast=1.05:brightness=0.03:saturation=1.08,"
               "hue=h=2*t,"
               "noise=alls=6:allf=t,"
               "mpdecimate,"
               "rotate=0.02*sin(2*PI*t/10),"  # Rotasi kecil yang berubah seiring waktu
               "boxblur=1:1,"
               "chromashift=-2",  # Ubah warna RGB sedikit
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "21",
        "-b:v", "3500k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-af", "asetrate=44100*1.02, atempo=0.98, volume=1.02, "
               "stereotools=mlev=0.015,"
               "rubberband=pitch=0.99,"
               "afftdn,"
               "aecho=0.8:0.88:6:0.4",
        "-movflags", "+faststart",
        "-map_metadata", "-1",
        "-metadata", "title=Edited for Reels",
        "-metadata", "encoder=CustomEncoder",
        "-metadata", "comment=Processed by Custom Pipeline",
        "-metadata", "creation_time=2024-02-10T12:00:00Z",  # Set metadata palsu
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
