# scripts/crowd_motion_analysis.py

import cv2
import numpy as np
import os


# -------------------------------
# Optical Flow Based Motion
# -------------------------------

def compute_optical_flow(prev_gray, curr_gray):
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray,
        curr_gray,
        None,
        0.5,
        3,
        15,
        3,
        5,
        1.2,
        0
    )

    magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return magnitude


# -------------------------------
# Main Crowd Motion Analyzer
# -------------------------------

def analyze_crowd_motion(frame_dir, max_frames=10):
    frames = sorted(os.listdir(frame_dir))[:max_frames]

    if len(frames) < 2:
        return {
            "motion_intensity": 0,
            "motion_variance": 0,
            "crowd_motion": "unknown"
        }

    motion_values = []

    prev_frame = cv2.imread(os.path.join(frame_dir, frames[0]))
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

    for frame in frames[1:]:
        frame_path = os.path.join(frame_dir, frame)
        curr_frame = cv2.imread(frame_path)

        if curr_frame is None:
            continue

        curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

        magnitude = compute_optical_flow(prev_gray, curr_gray)

        motion_values.append(np.mean(magnitude))

        prev_gray = curr_gray

    if not motion_values:
        return {
            "motion_intensity": 0,
            "motion_variance": 0,
            "crowd_motion": "unknown"
        }

    avg_motion = float(np.mean(motion_values))
    motion_var = float(np.var(motion_values))

    # -------------------------------
    # Motion Classification
    # -------------------------------

    if avg_motion > 2.5 and motion_var > 1.0:
        motion_state = "chaotic"
    elif avg_motion > 1.2:
        motion_state = "active"
    elif avg_motion > 0.5:
        motion_state = "mild"
    else:
        motion_state = "static"

    return {
        "motion_intensity": round(avg_motion, 3),
        "motion_variance": round(motion_var, 3),
        "crowd_motion": motion_state
    }


# -------------------------------
# Debug Run
# -------------------------------

if __name__ == "__main__":
    FRAME_DIR = "data/processed_videos/gDN7cJ3Rt80/frames"

    result = analyze_crowd_motion(FRAME_DIR)

    print("\n--- CROWD MOTION ANALYSIS ---")
    print(result)