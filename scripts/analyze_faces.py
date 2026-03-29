# scripts/analyze_faces.py

import os
from deepface import DeepFace
from collections import Counter
import uuid

# -------------------------------
# Utility Functions
# -------------------------------

def bucket_age(age):
    if age < 15:
        return "Below 15"
    elif age <= 25:
        return "15-25"
    elif age <= 35:
        return "26-35"
    elif age <= 45:
        return "36-45"
    elif age <= 55:
        return "46-55"
    else:
        return "55+"


# -------------------------------
# Core Face Analysis
# -------------------------------

def analyze_frames_multi_person(frame_dir, max_frames=3):
    """
    Returns structured multi-person data + aggregated summary.
    """

    frames = sorted(os.listdir(frame_dir))[:max_frames]

    all_persons = []
    person_id_counter = 0

    for frame in frames:
        frame_path = os.path.join(frame_dir, frame)

        try:
            results = DeepFace.analyze(
                img_path=frame_path,
                actions=["age", "gender", "emotion"],
                enforce_detection=False
            )

            # DeepFace returns list of faces
            for res in results:

                person_data = {
                    "person_id": str(uuid.uuid4()),  # unique ID per detection
                    "frame": frame,
                    "age": int(res.get("age", 0)),
                    "age_group": bucket_age(int(res.get("age", 0))),
                    "gender": res.get("dominant_gender", "Unknown"),
                    "emotion": res.get("dominant_emotion", "neutral")
                }

                all_persons.append(person_data)
                person_id_counter += 1

        except Exception as e:
            print(f"[Face Analysis] Skipped {frame}: {e}")

    # -------------------------------
    # Aggregation Layer
    # -------------------------------

    if not all_persons:
        return {
            "persons": [],
            "summary": {
                "total_persons": 0,
                "dominant_gender": "Unknown",
                "dominant_emotion": "Neutral",
                "dominant_age_group": "Unknown"
            }
        }

    genders = [p["gender"] for p in all_persons]
    emotions = [p["emotion"] for p in all_persons]
    age_groups = [p["age_group"] for p in all_persons]

    summary = {
        "total_persons": len(all_persons),
        "dominant_gender": Counter(genders).most_common(1)[0][0],
        "dominant_emotion": Counter(emotions).most_common(1)[0][0],
        "dominant_age_group": Counter(age_groups).most_common(1)[0][0],
    }

    return {
        "persons": all_persons,
        "summary": summary
    }


# -------------------------------
# Backward Compatibility Wrapper
# -------------------------------

def analyze_frames(frame_dir, max_frames=3):
    """
    Keeps compatibility with old pipeline.
    Returns simplified output (but internally uses new system)
    """

    result = analyze_frames_multi_person(frame_dir, max_frames)

    summary = result["summary"]

    return {
        "age_group": summary["dominant_age_group"],
        "gender": summary["dominant_gender"],
        "emotion": summary["dominant_emotion"],
        "person_count": min(summary["total_persons"], 2)
    }


# -------------------------------
# Debug Run
# -------------------------------

if __name__ == "__main__":
    FRAME_DIR = "data/processed_videos/gDN7cJ3Rt80/frames"

    output = analyze_frames_multi_person(FRAME_DIR)
    print("\n--- FULL MULTI-PERSON OUTPUT ---")
    print(output)

    print("\n--- LEGACY OUTPUT ---")
    print(analyze_frames(FRAME_DIR))
