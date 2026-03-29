import json
import os
import sys
import time
from datetime import datetime, timezone


import requests
from deep_translator import GoogleTranslator
from dotenv import load_dotenv
from huggingface_hub import snapshot_download
from langdetect import detect
from transformers import pipeline

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRIMARY_ENV_PATH = os.path.join(BASE_DIR, ".env")
FALLBACK_ENV_PATH = os.path.join(BASE_DIR, "news_sentiment", ".env")

if os.path.exists(PRIMARY_ENV_PATH):
    load_dotenv(dotenv_path=PRIMARY_ENV_PATH)
else:
    load_dotenv(dotenv_path=FALLBACK_ENV_PATH)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# API_KEY = os.getenv("NEWS_API_KEY")
API_KEY = os.getenv("NEWS_API_KEY")
BASE_URL = "https://newsapi.org/v2/everything"

DEFAULT_TOPICS = [
    "politics",
    "economy",
    "technology",
    "health",
    "artificial intelligence",
]
DEFAULT_LIMIT = 10
TOPIC_DELAY_SECONDS = 10
RUN_FOREVER = False
CYCLE_DELAY_SECONDS = 300
EXPORT_JSON = True
OUTPUT_JSON_PATH = os.path.join(BASE_DIR, "dashboard_news_sentiment.json")
DEFAULT_SENTIMENT_MODEL = "distilbert/distilbert-base-uncased-finetuned-sst-2-english"
MODEL_CACHE_DIR = os.path.join(BASE_DIR, ".hf_cache")
MODEL_LOCAL_DIR = os.path.join(MODEL_CACHE_DIR, "sentiment_model")

#sentiment_pipeline = pipeline("sentiment-analysis")
# sentiment_pipeline = pipeline(
#     "sentiment-analysis",
#     model="distilbert-base-uncased-finetuned-sst-2-english"
# )

# sentiment_pipeline = pipeline(
#     "sentiment-analysis",
#     model="distilbert-base-uncased-finetuned-sst-2-english",
#     trust_remote_code=True
# )

_sentiment_pipeline = None


CATEGORY_KEYWORDS = {
    "politics": ["election", "government", "minister", "policy", "politics"],
    "economy": ["stock", "market", "economy", "finance", "business"],
    "technology": ["ai", "technology", "software", "tech"],
    "health": ["health", "hospital", "disease", "medical"],
}

POSITIVE_CUES = {
    "gain",
    "growth",
    "improve",
    "improved",
    "improvement",
    "boost",
    "success",
    "record",
    "rise",
    "rally",
    "strong",
    "optimistic",
    "expansion",
    "win",
    "breakthrough",
    "benefit",
}

NEGATIVE_CUES = {
    "crisis",
    "loss",
    "losses",
    "fall",
    "decline",
    "war",
    "conflict",
    "concern",
    "risk",
    "slams",
    "cuts",
    "drop",
    "weak",
    "inflation",
    "layoffs",
    "probe",
    "scandal",
    "attack",
}

QUERY_STOPWORDS = {"the", "a", "an", "in", "on", "for", "of", "to", "and"}
INDIA_HINTS = {
    "india", "indian", "delhi", "mumbai", "bengaluru", "bangalore", "kolkata",
    "chennai", "hyderabad", "uttar pradesh", "gujarat", "punjab", "rajasthan",
    "bihar", "assam", "west bengal", "odisha",
}


def fetch_news(query="politics", limit=20):
    if not API_KEY:
        raise RuntimeError("NEWS_API_KEY is not set in the environment.")

    normalized_query = normalize_query(query)
    search_query = query
    if "india" in normalized_query or "indian" in normalized_query:
        search_query = f"({query}) AND (India OR Indian)"

    params = {
        "q": search_query,
        "searchIn": "title,description,content",
        "sortBy": "relevancy",
        "language": "en",
        "pageSize": limit,
        "apiKey": API_KEY,
    }

    response = requests.get(BASE_URL, params=params, timeout=15)
    response.raise_for_status()

    data = response.json()
    if data.get("status") != "ok":
        message = data.get("message", "Unknown NewsAPI error")
        raise RuntimeError(f"Failed to fetch news: {message}")

    articles = []
    for article in data.get("articles", []):
        articles.append(
            {
                "title": article.get("title", ""),
                "description": article.get("description", ""),
                "content": article.get("content", ""),
                "url": article.get("url", ""),
                "source": (article.get("source") or {}).get("name", ""),
                "published_at": article.get("publishedAt", ""),
            }
        )

    return articles


