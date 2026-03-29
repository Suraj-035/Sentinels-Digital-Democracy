import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from yt_dlp import YoutubeDL

PIPELINE_ROOT = Path(__file__).resolve().parents[2]
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

os.chdir(PIPELINE_ROOT)

from scripts.analyze_audio import analyze_audio
from scripts.analyze_faces import analyze_frames
from scripts.comment_analysis import analyze_comments
from scripts.crowd_motion_analysis import analyze_crowd_motion
from scripts.detect_objects import detect_accessories
from scripts.download_video import download_video
from scripts.event_builder import build_event
from scripts.extract_audio import extract_audio
from scripts.extract_frames import extract_frames
from scripts.fuse_behaviour import infer_behaviour
from scripts.generate_description import generate_description
from scripts.infer_activity import infer_activity
from scripts.infer_clothing import infer_clothing
from scripts.news_sentiment_pipeline import run_pipeline as run_news_pipeline
from scripts.region_detection import detect_region
from scripts.scrape_youtube import search_videos
from scripts.summarizer import (
    analyze_transcript_sentiment,
    build_transcript_sentiment_summary,
    explain_comments,
    explain_video,
    summarize_transcript,
)


def parse_video_id(url):
    parsed = urlparse(url)
    if parsed.hostname in {"youtu.be"}:
        return parsed.path.strip("/")
    if parsed.query:
        return parse_qs(parsed.query).get("v", [""])[0]
    return parsed.path.strip("/").split("/")[-1]


def fetch_video_metadata(url):
    options = {
        "quiet": True,
        "skip_download": True,
    }

    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        video_id = parse_video_id(url)
        return {
            "title": f"YouTube Video {video_id}",
            "description": "",
            "thumbnail": "",
            "channel": "",
        }

    return {
        "title": info.get("title") or f"YouTube Video {parse_video_id(url)}",
        "description": info.get("description") or "",
        "thumbnail": info.get("thumbnail") or "",
        "channel": info.get("channel") or "",
    }


def normalize_news_result(news_result, query):
    return {
        "completed": True,
        "query": news_result.get("query", ""),
        "runAt": news_result.get("run_at"),
        "summary": news_result.get("summary", {}),
        "results": [
            {
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
                "publishedAt": item.get("published_at", ""),
                "sentiment": item.get("sentiment", "unknown"),
                "confidence": item.get("confidence", 0),
                "category": query,
                "language": item.get("language", "unknown"),
                "analysisBasis": item.get("analysis_basis", ""),
                "explanation": item.get("explanation", ""),
            }
            for item in news_result.get("results", [])
        ],
    }


def format_region_label(region_result):
    region_name = region_result.get("region", "Unknown")
    confidence = float(region_result.get("confidence", 0.0) or 0.0)

    if region_name == "Unknown":
        return "Unknown"

    if confidence >= 0.8:
        return f"Likely {region_name}"
    if confidence >= 0.6:
        return f"Maybe {region_name}"
    return "Unknown"


