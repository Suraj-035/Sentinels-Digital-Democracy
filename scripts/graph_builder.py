# scripts/graph_builder.py

from neo4j import GraphDatabase
from datetime import datetime

# -------------------------------
# CONFIG
# -------------------------------

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"  # CHANGE THIS


driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)


# -------------------------------
# MAIN FUNCTION
# -------------------------------

def store_event_graph(video_id, event, region, comments):

    timestamp = datetime.utcnow().isoformat()

    with driver.session() as session:
        session.execute_write(
            _create_graph,
            video_id,
            event,
            region,
            comments,
            timestamp
        )


# -------------------------------
# GRAPH CREATION
# -------------------------------

def _create_graph(tx, video_id, event, region, comments, timestamp):

    tx.run("""
    MERGE (v:Video {id: $video_id})

    SET v.timestamp = $timestamp,
        v.people_count = $people_count,
        v.intensity = $intensity,
        v.motion = $motion,
        v.confidence = $confidence

    MERGE (e:Event {type: $event_type})
    MERGE (r:Region {name: $region})
    MERGE (s:Sentiment {type: $sentiment})

    MERGE (v)-[:HAS_EVENT]->(e)
    MERGE (v)-[:OCCURS_IN]->(r)
    MERGE (v)-[:HAS_SENTIMENT]->(s)
    """,
    video_id=video_id,
    event_type=event["event_type"],
    region=region["region"],
    sentiment=comments.get("sentiment", "unknown"),
    people_count=event["num_people"],
    intensity=event["intensity"],
    motion=event.get("motion", "unknown"),
    confidence=event["confidence"],
    timestamp=timestamp
    )

    # -------------------------------
    # TOPICS
    # -------------------------------

    for topic in comments.get("topics", []):
        tx.run("""
        MERGE (t:Topic {name: $topic})
        WITH t
        MATCH (v:Video {id: $video_id})
        MERGE (v)-[:HAS_TOPIC]->(t)
        """,
        topic=topic,
        video_id=video_id
        )