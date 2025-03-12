import os
import subprocess
import logging
import tempfile
import re
from flask import Flask, request, send_file, jsonify

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)

def safe_remove(file_path):
    """Menghapus file sementara jika masih ada."""
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
        duration = hours * 3600 + minutes * 60 + seconds - 1  # Kurangi 1 detik biar unik
    else:
        logging.error("Gagal mendapatkan durasi video!")
        safe_remove(input_path)
        return jsonify({"error": "Failed to get video duration!"}), 500

    # FFmpeg Command (Optimized & Fixed)
    command = [
        ffmpeg_path, "-y",
        "-loglevel", "info",  # Logging tambahan
        "-hide_banner",
        "-fflags", "+genpts",  # FIX: Perbaiki timestamp
        "-r", "30",  # FPS tetap 30
        "-vsync", "vfr",
        "-i", input_path,
        "-t", str(duration - 1),  # Potong 1 detik akhir biar unik
        "-vf", "eq=contrast=1.02:brightness=0.02:saturation=1.04",  # Efek warna tetap
        "-c:v", "libx264",
        "-preset", "faster",  # FIX: Encoding lebih ringan
        "-crf", "28",  # FIX: Kurangi beban encoding
        "-b:v", "1200k",  # Turunkan bitrate sedikit
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "96k",  # Turunkan bitrate audio
        "-af", "asetrate=44100*1.004, atempo=0.996, volume=1.02",  # FIX: Lebih stabil
        "-movflags", "+faststart",
        "-map_metadata", "-1",  # Hapus metadata asli
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

    # Hapus file sementara
    safe_remove(input_path)
    safe_remove(output_path)

    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
