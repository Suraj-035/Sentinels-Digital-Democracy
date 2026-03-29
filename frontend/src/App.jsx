import { useEffect, useRef, useState } from "react";

const initialForm = {
  query: "",
  maxVideos: 2,
  newsLimit: 8,
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const wsBaseUrl = apiBaseUrl.replace(/^http/, "ws");

function sentimentTone(value) {
  if (value === "positive") return "positive";
  if (value === "negative") return "negative";
  return "neutral";
}

function App() {
  const [form, setForm] = useState(initialForm);
  const [state, setState] = useState(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [backendStatus, setBackendStatus] = useState("checking");
  const socketRef = useRef(null);

  useEffect(() => {
    let mounted = true;

    const checkBackend = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/api/health`);
        if (!mounted) return;
        setBackendStatus(response.ok ? "online" : "offline");
      } catch {
        if (!mounted) return;
        setBackendStatus("offline");
      }
    };

    checkBackend();
    const intervalId = window.setInterval(checkBackend, 15000);

    return () => {
      mounted = false;
      window.clearInterval(intervalId);
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, []);

  const connectSocket = (runId) => {
    if (socketRef.current) {
      socketRef.current.close();
    }

    const socket = new WebSocket(`${wsBaseUrl}/ws/${runId}`);

    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.state) {
        setState(payload.state);
      }
    };

    socket.onerror = () => {
      setError("Live updates were interrupted. The backend may be restarting, but the latest saved state is still visible.");
    };

    socketRef.current = socket;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      let response;
      let lastError;

      for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
          response = await fetch(`${apiBaseUrl}/api/search`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              query: form.query,
              maxVideos: Number(form.maxVideos),
              newsLimit: Number(form.newsLimit),
            }),
          });
          break;
        } catch (submitError) {
          lastError = submitError;
          await new Promise((resolve) => window.setTimeout(resolve, 1200));
        }
      }

      if (!response && lastError) {
        throw new Error("Backend is unreachable right now. Please wait a moment and try again.");
      }

      if (!response.ok) {
        throw new Error("Unable to start the analysis run.");
      }

      const data = await response.json();
      setState(data.state);
      setBackendStatus("online");
      connectSocket(data.runId);
    } catch (submitError) {
      setError(submitError.message);
      setBackendStatus("offline");
    } finally {
      setIsSubmitting(false);
    }
  };

  const youtubeVideos = state?.youtube?.videos ?? [];
  const newsResults = state?.news?.results ?? [];

  return (
    <div className="app-shell">
      <div className="bg-orb bg-orb-a" />
      <div className="bg-orb bg-orb-b" />

      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow"> Dashboard</p>
          <h1>Sentinels</h1>
          <p className="hero-text">
            Search a topic and watch your YouTube + News intelligence pipeline
            stream live analysis into one command center.
          </p>
        </div>

        <form className="search-panel" onSubmit={handleSubmit}>
          <label className="field-label" htmlFor="query">
            Search Topic
          </label>
          <input
            id="query"
            className="search-input"
            value={form.query}
            placeholder="Try: farmers protest, election rally, AI layoffs..."
            onChange={(event) =>
              setForm((current) => ({ ...current, query: event.target.value }))
            }
          />

          <div className="field-grid">
            <label>
              <span className="field-label">Videos</span>
              <input
                className="mini-input"
                type="number"
                min="1"
                max="5"
                value={form.maxVideos}
                onChange={(event) =>
                  setForm((current) => ({ ...current, maxVideos: event.target.value }))
                }
              />
            </label>

            <label>
              <span className="field-label">News</span>
              <input
                className="mini-input"
                type="number"
                min="1"
                max="20"
                value={form.newsLimit}
                onChange={(event) =>
                  setForm((current) => ({ ...current, newsLimit: event.target.value }))
                }
              />
            </label>
          </div>

          <button className="search-button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Launching..." : "Run Live Analysis"}
          </button>
        </form>
      </header>

      <section className="status-bar">
        <div className="status-card">
          <span className="status-label">Current Stage</span>
          <strong>{state?.progress?.stage ?? "idle"}</strong>
          <p>{state?.progress?.message ?? "Submit a search to begin streaming data."}</p>
        </div>

        <div className="status-card">
          <span className="status-label">Run Status</span>
          <strong>{state?.status ?? "ready"}</strong>
          <p>{state?.query ? `Query: ${state.query}` : "No active query yet."}</p>
        </div>

        <div className="status-card">
          <span className="status-label">Live Counts</span>
          <strong>
            {youtubeVideos.length} videos / {newsResults.length} articles
          </strong>
          <p>Results appear as each backend stage finishes.</p>
        </div>

        <div className="status-card">
          <span className="status-label">Backend</span>
          <strong>{backendStatus}</strong>
          <p>
            {backendStatus === "online"
              ? "API is reachable."
              : backendStatus === "offline"
                ? "API is currently unavailable."
                : "Checking API status."}
          </p>
        </div>
      </section>

      {error ? <div className="banner error-banner">{error}</div> : null}
      {state?.errors?.length ? (
        <div className="banner warning-banner">
          {state.errors.map((item, index) => (
            <p key={`${item.source}-${index}`}>
              {item.source}: {item.message}
            </p>
          ))}
        </div>
      ) : null}

      <main className="content-grid">
        <section className="panel primary-panel">
          <div className="panel-header">
            <p className="eyebrow">YouTube Intelligence</p>
            <h2>Video Analysis Stream</h2>
          </div>

          {youtubeVideos.length === 0 ? (
            <div className="empty-state">
              Video cards will appear here with summaries, motion intensity, comments
              sentiment, and the live player.
            </div>
          ) : (
            <div className="video-list">
              {youtubeVideos.map((video) => (
                <article className="video-card" key={video.videoId}>
                  <div className="video-frame-wrap">
                    {video.thumbnail ? (
                      <img
                        className="video-thumbnail"
                        src={video.thumbnail}
                        alt={video.title}
                      />
                    ) : null}
                    <iframe
                      className="video-frame"
                      src={video.embedUrl}
                      title={video.title}
                      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                      referrerPolicy="strict-origin-when-cross-origin"
                      allowFullScreen
                    />
                    <div className="player-fallback">
                      If the video does not play here, open it on YouTube.
                    </div>
                  </div>

                  <div className="video-content">
                    <div className="card-topline">
                      <span className={`pill tone ${sentimentTone(video.transcriptSentiment?.label)}`}>
                        transcript {video.transcriptSentiment?.label ?? "unknown"}
                      </span>
                      <span className="pill subtle">{video.audio.language}</span>
                    </div>

                    <h3>{video.title}</h3>
                    <div className="summary-block">
                      <span className="summary-label">Video Description</span>
                      <p className="card-copy">{video.videoSummary || video.generatedDescription}</p>
                    </div>

                    <div className="summary-block">
                      <span className="summary-label">Transcript Summary</span>
                      <p className="card-copy">
                        {video.hasTranscript
                          ? video.transcriptSummary
                          : "Transcript could not be extracted reliably for this video."}
                      </p>
                    </div>

                    <div className="summary-block">
                      <span className="summary-label">Transcript Sentiment</span>
                      <p className="card-copy accent-copy">
                        {video.hasTranscript
                          ? video.transcriptSentimentSummary
                          : "Transcript sentiment is unavailable because speech-to-text did not return a reliable transcript."}
                      </p>
                    </div>

                    <div className="summary-block">
                      <span className="summary-label">Comment Sentiment</span>
                      <p className="card-copy">{video.commentSummary}</p>
                    </div>

                    <div className="metric-grid">
                      <div className="metric-box">
                        <span>Motion</span>
                        <strong>{video.motion.motion_intensity}</strong>
                        <small>{video.motion.crowd_motion}</small>
                      </div>
                      <div className="metric-box">
                        <span>Comments</span>
                        <strong>{video.comments.sentiment}</strong>
                        <small>{video.comments.num_comments} pulled</small>
                      </div>
                      <div className="metric-box">
                        <span>Audio</span>
                        <strong>{video.audio.intensity}</strong>
                        <small>{video.audio.speaking ? "speech detected" : "quiet scene"}</small>
                      </div>
                      <div className="metric-box">
                        <span>Transcript Mood</span>
                        <strong>{video.transcriptSentiment?.label ?? "unknown"}</strong>
                        <small>score {video.transcriptSentiment?.score ?? 0}</small>
                      </div>
                      <div className="metric-box">
                        <span>Region</span>
                        <strong>{video.regionLabel || "Unknown"}</strong>
                        <small>confidence {video.region?.confidence ?? 0}</small>
                      </div>
                    </div>

                    <a className="card-link" href={video.url} target="_blank" rel="noreferrer">
                      Open YouTube Video
                    </a>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="panel side-panel">
          <div className="panel-header">
            <p className="eyebrow">News Intelligence</p>
            <h2>Article Sentiment Feed</h2>
          </div>

          {newsResults.length === 0 ? (
            <div className="empty-state">
              News sentiment results will stream here with explanations and source links.
            </div>
          ) : (
            <div className="news-list">
              {newsResults.map((article, index) => (
                <article className={`news-card ${sentimentTone(article.sentiment)}`} key={`${article.url}-${index}`}>
                  <div className="card-topline">
                    <span className="pill">{state?.query || article.category}</span>
                    <span className={`pill tone ${sentimentTone(article.sentiment)}`}>
                      {article.sentiment}
                    </span>
                  </div>
                  <h3>{article.title}</h3>
                  <p className="card-copy">{article.explanation}</p>
                  <div className="news-meta">
                    <span>{article.source || "Unknown source"}</span>
                    <span>{article.language}</span>
                    <span>{Number(article.confidence).toFixed(2)}</span>
                  </div>
                  <a className="card-link" href={article.url} target="_blank" rel="noreferrer">
                    Read article
                  </a>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
