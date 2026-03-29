# scripts/summarizer.py

import re
from collections import Counter

from deep_translator import GoogleTranslator
from langdetect import detect
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


analyzer = SentimentIntensityAnalyzer()

TRANSCRIPT_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "he", "her", "his", "i", "in", "is", "it", "its", "of",
    "on", "or", "that", "the", "their", "them", "they", "this", "to", "was",
    "we", "were", "will", "with", "you", "your",
}


def split_sentences(text):
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text or "") if sentence.strip()]


def detect_language(text):
    try:
        return detect(text)
    except Exception:
        return "unknown"


def translate_to_english(text):
    language = detect_language(text)
    if language in {"en", "unknown"}:
        return text

    try:
        return GoogleTranslator(source="auto", target="en").translate(text)
    except Exception:
        return text


def trim_summary(summary, max_words=45):
    words = summary.split()
    if len(words) <= max_words:
        return summary
    return " ".join(words[:max_words]).rstrip(",.;:") + "..."


def summarize_transcript(transcript, max_sentences=2):
    transcript = (transcript or "").strip()
    if not transcript:
        return "Transcript unavailable for this video."

    transcript = translate_to_english(transcript)

    sentences = split_sentences(transcript)
    if not sentences:
        short_text = transcript[:220].strip() + ("..." if len(transcript) > 220 else "")
        return trim_summary(short_text)

    useful_sentences = []
    for sentence in sentences:
        cleaned = sentence.strip()
        word_count = len(cleaned.split())
        if word_count < 6:
            continue
        useful_sentences.append(cleaned)
        if len(useful_sentences) >= max_sentences:
            break

    if not useful_sentences:
        useful_sentences = sentences[:max_sentences]

    summary = " ".join(useful_sentences).strip()
    return trim_summary(summary)


def analyze_transcript_sentiment(transcript):
    transcript = (transcript or "").strip()
    if not transcript:
        return {"label": "unknown", "score": 0.0}

    transcript = translate_to_english(transcript)

    score = analyzer.polarity_scores(transcript)["compound"]
    if score >= 0.05:
        label = "positive"
    elif score <= -0.05:
        label = "negative"
    else:
        label = "neutral"

    return {"label": label, "score": round(score, 3)}


def extract_transcript_keywords(transcript, top_k=5):
    transcript = translate_to_english(transcript or "")
    words = re.findall(r"\b[a-zA-Z]{4,}\b", transcript.lower())
    filtered = [word for word in words if word not in TRANSCRIPT_STOPWORDS]
    return [word for word, _ in Counter(filtered).most_common(top_k)]


def build_transcript_sentiment_summary(transcript):
    transcript_english = translate_to_english(transcript or "")
    summary = summarize_transcript(transcript_english)
    sentiment = analyze_transcript_sentiment(transcript_english)
    keywords = extract_transcript_keywords(transcript_english)

    if sentiment["label"] == "positive":
        tone = "The speaker sounds mostly positive"
    elif sentiment["label"] == "negative":
        tone = "The speaker sounds mostly negative"
    elif sentiment["label"] == "neutral":
        tone = "The speaker sounds mostly neutral"
    else:
        tone = "The speaker sentiment is unclear"

    if keywords:
        return f"{tone}. Key themes are {', '.join(keywords[:3])}. {summary}"

    return f"{tone}. {summary}"


def summarize_comments(comment_data):
    comments = [translate_to_english(comment) for comment in comment_data.get("sample_comments", []) if comment]
    sentiment = comment_data.get("sentiment", "unknown")
    topics = comment_data.get("topics", [])

    if not comments:
        return "Not enough comments were available to summarize public opinion."

    opening = comments[:2]
    excerpt = " ".join(opening)

    if sentiment == "positive":
        prefix = "People are mostly supportive."
    elif sentiment == "negative":
        prefix = "People are mostly critical or concerned."
    else:
        prefix = "People have mixed opinions."

    if topics:
        return f"{prefix} Common themes include {', '.join(topics[:3])}. Sample opinion: {trim_summary(excerpt, max_words=28)}"

    return f"{prefix} Sample opinion: {trim_summary(excerpt, max_words=28)}"


def explain_video(event, audio, face):
    event_type = event.get("event_type", "unknown")
    intensity = audio.get("intensity", "low")
    transcript_summary = summarize_transcript(audio.get("transcript", ""))

    if event_type == "crowd_agitation":
        return (
            f"This video appears to show a tense or highly active situation. "
            f"{transcript_summary} Motion is {event.get('motion', 'unknown')} with {intensity} audio."
        )

    elif event_type in {"presentation", "speaker_led_video", "interview"}:
        return f"This video mainly features a speaker-led segment. {transcript_summary}"

    return f"This video appears to show a general scene. {transcript_summary}"


def explain_comments(comment_data):

    sentiment = comment_data.get("sentiment", "unknown")
    total_comments = comment_data.get("num_comments", 0)
    distribution = comment_data.get("sentiment_distribution", {})
    positive_count = distribution.get("positive", 0)
    negative_count = distribution.get("negative", 0)
    neutral_count = distribution.get("neutral", 0)

    if sentiment == "positive":
        distribution_line = (
            f"Out of {total_comments} comments, {positive_count} are positive, "
            f"{neutral_count} are neutral, and {negative_count} are negative."
        )
    elif sentiment == "negative":
        distribution_line = (
            f"Out of {total_comments} comments, {negative_count} are negative, "
            f"{neutral_count} are neutral, and {positive_count} are positive."
        )
    else:
        distribution_line = (
            f"Out of {total_comments} comments, {positive_count} are positive, "
            f"{neutral_count} are neutral, and {negative_count} are negative."
        )

    return f"{summarize_comments(comment_data)} {distribution_line}"
