import os
import subprocess
import logging
import tempfile
import re
from flask import Flask, request, send_file, jsonify

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)

def safe_remove(file_path):
    """Menghapus file jika masih ada untuk menghindari error."""
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
        duration = hours * 3600 + minutes * 60 + seconds - 1  # Kurangi 1 detik agar unik
    else:
        logging.error("Gagal mendapatkan durasi video!")
        safe_remove(input_path)
        return jsonify({"error": "Failed to get video duration!"}), 500

    # Perbaikan: Pindahkan "-r 29.97" sebelum "-i"
    command = [
        ffmpeg_path, "-y",
        "-r", "29.97",  # **Letakkan sebelum "-i" untuk menghindari error**
        "-ss", "1",  # Potong 1 detik awal
        "-i", input_path,
        "-t", str(duration - 1),  # Potong 1 detik akhir
        "-vf", "minterpolate=mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
               "tblend=all_mode=difference128,"
               "eq=contrast=1.02:brightness=0.01:saturation=1.03,"
               "rotate=0.005*sin(2*PI*t/8)",  # Perubahan kecil pada rotasi
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-b:v", "1600k",
        "-c:a", "aac",  # Gunakan format audio AAC agar lebih kompatibel
        "-b:a", "128k",
        "-af", "asetrate=44100*1.005, atempo=0.995, volume=1.02",  # Sedikit mengubah tempo & pitch
        "-movflags", "+faststart",
        "-map_metadata", "-1",  # Hapus metadata asli
        "-pix_fmt", "yuv420p",
        "-metadata", "title=New Video",
        "-metadata", "encoder=FFmpeg Custom",
        "-metadata", "comment=Processed by AI Pipeline",
        "-metadata", f"creation_time=202{str(hours)[0]}-{minutes}-{int(seconds)%28+1}T{hours}:{minutes}:{int(seconds)}Z",  # Random timestamp
        output_path
    ]

    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    logging.info(f"FFmpeg Output:\n{result.stdout}")
    logging.error(f"FFmpeg Error:\n{result.stderr}")

    if result.returncode != 0 or not os.path.exists(output_path):
        safe_remove(input_path)
        safe_remove(output_path)
        return jsonify({"error": "FFmpeg failed!"}), 500

    response = send_file(output_path, as_attachment=True)

    # Hapus file sementara
    safe_remove(input_path)
    safe_remove(output_path)

    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
