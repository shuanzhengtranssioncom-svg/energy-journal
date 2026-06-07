import json
import os
import urllib.request
import urllib.error

from flask import Flask, jsonify, redirect, render_template, make_response, request

app = Flask(__name__)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"


def chat(system_prompt, user_message):
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY not set")

    body = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.7,
        "max_tokens": 256,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API error {e.code}: {msg[:200]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")


@app.route("/")
def index():
    return redirect("/energy-journal")


@app.route("/energy-journal")
def energy_journal():
    resp = make_response(render_template("energy_journal.html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/api/energy-journal/feedback", methods=["POST"])
def api_energy_journal_feedback():
    if not DEEPSEEK_API_KEY:
        return jsonify({"encouragement": None, "fallback": True})

    data = request.get_json() or {}
    action = data.get("action", "")
    feeling = data.get("feeling", "")
    thanks_target = data.get("thanks_target", "双手")
    thanks = data.get("thanks", "")
    day = data.get("day", 1)
    request_review = data.get("request_review", False)
    is_week_complete = data.get("is_week_complete", False)
    week_entries = data.get("week_entries", [])

    if not action or not feeling:
        return jsonify({"error": "缺少必填字段"}), 400

    result = {"encouragement": None, "is_week_complete": is_week_complete, "week_review": None}

    system_prompt = "你是一个温暖的心理陪伴者，遵循行为激活和具身认知的原则。你的每一句话都是为了帮来访者看见自己的行动力。\n\n规则：\n1. 必须具体提到用户做的事（证明你看到了）\n2. 肯定感受的合理性\n3. 呼应被感谢的身体部位——如果用户感谢了脚，就说“你的脚…”；感谢了手，就说“你的手…”\n4. 不做比较（不说“比昨天好”）\n5. 不给建议（不说“明天可以试试…”）\n6. 不用感叹号结尾\n7. 生成30-50字，温暖但克制"

    try:
        if request_review and is_week_complete and week_entries:
            actions_summary = "、".join([e.get("action", "") for e in week_entries])
            user_prompt = f"用户完成了一周的7天记录。这一周做过的事：{actions_summary}\n\n请生成一段100-150字的一周回顾：\n1. 回顾这些具体的事情\n2. 提炼一个共同的主题（如“你的身体这周都在照顾生命”）\n3. 不评分、不排名、不比较\n4. 温暖而不煎情，不用感叹号结尾"
            try:
                result["week_review"] = chat(system_prompt, user_prompt)
            except Exception:
                result["week_review"] = None

        user_prompt = f"用户今天第{day}天的记录：\n- 做了什么事：{action}\n- 感受：{feeling}\n- 感谢的身体部位：{thanks_target}\n- 感谢的话：{thanks}\n\n请生成一段温暖反馈。"
        result["encouragement"] = chat(system_prompt, user_prompt)
    except Exception:
        result["encouragement"] = None
        result["fallback"] = True

    return jsonify(result)