def detect_language(text):
    try:
        return detect(text)
    except Exception:
        return "unknown"


def normalize_label(label):
    normalized = (label or "").upper()
    if normalized in {"LABEL_0", "NEGATIVE"}:
        return "negative"
    if normalized in {"LABEL_1", "NEUTRAL"}:
        return "neutral"
    if normalized in {"LABEL_2", "POSITIVE"}:
        return "positive"
    return normalized.lower() or "unknown"


def translate_to_english(text, language):
    if language in {"en", "unknown"}:
        return text

    try:
        return GoogleTranslator(source="auto", target="en").translate(text)
    except Exception:
        return text


def get_sentiment_pipeline():
    global _sentiment_pipeline

    if _sentiment_pipeline is None:
        os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
        try:
            snapshot_download(
                repo_id=DEFAULT_SENTIMENT_MODEL,
                cache_dir=MODEL_CACHE_DIR,
                local_dir=MODEL_LOCAL_DIR,
                local_dir_use_symlinks=False,
            )
        except FileNotFoundError:
            snapshot_download(
                repo_id=DEFAULT_SENTIMENT_MODEL,
                cache_dir=MODEL_CACHE_DIR,
                local_dir=MODEL_LOCAL_DIR,
                local_dir_use_symlinks=False,
                force_download=True,
            )

        try:
            _sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model=MODEL_LOCAL_DIR,
            )
        except FileNotFoundError:
            _sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model=MODEL_LOCAL_DIR,
            )

    return _sentiment_pipeline


def prepare_text(text):
    cleaned = (text or "").strip()
    if not cleaned:
        return None

    language = detect_language(cleaned)
    translated = translate_to_english(cleaned, language)
    return translated, language


def analyze_batch(texts):
    prepared_texts = []
    languages = []
    valid_indexes = []

    for index, text in enumerate(texts):
        prepared = prepare_text(text)
        if prepared is None:
            continue

        normalized_text, language = prepared
        prepared_texts.append(normalized_text)
        languages.append(language)
        valid_indexes.append(index)

    outputs = [
        {"label": "neutral", "score": 0.0, "language": "unknown"} for _ in texts
    ]

    if not prepared_texts:
        return outputs

    results = get_sentiment_pipeline()(prepared_texts, truncation=True)

    for index, language, result in zip(valid_indexes, languages, results):
        outputs[index] = {
            "label": normalize_label(result.get("label")),
            "score": float(result.get("score", 0.0)),
            "language": language,
        }

    return outputs


def categorize(text):
    normalized_text = (text or "").lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in normalized_text for keyword in keywords):
            return category

    return "general"


def build_article_text(article):
    title = (article.get("title") or "").strip()
    description = (article.get("description") or "").strip()
    content = (article.get("content") or "").strip()
    return " ".join(part for part in [title, description, content] if part)


def normalize_query(query):
    return (query or "").strip().lower()


def extract_query_terms(query):
    return [
        term for term in normalize_query(query).replace("-", " ").split()
        if len(term) > 2 and term not in QUERY_STOPWORDS
    ]


def is_category_query(query):
    return query in {"politics", "economy", "technology", "health", "general"}


def is_relevant_article(query, text, detected_category):
    normalized_query = normalize_query(query)
    normalized_text = (text or "").lower()

    if not normalized_query:
        return True

    if is_category_query(normalized_query):
        return True

    query_terms = extract_query_terms(normalized_query)
    if not query_terms:
        return normalized_query in normalized_text

    matches = sum(term in normalized_text for term in query_terms)

    india_requested = any(term in {"india", "indian"} for term in query_terms)
    if india_requested and not any(hint in normalized_text for hint in INDIA_HINTS):
        return False

    if len(query_terms) >= 4:
        return matches >= 2

    return matches >= 1


