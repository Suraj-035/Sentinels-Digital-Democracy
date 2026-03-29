# scripts/event_builder.py

# -------------------------------
# Helper Functions
# -------------------------------

def detect_keywords(text, keywords):
    text = text.lower()
    return any(word in text for word in keywords)


# -------------------------------
# Core Event Builder
# -------------------------------

def build_event(face_data, audio_data, object_data, motion_data, comment_data):

    # -------------------------------
    # Extract Signals
    # -------------------------------

    num_people = face_data.get("person_count", 1)
    emotion = face_data.get("emotion", "neutral")

    speaking = audio_data.get("speaking", False)
    intensity = audio_data.get("intensity", "low")
    transcript = audio_data.get("transcript", "")

    motion_state = motion_data.get("crowd_motion", "unknown")
    
    transcript_lower = transcript.lower()

    accessories, _ = object_data
    has_bag = "bag" in accessories
    has_helmet = "helmet" in accessories

    
    motion_intensity = motion_data.get("motion_intensity", 0)

    comment_sentiment = comment_data.get("sentiment", "unknown")
    comment_topics = comment_data.get("topics", [])

    # -------------------------------
    # Keyword Sets
    # -------------------------------

    protest_keywords = [
        "protest", "rights", "justice", "against",
        "demand", "strike", "freedom", "issue"
    ]

    interview_keywords = [
        "interview", "job", "experience",
        "tell me", "question", "answer"
    ]

    casual_keywords = [
        "hello", "hi", "vlog", "today",
        "guys", "welcome"
    ]

    presentation_keywords = [
        "explain", "system", "how", "what is",
        "analysis", "report", "update", "discussion",
    ]
    
    if num_people <= 2:
        motion_state = "irrelevant"

    # -------------------------------
    # Evidence Scoring System
    # -------------------------------

    score = 0
    evidence = []

    
    if (
        num_people >= 5 and
        intensity == "high" and
        motion_state in ["active", "chaotic"] and
        (
            emotion in ["angry", "sad"] or
            detect_keywords(transcript, protest_keywords)
        )
    ):
        score += 2  # stronger condition

    if intensity == "high":
        score += 1
        evidence.append("high_audio_intensity")

    if motion_state in ["active", "chaotic"]:
        score += 1
        evidence.append("dynamic_motion")

    if emotion in ["angry", "sad"]:
        score += 1
        evidence.append("negative_emotion")

    if detect_keywords(transcript, protest_keywords):
        score += 1
        evidence.append("protest_keywords")

    if comment_sentiment == "negative":
        score += 1
        evidence.append("negative_public_reaction")

    if any(word in comment_topics for word in ["protest", "issue", "government", "problem"]):
        score += 1
        evidence.append("relevant_public_discussion")

    # -------------------------------
    # Event Classification
    # -------------------------------

    event_type = "unknown"
    confidence = 0.5

    # Priority: Strong multi-signal agreement
    if score >= 5:
        event_type = "crowd_agitation"
        confidence = round(score / 5, 2)

    elif num_people >= 3 and speaking:
        event_type = "group_interaction"
        confidence = 0.7

    elif num_people <= 2 and detect_keywords(transcript, interview_keywords):
        event_type = "interview"
        confidence = 0.8

    elif speaking and detect_keywords(transcript, presentation_keywords):
        event_type = "presentation"
        confidence = 0.65

    elif detect_keywords(transcript, casual_keywords):
        event_type = "casual_conversation"
        confidence = 0.6

    elif speaking:
        event_type = "speaker_led_video"
        confidence = 0.55

    elif not speaking:
        event_type = "silent_scene"
        confidence = 0.6

    # -------------------------------
    # Contextual Tags
    # -------------------------------

    tags = []

    if num_people > 5:
        tags.append("crowd")

    if motion_state == "chaotic":
        tags.append("chaotic_motion")

    elif motion_state == "active":
        tags.append("active_movement")

    if has_bag:
        tags.append("public_setting")

    if has_helmet:
        tags.append("road_activity")
    
    if comment_sentiment != "unknown":
        tags.append(f"public_sentiment_{comment_sentiment}")

    tags.extend(evidence)

    # -------------------------------
    # Final Output
    # -------------------------------

    return {
        "event_type": event_type,
        "confidence": confidence,
        "num_people": num_people,
        "emotion": emotion,
        "intensity": intensity,
        "motion": motion_state,
        "tags": tags,
        "key_transcript": transcript[:120]
    }
