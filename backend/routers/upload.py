from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
import os
from pathlib import Path
import uuid

UPLOAD_DIR = Path("temp/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter()

@router.post("/upload")
async def upload_contract(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}.pdf"

    with open(file_path, "wb") as f:
        f.write(await file.read())

    return JSONResponse({
        "message": "Upload concluído com sucesso.",
        "file_id": file_id,
        "file_path": str(file_path)
    })
