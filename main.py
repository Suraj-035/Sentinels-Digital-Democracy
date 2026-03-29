# main.py

from scripts.scrape_youtube import search_videos
from scripts.download_video import download_video
from scripts.extract_frames import extract_frames
from scripts.extract_audio import extract_audio
from scripts.analyze_faces import analyze_frames
from scripts.analyze_audio import analyze_audio
from scripts.graph_builder import store_event_graph
from scripts.comment_analysis import analyze_comments
from scripts.region_detection import detect_region
from scripts.crowd_motion_analysis import analyze_crowd_motion
from scripts.fuse_behaviour import infer_behaviour
from scripts.detect_objects import detect_accessories
from scripts.infer_clothing import infer_clothing
from scripts.infer_activity import infer_activity
from scripts.summarizer import explain_video, explain_comments
from scripts.generate_description import generate_description
from scripts.update_csv import append_to_csv

SEARCH_QUERY = "India's housing price"
MAX_VIDEOS = 1

def run_pipeline():
    urls = search_videos(SEARCH_QUERY, MAX_VIDEOS)

    for url in urls:
        print(f"\nProcessing: {url}")

        # Download
        download_video(url, "data/raw_videos/%(id)s.%(ext)s")

        video_id = url.split("v=")[-1]

        # Paths
        video_path = f"data/raw_videos/{video_id}.mp4"
        frame_dir = f"data/processed_videos/{video_id}/frames"
        audio_path = f"data/processed_videos/{video_id}/audio.wav"

        # Processing
        extract_frames(video_path, frame_dir)
        extract_audio(video_path, audio_path)

        face = analyze_frames(frame_dir)
        print(face["person_count"])

        motion = analyze_crowd_motion(frame_dir)


        audio = analyze_audio(audio_path)
        print(audio["language"])  # NEW
        print(audio["transcript"][:100])  # DEBUG

        metadata = {
        "title": url,   # TEMP (later fix scraper)
        "description": ""
        }

        accessories, person_boxes = detect_accessories(frame_dir)
        clothing = infer_clothing("Unknown", face["gender"])
        activity = infer_activity(person_boxes)

        comments = analyze_comments(video_id)

        print("\n--- COMMENT INSIGHT ---")
        print(comments)


        from scripts.event_builder import build_event

        event = build_event(face, audio, (accessories, person_boxes), motion, comments)
        print("\n--- EVENT DETECTED ---")
        print(event)
        
        fused = infer_behaviour(
            face,
            audio,
            accessories,
            clothing,
            activity
        )

        description = generate_description(fused)
        record = {
            "Video ID": video_id,
            "Video method": "scraped",
            "language": "Hindi/English",
            "Gender": face["gender"],
            "Age Group": face["age_group"],
            "Region": "Unknown",
            "Description": description
        }

        region = detect_region(
            metadata,
            audio.get("transcript", ""),
            comments
        )

        
        video_summary = explain_video(event, audio, face)
        comment_summary = explain_comments(comments)

        

        append_to_csv(record)
        print(description)

        

        print("\n--- COMMENT INSIGHT ---")
        print(comments)

        print("\n--- FACE ---", face)
        print("\n--- AUDIO ---", audio)
        print("\n--- MOTION ---", motion)
        print("\n--- COMMENTS ---", comments)
        print("\n--- REGION ---", region)
        print("\n--- EVENT ---", event)

        print("\n--- VIDEO SUMMARY ---")
        print(video_summary)

        print("\n--- COMMENT SUMMARY ---")
        print(comment_summary)


        try:
            store_event_graph(
                video_id,
                event,
                region,
                comments
            )
        except Exception as e:
            print("[Graph ERROR]:", e)



if __name__ == "__main__":
    run_pipeline()