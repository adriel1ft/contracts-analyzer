from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import upload, anonymize

app = FastAPI(title="Contract Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api")
app.include_router(anonymize.router, prefix="/api")

@app.get("/")
def home():
    return {"message": "API de Análise de Contratos ativa 🚀"}
