import os
import subprocess
import logging
import tempfile
import re
from flask import Flask, request, send_file, jsonify

# Konfigurasi logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # Maks 500MB upload

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

    # 🔍 Ambil durasi video dengan cara lebih akurat
    duration_cmd = [ffmpeg_path, "-i", input_path, "-f", "null", "-"]
    duration_result = subprocess.run(duration_cmd, stderr=subprocess.PIPE, text=True)

    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", duration_result.stderr)
    if match:
        hours, minutes, seconds = map(float, match.groups())
        duration = hours * 3600 + minutes * 60 + seconds  # Tidak dikurangi 1 detik
    else:
        logging.error("Gagal mendapatkan durasi video!")
        safe_remove(input_path)
        return jsonify({"error": "Failed to get video duration!"}), 500

    # ⚙️ Perintah FFmpeg dengan proteksi dari deteksi reupload
    command = [
        ffmpeg_path, "-y",
        "-loglevel", "info",
        "-hide_banner",
        "-fflags", "+genpts",
        "-r", "30",
        "-vsync", "vfr",
        "-i", input_path,

        # 🎨 Filter visual (diperbaiki)
        "-vf", "eq=contrast=1.02:brightness=0.02:saturation=1.04,"
               "noise=alls=4:allf=t,"  # Noise lebih dinamis
               "gblur=sigma=0.3,"  # Blur lebih halus
               "drawtext=text='\ \ ':fontsize=30:fontcolor=white@0.02:"  # Watermark acak per frame
               "x=rand(0\,w-50):y=rand(0\,h-50)",

        # 🎥 Encoding video
        "-c:v", "libx264",
        "-profile:v", "high",  # 🔥 FIX: Ubah profile ke High
        "-preset", "ultrafast",
        "-crf", "28",  # 🔥 FIX: Turunkan CRF untuk mengubah lebih banyak detail
        "-b:v", "1200k",
        "-pix_fmt", "yuv420p",

        # 🔊 Audio processing (diperbaiki)
        "-c:a", "aac",
        "-b:a", "128k",
        "-af", "rubberband=pitch=1.01,volume=1.02",  # Pitch shift lebih smooth

        # 🔄 Sinkronisasi dan optimasi
        "-strict", "-2",
        "-shortest",
        "-movflags", "+faststart",
        "-map_metadata", "-1",  # 🔥 Hapus semua metadata
        "-metadata", "title=New Video",
        "-metadata", "encoder=FFmpeg Custom",
        "-metadata", "comment=Processed by AI Pipeline",
        
        output_path
    ]

    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        logging.error("FFmpeg timeout! Video terlalu lama diproses.")
        safe_remove(input_path)
        safe_remove(output_path)
        return jsonify({"error": "Processing timeout!"}), 500

    logging.info(f"FFmpeg Exit Code: {result.returncode}")
    logging.debug(f"FFmpeg Output: {result.stdout}")  # Ubah ke debug agar tidak selalu tampil
    logging.error(f"FFmpeg Error: {result.stderr}" if result.returncode != 0 else "FFmpeg berhasil!")

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
