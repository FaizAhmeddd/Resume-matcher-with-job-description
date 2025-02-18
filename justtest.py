import os
import re
import pathlib
from datetime import datetime
import fitz  # PyMuPDF for PDF extraction
from docx import Document
from openai import OpenAI

class DocumentParser:
    @staticmethod
    def read_file(file_path):
        """Read file based on its extension using the appropriate method"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            file_extension = pathlib.Path(file_path).suffix.lower()
            if file_extension == '.pdf':
                return DocumentParser.read_pdf(file_path)
            elif file_extension in ['.docx', '.doc', '.docs']:
                return DocumentParser.read_docx(file_path)
            elif file_extension == '.txt':
                return DocumentParser.read_txt(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
        except Exception as e:
            print(f"Error reading file: {str(e)}")
            return None

    @staticmethod
    def read_pdf(file_path):
        """Extract text from a PDF file using PyMuPDF (fitz)"""
        try:
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            return text.strip()
        except Exception as e:
            print(f"Error reading PDF file: {str(e)}")
            return None

    @staticmethod
    def read_docx(file_path):
        """Extract text from a DOCX/DOC/DOCS file"""
        try:
            doc = Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text.strip()
        except Exception as e:
            print(f"Error reading DOCX file: {str(e)}")
            return None

    @staticmethod
    def read_txt(file_path):
        """Read text from a TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except Exception as e:
            print(f"Error reading TXT file: {str(e)}")
            return None



