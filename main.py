import os
import re
import pathlib
from datetime import datetime
import fitz  # PyMuPDF for PDF extraction
from docx import Document
from openai import OpenAI
from typing import Optional, Dict, Any
from document_text_extraction import DocumentParser
from resume_analyzer import ResumeAnalyzer

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

def save_analysis_results(analysis_result: str, output_dir: str = "analysis_results") -> None:
    """Save analysis results to a file"""
    try:
        # Create output directory if it doesn't exist
        output_path = pathlib.Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_path / f"resume_analysis_{timestamp}.txt"
        
        # Save results
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(analysis_result)
            
        print(f"\nAnalysis results saved to: {output_file}")
        
    except Exception as e:
        print(f"Error saving analysis results: {str(e)}")

def main() -> None:
    """Main function with enhanced error handling and progress tracking"""
    try:
        # Get API key from environment variable
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Please set the OPENAI_API_KEY environment variable")

        # File paths - you can modify these or add command line arguments
        resume_file_path = "dumps/Faizan_Resume_AI_ML_ENGINEER.pdf"
        job_description_file_path = "dumps/EXAMPLE job_description.txt"

        # Print startup message
        print("\n" + "="*80)
        print("RESUME ANALYSIS SYSTEM".center(80))
        print("="*80 + "\n")

        # Setup paths
        print("Validating file paths...")
        resume_path, job_desc_path = setup_paths(resume_file_path, job_description_file_path)

        # Initialize analyzer
        analyzer = ResumeAnalyzer(api_key)

        # Read files with progress indicators
        print("\nReading resume file...")
        resume_text = DocumentParser.read_file(resume_path)
        if not resume_text:
            raise ValueError(f"Failed to read resume file: {resume_path}")
        print("✓ Resume file read successfully")
        
        print("\nReading job description file...")
        job_description_text = DocumentParser.read_file(job_desc_path)
        if not job_description_text:
            raise ValueError(f"Failed to read job description file: {job_desc_path}")
        print("✓ Job description file read successfully")

        # Perform analysis
        print("\nAnalyzing resume against job description...")
        print("This may take a few moments...\n")
        analysis_result = analyzer.analyze_resume(resume_text, job_description_text)
        
        # Display the results (the analysis_result is already formatted in the ResumeAnalyzer class)
        print(analysis_result)
        
        # Save results to file
        save_analysis_results(analysis_result)
        
        print("\nAnalysis completed successfully!")
        print("="*80 + "\n")

    except FileNotFoundError as e:
        print(f"\nError: File not found - {str(e)}")
    except ValueError as e:
        print(f"\nError: Invalid input - {str(e)}")
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        print("Please check your input files and try again.")
    finally:
        print("\nExiting program.")

if __name__ == "__main__":
    main()