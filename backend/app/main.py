from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.demo_company import router as demo_company_router

app = FastAPI(
    title="AI Decision Laboratory V2",
    description="Organization-Oriented Decision Engineering Framework",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(demo_company_router)


@app.get("/")
def root():
    return {
        "message": "Welcome to AI Decision Laboratory V2"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "AI Decision Laboratory V2",
        "version": "2.0.0",
    }