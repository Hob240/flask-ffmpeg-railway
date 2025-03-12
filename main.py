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

    # Cek FFmpeg
    ffmpeg_path = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True).stdout.strip()
    if not ffmpeg_path:
        ffmpeg_path = "ffmpeg"

    # Ambil durasi video
    duration_cmd = [
        ffmpeg_path, "-i", input_path
    ]
    duration_result = subprocess.run(duration_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Gunakan regex untuk mencari durasi jika metode sebelumnya gagal
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", duration_result.stderr)
    
    if match:
        hours, minutes, seconds = map(float, match.groups())
        duration = hours * 3600 + minutes * 60 + seconds - 1  # Kurangi 1 detik
    else:
        logging.error("Gagal mendapatkan durasi video!")
        os.remove(input_path)
        return jsonify({"error": "Failed to get video duration!"}), 500

    # Perbaikan Scale, Encoding, Audio, dan Randomisasi agar sulit dideteksi
    command = [
        ffmpeg_path, "-y",
        "-ss", "0.5",  # Potong 0.5 detik awal
        "-i", input_path,
        "-t", str(duration),  # Potong 0.5 detik akhir
        "-vf", "scale=w=1280:h=720:force_original_aspect_ratio=decrease,"
               "pad=1280:720:(ow-iw)/2:(oh-ih)/2,"
               "gblur=sigma=0.3,unsharp=5:5:0.8:5:5:0.8,"
               "drawtext=text='CustomWatermark':x=10:y=10:fontsize=10:fontcolor=white@0.1,"
               "tblend=all_mode=average,"  # Frame blending untuk mengubah frame pattern
               "eq=contrast=1.02:brightness=0.02:saturation=0.98,"  # Sedikit tweak warna
               "noise=alls=20:allf=t",  # Tambahkan noise agar berbeda
        "-r", "23.976",
        "-c:v", "libx264",  # Tetap menggunakan H.264 seperti permintaanmu
        "-preset", "veryfast",
        "-crf", "26",
        "-b:v", "1000k",
        "-c:a", "aac",
        "-b:a", "128k",
        "-af", "asetrate=44100*1.02, atempo=0.98, volume=1.03, "
               "aecho=0.8:0.88:60:0.4, aphaser",  # Tambahkan efek suara agar sulit dikenali
        "-movflags", "+faststart",
        "-map_metadata", "-1",  # Hapus metadata sepenuhnya
        "-pix_fmt", "yuv420p",
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