def summarize_results(results):
    category_stats = {}

    for result in results:
        category = result["category"]
        sentiment = result["sentiment"]

        if category not in category_stats:
            category_stats[category] = {"positive": 0, "negative": 0, "neutral": 0}

        normalized = sentiment.lower()
        if normalized in category_stats[category]:
            category_stats[category][normalized] += 1
        else:
            category_stats[category]["neutral"] += 1

    return category_stats


def extract_signal_terms(text):
    words = [word.strip(".,:;!?()[]{}\"'").lower() for word in text.split()]
    positives = []
    negatives = []

    for word in words:
        if word in POSITIVE_CUES and word not in positives:
            positives.append(word)
        if word in NEGATIVE_CUES and word not in negatives:
            negatives.append(word)

    return positives[:3], negatives[:3]


def trim_to_word_limit(text, minimum_words=50, maximum_words=60):
    words = text.split()
    if len(words) <= maximum_words:
        return text

    sentences = [sentence.strip() for sentence in text.split(".") if sentence.strip()]
    collected = []

    for sentence in sentences:
        candidate = ". ".join(collected + [sentence]) + "."
        if len(candidate.split()) > maximum_words:
            break
        collected.append(sentence)

    if collected and len(". ".join(collected).split()) >= minimum_words:
        return ". ".join(collected) + "."

    return " ".join(words[:maximum_words]).rstrip(",.;:") + "."


def shorten_title(title, max_words=8):
    words = title.split()
    if len(words) <= max_words:
        return title
    return " ".join(words[:max_words]) + "..."


def build_explanation(article, sentiment, category, query, analysis_basis):
    title = (article.get("title") or "This article").strip()
    short_title = shorten_title(title)
    description = (article.get("description") or "").strip()
    text = build_article_text(article)
    positives, negatives = extract_signal_terms(text)
    article_focus = description or title

    if positives:
        positive_phrase = ", ".join(positives)
    else:
        positive_phrase = "constructive or encouraging wording"

    if negatives:
        negative_phrase = ", ".join(negatives)
    else:
        negative_phrase = "risk-oriented or critical wording"

    if sentiment["label"] == "positive":
        explanation = (
            f"This article focuses on {article_focus}. "
            f"The overall tone is positive because the wording around '{short_title}' is more optimistic than harmful, "
            f"with signals such as {positive_phrase}. The sentiment model reviewed the {analysis_basis} and found "
            f"an overall encouraging direction."
        )
    elif sentiment["label"] == "negative":
        explanation = (
            f"This article focuses on {article_focus}. "
            f"The overall tone is negative because the wording around '{short_title}' leans more adverse than hopeful, "
            f"with signals such as {negative_phrase}. The sentiment model reviewed the {analysis_basis} and found "
            f"the article framed the topic in a more concerning direction."
        )
    else:
        explanation = (
            f"This article focuses on {article_focus}. "
            f"The overall tone is neutral because the wording around '{short_title}' is mostly informational and "
            f"does not strongly lean positive or negative. The sentiment model reviewed the {analysis_basis} and "
            f"found a balanced presentation of the topic."
        )

    return trim_to_word_limit(explanation)


def print_results(results, category_stats):
    for result in results:
        print(
            f"{result['category'].upper()} | "
            f"{result['sentiment']} ({result['confidence']:.2f}) | "
            f"{result['language']}"
        )
        print(f"-> {result['title']}\n")
        print(f"Analysis basis: {result['analysis_basis']}")
        print(f"Why: {result['explanation']}")
        if result["source"]:
            print(f"Source: {result['source']}")
        if result["url"]:
            print(f"Link: {result['url']}")
        print()

    print("\nCATEGORY-WISE SUMMARY\n")

    for category, stats in category_stats.items():
        total = stats["positive"] + stats["negative"] + stats["neutral"]
        score = (
            (stats["positive"] - stats["negative"]) / total
            if total > 0
            else 0.0
        )

        print(category.upper())
        print(f"  Positive: {stats['positive']}")
        print(f"  Negative: {stats['negative']}")
        print(f"  Neutral: {stats['neutral']}")
        print(f"  Score: {score:.2f}\n")


