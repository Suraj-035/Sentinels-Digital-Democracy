# scripts/comment_analysis.py

from googleapiclient.discovery import build
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from collections import Counter
import re

from scripts.config import YOUTUBE_API_KEY

# -------------------------------
# Initialize
# -------------------------------

youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
analyzer = SentimentIntensityAnalyzer()


# -------------------------------
# Fetch Comments
# -------------------------------

def fetch_comments(video_id, max_comments=25):
    comments = []

    try:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(max_comments, 100),
            textFormat="plainText"
        )
        response = request.execute()

        for item in response.get("items", []):
            text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
            comments.append(text)

    except Exception as e:
        print(f"[Comments] Error fetching comments: {e}")

    return comments


# -------------------------------
# Sentiment Analysis
# -------------------------------

def analyze_sentiment(comments):
    sentiments = []

    for text in comments:
        score = analyzer.polarity_scores(text)["compound"]

        if score >= 0.05:
            sentiments.append("positive")
        elif score <= -0.05:
            sentiments.append("negative")
        else:
            sentiments.append("neutral")

    if not sentiments:
        return {
            "overall_sentiment": "unknown",
            "distribution": {}
        }

    distribution = dict(Counter(sentiments))
    overall = Counter(sentiments).most_common(1)[0][0]

    return {
        "overall_sentiment": overall,
        "distribution": distribution
    }


# -------------------------------
# Topic Extraction (Simple)
# -------------------------------

def extract_topics(comments, top_k=5):
    words = []

    for text in comments:
        tokens = re.findall(r'\b\w+\b', text.lower())
        words.extend(tokens)

    stopwords = set([
        "the", "is", "and", "to", "of", "in", "this", "that",
        "it", "for", "on", "with", "as", "was", "are", "but",
        "they", "them", "their", "people", "just", "indians", "imagine",
        "video", "really", "very", "from", "have", "what", "your",
    ])

    filtered = [w for w in words if w not in stopwords and len(w) > 3]

    most_common = Counter(filtered).most_common(top_k)

    return [word for word, _ in most_common]


# -------------------------------
# Main Function
# -------------------------------

def analyze_comments(video_id):

    comments = fetch_comments(video_id)

    sentiment_data = analyze_sentiment(comments)
    topics = extract_topics(comments)

    return {
        "num_comments": len(comments),
        "sentiment": sentiment_data["overall_sentiment"],
        "sentiment_distribution": sentiment_data["distribution"],
        "topics": topics,
        "sample_comments": comments[:5],
    }


# -------------------------------
# Debug Run
# -------------------------------

if __name__ == "__main__":
    video_id = "gDN7cJ3Rt80"

    result = analyze_comments(video_id)

    print("\n--- COMMENT ANALYSIS ---")
    print(result)
