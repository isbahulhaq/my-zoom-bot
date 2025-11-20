import os
import asyncio
import threading
import random
from flask import Flask, render_template, request, jsonify
from playwright.async_api import async_playwright
import nest_asyncio
import indian_names

# Apply async patch
nest_asyncio.apply()

app = Flask(__name__)

running = True
activity_logs = []    # LIVE logs for Dashboard (Success + Failure)


# ================================
# OPTIONAL: MONGODB SUPPORT
# ================================
mongo_uri = os.environ.get("MONGO_URI")  # agar Mongo use karna ho
db = None
logs_col = None

if mongo_uri:
    from pymongo import MongoClient
    client = MongoClient(mongo_uri)
    db = client["zoom_bot_db"]
    logs_col = db["bot_logs"]


# ================================
# NAME DATABASES
# ================================
hindu_names = ["Aarav", "Vivaan", "Ishaan", "Rudra", "Kabir", "Raghav"]
muslim_names = ["Ayan", "Rehan", "Zaid", "Arham", "Faizan", "Imran", "Saad"]
english_names = ["Ethan Johnson", "Liam White", "Noah Carter", "James Hill", "Logan King"]
hindi_names = ["अजय", "मोहन", "सूरज", "राजेश", "विक्रम", "संदीप"]


# ================================
# NAME GENERATOR
# ================================
def generate_user(name_type):

    if name_type == "hindu":
        return random.choice(hindu_names)

    if name_type == "muslim":
        return random.choice(muslim_names)

    if name_type == "english":
        return random.choice(english_names)

    if name_type == "hindi":
        return random.choice(hindi_names)

    if name_type == "indian_mix":
        return indian_names.get_first_name() + " " + indian_names.get_last_name()

    # Mix all
    all_names = (
        hindu_names +
        muslim_names +
        english_names +
        hindi_names +
        [indian_names.get_first_name() + " " + indian_names.get_last_name()]
    )
    return random.choice(all_names)


# ================================
# PLAYWRIGHT JOIN BOT
# ================================
async def join_zoom(user, wait_time, meeting_id, passcode):
    global running, activity_logs, logs_col
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context()
            await context.grant_permissions(["microphone"])
            page = await context.new_page()

            await page.goto(f"https://app.zoom.us/wc/join/{meeting_id}")

            try:
                await page.fill('input[type="text"]', user)
                await page.fill('input[type="password"]', passcode)
                await page.click('button.preview-join-button')

                log_item = {
                    "name": user,
                    "status": "success",
                    "reason": "Joined successfully",
                    "meeting_id": meeting_id
                }
                activity_logs.append(log_item)

                if logs_col:
                    logs_col.insert_one(log_item)

            except Exception as e:

                log_item = {
                    "name": user,
                    "status": "failed",
                    "reason": f"Join failed: {str(e)}",
                    "meeting_id": meeting_id
                }
                activity_logs.append(log_item)

                if logs_col:
                    logs_col.insert_one(log_item)

            # Stay in meeting
            total = wait_time
            while running and total > 0:
                await asyncio.sleep(1)
                total -= 1

            await browser.close()

    except Exception as e:

        log_item = {
            "name": user,
            "status": "failed",
            "reason": f"Browser crash: {str(e)}",
            "meeting_id": meeting_id
        }
        activity_logs.append(log_item)

        if logs_col:
            logs_col.insert_one(log_item)


# ================================
# MULTI BOT LAUNCH
# ================================
async def launch_bots(meeting_id, passcode, members, timeout, name_type):
    tasks = []
    for _ in range(members):
        user = generate_user(name_type)
        tasks.append(join_zoom(user, timeout, meeting_id, passcode))

    await asyncio.gather(*tasks)


# ================================
# ROUTES
# ================================
@app.route("/")
def home():
    return render_template("index.html")


# OLD + NEW UI START
@app.route("/start", methods=["GET", "POST"])
def start_meeting():
    try:
        meeting_id = request.values.get("meetingid")
        password = request.values.get("password")
        wait_time = int(request.values.get("waittime", 5))
        name_type = request.values.get("name_type", "mix_all")

        user = generate_user(name_type)
        asyncio.run(join_zoom(user, wait_time, meeting_id, password))

        return jsonify({"status": "started"})
    except Exception as e:
        return jsonify({"error": str(e)})


# NEW UI JOIN
@app.route("/join", methods=["POST"])
def join_new():
    try:
        meeting_id = request.form.get("meeting_id")
        password = request.form.get("password")
        members = int(request.form.get("members"))
        timeout = int(request.form.get("timeout"))
        name_type = request.form.get("name_type", "mix_all")

        asyncio.run(launch_bots(meeting_id, password, members, timeout, name_type))

        return jsonify({
            "status": "meeting started",
            "members": members,
            "name_type": name_type
        })

    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/end", methods=["GET", "POST"])
def end_meeting():
    global running
    running = False
    return jsonify({"message": "Meeting Ended"})


# LIVE LOGS FOR DASHBOARD
@app.route("/logs")
def get_logs():
    return jsonify(activity_logs)


# MONGO LOGS (Optional)
@app.route("/mongo-logs")
def mongo_logs():
    if not logs_col:
        return jsonify({"error": "MongoDB not enabled"})

    data = []
    for log in logs_col.find().sort("_id", -1):
        data.append({
            "meeting_id": log["meeting_id"],
            "name": log["name"],
            "status": log["status"],
            "reason": log["reason"]
        })
    return jsonify(data)


# ================================
# RUN SERVER
# ================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