def export_results_to_json(data, output_path=OUTPUT_JSON_PATH):
    directory = os.path.dirname(output_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    temp_output_path = f"{output_path}.tmp"
    with open(temp_output_path, "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, indent=2, ensure_ascii=False)
    os.replace(temp_output_path, output_path)


def run_pipeline(query="politics", limit=20, verbose=True):
    articles = fetch_news(query=query, limit=limit)

    valid_articles = []
    texts = []

    for article in articles:
        text = build_article_text(article)
        if not text:
            continue

        detected_category = categorize(text)
        if not is_relevant_article(query, text, detected_category):
            continue

        article["detected_category"] = detected_category
        valid_articles.append(article)
        texts.append(text)

    if verbose:
        print(f"\nFetched articles: {len(articles)}")
        print(f"Relevant articles: {len(valid_articles)}\n")

    if not valid_articles and articles:
        valid_articles = articles[: min(len(articles), limit)]
        texts = [build_article_text(article) for article in valid_articles if build_article_text(article)]
        for article in valid_articles:
            article["detected_category"] = query

    if not texts:
        return {"query": query, "run_at": datetime.now(timezone.utc).isoformat(), "results": [], "summary": {}}

    sentiments = analyze_batch(texts)
    results = []
    analysis_basis = "title + description + content snippet"

    for article, sentiment in zip(valid_articles, sentiments):
        results.append(
            {
                "title": article.get("title", ""),
                "description": article.get("description", ""),
                "content": article.get("content", ""),
                "source": article.get("source", ""),
                "url": article.get("url", ""),
                "published_at": article.get("published_at", ""),
                "sentiment": sentiment["label"],
                "confidence": sentiment["score"],
                "category": article["detected_category"],
                "language": sentiment["language"],
                "analysis_basis": analysis_basis,
                "explanation": build_explanation(
                    article=article,
                    sentiment=sentiment,
                    category=article["detected_category"],
                    query=query,
                    analysis_basis=analysis_basis,
                ),
            }
        )

    category_stats = summarize_results(results)

    if verbose:
        print_results(results, category_stats)

    return {
        "query": query,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "summary": category_stats,
    }


def run_topics_once(
    topics=None,
    limit=DEFAULT_LIMIT,
    delay_seconds=TOPIC_DELAY_SECONDS,
    verbose=True,
    export_json=EXPORT_JSON,
    output_path=OUTPUT_JSON_PATH,
):
    topics = topics or DEFAULT_TOPICS
    all_results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topics": topics,
        "items": {},
    }

    for index, topic in enumerate(topics):
        if verbose:
            print(f"\n=== Running topic: {topic} ===")

        try:
            all_results["items"][topic] = run_pipeline(query=topic, limit=limit, verbose=verbose)
        except Exception as exc:
            all_results["items"][topic] = {
                "query": topic,
                "run_at": datetime.now(timezone.utc).isoformat(),
                "results": [],
                "summary": {},
                "error": str(exc),
            }
            print(f"Error while processing '{topic}': {exc}")

        if export_json:
            all_results["generated_at"] = datetime.now(timezone.utc).isoformat()
            export_results_to_json(all_results, output_path=output_path)

        should_wait = index < len(topics) - 1 and delay_seconds > 0
        if should_wait:
            if verbose:
                print(f"Waiting {delay_seconds} seconds before the next topic...")
            time.sleep(delay_seconds)

    return all_results


def run_topics_forever(
    topics=None,
    limit=DEFAULT_LIMIT,
    topic_delay_seconds=TOPIC_DELAY_SECONDS,
    cycle_delay_seconds=CYCLE_DELAY_SECONDS,
    verbose=True,
    export_json=EXPORT_JSON,
    output_path=OUTPUT_JSON_PATH,
):
    while True:
        all_results = run_topics_once(
            topics=topics,
            limit=limit,
            delay_seconds=topic_delay_seconds,
            verbose=verbose,
            export_json=export_json,
            output_path=output_path,
        )

        if export_json:
            all_results["generated_at"] = datetime.now(timezone.utc).isoformat()
            export_results_to_json(all_results, output_path=output_path)

        if verbose:
            print(f"Cycle complete. Waiting {cycle_delay_seconds} seconds before restarting...")

        time.sleep(cycle_delay_seconds)


if __name__ == "__main__":
    if RUN_FOREVER:
        run_topics_forever()
    else:
        run_topics_once()
