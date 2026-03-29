VideoData = {
    "video_id": str,
    "frames": list,
    "audio_path": str
}

Person = {
    "id": int,
    "age": int,
    "gender": str,
    "emotion": str
}

AudioData = {
    "language": str,
    "transcript": str,
    "loudness": float
}

Event = {
    "type": str,
    "confidence": float
}