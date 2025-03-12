import os
import subprocess
import logging
from flask import Flask, request, send_file, jsonify

# Konfigurasi logging
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
        logging.error("No file uploaded!")
        return jsonify({"error": "No file uploaded!"}), 400

    file = request.files["file"]
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    output_path = os.path.join(PROCESSED_FOLDER, f"clean_{file.filename}")

    try:
        file.save(input_path)
        logging.info(f"File berhasil disimpan: {input_path}")
    except Exception as e:
        logging.error(f"Error menyimpan file: {e}")
        return jsonify({"error": "Failed to save file!"}), 500

    try:
        # Cek apakah FFmpeg tersedia
        ffmpeg_path = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True).stdout.strip()
        if not ffmpeg_path:
            logging.warning("FFmpeg tidak ditemukan, menggunakan ffmpeg-static bawaan Railway.")
            ffmpeg_path = "ffmpeg"

        logging.info(f"FFmpeg ditemukan di: {ffmpeg_path}")

        # Jalankan FFmpeg dengan pengaturan yang lebih ringan
        logging.info(f"Mulai proses FFmpeg untuk {input_path} ➝ {output_path}")

        result = subprocess.run([
            ffmpeg_path, "-y",  # Overwrite otomatis
            "-i", input_path, 
            "-threads", "2",  # Batasi penggunaan thread
            "-map_metadata", "-1",  # Hapus metadata
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2, crop=iw-10:ih-10",  # Crop video
            "-r", "24",  # Turunkan frame rate agar lebih ringan
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",  # Gunakan ultrafast agar lebih cepat
            "-c:a", "aac", "-b:a", "96k",  # Kompres audio lebih hemat
            output_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        logging.info(f"FFmpeg Output:\n{result.stdout}")
        logging.error(f"FFmpeg Error:\n{result.stderr}")

        if result.returncode != 0:
            logging.error(f"FFmpeg gagal dengan kode {result.returncode}")
            return jsonify({"error": f"FFmpeg failed! {result.stderr}"}), 500

        if not os.path.exists(output_path):
            logging.error("File output tidak ditemukan setelah pemrosesan.")
            return jsonify({"error": "Processed file not found!"}), 500

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return jsonify({"error": f"Unexpected error: {e}"}), 500

    logging.info(f"Proses selesai, mengirim file: {output_path}")

    # Hapus file setelah dikirim untuk menghemat storage di Railway
    response = send_file(output_path, as_attachment=True)
    try:
        os.remove(input_path)
        os.remove(output_path)
        logging.info(f"File {input_path} dan {output_path} dihapus untuk menghemat storage.")
    except Exception as e:
        logging.warning(f"Gagal menghapus file: {e}")

    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Gunakan PORT dari Railway jika tersedia
    logging.info(f"Server berjalan di port {port}")
    app.run(host="0.0.0.0", port=port, debug=True)
