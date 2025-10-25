from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from gemini.models.models import get_model_names, get_available_models

app = FastAPI()

# Configure CORS
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:1420",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/models")
def get_models():
    try:
        models = get_model_names()
        return {"success": True, "models": models}
    except Exception as e:
        return {"success": False, "error": "Error getting models", "message": str(e)}
    
@app.get("/models/list")
def get_models_list():
    try:
        models = get_available_models()
        return {"success": True, "models": models}
    except Exception as e:
        return {"success": False, "error": "Error getting models", "message": str(e)}
    


# ========================================
# RAG STORE FILES & Documents
# ========================================
@app.post("/api/v0/rag/store_files")
def store_files(files: List[UploadFile] = File(...)):
    pass

@app.post("/api/v0/rag/store_documents")
def store_documents(documents: List[str] = Form(...)):
    pass

@app.post("/api/v0/rag/index_documents")
def index_documents(documents: List[str] = Form(...)):
    pass

@app.post("/api/v0/rag/query_documents")
def query_documents(query: str = Form(...)):
    pass

