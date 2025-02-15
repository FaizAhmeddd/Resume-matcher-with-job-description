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
        """Analyze resume against job description with improved skill analysis"""
        if not resume_text or not job_description_text:
            return "Error: Missing resume or job description text"

        # First prompt to extract technical skills
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
            
            # Process skills analysis
            skills_text = skills_response.choices[0].message.content
            skills_analysis = []
            
            # Split text into skill sections
            sections = skills_text.split('\n\n')
            
            for section in sections:
                lines = section.strip().split('\n')
                if not lines:
                    continue
                
                skill_name = lines[0].strip(':').strip() if lines[0].endswith(':') else lines[0].strip()
                
                # Skip empty skill names
                if not skill_name:
                    continue
                
                # Extract skill periods from resume text
                skill_periods = self.extract_skill_duration_from_experience(resume_text, skill_name)
                
                # Calculate total experience and last used
                total_years = self.calculate_total_skill_duration(skill_periods)
                last_used = max([period[1] for period in skill_periods]) if skill_periods else self.current_year
                
                # Count actual mentions
                mentions = self.count_skill_occurrences(resume_text, skill_name)
                
                # Skip if no actual mentions found
                if mentions <= 0:
                    continue
                
                # Calculate scores
                scores = self.calculate_skill_scores(mentions, last_used, total_years)
                
                # Combine all information
                skill_data = {
                    'skill': skill_name,
                    'mentions': mentions,
                    'last_used': last_used,
                    'years_experience': total_years,
                    **scores
                }
                
                skills_analysis.append(skill_data)

            # Format skills output
            skills_output = self.format_skills_output(skills_analysis)

            # Get general analysis from GPT-4
            general_prompt = f"""
            Analyze the following resume against the job description. 
            Provide a detailed analysis in these categories:

            **1 Work Experience or Professional Experience Evaluation also extract company names candidate worked at:**
                - **Total Years of IT Experience**:
                - Extract total years of experience.
                - Compare with JD requirement.
                - Categorize: ✅ Meets, ⚠️ Close, ❌ Below.
                - Example: Candidate: 10 years, JD: 7 years → ✅  
                    Candidate: 5 years, JD: 7 years → ❌  
                - **Job Title Match**:
                - Extract job titles from resume and Total Number of experience in that role calculate in months.
                - Compare against acceptable titles from JD.
                - Check for related roles.

            **2 Education & Certification Match**
                - **Degree Requirement**:
                - Check if highest degree **meets or exceeds** JD.
                - Example: JD requires Bachelor's, Candidate has Master's → ✅  
                - **Field of Study Relevance**:
                - Identify if degree is **IT-related**.
                - **Certification Match**:
                - Extract required certifications from JD.
                - Compare against the candidate's certifications.
                - ✅ Has Required Certifications  
                - ❌ Missing Required Certifications  

            **3 Achievements & Domain Experience**
                - Extract **awards, patents, publications**.
                - Categorize: ✅ Has awards, ❌ No major recognitions.
                - Identify industries the candidate has worked in.
                - Compare against **preferred job domains**.

            4. PROJECT & TENURE ANALYSIS
                - Number of companies worked with
                - Total duration per company
                - Rate tenure pattern (✅ >3 years, ⚠️ ~3 years, ❌ <3 years)
                
            5. Projects & Achievements
            - Extract projects from resume
            - Categorize: ✅ Has relevant projects, ❌ No relevant projects
            

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


def format_analysis_output(analysis_text, width=80):
    """Format the analysis output with enhanced styling"""
    def print_header(text, char='=', emoji=''):
        if emoji:
            text = f"{emoji} {text}"
        print(f"\n{char * width}")
        print(f"{text:^{width}}")
        print(f"{char * width}\n")
    
    def print_section(title, content, emoji=''):
        if emoji:
            title = f"{emoji} {title}"
        print(f"\n{'-' * width}")
        print(f"{title}")
        print(f"{'-' * width}")
        
        lines = content.strip().split('\n')
        for line in lines:
            if line.strip():
                if line.lstrip().startswith(('•', '-', '*')) or line.lstrip()[0].isdigit():
                    print(f"  {line.strip()}")
                else:
                    current_line = ''
                    words = line.strip().split()
                    for word in words:
                        if len(current_line) + len(word) + 1 <= (width - 4):
                            current_line += (word + ' ')
                        else:
                            print(f"    {current_line.strip()}")
                            current_line = word + ' '
                    if current_line:
                        print(f"    {current_line.strip()}")
        print()

    # Start formatting
    print_header("RESUME ANALYSIS REPORT", '=', '📑')
    
    sections = {
        'SUMMARY': ('📋', 'Executive Summary'),
        'TECHNICAL SKILLS': ('💻', 'Technical Skills Assessment'),
        'WORK EXPERIENCE': ('💼', 'Professional Experience Analysis'),
        'EDUCATION': ('🎓', 'Educational Background'),
        'ACHIEVEMENTS': ('🏆', 'Key Achievements'),
        'PROJECTS': ('🚀', 'Project Experience'),
        'CERTIFICATIONS': ('📜', 'Certifications'),
        'RECOMMENDATIONS': ('💡', 'Recommendations'),
        'GAPS': ('⚠️', 'Identified Gaps'),
        'MATCH SCORE': ('🎯', 'Overall Match Score')
    }
    
    current_section = ''
    current_content = []
    
    for line in analysis_text.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        is_header = False
        for key in sections:
            if key in line.upper():
                if current_section and current_content:
                    emoji, title = sections.get(current_section, ('', current_section))
                    print_section(title, '\n'.join(current_content), emoji)
                
                current_section = key
                current_content = []
                is_header = True
                break
        
        if not is_header:
            current_content.append(line)
    
    if current_section and current_content:
        emoji, title = sections.get(current_section, ('', current_section))
        print_section(title, '\n'.join(current_content), emoji)
    
    print_header("END OF ANALYSIS", '=', '🏁')