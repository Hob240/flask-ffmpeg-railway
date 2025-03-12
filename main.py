import os
import subprocess
import logging
import tempfile
import re
from flask import Flask, request, send_file, jsonify

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)

def safe_remove(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logging.warning(f"Gagal menghapus {file_path}: {e}")

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

    ffmpeg_path = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True).stdout.strip()
    if not ffmpeg_path:
        ffmpeg_path = "ffmpeg"

    duration_cmd = [ffmpeg_path, "-i", input_path]
    duration_result = subprocess.run(duration_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", duration_result.stderr)
    if match:
        hours, minutes, seconds = map(float, match.groups())
        duration = hours * 3600 + minutes * 60 + seconds - 1  
    else:
        logging.error("Gagal mendapatkan durasi video!")
        safe_remove(input_path)
        return jsonify({"error": "Failed to get video duration!"}), 500

    # 🔥 Versi lebih sulit dideteksi Content ID
    command = [
        ffmpeg_path, "-y",
        "-loglevel", "info",
        "-hide_banner",
        "-fflags", "+genpts",
        "-r", "29.89",  # ✅ FPS sedikit diubah
        "-vsync", "vfr",
        "-i", input_path,
        "-ss", "0.5",  # ✅ Potong sedikit di awal
        "-t", str(duration - 1.5),  # ✅ Potong sedikit di akhir
        "-vf", "eq=contrast=1.02:brightness=0.02:saturation=1.04,noise=alls=3:allf=t,drawtext=text=' ':fontcolor=white@0.01:x=10:y=10",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "30",
        "-b:v", "1000k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-af", "asetrate=44100*1.005, atempo=0.995, volume=1.02",  # ✅ Ubah pitch audio sedikit
        "-strict", "-2",
        "-shortest",
        "-movflags", "+faststart",
        "-map_metadata", "-1",
        "-metadata", "title=New Video",
        "-metadata", "encoder=FFmpeg Custom",
        "-metadata", "comment=Processed by AI Pipeline",
        output_path
    ]

    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    logging.info(f"FFmpeg Output:\n{result.stdout}")
    logging.error(f"FFmpeg Error:\n{result.stderr}")

    if result.returncode != 0 or not os.path.exists(output_path) or os.stat(output_path).st_size == 0:
        logging.error("FFmpeg gagal atau output video kosong!")
        safe_remove(input_path)
        safe_remove(output_path)
        return jsonify({"error": "FFmpeg failed or output file is empty!"}), 500

    response = send_file(output_path, as_attachment=True)

    safe_remove(input_path)
    safe_remove(output_path)

    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