class ResumeAnalyzer:
    def __init__(self, api_key):
        if not api_key:
            raise ValueError("API key cannot be empty")
        self.client = OpenAI(api_key=api_key)
        self.current_year = datetime.now().year

    def count_skill_occurrences(self, text, skill):
        """Count how many times a skill is mentioned in text"""
        if not text or not skill:
            return 0
        pattern = r'\b' + re.escape(skill.lower()) + r'\b'
        matches = re.findall(pattern, text.lower())
        return len(matches)

    def extract_year(self, text, default=None):
        """Safely extract year from text"""
        if not text:
            return default or self.current_year
        match = re.search(r'\b(19|20)\d{2}\b', text)
        return int(match.group()) if match else (default or self.current_year)

    def calculate_experience_years(self, year_or_duration):
        """Convert year or duration to years of experience"""
        if isinstance(year_or_duration, int):
            if year_or_duration > 1900:  # It's a year
                return max(0, self.current_year - year_or_duration)
            return year_or_duration  # It's already duration
        return 0

    def calculate_skill_scores(self, mentions, last_used_year, experience_years):
        """Calculate skill scores based on mentions, recency, and experience"""
        # Frequency score: 10 points per mention, max 100
        frequency_score = min(mentions * 10, 100)
        
        # Recency score
        if last_used_year >= self.current_year:
            recency_score = 100
        else:
            years_ago = self.current_year - last_used_year
            if years_ago <= 2:
                recency_score = 90
            elif years_ago <= 5:
                recency_score = 70
            else:
                recency_score = max(0, 50 - (years_ago - 5) * 10)
        
        # Duration score: 10 points per year, max 100
        duration_score = min(experience_years * 10, 100)
        
        # Calculate weighted total
        total_score = (
            frequency_score * 0.4 +  # 40% weight for frequency
            recency_score * 0.3 +    # 30% weight for recency
            duration_score * 0.3      # 30% weight for duration
        )
        
        return {
            'frequency_score': frequency_score,
            'recency_score': recency_score,
            'duration_score': duration_score,
            'total_score': round(total_score, 2)
        }

    def format_skills_output(self, skills_analysis):
        """
        Format the skills output exactly as:
        
        Skill: <Skill Name>
          Frequency Score: <score> (from <matches> matches)
          Recency Score:   <score> (Last used: <year or 'Not specified'>)
          Duration Score:  <score> (Duration: <years> or 'Not specified')
          Final Match Score: <score> / 100
        
        Followed by an overall score summary.
        """
        output = ""
        overall_score = 0
        count = 0
        for skill in skills_analysis:
            if not skill['skill']:
                continue
            overall_score += skill['total_score']
            count += 1
            output += f"Skill: {skill['skill']}\n"
            output += f"  Frequency Score: {skill['frequency_score']} (from {skill['mentions']} matches)\n"
            # If last_used equals current_year, assume it was not specified
            last_used_display = f"{skill['last_used']}" if skill['last_used'] != self.current_year else "Not specified"
            output += f"  Recency Score:   {skill['recency_score']} (Last used: {last_used_display})\n"
            # If years_experience is 0, show as not specified
            duration_display = f"{skill['years_experience']} years" if skill['years_experience'] > 0 else "Not specified"
            output += f"  Duration Score:  {skill['duration_score']} (Duration: {duration_display})\n"
            output += f"  Final Match Score: {skill['total_score']:.2f} / 100\n\n"
        
        if count > 0:
            overall_final_score = overall_score / count
            output += "=" * 40 + "\n"
            output += f"  Final Match Score: {overall_final_score:.2f} / 100\n\n"
        return output

    def analyze_resume(self, resume_text, job_description_text):
        """Analyze resume against job description"""
        if not resume_text or not job_description_text:
            return "Error: Missing resume or job description text"

        # First prompt to extract technical skills
        skills_prompt = f"""
        Analyze the job description and identify required technical skills.
        For each skill found in both the job description and resume, list:
        1. The skill name
        2. When it was last used in the resume
        3. Total years of experience

        Use EXACTLY this format for each skill (including the exact labels):
        SKILL NAME:
        - Last Used: YYYY
        - Years Experience: X

        Resume Text:
        {resume_text}

        Job Description:
        {job_description_text}
        """

        try:
            # Get skills analysis
            skills_response = self.client.chat.completions.create(
                model="gpt-4-0125-preview",
                messages=[
                    {"role": "system", "content": "You are a technical skills analyzer. Extract and list skills exactly in the requested format."},
                    {"role": "user", "content": skills_prompt}
                ],
                temperature=0.2
            )
            
            # Process skills analysis
            skills_text = skills_response.choices[0].message.content
            skills_analysis = []
            
            # Split text into skill sections (assuming two newlines separate each skill block)
            sections = skills_text.split('\n\n')
            
            for section in sections:
                lines = section.strip().split('\n')
                if not lines:
                    continue
                
                # Initialize default values
                skill_data = {
                    'skill': '',
                    'last_used': self.current_year,
                    'years_experience': 0,
                    'mentions': 0
                }
                
                # First line should be the skill name (strip any trailing colon)
                if lines[0].endswith(':'):
                    skill_data['skill'] = lines[0][:-1].strip()
                else:
                    skill_data['skill'] = lines[0].strip()
                
                # Process detail lines
                for line in lines[1:]:
                    if ':' not in line:
                        continue
                    key, value = [x.strip() for x in line.strip('- ').split(':', 1)]
                    
                    if 'Last Used' in key:
                        skill_data['last_used'] = self.extract_year(value, self.current_year)
                    elif 'Years Experience' in key:
                        years = self.extract_year(value, 0)
                        if years > 1900:  # If it's a year instead of a duration
                            years = self.current_year - years
                        skill_data['years_experience'] = years
                
                # Count actual mentions in the resume text
                if skill_data['skill']:
                    skill_data['mentions'] = self.count_skill_occurrences(resume_text, skill_data['skill'])
                    
                    # Calculate scores
                    scores = self.calculate_skill_scores(
                        skill_data['mentions'],
                        skill_data['last_used'],
                        skill_data['years_experience']
                    )
                    
                    skill_data.update(scores)
                    skills_analysis.append(skill_data)

            # Format skills output using the new helper method
            skills_output = self.format_skills_output(skills_analysis)

            # Get general analysis from GPT-4
            general_prompt = f"""
            Analyze the following resume against the job description. 
            Provide a detailed analysis in these categories:

            1. WORK EXPERIENCE EVALUATION
            - Total years of IT experience
            - Compare with job requirement (✅ Meets, ⚠️ Close, ❌ Below)
            - List all job titles with duration in months
            - Note which titles match job requirements

            2. EDUCATION & CERTIFICATION MATCH
            - Highest degree and field
            - Whether it meets job requirements (✅/❌)
            - Whether field is IT-related
            - List all certifications
            - Compare against required certifications

            3. ACHIEVEMENTS & DOMAIN EXPERIENCE
            - List any awards, patents, publications
            - Note presence of major achievements (✅/❌)
            - List industries worked in
            - Compare against preferred job domains

            4. PROJECT & TENURE ANALYSIS
            - Number of companies worked with
            - Average project duration per company
            - Rate tenure pattern (✅ >3 years, ⚠️ ~3 years, ❌ <3 years)

            Resume Text:
            {resume_text}

            Job Description:
            {job_description_text}
            """

            general_response = self.client.chat.completions.create(
                model="gpt-4-0125-preview",
                messages=[
                    {"role": "system", "content": "You are an expert resume analyzer providing detailed, well-structured analysis."},
                    {"role": "user", "content": general_prompt}
                ],
                temperature=0.2
            )

            # Combine the formatted skills output with the general analysis
            result = skills_output + "\n" + general_response.choices[0].message.content
            return result

        except Exception as e:
            return f"Error in analysis: {str(e)}"


def format_analysis_output(analysis_text):
    """Format the analysis output with clear sections and styling"""
    print("\n" + "="*50)
    print("📑 RESUME ANALYSIS REPORT")
    print("="*50 + "\n")
    
    # Split analysis into sections and print with formatting
    sections = analysis_text.split('\n\n')
    for section in sections:
        if section.strip():
            # Add extra formatting for section headers
            if any(header in section for header in ["TECHNICAL SKILLS", "WORK EXPERIENCE", "EDUCATION", "ACHIEVEMENTS", "PROJECT"]):
                print("\n" + "-"*50)
            print(section.strip())
            
    print("\n" + "="*50 + "\n")

def main():
    try:
        # Get API key from environment variable
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Please set the OPENAI_API_KEY environment variable")

        # Initialize analyzer
        analyzer = ResumeAnalyzer(api_key)

        # File paths
        resume_file_path = "RESUME/Raghavendra Gadde Resume.docx"
        job_description_file_path = "EXAMPLE job_description.txt"

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