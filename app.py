import os
import json
import shlex
import subprocess
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, flash

# ---------- CONFIG ----------
UPLOAD_FOLDER = "uploads"
CMD_TIMEOUT = 25  # per-tool timeout

# Optional sample file (only if you really use it)
SAMPLE_FILE_PATH = "/mnt/data/A_digital_photograph_displays_a_daytime_landscape_.png"

# ---------- SAFE TOOL COMMANDS ----------
TOOL_COMMANDS = {
    # Image Tools (SAFE)
    "exiftool": ["exiftool", "{file}"],
    "exiv2": ["exiv2", "{file}"],
    "identify": ["identify", "-verbose", "{file}"],
    "mat2": ["mat2", "{file}"],
    "strings": ["strings", "-a", "{file}"],
    "binwalk": ["binwalk", "{file}"],

    # Video / Audio Tools (SAFE)
    "ffprobe": [
        "ffprobe", "-v", "error",
        "-show_format", "-show_streams",
        "-print_format", "json", "{file}"
    ],
    "mediainfo": ["mediainfo", "{file}"],

    # Binary / Firmware Tools (SAFE)
    "readelf": ["readelf", "-h", "{file}"],
    "objdump": ["objdump", "-f", "{file}"],
    "rabin2": ["rabin2", "-I", "{file}"],
    "file": ["file", "-k", "{file}"],

    # Document Tools (SAFE)
    "pdfinfo": ["pdfinfo", "{file}"],
    "pdfimages": ["pdfimages", "-list", "{file}"],
    "docx2txt": ["docx2txt", "{file}", "-"],
    "qpdf": ["qpdf", "--show-encryption", "{file}"],
    "mutool": ["mutool", "info", "{file}"],

    # Network Tools (SAFE – PCAP only)
    "tshark": ["tshark", "-r", "{file}"],
}

# Tool categories (for UI)
IMAGE_TOOLS = ["exiftool", "exiv2", "identify", "mat2", "strings", "binwalk"]
VIDEO_TOOLS = ["ffprobe", "mediainfo"]
BINARY_TOOLS = ["readelf", "objdump", "rabin2", "strings", "file"]
DOC_TOOLS = ["pdfinfo", "pdfimages", "docx2txt", "qpdf", "mutool"]
NETWORK_TOOLS = ["tshark"]

# ---------- APP ----------
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.secret_key = "change-this-in-production"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- HELPERS ----------
def safe_run(cmd_list, timeout=CMD_TIMEOUT):
    """Run tool safely without shell"""
    try:
        start = datetime.now()
        proc = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        end = datetime.now()
        return {
            "cmd": " ".join(shlex.quote(x) for x in cmd_list),
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "elapsed": (end - start).total_seconds()
        }
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except FileNotFoundError:
        return {"error": "binary-not-found"}
    except Exception as e:
        return {"error": str(e)}

def run_tools_on_file(filepath, selected_tools):
    results = {}
    for tool in selected_tools:
        if tool not in TOOL_COMMANDS:
            results[tool] = {"error": "tool-not-configured"}
            continue
        cmd = [c.format(file=filepath) for c in TOOL_COMMANDS[tool]]
        results[tool] = safe_run(cmd)
    return results

def save_uploaded_file(file_storage):
    filename = os.path.basename(file_storage.filename)
    dest = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    base, ext = os.path.splitext(filename)
    i = 1
    while os.path.exists(dest):
        dest = os.path.join(app.config["UPLOAD_FOLDER"], f"{base}_{i}{ext}")
        i += 1
    file_storage.save(dest)
    return os.path.abspath(dest), os.path.basename(dest)

# ---------- SUSPICION SCORING ----------
def compute_suspicion_score(results, filename):
    score = 0
    reasons = []

    # File signature mismatch
    f_out = results.get("file", {}).get("stdout", "").lower()
    if f_out:
        if "jpeg" in f_out and not filename.lower().endswith((".jpg", ".jpeg")):
            score += 15; reasons.append("JPEG signature but extension mismatch")
        if "png" in f_out and not filename.lower().endswith(".png"):
            score += 12; reasons.append("PNG signature but extension mismatch")
        if "pdf" in f_out and not filename.lower().endswith(".pdf"):
            score += 14; reasons.append("PDF signature but extension mismatch")

    # Strings analysis
    s_out = results.get("strings", {}).get("stdout", "").lower()
    if s_out:
        head = s_out[:800]
        if "mz" in head:
            score += 25; reasons.append("Embedded Windows PE (MZ) header detected")
        if "elf" in head:
            score += 22; reasons.append("Embedded ELF binary detected")
        for kw in ["password", "secret", "private key", "-----begin"]:
            if kw in s_out:
                score += 8; reasons.append(f"Sensitive keyword found: {kw}")

    # Binwalk detection
    bw_out = results.get("binwalk", {}).get("stdout", "")
    if bw_out:
        lines = bw_out.strip().splitlines()
        if len(lines) > 2:
            score += min(25, 5 + len(lines))
            reasons.append("Embedded data detected by binwalk")

    # Media parsing issues
    ff_err = results.get("ffprobe", {}).get("stderr", "")
    if ff_err:
        score += 10; reasons.append("Media parsing errors detected")

    # ELF detection via readelf
    if "ELF" in results.get("readelf", {}).get("stdout", ""):
        score += 25; reasons.append("ELF header confirmed by readelf")

    score = min(100, score)
    verdict = (
        "Likely Malicious" if score >= 50
        else "Possibly Suspicious" if score >= 25
        else "Likely Clean"
    )
    return score, verdict, reasons

# ---------- ROUTES ----------
@app.route("/")
def index():
    return render_template(
        "index.html",
        image_tools=IMAGE_TOOLS,
        video_tools=VIDEO_TOOLS,
        binary_tools=BINARY_TOOLS,
        doc_tools=DOC_TOOLS,
        network_tools=NETWORK_TOOLS
    )

@app.route("/analyze", methods=["POST"])
def analyze():
    selected_tools = request.form.getlist("tools")
    if not selected_tools:
        selected_tools = ["file", "strings", "exiftool"]

    if "file" not in request.files:
        flash("No file uploaded", "danger")
        return redirect(url_for("index"))

    file = request.files["file"]
    if file.filename == "":
        flash("Empty filename", "danger")
        return redirect(url_for("index"))

    filepath, filename = save_uploaded_file(file)

    results = run_tools_on_file(filepath, selected_tools)
    score, verdict, reasons = compute_suspicion_score(results, filename)

    # Save JSON report
    json_name = f"{filename}_analysis.json"
    json_path = os.path.join(app.config["UPLOAD_FOLDER"], json_name)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "file": filename,
            "score": score,
            "verdict": verdict,
            "reasons": reasons,
            "results": results
        }, f, indent=2)

    return render_template(
        "results.html",
        filename=filename,
        results=results,
        score=score,
        verdict=verdict,
        reasons=reasons,
        json_download=url_for("download", name=json_name)
    )

@app.route("/download/<name>")
def download(name):
    path = os.path.join(app.config["UPLOAD_FOLDER"], name)
    if not os.path.exists(path):
        flash("File not found", "danger")
        return redirect(url_for("index"))
    return send_file(path, as_attachment=True)

@app.route("/ping")
def ping():
    return "pong"

# ---------- RENDER-SAFE RUN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