def process_youtube_video(url, query):
    video_id = parse_video_id(url)
    metadata = fetch_video_metadata(url)

    raw_video_path = PIPELINE_ROOT / "data" / "raw_videos" / f"{video_id}.mp4"
    processed_dir = PIPELINE_ROOT / "data" / "processed_videos" / video_id
    frame_dir = processed_dir / "frames"
    audio_path = processed_dir / "audio.wav"

    processed_dir.mkdir(parents=True, exist_ok=True)
    frame_dir.mkdir(parents=True, exist_ok=True)

    download_video(url, str(PIPELINE_ROOT / "data" / "raw_videos" / "%(id)s.%(ext)s"))
    extract_frames(str(raw_video_path), str(frame_dir))
    extract_audio(str(raw_video_path), str(audio_path))

    face = analyze_frames(str(frame_dir))
    motion = analyze_crowd_motion(str(frame_dir))
    audio = analyze_audio(str(audio_path))
    accessories, person_boxes = detect_accessories(str(frame_dir))
    clothing = infer_clothing("Unknown", face.get("gender", "Unknown"))
    activity = infer_activity(person_boxes)
    comments = analyze_comments(video_id)
    event = build_event(face, audio, (accessories, person_boxes), motion, comments)
    fused = infer_behaviour(face, audio, accessories, clothing, activity)
    description = generate_description(fused)
    region = detect_region(metadata, audio.get("transcript", ""), comments)
    transcript_summary = summarize_transcript(audio.get("transcript", ""))
    transcript_sentiment = analyze_transcript_sentiment(audio.get("transcript", ""))
    transcript_sentiment_summary = build_transcript_sentiment_summary(audio.get("transcript", ""))
    video_summary = explain_video(event, audio, face)
    comment_summary = explain_comments(comments)

    return {
        "videoId": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "embedUrl": f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&modestbranding=1&playsinline=1",
        "title": metadata["title"],
        "description": metadata["description"],
        "thumbnail": metadata["thumbnail"],
        "channel": metadata["channel"],
        "query": query,
        "hasTranscript": bool((audio.get("transcript") or "").strip()),
        "transcriptSummary": transcript_summary,
        "transcriptSentiment": transcript_sentiment,
        "transcriptSentimentSummary": transcript_sentiment_summary,
        "videoSummary": video_summary,
        "commentSummary": comment_summary,
        "generatedDescription": description,
        "region": region,
        "regionLabel": format_region_label(region),
        "face": face,
        "audio": {
            "language": audio.get("language", "unknown"),
            "transcript": audio.get("transcript", ""),
            "speaking": audio.get("speaking", False),
            "intensity": audio.get("intensity", "low"),
            "durationSec": audio.get("duration_sec", 0),
            "avgRms": audio.get("avg_rms", 0),
            "maxRms": audio.get("max_rms", 0),
        },
        "motion": motion,
        "comments": comments,
        "event": event,
        "accessories": accessories,
        "activity": activity,
        "clothing": clothing,
    }


def execute_query_job(run_id, state, manager):
    query = state["query"]
    max_videos = state["options"]["maxVideos"]
    news_limit = state["options"]["newsLimit"]

    state["status"] = "running"
    state["progress"] = {
        "stage": "starting",
        "message": f"Starting analysis for '{query}'",
    }
    manager.publish(run_id, "job.started", state)

    try:
        state["progress"] = {
            "stage": "news_fetch",
            "message": "Fetching and analyzing news sentiment",
        }
        manager.publish(run_id, "news.started", state)

        news_result = run_news_pipeline(query=query, limit=news_limit, verbose=False)
        state["news"] = normalize_news_result(news_result, query)
        manager.publish(run_id, "news.completed", state)
    except Exception as exc:
        state["errors"].append({"source": "news", "message": str(exc)})
        manager.publish(run_id, "news.failed", state)

    try:
        state["progress"] = {
            "stage": "youtube_search",
            "message": "Searching YouTube videos for the query",
        }
        manager.publish(run_id, "youtube.search_started", state)

        urls = search_videos(query, max_videos)
        manager.publish(run_id, "youtube.search_completed", state)

        for index, url in enumerate(urls, start=1):
            state["progress"] = {
                "stage": "youtube_video",
                "message": f"Processing video {index} of {len(urls)}",
            }
            manager.publish(run_id, "youtube.video_started", state)

            try:
                video_result = process_youtube_video(url, query)
                state["youtube"]["videos"].append(video_result)
                manager.publish(run_id, "youtube.video_completed", state)
            except Exception as exc:
                state["errors"].append({"source": "youtube", "message": f"{url}: {exc}"})
                manager.publish(run_id, "youtube.video_failed", state)

        state["youtube"]["completed"] = True
    except Exception as exc:
        state["errors"].append({"source": "youtube", "message": str(exc)})
        manager.publish(run_id, "youtube.failed", state)

    state["status"] = "completed" if not state["errors"] else "completed_with_errors"
    state["progress"] = {"stage": "done", "message": "Live analysis finished"}
    manager.publish(run_id, "job.completed", state)
