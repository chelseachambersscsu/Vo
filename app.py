import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify, g

app = Flask(__name__)
app.jinja_env.filters["fromjson"] = json.loads

DATABASE = os.path.join(os.path.dirname(__file__), "memoboat.db")
OPENAI_API_KEY = "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"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    """Open a new database connection per-request and store it on `g`."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the three required tables and seed meeting types."""
    db = sqlite3.connect(DATABASE)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS meeting_types (
            type_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name TEXT    NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS transcripts (
            transcript_id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_id       INTEGER NOT NULL,
            raw_notes     TEXT    NOT NULL,
            timestamp     TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (type_id) REFERENCES meeting_types(type_id)
        );

        CREATE TABLE IF NOT EXISTS summaries (
            summary_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            transcript_id INTEGER NOT NULL UNIQUE,
            summary       TEXT    NOT NULL,
            action_items  TEXT    NOT NULL,
            key_decisions TEXT    NOT NULL,
            FOREIGN KEY (transcript_id) REFERENCES transcripts(transcript_id)
        );
        """
    )
    # Seed default meeting types
    default_types = [
        "Stand-up",
        "Sprint Planning",
        "Retrospective",
        "One-on-One",
        "Brainstorming",
        "Client Call",
        "All Hands",
        "Design Review",
    ]
    for t in default_types:
        db.execute(
            "INSERT OR IGNORE INTO meeting_types (type_name) VALUES (?)", (t,)
        )
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    db = get_db()
    meeting_types = db.execute(
        "SELECT type_id, type_name FROM meeting_types ORDER BY type_name"
    ).fetchall()
    return render_template("home.html", meeting_types=meeting_types)


@app.route("/saved")
def saved_memos():
    db = get_db()
    memos = db.execute(
        """
        SELECT s.summary_id, s.summary, t.timestamp, mt.type_name
        FROM summaries s
        JOIN transcripts t  ON s.transcript_id = t.transcript_id
        JOIN meeting_types mt ON t.type_id = mt.type_id
        ORDER BY t.timestamp DESC
        """
    ).fetchall()
    return render_template("saved.html", memos=memos)


@app.route("/memo/<int:summary_id>")
def view_memo(summary_id):
    db = get_db()
    memo = db.execute(
        """
        SELECT s.summary_id, s.summary, s.action_items, s.key_decisions,
               t.raw_notes, t.timestamp, mt.type_name
        FROM summaries s
        JOIN transcripts t  ON s.transcript_id = t.transcript_id
        JOIN meeting_types mt ON t.type_id = mt.type_id
        WHERE s.summary_id = ?
        """,
        (summary_id,),
    ).fetchone()
    if memo is None:
        return "Memo not found", 404
    return render_template("view_memo.html", memo=memo)


@app.route("/about")
def about():
    return render_template("about.html")


# ---------------------------------------------------------------------------
# API: Generate memo via OpenAI
# ---------------------------------------------------------------------------

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True)
    raw_notes = data.get("raw_notes", "").strip()
    type_id = data.get("type_id")

    if not raw_notes or not type_id:
        return jsonify({"error": "Meeting type and notes are required."}), 400

    # Call OpenAI
    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a meeting memo assistant. Given raw meeting notes, "
                        "produce a JSON object with exactly three keys:\n"
                        '  "summary": a concise paragraph summarising the meeting,\n'
                        '  "action_items": a JSON array of action-item strings,\n'
                        '  "key_decisions": a JSON array of key-decision strings.\n'
                        "Return ONLY valid JSON, no markdown fences."
                    ),
                },
                {"role": "user", "content": raw_notes},
            ],
            temperature=0.4,
        )
        content = completion.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        result = json.loads(content)
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse AI response."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Persist to database
    db = get_db()
    cur = db.execute(
        "INSERT INTO transcripts (type_id, raw_notes) VALUES (?, ?)",
        (type_id, raw_notes),
    )
    transcript_id = cur.lastrowid
    db.execute(
        "INSERT INTO summaries (transcript_id, summary, action_items, key_decisions) VALUES (?, ?, ?, ?)",
        (
            transcript_id,
            result.get("summary", ""),
            json.dumps(result.get("action_items", [])),
            json.dumps(result.get("key_decisions", [])),
        ),
    )
    db.commit()

    return jsonify(result)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=3000)
