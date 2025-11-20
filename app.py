import os
import asyncio
import random
from flask import Flask, render_template, request, jsonify
from playwright.async_api import async_playwright
import nest_asyncio
import indian_names

nest_asyncio.apply()

app = Flask(__name__)

# =====================================
# GLOBAL BROWSER (mic & camera fix)
# =====================================
playwright_obj = None
shared_browser = None


async def get_browser():
    """
    Start only ONE browser instance for all bots.
    This allows microphone & camera permissions to work for ALL users.
    """
    global playwright_obj, shared_browser

    if playwright_obj is None:
        playwright_obj = await async_playwright().start()

    if shared_browser is None:
        shared_browser = await playwright_obj.chromium.launch(
            headless=True,
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security"
            ]
        )

    return shared_browser


# =====================================
# NAME DATABASES
# =====================================
hindu_names = ["Aarav", "Vivaan", "Ishaan", "Rudra", "Kabir", "Raghav"]
muslim_names = ["Ayan", "Rehan", "Zaid", "Arham", "Faizan", "Imran", "Saad"]
english_names = ["Ethan Johnson", "Liam White", "Noah Carter", "James Hill", "Logan King"]
hindi_names = ["अजय", "मोहन", "सूरज", "राजेश", "विक्रम", "संदीप"]


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

    # all mix
    all_names = (
        hindu_names
        + muslim_names
        + english_names
        + hindi_names
        + [indian_names.get_first_name() + " " + indian_names.get_last_name()]
    )
    return random.choice(all_names)


# =====================================
# JOIN BOT FUNCTION
# =====================================
async def join_zoom(user, wait_time, meeting_id, passcode, logs):
    try:
        browser = await get_browser()

        context = await browser.new_context(
            permissions=["camera", "microphone"],
            ignore_https_errors=True
        )

        page = await context.new_page()

        # Force Zoom mic/camera allow
        await page.evaluate("""
            navigator.mediaDevices.getUserMedia = async () => {
                return new MediaStream();
            };
        """)

        await page.goto(f"https://app.zoom.us/wc/join/{meeting_id}")

        try:
            await page.fill('input[type="text"]', user)
            await page.fill('input[type="password"]', passcode)

            # Try join button repeatedly until success
            for _ in range(10):
                try:
                    await page.click('button.preview-join-button', timeout=2000)
                    break
                except:
                    await asyncio.sleep(1)

            logs.append({"name": user, "status": "Success", "reason": "Joined successfully"})

        except Exception as e:
            logs.append({"name": user, "status": "Failed", "reason": f"Join failed: {str(e)}"})

        await asyncio.sleep(wait_time)
        await context.close()

    except Exception as e:
        logs.append({"name": user, "status": "Failed", "reason": f"Browser crash: {str(e)}"})


# =====================================
# MULTI BOT PARALLEL LAUNCH
# =====================================
async def launch_bots(meeting_id, passcode, members, timeout, name_type):
    logs = []
    tasks = []

    for _ in range(members):
        user = generate_user(name_type)
        tasks.append(join_zoom(user, timeout, meeting_id, passcode, logs))

    await asyncio.gather(*tasks, return_exceptions=True)
    return logs


# =====================================
# ROUTES
# =====================================
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/join", methods=["POST"])
def join_new():
    try:
        meeting_id = request.form.get("meeting_id")
        password = request.form.get("password")
        members = int(request.form.get("members"))
        timeout = int(request.form.get("timeout"))
        name_type = request.form.get("name_type", "mix_all")

        logs = asyncio.run(
            launch_bots(meeting_id, password, members, timeout, name_type)
        )

        return jsonify({"status": "success", "logs": logs})

    except Exception as e:
        return jsonify({"error": str(e)})


# =====================================
# RUN SERVER
# =====================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

