
import json
import base64
import os
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydantic import BaseModel, Field
from pypdf import PdfReader
from pymongo import MongoClient, DESCENDING
from pymongo.errors import PyMongoError


# Load environment variables
load_dotenv()


# Groq connection
client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

model = "openai/gpt-oss-120b"


# MongoDB connection
mongodb_url = os.getenv("MONGODB_URL")

if not mongodb_url:
    raise ValueError("MONGODB_URL is missing")

mongo_client = MongoClient(
    mongodb_url,
    serverSelectionTimeoutMS=5000
)

database = mongo_client["hiremeai"]
chat_collection = database["chat_history"]


app = FastAPI()


# Allow React frontend to communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://hiremeai-self-nine.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Resume data models

class Experience(BaseModel):
    company: str | None = None
    role: str | None = None
    duration: str | None = None
    description: str | None = None
    skills_used: list[str] = Field(default_factory=list)


class Resume(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None

    total_experience_years: float | None = None

    skills: list[str] = Field(default_factory=list)
    experiences: list[Experience] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


resume_schema = Resume.model_json_schema()


class ChatRequest(BaseModel):
    question: str


# Store parsed resume in memory
candidate_resume = None


# Extract text from PDF

def read_pdf(file_path: Path):

    reader = PdfReader(str(file_path))

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    if not text.strip():
        raise ValueError("No readable text found in the resume PDF.")

    return text


# Parse resume using Groq

def parse_resume(resume_text):

    system_prompt = f"""
    You are an expert resume parser.

    Extract information from the resume based on its meaning,
    not only based on exact section headings.

    Different resumes may use different headings.

    For example:
    - Experience
    - Professional Experience
    - Work History
    - Employment
    - Internships

    These may all contain relevant experience.

    Skills may also appear in the skills section, work experience,
    internships or projects.

    Return ONLY valid JSON matching this schema:

    {resume_schema}

    Important rules:

    1. Do not invent information.
    2. If a value is not available, return null.
    3. If a list has no information, return an empty list.
    4. Include internships inside experiences.
    5. Extract skills mentioned across the entire resume.
    """

    user_prompt = f"""
    Parse the following resume:

    {resume_text}
    """

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        response_format={
            "type": "json_object"
        }
    )

    raw_output = response.choices[0].message.content

    data = json.loads(raw_output)

    resume = Resume(**data)

    return resume


# Load and parse resume when backend starts

@app.on_event("startup")
def load_candidate_resume():

    global candidate_resume

    # Test MongoDB connection
    mongo_client.admin.command("ping")

    print("MongoDB connected successfully!")

    # Check Render Secret File first
    secret_path = Path("/etc/secrets/my_resume.pdf")

    if secret_path.exists():

        print("Loading resume from Render Secret File...")

        encoded_pdf = secret_path.read_text().strip()

        decoded_pdf = base64.b64decode(encoded_pdf)

        pdf_path = Path("/tmp/my_resume.pdf")

        pdf_path.write_bytes(decoded_pdf)

    else:

        # Use local PDF during development
        print("Loading resume from local folder...")

        pdf_path = Path(__file__).resolve().parent / "my_resume.pdf"

    if not pdf_path.exists():
        raise FileNotFoundError("my_resume.pdf was not found.")

    print("Reading candidate resume...")

    resume_text = read_pdf(pdf_path)

    print("Parsing candidate resume...")

    candidate_resume = parse_resume(resume_text)

    print("Candidate resume loaded successfully!")


# Generate HR answers using Groq

def ask_candidate(question: str, resume: Resume):

    system_prompt = f"""
    You are an AI assistant representing a job candidate during an HR interview.

    Here is the candidate's resume information:

    {resume.model_dump_json(indent=2)}

    Follow these rules strictly:

    1. Answer only using the information provided in the resume.
    2. Never invent skills, experience, achievements or project details.
    3. Keep answers concise, professional and natural.
    4. Keep most answers within 40 to 70 words.
    5. For project-related questions, answer in 2 to 3 sentences
       per project.
    6. Mention the project's purpose, implementation details
       and technologies only when available.
    7. For technical skills questions, use short bullet points
       when appropriate.
    8. Avoid unnecessary introductions and repeated information.
    9. Speak in the first person, as if the candidate is answering HR.
    10. If information is unavailable, clearly say:
        "I don't have enough information to answer that based on my resume."
    11. Do not make assumptions to fill missing information.

    Your goal is to give HR clear, accurate and easy-to-read answers.
    """

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": question
            }
        ]
    )

    return response.choices[0].message.content


# Home route

@app.get("/")
def home():

    return {
        "message": "Ye home page hai"
    }


# Chat route

@app.post("/chat")
def chat(request: ChatRequest):

    if candidate_resume is None:
        raise HTTPException(
            status_code=503,
            detail="Candidate resume is not loaded yet."
        )

    answer = ask_candidate(
        request.question,
        candidate_resume
    )

    created_at = datetime.now(timezone.utc)

    chat_document = {
        "question": request.question,
        "answer": answer,
        "created_at": created_at
    }

    try:
        result = chat_collection.insert_one(chat_document)

    except PyMongoError:
        raise HTTPException(
            status_code=500,
            detail="Could not save chat history."
        )

    return {
        "answer": answer,
        "id": str(result.inserted_id),
        "created_at": created_at.isoformat()
    }


# Get saved chat history

@app.get("/history")
def get_history():

    try:
        history_documents = list(
            chat_collection.find()
            .sort("created_at", DESCENDING)
            .limit(100)
        )

        history_documents.reverse()

        history = []

        for document in history_documents:

            history.append({
                "id": str(document["_id"]),
                "question": document["question"],
                "answer": document["answer"],
                "created_at": document["created_at"].isoformat()
            })

        return {
            "history": history
        }

    except PyMongoError:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve chat history."
        )
