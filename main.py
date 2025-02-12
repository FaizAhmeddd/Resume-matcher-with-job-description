import os
import re
import pathlib
from datetime import datetime
import fitz  # PyMuPDF for PDF extraction
from docx import Document
from openai import OpenAI
from document_text_extraction import DocumentParser
from resume_analyzer import ResumeAnalyzer , format_analysis_output

def main():
    try:
        # Get API key from environment variable
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Please set the OPENAI_API_KEY environment variable")

        # Initialize analyzer
        analyzer = ResumeAnalyzer(api_key)

        # File paths
        resume_file_path = "RESUME/1.docx"
        job_description_file_path = "dumps/EXAMPLE job_description.txt"

        # Read files
        print("Reading resume file...")
        resume_text = DocumentParser.read_file(resume_file_path)
        
        print("Reading job description file...")
        job_description_text = DocumentParser.read_file(job_description_file_path)

        if not resume_text or not job_description_text:
            raise ValueError("Failed to read one or both of the files")

        # Perform analysis
        print("Analyzing resume against job description...")
        analysis_result = analyzer.analyze_resume(resume_text, job_description_text)
        
        # Format and display the results
        format_analysis_output(analysis_result)

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()