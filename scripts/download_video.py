# scripts/download_video.py
import subprocess

def download_video(url, output_path):
    command = [
        "yt-dlp",
        "-S", "res:720",
        "-f", "bv*[vcodec=h264]+ba[acodec=aac]/mp4",
        "--download-sections", "*0-600",
        "--merge-output-format", "mp4",
        "-o", output_path,
        url
    ]
    subprocess.run(command)

# if __name__ == "__main__":
#     download_video(
#         "https://www.youtube.com/watch?v=gDN7cJ3Rt80", ##example video
#         "data/raw_videos/%(id)s.%(ext)s"
#     )