import os
import uuid
import shutil
import asyncio
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

from video_processor import get_video_info, compute_logical_segments, interleave_and_merge

app = FastAPI(title="Video Logical Segment Editor", version="1.0.0")

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
WORK_DIR   = BASE_DIR / "work"

for _d in [UPLOAD_DIR, OUTPUT_DIR, WORK_DIR]:
    _d.mkdir(exist_ok=True)

# In-memory state (sufficient for single-user local app)
videos: dict = {}   # file_id -> {path, info, filename}
jobs:   dict = {}   # job_id  -> {status, progress, result_id, error}


# ── Upload ──────────────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    ct = file.content_type or ""
    if not ct.startswith("video/"):
        raise HTTPException(400, "File must be a video")

    file_id = str(uuid.uuid4())
    ext = Path(file.filename or "video").suffix or ".mp4"
    dest = UPLOAD_DIR / f"{file_id}{ext}"

    with open(dest, "wb") as f:
        f.write(await file.read())

    try:
        info = get_video_info(str(dest))
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, f"Cannot read video: {e}")

    videos[file_id] = {"path": str(dest), "info": info, "filename": file.filename}

    return {
        "file_id":  file_id,
        "filename": file.filename,
        "duration": info["duration"],
        "width":    info["width"],
        "height":   info["height"],
    }


# ── Segment detection ────────────────────────────────────────────────────────

class DetectRequest(BaseModel):
    file_id:      str
    threshold:    float = 0.3
    max_segments: int   = 8


@app.post("/api/detect")
async def detect_segments(req: DetectRequest):
    if req.file_id not in videos:
        raise HTTPException(404, "Video not found")

    loop = asyncio.get_event_loop()
    try:
        segments = await loop.run_in_executor(
            None,
            compute_logical_segments,
            videos[req.file_id]["path"],
            max(0.1, min(0.9, req.threshold)),
            max(2, min(20, req.max_segments)),
        )
    except Exception as e:
        raise HTTPException(500, f"Detection failed: {e}")

    return {"segments": segments, "count": len(segments)}


# ── Merge ────────────────────────────────────────────────────────────────────

class MergeRequest(BaseModel):
    video1_id:  str
    video2_id:  str
    segments1:  list
    segments2:  list


@app.post("/api/merge")
async def merge_videos(req: MergeRequest, background_tasks: BackgroundTasks):
    for vid_id in [req.video1_id, req.video2_id]:
        if vid_id not in videos:
            raise HTTPException(404, f"Video {vid_id} not found")
    if not req.segments1:
        raise HTTPException(400, "segments1 must not be empty")

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "progress": 0, "result_id": None, "error": None}

    background_tasks.add_task(
        _run_merge,
        job_id,
        videos[req.video1_id]["path"],
        req.segments1,
        videos[req.video2_id]["path"],
        req.segments2,
    )
    return {"job_id": job_id}


async def _run_merge(job_id, v1_path, segs1, v2_path, segs2):
    jobs[job_id].update(status="processing", progress=10)
    result_id = str(uuid.uuid4())
    output_path = str(OUTPUT_DIR / f"{result_id}.mp4")
    work_dir = str(WORK_DIR / job_id)

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            interleave_and_merge,
            v1_path, segs1, v2_path, segs2, output_path, work_dir,
        )
        shutil.rmtree(work_dir, ignore_errors=True)
        jobs[job_id].update(status="done", progress=100, result_id=result_id)
    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        jobs[job_id].update(status="error", error=str(e))


@app.get("/api/status/{job_id}")
def job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]


@app.get("/api/download/{result_id}")
def download_result(result_id: str):
    path = OUTPUT_DIR / f"{result_id}.mp4"
    if not path.exists():
        raise HTTPException(404, "Result not found")
    return FileResponse(str(path), media_type="video/mp4", filename="merged_video.mp4")


# ── Static files ─────────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

@app.get("/")
def index():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)
