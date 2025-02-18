import os
import re
import pathlib
from datetime import datetime
import fitz  # PyMuPDF for PDF extraction
from docx import Document
from openai import OpenAI
from typing import Optional, Dict, Any
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from document_text_extraction import DocumentParser
from resume_analyzer import ResumeAnalyzer

app = FastAPI()

def setup_paths(resume_path: str, job_desc_path: str) -> tuple[pathlib.Path, pathlib.Path]:
    """Setup and validate file paths"""
    resume_path = pathlib.Path(resume_path)
    job_desc_path = pathlib.Path(job_desc_path)
    
    for path in [resume_path, job_desc_path]:
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not path.is_file():
            raise ValueError(f"Not a file: {path}")
    
    return resume_path, job_desc_path

import json

def save_analysis_results(analysis_result, output_dir: str = "analysis_results") -> None:
    """Save analysis results to a file"""
    try:
        # Create output directory if it doesn't exist
        output_path = pathlib.Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Convert dict to a JSON string if necessary
        if isinstance(analysis_result, dict):
            analysis_result = json.dumps(analysis_result, indent=2)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_path / f"resume_analysis_{timestamp}.txt"
        
        # Save results
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(analysis_result)
            
        print(f"\nAnalysis results saved to: {output_file}")
        
    except Exception as e:
        print(f"Error saving analysis results: {str(e)}")


@app.post("/analyze-resume/")
async def analyze_resume(resume: UploadFile = File(...), job_description: UploadFile = File(...)):
    """API endpoint to analyze resume against job description"""
    try:
        # Get API key from environment variable
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Please set the OPENAI_API_KEY environment variable")

        # Save uploaded files temporarily
        resume_path = pathlib.Path("temp_resume.pdf")
        job_desc_path = pathlib.Path("temp_job_desc.txt")

        with open(resume_path, "wb") as resume_file:
            resume_file.write(resume.file.read())
        
        with open(job_desc_path, "wb") as job_desc_file:
            job_desc_file.write(job_description.file.read())

        # Setup paths
        resume_path, job_desc_path = setup_paths(str(resume_path), str(job_desc_path))

        # Initialize analyzer
        analyzer = ResumeAnalyzer(api_key)

        # Read files
        resume_text = DocumentParser.read_file(resume_path)
        if not resume_text:
            raise ValueError(f"Failed to read resume file: {resume_path}")
        
        job_description_text = DocumentParser.read_file(job_desc_path)
        if not job_description_text:
            raise ValueError(f"Failed to read job description file: {job_desc_path}")

        # Perform analysis
        analysis_result = analyzer.analyze_resume(resume_text, job_description_text)
        
        # Save results to file
        save_analysis_results(analysis_result)
        
        # Return the analysis result
        return JSONResponse(content={"analysis_result": analysis_result})

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    finally:
        # Clean up temporary files
        if 'resume_path' in locals() and resume_path.exists():
            resume_path.unlink()
        if 'job_desc_path' in locals() and job_desc_path.exists():
            job_desc_path.unlink()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)