import re

# -------------------------------
# Region Keywords (India-focused)
# -------------------------------

REGION_KEYWORDS = {
    "Delhi": ["delhi", "new delhi"],
    "Mumbai": ["mumbai", "bombay"],
    "Bangalore": ["bangalore", "bengaluru"],
    "Chennai": ["chennai", "madras"],
    "Kolkata": ["kolkata", "calcutta"],
    "Hyderabad": ["hyderabad"],
    "Pune": ["pune"],
    "Uttar Pradesh": ["uttar pradesh"],
    "Punjab": ["punjab"],
    "Haryana": ["haryana"],
    "Rajasthan": ["rajasthan"],
    "Gujarat": ["gujarat"],
    "Odisha" : ["Odisha","Orissa"],
    "Bihar": ["bihar"],
    "West Bengal": ["west bengal"],
    "Assam": ["assam", "guwahati", "axom"]
}


# -------------------------------
# Helper
# -------------------------------

def clean_text(text):
    return re.sub(r'[^a-zA-Z0-9 ]', ' ', text.lower())


# -------------------------------
# Extract Region from Text
# -------------------------------

def extract_region_from_text(text):
    text = clean_text(text)

    scores = {}

    for region, keywords in REGION_KEYWORDS.items():
        for word in keywords:
            if f" {word} " in f" {text} ":
                if word in ["up", "mp"] and "election" in text:
                    continue
                scores[region] = scores.get(region, 0) + 1
            

    if not scores:
        return None, 0

    best_region = max(scores, key=scores.get)
    confidence = scores[best_region] / sum(scores.values())

    return best_region, round(confidence, 2)


# -------------------------------
# Main Function
# -------------------------------

def detect_region(metadata, transcript, comments_data):
    """
    metadata → dict with title, description
    transcript → string
    comments_data → dict
    """

    sources = []

    # 1. Metadata
    meta_text = (metadata.get("title", "") + " " +
                 metadata.get("description", ""))

    sources.append(("metadata", meta_text, 2.0))  # higher weight

    # 2. Transcript
    sources.append(("transcript", transcript, 1.5))

    # 3. Comments (sample text)
    comment_text = " ".join(comments_data.get("sample_comments", []))
    sources.append(("comments", comment_text, 0.8))

    region_scores = {}

    for source_name, text, weight in sources:
        region, confidence = extract_region_from_text(text)

        if region:
            region_scores[region] = region_scores.get(region, 0) + confidence * weight

    if not region_scores:
        return {
            "region": "Unknown",
            "confidence": 0.0
        }

    best_region = max(region_scores, key=region_scores.get)
    confidence = region_scores[best_region] / sum(region_scores.values())

    if confidence < 0.6:
        return {
            "region": "Unknown",
            "confidence": round(confidence, 2)
        }

    return {
        "region": best_region,
        "confidence": round(confidence, 2)
    }


# -------------------------------
# Debug Run
# -------------------------------

if __name__ == "__main__":
    metadata = {
        "title": "Protest happening in Delhi streets",
        "description": "Citizens protesting near India Gate"
    }

    transcript = "Yeh Delhi mein ho raha hai"

    comments = {
        "topics": ["delhi", "protest", "government"]
    }

    result = detect_region(metadata, transcript, comments)

    print("\n--- REGION DETECTION ---")
    print(result)
