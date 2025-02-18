import re
from datetime import datetime
from docx import Document
from openai import OpenAI

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

    def extract_skill_duration_from_experience(self, text, skill):
        """
        Extract skill duration by analyzing work experience sections based on the diagram rules.
        Returns list of (start_year, end_year) tuples for each period the skill was used.
        """
        current_year = datetime.now().year
        skill_pattern = rf'\b{re.escape(skill.lower())}\b'
        date_patterns = [
            # Current/Present patterns
            (r'(\b20\d{2}\b)\s*(?:-|to|–)\s*(?:present|current|now|ongoing)', lambda m: (int(m.group(1)), current_year)),
            
            # Year range patterns
            (r'(\b20\d{2}\b)\s*(?:-|to|–)\s*(\b20\d{2}\b)', lambda m: (int(m.group(1)), int(m.group(2)))),
            
            # Month Year format
            (r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})\s*(?:-|to|–)\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})',
             lambda m: (int(m.group(1)), int(m.group(2)))),
        ]
        
        # Find paragraphs containing the skill
        paragraphs = text.split('\n\n')
        skill_periods = []
        
        for para in paragraphs:
            if re.search(skill_pattern, para.lower()):
                # Try each date pattern
                for pattern, extract_years in date_patterns:
                    matches = re.finditer(pattern, para.lower())
                    for match in matches:
                        try:
                            start_year, end_year = extract_years(match)
                            # Validate years
                            if start_year <= end_year and end_year <= current_year:
                                # Get project/company context (first line of paragraph)
                                context_lines = para.split('\n')
                                project_context = context_lines[0].strip()
                                skill_periods.append((start_year, end_year, project_context))
                        except (ValueError, IndexError):
                            continue
        
        # If no periods found, try to find experience in work history sections
        if not skill_periods and re.search(skill_pattern, text.lower()):
            exp_sections = re.split(r'(?i)(experience|work history|employment|professional background)[:.\n]', text.lower())
            
            for section in exp_sections:
                if re.search(skill_pattern, section):
                    # Find all years in the section
                    years = sorted([int(y) for y in re.findall(r'\b(20\d{2})\b', section) 
                                 if int(y) <= current_year])
                    
                    if len(years) >= 2:
                        start_year = min(years)
                        end_year = max(years)
                        context = section.split('\n')[0].strip()
                        skill_periods.append((start_year, end_year, context))
        
        return skill_periods

    def calculate_total_skill_duration(self, periods):
        """
        Calculate total duration accounting for overlapping periods.
        Returns total years of experience.
        """
        if not periods:
            return 0
            
        # Sort periods by start date
        sorted_periods = [(start, end) for start, end, _ in periods]
        sorted_periods.sort()
        merged = [sorted_periods[0]]
        
        for current in sorted_periods[1:]:
            previous = merged[-1]
            
            # Check for overlap
            if current[0] <= previous[1]:
                # Merge overlapping periods
                merged[-1] = (previous[0], max(previous[1], current[1]))
            else:
                merged.append(current)
        
        # Calculate total years
        total_years = sum(end - start for start, end in merged)
        return total_years

    def calculate_skill_scores(self, mentions, last_used_year, experience_years):
        """Calculate skill scores based on the provided scoring diagram"""
        # Frequency score: 10 points per mention, max 100
        frequency_score = min(mentions * 10, 100)
        
        # Recency score based on last used year
        current_year = datetime.now().year
        if last_used_year == current_year:
            recency_score = 100  # Currently using
        elif last_used_year >= current_year - 3:  # Within last 3 years
            recency_score = 80
        elif last_used_year >= current_year - 5:  # Within last 5 years
            recency_score = 60
        else:
            recency_score = 0  # More than 5 years ago
        
        # Duration score based on experience years
        # Limit experience years to realistic values (e.g., max 10 years)
        capped_experience = min(experience_years, 10)
        duration_score = min(capped_experience * 10, 100)  # 10 points per year, max 100
        
        # Calculate weighted total
        total_score = (
            frequency_score * 0.4 +    # 40% weight for frequency
            recency_score * 0.3 +      # 30% weight for recency
            duration_score * 0.3        # 30% weight for duration
        )
        
        return {
            'frequency_score': round(frequency_score, 2),
            'recency_score': round(recency_score, 2),
            'duration_score': round(duration_score, 2),
            'total_score': round(total_score, 2)
        }

    def format_skills_output(self, skills_analysis):
        """Format the skills output with project context"""
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
            output += f"  Recency Score:   {skill['recency_score']} (Last used: {skill['last_used']})\n"
            output += f"  Duration Score:  {skill['duration_score']} (Duration: {skill['years_experience']} years)\n"
            if 'last_project' in skill:
                output += f"  Last Project:    {skill['last_project']}\n"
            output += f"  Final Match Score: {skill['total_score']:.2f} / 100\n\n"
        
        if count > 0:
            overall_final_score = overall_score / count
            output += "=" * 40 + "\n"
            output += f"  Final Match Score: {overall_final_score:.2f} / 100\n\n"
        return output

    def analyze_resume(self, resume_text, job_description_text):
        if not resume_text or not job_description_text:
            return "Error: Missing resume or job description text"

        # ----- SKILLS ANALYSIS -----
        skills_prompt = f"""
        "Only list skills that are explicitly mentioned in both the resume AND job description and make sure you get each skill from job description ."
        For each skill found in both the job description and resume, extract from the resume:
        1. The skill name
        2. When it was last used (look for date ranges in projects/experience)
        3. Total years of experience (calculate from work experience sections)
        4. Project or role context where it was used

        Use EXACTLY this format for each skill (including the exact labels):
        SKILL NAME:
        - Last Used: YYYY or "Present" if current
        - Years Experience: X (calculated from actual date ranges)
        - Context: Brief description of where/how used
        -

        Resume Text:
        {resume_text}

        Job Description:
        {job_description_text}
        """

        try:
            # Get skills analysis from GPT
            skills_response = self.client.chat.completions.create(
                model="gpt-4-0125-preview",
                messages=[
                    {"role": "system", "content": "You are a technical skills analyzer. Extract skills with accurate duration information from work experience and project sections."},
                    {"role": "user", "content": skills_prompt}
                ],
                temperature=0.2
            )
            skills_text = skills_response.choices[0].message.content
            skills_analysis = []

            # Process each skill section from the GPT response
            sections = skills_text.split('\n\n')
            for section in sections:
                lines = section.strip().split('\n')
                if not lines:
                    continue

                # Extract the skill name (assumes the first line is the skill name)
                skill_name = lines[0].replace(":", "").strip()
                if not skill_name:
                    continue

                # Extract date ranges and compute duration from the resume text
                skill_periods = self.extract_skill_duration_from_experience(resume_text, skill_name)
                total_years = self.calculate_total_skill_duration(skill_periods)
                last_used = max([period[1] for period in skill_periods]) if skill_periods else self.current_year

                # Count actual mentions in resume
                mentions = self.count_skill_occurrences(resume_text, skill_name)
                if mentions <= 0:
                    continue

                # Calculate scores
                scores = self.calculate_skill_scores(mentions, last_used, total_years)
                skill_data = {
                    'skill': skill_name,
                    'mentions': mentions,
                    'last_used': last_used if last_used != self.current_year else "Present",
                    'years_experience': total_years,
                    **scores
                }
                skills_analysis.append(skill_data)

            skills_output = self.format_skills_output(skills_analysis)

            # ----- GENERAL ANALYSIS -----
            general_prompt = f"""
            Analyze the following resume against the job description. 
            Provide a detailed analysis in these categories:

            **1. Work Experience or Professional Experience Evaluation (also extract company names):**
                - Total Years of IT Experience
                - Comparison with JD requirements
                - Job Title Match and role durations in months

            **2. Education & Certification Match:**
                - Degree Qualification (meets/exceeds JD requirements)
                - Field of Study Relevance
                - Certification Match

            **3. Achievements & Domain Experience:**
                - Awards, patents, publications
                - Industry experience and preferred domains

            **4. Project & Tenure Analysis:**
                - Number of companies worked at
                - Total duration per company and overall tenure pattern

            **5. Projects & Achievements:**
                - List of relevant projects

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
            general_analysis = general_response.choices[0].message.content

            # ----- COMBINING OUTPUTS INTO A FINAL REPORT -----
            final_report = ""
            final_report += self.format_section("SKILLS ANALYSIS", skills_output)
            final_report += self.format_section("GENERAL ANALYSIS", general_analysis)
            final_report += self.format_section("OVERALL EVALUATION", "Please refer to the above sections for a detailed evaluation of the candidate's fit for the role.")
            
            return final_report

        except Exception as e:
            return f"Error in analysis: {str(e)}"



    def format_section(self, title, content=""):
        """Format a main section with title and optional content"""
        width = 80
        border = "═" * width
        output = f"\n{border}\n║ {title.center(width-4)} ║\n{border}\n"
        if content:
            output += f"{content}\n"
        return output

    def format_subsection(self, title, content=""):
        """Format a subsection with title and optional content"""
        width = 76  # Slightly smaller than main section for indentation
        border = "─" * width
        output = f"\n  ┌{border}┐\n  │ {title.ljust(width-2)}│\n  └{border}┘\n"
        if content:
            # Indent the content under the subsection
            formatted_content = "\n".join(f"    {line}" for line in content.split('\n'))
            output += f"{formatted_content}\n"
        return output

    def format_bullet_point(self, text, indent=4):
        """Format a bullet point with proper indentation and unicode bullets"""
        indent_str = " " * indent
        return f"{indent_str}• {text}\n"

    def format_analysis_output(self, analysis_data):
        """Format the resume analysis output in a clean, professional style"""
        width = 80
        def create_section_header(title):
            return f"\n{'=' * width}\n{title.center(width)}\n{'=' * width}\n"
        
        def create_subsection_header(title):
            return f"\n{title}\n{'-' * len(title)}\n"
        
        def format_field(label, value, indent=2):
            indent_space = " " * indent
            return f"{indent_space}{label}: {value}\n"
        
        output = create_section_header("RESUME EVALUATION REPORT")
        
        # 1. Work Experience Section
        output += create_subsection_header("1. Work Experience Evaluation")
        output += format_field("Total Years of IT Experience", "")
        output += format_field("Candidate", "1+ year as stated in the resume", 4)
        output += format_field("JD Requirement", "5+ years", 4)
        output += format_field("Assessment", "Below requirement", 4)
        
        output += "\n"
        output += format_field("Job Title Analysis", "")
        output += format_field("Current Roles", "AI ML Engineer, Computer Vision Engineer (R&D), Database Management Intern", 4)
        output += format_field("Duration in Roles", "Less than 1 year in current positions", 4)
        output += format_field("Experience Level", "Below JD requirements", 4)
        
        # 2. Education & Certification Section
        output += create_subsection_header("2. Education & Certification Match")
        output += format_field("Degree Qualification", "")
        output += format_field("Candidate Degree", "Bachelor's Degree in Computer Engineering", 4)
        output += format_field("JD Requirement", "Bachelors or Masters in Computer Science or related field", 4)
        output += format_field("Assessment", "Meets requirements", 4)
        
        output += "\n"
        output += format_field("Certification Status", "")
        output += format_field("Required Certifications", "ML and AI certifications preferred", 4)
        output += format_field("Candidate Certifications", "None mentioned", 4)
        output += format_field("Assessment", "Missing preferred certifications", 4)
        
        # 3. Achievements & Domain Experience
        output += create_subsection_header("3. Achievements & Domain Experience")
        output += format_field("Professional Recognition", "")
        output += format_field("Awards/Patents", "None mentioned", 4)
        output += format_field("Publications", "None mentioned", 4)
        
        output += "\n"
        output += format_field("Industry Experience", "")
        output += format_field("Primary Focus", "AI and Machine Learning", 4)
        output += format_field("Sectors", "Technology, Automotive (CAIR Drive Product)", 4)
        
        # 4. Project & Tenure Analysis
        output += create_subsection_header("4. Project & Tenure Analysis")
        output += format_field("Company History", "")
        output += format_field("Total Companies", "2 (NSAI and POLTIO)", 4)
        output += format_field("Duration at NSAI", "Less than 1 year", 4)
        output += format_field("Duration at POLTIO", "3 months", 4)
        output += format_field("Tenure Assessment", "Short tenure pattern (< 3 years)", 4)
        
        # 5. Projects & Achievements
        output += create_subsection_header("5. Projects & Achievements")
        output += format_field("Notable Projects", "")
        output += format_field("1", "Facial Recognition and Gaze Tracking for Online Interviews", 4)
        output += format_field("2", "Resume Matcher with Job Description and Evaluation", 4)
        output += format_field("3", "Nested U-Net Architecture For Medical Image Segmentation", 4)
        output += format_field("4", "Video Segmentation using Meta SAM2 model", 4)
        
        # Summary Section
        output += create_section_header("EVALUATION SUMMARY")
        output += "Overall, the candidate shows strong technical foundation in AI and ML through relevant\n"
        output += "projects, but falls short of the required years of experience. While the educational\n"
        output += "background meets requirements, the lack of industry certifications and limited\n"
        output += "professional experience suggest a junior level profile compared to the JD requirements.\n"
        
        output += create_section_header("END OF REPORT")
        return output