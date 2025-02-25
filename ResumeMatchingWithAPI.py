import os
import boto3
import psycopg2
from fastapi import HTTPException
import sshtunnel
import re
import pathlib
from typing import List, Optional, Dict, Set, Any, Union
import fitz  # PyMuPDF for PDF extraction
from docx import Document
from datetime import datetime
import openai
import logging
import traceback
from dotenv import load_dotenv

load_dotenv()
# -------------------------- Database Connection --------------------------


class DatabaseConnection:
    def __init__(self):
        self.conn = None
        self.cur = None
    #     self.ssh_tunnel = None

    # def create_ssh_tunnel(self):
    #     """
    #     Creates and returns an SSHTunnelForwarder object.
    #     """
    #     try:
    #         self.ssh_tunnel = sshtunnel.SSHTunnelForwarder(
    #             (
    #                 "ec2-52-15-194-170.us-east-2.compute.amazonaws.com",
    #                 22,
    #             ),  # Bastion host
    #             ssh_username="ec2-user",
    #             ssh_pkey="BastionHostKeyPair.pem",  # Path to your key file
    #             remote_bind_address=(
    #                 "databasets.chygq4ecec7u.us-east-2.rds.amazonaws.com",
    #                 5432,
    #             ),
    #             local_bind_address=("127.0.0.1", 6543),  # Local port forwarding
    #         )
    #         self.ssh_tunnel.start()
    #     except Exception as e:
    #         raise HTTPException(
    #             status_code=500, detail=f"SSH tunnel creation failed: {str(e)}"
    #         )

    def connect(self):
        """Establishes connection to the database through SSH tunnel"""
        try:
            # # First create the SSH tunnel
            # self.create_ssh_tunnel()

            # Then connect to the database through the tunnel
            self.conn = psycopg2.connect(
                dbname="seekers",
                user="postgres_TS",
                password="BBCPs2025_",
                host="databasets.chygq4ecec7u.us-east-2.rds.amazonaws.com",  # Connect to local tunnel endpoint
                port=5432,  # Use the local tunnel port
            )
            self.cur = self.conn.cursor()
        except Exception as e:
            # if self.ssh_tunnel:
                # self.ssh_tunnel.close()
            raise HTTPException(
                status_code=500, detail=f"Database connection failed: {str(e)}"
            )

    def close(self):
        """Closes database connection and cursor"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.commit()
            self.conn.close()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# -------------------------- S3 File Download --------------------------


class S3FileDownload:
    @staticmethod
    def parse_s3_uri(s3_uri: str):
        """
        Parses an S3 URI to extract the bucket name and key.
        Example: s3://bucket-name/folder/file.pdf -> ('bucket-name', 'folder/file.pdf')
        """
        if s3_uri.startswith("s3://"):
            s3_uri = s3_uri[5:]
        bucket_name, key = s3_uri.split("/", 1)
        return bucket_name, key

    @staticmethod
    def download_s3_file(s3_uri: str, local_path: str):
        """
        Downloads a file from S3 using given credentials
        and stores it locally at local_path.
        """
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

        bucket_name, key = S3FileDownload.parse_s3_uri(s3_uri)

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        print(f"[INFO] Downloading from S3: bucket={bucket_name}, key={key}")
        s3_client.download_file(bucket_name, key, local_path)
        print(f"[INFO] Download complete -> {local_path}")


#  -------------------------- Access JOBS Table --------------------------
class JobDataAccess:
    @staticmethod
    def get_job_details(job_id: int) -> dict:
        """
        Fetches the job details including description, title, and years of experience for a specific job_id.

        Args:
            job_id (int): The ID of the job

        Returns:
            dict: Dictionary containing job details

        Raises:
            HTTPException: If job_id not found or database error occurs
        """
        with DatabaseConnection() as db_conn:
            try:
                query = """
                    SELECT job_desc, job_title, years_of_exp
                    FROM public.jobs
                    WHERE job_id = %s
                """
                db_conn.cur.execute(query, (job_id,))

                result = db_conn.cur.fetchone()

                if not result:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Job details for job ID {job_id} not found.",
                    )

                return {
                    "job_desc": result[0],
                    "job_title": result[1],
                    "years_of_exp": result[2]
                }

            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Database error while fetching job details: {str(e)}",
                )
    
    @staticmethod
    def get_job_description(job_id: int) -> str:
        """
        Fetches the job description text for a specific job_id.
        
        Args:
            job_id (int): The ID of the job
            
        Returns:
            str: The job description text
            
        Raises:
            HTTPException: If job_id not found or database error occurs
        """
        job_details = JobDataAccess.get_job_details(job_id)
        return job_details["job_desc"]


#  -------------------------- Access JOB_SKILLS Table From Database --------------------------


class JobSkillsDataAccess:
    def __init__(self):
        self.job_skills = None
        self.job_id = None

    def fetch_and_store_job_skills(
        self, db_conn: DatabaseConnection, job_id: int
    ) -> List[Dict]:
        """Fetches and stores skill IDs and skill names based on job_id."""
        try:
            query = """
                SELECT js.skill_id, s.skill_name
                FROM public.job_skills js
                JOIN public.skills s ON js.skill_id = s.skill_id
                WHERE js.job_id = %s
            """
            db_conn.cur.execute(query, (job_id,))

            # Fetching column names and rows
            rows = db_conn.cur.fetchall()

            if not rows:
                raise HTTPException(
                    status_code=404, detail=f"No skills found for job_id {job_id}."
                )

            # Storing the fetched data in instance variables
            self.job_id = job_id
            self.job_skills = [
                {"skill_id": row[0], "skill_name": row[1]} for row in rows
            ]
            print(f"Successfully fetched job skills for job_id {job_id}")
            print(self.job_skills)
            return self.job_skills

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Database error while fetching job skills: {str(e)}",
            )

    def get_stored_job_skills(self) -> Optional[List[Dict]]:
        """Returns the stored job skills if available."""
        return self.job_skills

    def get_stored_job_id(self) -> Optional[int]:
        """Returns the stored job ID if available."""
        return self.job_id


#  -------------------------- Access SKILLS Table --------------------------


class SkillDataAccess:
    @staticmethod
    def get_skill_details(db_conn: DatabaseConnection) -> List[Dict]:
        """Fetches all skill details from the skills table."""
        try:
            query = """
                SELECT skill_id, skill_name
                FROM public.skills
            """
            db_conn.cur.execute(query)

            columns = [desc[0] for desc in db_conn.cur.description]
            rows = db_conn.cur.fetchall()

            if not rows:
                raise HTTPException(
                    status_code=404, detail="No skills found in the database."
                )

            skills = [dict(zip(columns, row)) for row in rows]
            return skills
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Database error while fetching skill details: {str(e)}",
            )


# -------------------------- Access JOB_SHORTLISTED_PROFILES Table --------------------------


class ShortlistDataAccess:
    @staticmethod
    def get_shortlisted_profiles(
        db_conn: DatabaseConnection, job_id: int
    ) -> List[Dict]:
        """Fetches profiles from the job_shortlisted_profiles table."""
        try:
            query = """
                SELECT shortlist_id, job_id, manager_id, candidate_id 
                FROM public.job_shortlisted_profiles
                WHERE job_id = %s
            """
            db_conn.cur.execute(query, (job_id,))

            columns = [desc[0] for desc in db_conn.cur.description]
            rows = db_conn.cur.fetchall()

            if not rows:
                raise HTTPException(
                    status_code=404,
                    detail=f"No shortlisted profiles found for job_id {job_id}. Please ensure candidates have been shortlisted for this job.",
                )

            profiles = [dict(zip(columns, row)) for row in rows]
            return profiles
        except HTTPException:
            raise
        except Exception as e:
            error_message = f"Database error while fetching shortlisted profiles: {str(e)}"
            print(error_message)  # Add direct console logging for debugging
            raise HTTPException(
                status_code=500, 
                detail=error_message
            )

# -------------------------- Access CANDIDATE Table --------------------------


class CandidateDataAccess:
    @staticmethod
    def get_candidate_details(
        db_conn: DatabaseConnection, candidate_id: int
    ) -> List[Dict]:
        """Fetches candidate details from the candidate table."""
        try:
            query = """
                SELECT candidate_id, s3_key_resume
                FROM public.candidate
                WHERE candidate_id = %s AND is_deleted = false
            """
            db_conn.cur.execute(query, (candidate_id,))

            columns = [desc[0] for desc in db_conn.cur.description]
            rows = db_conn.cur.fetchall()

            if not rows:
                raise HTTPException(
                    status_code=404, detail=f"Candidate ID {candidate_id} not found."
                )

            candidates = [dict(zip(columns, row)) for row in rows]
            return candidates
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Database error while fetching candidate details: {str(e)}",
            )


# -------------------------- Document Parsing --------------------------


class DocumentParser:
    @staticmethod
    def read_file(file_path: str) -> Optional[str]:
        """
        Read file based on its extension using the appropriate method.

        Args:
            file_path (str): Path to the file to read.

        Returns:
            Optional[str]: Text content of the file or None if an error occurs.
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            file_extension = pathlib.Path(file_path).suffix.lower()

            if file_extension == ".pdf":
                return DocumentParser.read_pdf(file_path)
            elif file_extension == ".docx":
                return DocumentParser.read_docx(file_path)
            elif file_extension == ".txt":
                return DocumentParser.read_txt(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
        except Exception as e:
            print(f"Error reading file: {str(e)}")
            return None

    @staticmethod
    def read_pdf(file_path: str) -> Optional[str]:
        """Extract text from a PDF file using PyMuPDF (fitz)."""
        try:
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()  # Properly close the document
            return text.strip()
        except Exception as e:
            print(f"Error reading PDF file: {str(e)}")
            return None

    @staticmethod
    def read_docx(file_path: str) -> Optional[str]:
        """Extract text from a DOCX file."""
        try:
            doc = Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text.strip()
        except Exception as e:
            print(f"Error reading DOCX file: {str(e)}")
            return None

    @staticmethod
    def read_txt(file_path: str) -> Optional[str]:
        """Read text from a TXT file."""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read().strip()
        except Exception as e:
            print(f"Error reading TXT file: {str(e)}")
            return None

    def parse_resume(self, resume_text: str) -> Dict:
        """Parse the resume text for skills, experience, certifications, and education."""
        result = {
            "skills": set(),
            "experience": [],
            "education": set(),
            "certifications": set(),
        }

        # Extract information from the resume text
        result["skills"] = self._extract_skills(resume_text)
        result["experience"] = self._extract_experience_requirements(resume_text)
        result["education"] = self._extract_education_requirements(resume_text)
        result["certifications"] = self._extract_certifications(resume_text)

        result["skills"] = sorted(list(result["skills"]))
        result["experience"] = sorted(result["experience"])
        result["education"] = sorted(list(result["education"]))
        result["certifications"] = sorted(list(result["certifications"]))

        return result

    def _extract_skills(self, text: str) -> Set[str]:
        """Extract skills from the resume text."""
        skills = set(
            re.findall(r"\b\w+\b", text)
        )  # Placeholder: Modify this based on real skills extraction
        return skills

    def _extract_experience_requirements(self, text: str) -> List[str]:
        """Extract experience information from the resume text."""
        return re.findall(r"\d+ years of experience", text)

    def _extract_education_requirements(self, text: str) -> Set[str]:
        """Extract education information from the resume text."""
        return set(
            re.findall(
                r"(bachelor\'s|master\'s|Ph\.D|high school)", text, re.IGNORECASE
            )
        )

    def _extract_certifications(self, text: str) -> Set[str]:
        """Extract certifications from the resume text."""
        return set(
            re.findall(r"certified|certification|certificate", text, re.IGNORECASE)
        )


# -------------------------- Skill Matcher With Database -------------------------


class SkillMatcher:
    def __init__(self, job_id: int, api_key: str):
        self.job_id = job_id
        self.api_key = api_key
        self.skills_fetcher = SkillsFetcher()
        self.resume_analyzer = ResumeAnalyzer(api_key)

    def match_skills_and_get_score(self, resume_text: str, job_description_text: str):
        # Step 1: Fetch the required skills from the SkillsFetcher
        self.skills_fetcher.fetch_skills(self.job_id)
        required_skills = (
            self.skills_fetcher.get_skills_dict()
        )  # Dictionary of skill_id: skill_name

        # Step 2: Analyze the resume using ResumeAnalyzer
        skill_analysis_results = self.resume_analyzer.analyze_resume_skills(
            resume_text, required_skills
        )

        if isinstance(skill_analysis_results, str):  # If it's an error message
            return skill_analysis_results

        # Step 3: Extract skills from resume analysis
        resume_skills = []
        if "skills_analysis" in skill_analysis_results:
            for skill_data in skill_analysis_results["skills_analysis"]:
                resume_skills.append(skill_data["skill"])

        # Step 4: Match skills from both required skills and analyzed skills
        matched_skills = {}
        for skill_id, skill_name in required_skills.items():
            if skill_name in resume_skills:
                # Step 5: Calculate the score for the matched skills using ResumeAnalyzer's method
                mentions = self.resume_analyzer.count_skill_occurrences(
                    resume_text, skill_name
                )
                last_used_year = max(
                    [
                        year
                        for start, end, _ in self.resume_analyzer.extract_skill_duration_from_experience(
                            resume_text, skill_name
                        )
                        for year in [start, end]
                    ],
                    default=self.resume_analyzer.current_year,
                )
                total_experience = self.resume_analyzer.calculate_total_skill_duration(
                    self.resume_analyzer.extract_skill_duration_from_experience(
                        resume_text, skill_name
                    )
                )

                scores = self.resume_analyzer.calculate_skill_scores(
                    mentions, last_used_year, total_experience
                )
                matched_skills[skill_name] = {
                    "mentions": mentions,
                    "last_used_year": last_used_year,
                    "total_experience": total_experience,
                    "frequency_score": scores["frequency_score"],
                    "recency_score": scores["recency_score"],
                    "duration_score": scores["duration_score"],
                    "total_score": scores["total_score"],
                }

        return matched_skills


# -------------------------- Required Skills Feteching From Database --------------------------


class SkillsFetcher:
    """
    A simplified class to fetch and store job skills and their IDs.
    """

    def __init__(self):
        """
        Initialize the fetcher with variables to store skills
        """
        self.skill_ids = []  # List to store skill IDs
        self.skill_names = []  # List to store skill names
        self.skills_dict = {}  # Dictionary to store skill_id: skill_name pairs

    def fetch_skills(self, job_id: int) -> None:
        """
        Fetch skills and their IDs for a specific job ID and store them in instance variables.

        Args:
            job_id (int): The ID of the job to fetch skills for
        """
        with DatabaseConnection() as db_conn:
            try:
                query = """
                    SELECT 
                        js.skill_id,
                        s.skill_name
                    FROM public.job_skills js
                    JOIN public.skills s ON js.skill_id = s.skill_id
                    WHERE js.job_id = %s AND js.is_deleted = false
                """

                db_conn.cur.execute(query, (job_id,))
                results = db_conn.cur.fetchall()

                if not results:
                    raise Exception(f"No skills found for job ID {job_id}")

                # Clear existing data
                self.skill_ids.clear()
                self.skill_names.clear()
                self.skills_dict.clear()

                # Store results in instance variables
                for row in results:
                    skill_id, skill_name = row
                    self.skill_ids.append(skill_id)
                    self.skill_names.append(skill_name)
                    self.skills_dict[skill_id] = skill_name

            except Exception as e:
                print(f"Error fetching skills: {str(e)}")
                raise

    def get_skill_ids(self) -> list:
        """Return the list of skill IDs."""
        return self.skill_ids

    def get_skill_names(self) -> list:
        """Return the list of skill names."""
        return self.skill_names

    def get_skills_dict(self) -> dict:
        """Return the dictionary of skill_id: skill_name pairs."""
        return self.skills_dict


# -------------------------- Resume Analyzer --------------------------


class ResumeAnalyzer:
    def __init__(self, api_key: str):
        """Initialize the ResumeAnalyzer with OpenAI API key"""
        if not api_key:
            raise ValueError("API key cannot be empty")
        self.client = openai.OpenAI(api_key=api_key)
        self.current_year = datetime.now().year

    def analyze_resume_skills(
            self, resume_text: str, required_skills: Dict[str, str]
        ) -> Union[Dict[int, Dict[str, Any]], str]:
            """Analyze skills frequency in resume with improved skill detection for variations and abbreviations"""
            if not resume_text or not required_skills:
                return "Error: Missing resume text or required skills"

            # Map skill indexes to criteria IDs
            skill_criteria_mapping = {
                0: 1,  # skill1 -> criteria_id 1
                1: 2,  # skill2 -> criteria_id 2
                2: 3,  # skill3 -> criteria_id 3
                3: 9,  # skill4 -> criteria_id 9
                4: 8,  # skill5 -> criteria_id 8
            }

            # Initialize all criteria with zero scores
            criteria_scores = {}
            for skill_idx, criteria_id in skill_criteria_mapping.items():
                criteria_scores[criteria_id] = {
                    "criteria_id": criteria_id,
                    "name": f"skill{skill_idx + 1}",
                    "score": 0  # Default score of 0
                }

            skills_list = list(required_skills.values())
            skills_text = "\n".join(
                [f"{idx + 1}. {skill}" for idx, skill in enumerate(skills_list)]
            )

            prompt = f"""
            You are analyzing a resume for specific technical skills. Count ALL occurrences of each skill including related terms, variations, abbreviations, and different formatting either in specific section or in the entire resume in job roles or in project or tables or in any other section. Please count the occurrences of the required skills:

            Resume Text:
            {resume_text}

            Required Skills to Analyze:
            {skills_text}

            For each skill listed above, be EXTREMELY thorough in your analysis:

            1. Count ALL mentions including:
            - Exact matches regardless of case (e.g., "Spring Boot", "SPRING BOOT", "spring boot")
            - Variations with no spaces (e.g., "SpringBoot" for "Spring Boot")
            - Common abbreviations (e.g., "JS" for "JavaScript")
            - Hyphenated variations (e.g., "React-Native" for "React Native")
            - When used as part of another term (e.g., "Spring Boot Application")
            - Different formats/versions that refer to the same technology
            - When mentioned as part of lists, bullet points, or compound phrases
            - When mentioned in different contexts (development, environment, configuration, etc.)

            2. For multi-word skills:
            - Count joined-word variations (e.g., "ReactJS" for "React JS")
            - Count when words appear close to each other even if not directly adjacent
            - Count domain-specific variations (e.g., "Spring Framework" might count for "Spring")

            3. For frameworks/technologies:
            - Include ecosystem components (e.g., for "React" also count "React Router", "Redux")
            - Count references to specific modules/components of the technology

            4. Scoring:
            - Multiply the total number of occurrences by 5 to get the score (maximum score is 100)
            - If a skill appears 20 or more times, award the maximum score of 100

            Format your response EXACTLY like this for EACH skill:
            Skill [number]: [skill name]
            Found: [number of occurrences]
            Final Score: [number]

            Important:
            - Be extremely thorough - capture EVERY possible mention or variation
            - Pay attention to skill names that might be split across lines or formatted differently
            - When in doubt about whether something counts as a mention, include it in your count
            - Remember that technical resumes often use shorthand, abbreviations, and domain-specific terminology
            """

            try:
                response = self.client.chat.completions.create(
                    model="gpt-4-0125-preview",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a technical skills analyzer with expertise in identifying technology terms and their variations across different formats and contexts. Be extremely thorough in identifying all instances of required skills.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,  # Lower temperature for more consistent formatting
                )

                raw_scores = self._parse_skills_response(response.choices[0].message.content)
                
                # Update scores for skills that exist in the resume
                for skill_idx, skill_name in enumerate(skills_list):
                    if skill_idx in skill_criteria_mapping and skill_idx < len(skills_list):
                        criteria_id = skill_criteria_mapping[skill_idx]
                        skill_data = raw_scores.get(f"Skill {skill_idx + 1}", {'occurrences': 0, 'score': 0})
                        criteria_scores[criteria_id]["score"] = skill_data['score']
                
                return criteria_scores
                
            except Exception as e:
                logging.error(f"Error in skills analysis: {str(e)}")
                logging.error(traceback.format_exc())
                return f"Error in skills analysis: {str(e)}"
        

    def general_analyze_resume(
            self, resume_text: str, job_description: str, job_years_exp: int = None
        ) -> Union[Dict[str, Any], str]:
            """
            Analyze resume based on non-skill criteria

            Args:
                resume_text (str): The text content of the resume
                job_description (str): The job description text
                job_years_exp (int, optional): Years of experience required in the job

            Returns:
                Union[Dict[str, Any], str]: Dictionary containing analysis results or error message
            """
            prompt = f"""
            Analyze the following resume against the job description and provide scores for each criterion.
            Provide ONLY numerical scores (0-100) for each criterion.

            Scoring Criteria:

            4. Years of Experience Match:
            - Score 100 if candidate's years of experience matches or exceeds {job_years_exp if job_years_exp is not None else "what's in the job description"}
            - Score 0 if candidate's years of experience is below {job_years_exp if job_years_exp is not None else "what's required in job description"} or if no experience is mentioned
            - Score 100 if years of experience is not specified in the job description

            5. Job Title Match:
            - Score 100 if matches or exceeds level
            - Score 0 if below

            6. Total IT Experience:
            - Base requirement is 10 years
            - Add EXACTLY 25 points for EACH FULL YEAR above 10 years
            - Examples: 
            * 10 years experience = 0 points (meets base requirement)
            * 11 years experience = 25 points (1 year above requirement)
            * 12 years experience = 50 points (2 years above)
            * 14+ years experience = 100 points (4+ years above, capped at max)
            - Do not award more than 25 points per year above requirement

            7. Current Skills Usage:
            - Score 100 if skills in current/last project
            - Score 0 if not

            10. Domain Experience:
            - Add EXACTLY 10 points for EACH FULL YEAR of experience the candidate has in the specific domain mentioned in the job description
            - Examples:
            * 1 year in domain = 10 points
            * 5 years in domain = 50 points 
            * 10+ years in domain = 100 points (capped at max 100)
            - Score 100 if no specific domain is mentioned in the job description
            - Do not award partial points for partial years

            11. Awards and Recognition:
            - Score 100 if any awards present
            - Score 0 if none

            12. Certifications:
            - Score 100 if any certification present
            - Score 0 if none

            13. Education :
            - Score 100 for CS/CE degree
            - Score 0 for others

            14. Skill Usage Duration:
            - Award EXACTLY 5 points per year the candidate has used the primary skill mentioned in the job description
            - Calculate based on total relevant experience, not exceeding actual years
            - Examples:
            * 10 years using Java = 50 points (10 × 5 = 50)
            * 11 years using Java = 55 points (11 × 5 = 55)
            * 20+ years using Java = 100 points (capped at max 100)
            - Do not award more than 5 points per year of experience

            15. Average Project Length:
            - Score 100 if 3+ years average
            - Score 0 if less

            Resume:
            {resume_text}

            Job Description:
            {job_description}

            Format your response exactly like this:
            4: [score]
            5: [score]
            6: [score]
            7: [score]
            10: [score]
            11: [score]
            12: [score]
            13: [score]
            14: [score]
            15: [score]
            """

            try:
                response = self.client.chat.completions.create(
                    model="gpt-4-0125-preview",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a resume analyzer. Provide numerical scores only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                )

                criteria_scores = self._parse_general_analysis(
                    response.choices[0].message.content
                )

                # Calculate overall score
                scores = [
                    score["score"]
                    for score in criteria_scores.values()
                    if score["score"] is not None
                ]
                overall_score = sum(scores) / len(scores) if scores else 0

                return {"overall_score": overall_score, "detailed_scores": criteria_scores}

            except Exception as e:
                return f"Error in analysis: {str(e)}"

    def _parse_skills_response(self, response_text: str) -> Dict[str, Dict[str, int]]:
        """Parse the skills analysis response with improved pattern matching"""
        skills_scores = {}
        current_skill = None
        skill_pattern = re.compile(r"skill\s+(\d+)[:\s-]+([^:\n]+)", re.IGNORECASE)
        found_pattern = re.compile(r"found\s*:?\s*(\d+)", re.IGNORECASE)
        score_pattern = re.compile(r"(?:final\s+)?score\s*:?\s*(\d+)", re.IGNORECASE)
        
        # First try to extract all skills with their details in one pass
        skill_blocks = re.split(r"\n\s*\n|\n(?=Skill\s+\d+)", response_text, flags=re.IGNORECASE)
        
        for block in skill_blocks:
            block = block.strip()
            if not block:
                continue
                
            # Try to identify the skill number and name
            skill_match = skill_pattern.search(block)
            if not skill_match:
                continue
                
            skill_num = skill_match.group(1)
            skill_key = f"Skill {skill_num}"
            skills_scores[skill_key] = {"occurrences": 0, "score": 0}
            
            # Look for occurrences count
            found_match = found_pattern.search(block)
            if found_match:
                try:
                    occurrences = int(found_match.group(1))
                    skills_scores[skill_key]["occurrences"] = occurrences
                    # Calculate score but also look for explicit score
                    skills_scores[skill_key]["score"] = min(occurrences * 5, 100)
                except ValueError:
                    pass
            
            # Look for explicit score which overrides calculated score
            score_match = score_pattern.search(block)
            if score_match:
                try:
                    score = int(score_match.group(1))
                    skills_scores[skill_key]["score"] = min(score, 100)
                except ValueError:
                    pass
        
        # If the block approach failed, fall back to line-by-line parsing
        if not skills_scores:
            lines = response_text.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                skill_match = re.search(r"skill\s+(\d+)", line, re.IGNORECASE)
                if skill_match:
                    current_skill = f"Skill {skill_match.group(1)}"
                    skills_scores[current_skill] = {"occurrences": 0, "score": 0}
                    continue

                if current_skill:
                    found_match = re.search(r"found\s*:?\s*(\d+)", line, re.IGNORECASE)
                    if found_match:
                        try:
                            occurrences = int(found_match.group(1))
                            skills_scores[current_skill]["occurrences"] = occurrences
                            skills_scores[current_skill]["score"] = min(occurrences * 5, 100)
                        except ValueError:
                            pass
                        continue

                    score_match = re.search(r"(?:final\s+)?score\s*:?\s*(\d+)", line, re.IGNORECASE)
                    if score_match:
                        try:
                            score = int(score_match.group(1))
                            skills_scores[current_skill]["score"] = min(score, 100)
                        except ValueError:
                            pass
        
        # Add debug logging
        print(f"Parsed skills scores: {skills_scores}")
        
        return skills_scores

    def _parse_general_analysis(self, response_text: str) -> Dict[int, Dict[str, Any]]:
        """
        Parse the general analysis text into scores

        Args:
            response_text (str): The response text from the API

        Returns:
            Dict[int, Dict[str, Any]]: Dictionary containing parsed criteria scores
        """
        criteria_mapping = {
            4: "jd_match",
            5: "job_title_match",
            6: "it_experience",
            7: "current_skills",
            10: "domain_experience",
            11: "awards",
            12: "certifications",
            13: "education",
            14: "skill_duration",
            15: "project_length",
        }

        results = {}
        lines = response_text.split("\n")

        for line in lines:
            line = line.strip().lower()
            if not line:
                continue

            # Look for score patterns
            matches = re.findall(r"(?:criterion\s*)?(\d+)[:.]\s*(\d+)", line)

            for match in matches:
                try:
                    criteria_num = int(match[0])
                    score = min(int(match[1]), 100)

                    if criteria_num in criteria_mapping:
                        results[criteria_num] = {
                            "criteria_id": criteria_num,
                            "name": criteria_mapping[criteria_num],
                            "score": score,
                        }
                except (ValueError, IndexError):
                    continue

        return results

    def print_debug_info(self, response_text: str, parsed_results: Dict) -> None:
        """
        Print debug information about parsing results

        Args:
            response_text (str): Raw response text from API
            parsed_results (Dict): Parsed results dictionary
        """
        print("\nDebug Information:")
        print("=" * 50)
        print("\nRaw Response:")
        print(response_text)
        print("\nParsed Results:")
        print(parsed_results)
        print("=" * 50)


class ResumeScoreUpdater:
    @staticmethod
    def update_resume_scores(db_conn: DatabaseConnection, evaluation_results: list) -> None:
        """
        Update resume scores in the database for each candidate and criteria
        
        Args:
            db_conn: DatabaseConnection instance
            evaluation_results: List of dictionaries containing evaluation results
        """
        try:
            # All skill criteria IDs that must be updated regardless of required skills
            all_skill_criteria_ids = [1, 2, 3, 9, 8]  # skill1, skill2, skill3, skill4, skill5
            
            for result in evaluation_results:
                candidate_id = result['candidate_id']
                
                # Get manager_id from shortlisted profiles
                query_manager = """
                    SELECT manager_id, job_id 
                    FROM public.job_shortlisted_profiles 
                    WHERE candidate_id = %s
                """
                db_conn.cur.execute(query_manager, (candidate_id,))
                shortlist_data = db_conn.cur.fetchone()
                
                if not shortlist_data:
                    logging.warning(f"No shortlist data found for candidate {candidate_id}")
                    continue
                    
                manager_id, job_id = shortlist_data
                
                # Always update ALL skill criteria, regardless of what's in the skills_breakdown
                for criteria_id in all_skill_criteria_ids:
                    # Get score from skills_breakdown if it exists, otherwise use 0
                    if 'skills_breakdown' in result and criteria_id in result['skills_breakdown']:
                        score_data = result['skills_breakdown'][criteria_id]
                        score = score_data.get('score', 0)
                    else:
                        # If for any reason the criteria isn't in skills_breakdown, set score to 0
                        score = 0
                    
                    # Log the score being set for debugging
                    logging.info(f"Setting score for candidate {candidate_id}, criteria {criteria_id}: {score}")
                    
                    ResumeScoreUpdater._upsert_score(
                        db_conn,
                        candidate_id=candidate_id,
                        manager_id=manager_id,
                        job_id=job_id,
                        criteria_id=criteria_id,
                        score=score
                    )
                
                # Update general scores
                if 'general_breakdown' in result:
                    for criteria_id, score_data in result['general_breakdown'].items():
                        ResumeScoreUpdater._upsert_score(
                            db_conn,
                            candidate_id=candidate_id,
                            manager_id=manager_id,
                            job_id=job_id,
                            criteria_id=criteria_id,
                            score=score_data['score']
                        )
                
            db_conn.conn.commit()
            logging.info("Successfully updated all resume scores in database")
            
        except Exception as e:
            db_conn.conn.rollback()
            logging.error(f"Error updating resume scores: {str(e)}")
            logging.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Error updating resume scores: {str(e)}"
            )

    @staticmethod
    def _upsert_score(
        db_conn: DatabaseConnection,
        candidate_id: int,
        manager_id: int,
        job_id: int,
        criteria_id: int,
        score: int
    ) -> None:
        """
        Insert or update a score record in the resume_score table
        
        Args:
            db_conn: DatabaseConnection instance
            candidate_id: ID of the candidate
            manager_id: ID of the manager
            job_id: ID of the job
            criteria_id: ID of the scoring criteria
            score: The calculated score
        """
        try:
            # Ensure score is an integer
            try:
                score = int(score)
            except (TypeError, ValueError):
                score = 0  # Default to 0 if score is not a valid number
            
            # Check if record exists
            query_check = """
                SELECT score_id 
                FROM public.resume_scores
                WHERE candidate_id = %s 
                AND manager_id = %s 
                AND job_id = %s 
                AND criteria_id = %s
                AND is_deleted = false
            """
            db_conn.cur.execute(query_check, (candidate_id, manager_id, job_id, criteria_id))
            existing_record = db_conn.cur.fetchone()
            
            if existing_record:
                # Update existing record
                query_update = """
                    UPDATE public.resume_scores 
                    SET score = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE score_id = %s
                """
                db_conn.cur.execute(query_update, (score, existing_record[0]))
            else:
                # Insert new record
                query_insert = """
                    INSERT INTO public.resume_scores 
                    (candidate_id, manager_id, job_id, criteria_id, score, created_on, updated_at, is_deleted)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, false)
                """
                db_conn.cur.execute(query_insert, (candidate_id, manager_id, job_id, criteria_id, score))
                
        except Exception as e:
            logging.error(f"Error upserting score for candidate {candidate_id}, criteria {criteria_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error upserting score record: {str(e)}"
            )

def evaluate_candidates_comprehensive(job_id: int):
    """
    Evaluate all shortlisted candidates and update their scores in the database

    Args:
        job_id (int): The ID of the job to evaluate candidates for

    Returns:
        List[Dict]: List of final scores for all candidates
    """
    # Get API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not found in environment variables")
    
    # Set up logging if not already configured
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Check for AWS credentials
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    if not aws_access_key_id or not aws_secret_access_key:
        logging.error("AWS credentials not found in environment variables")
        raise HTTPException(
            status_code=500, 
            detail="AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables."
        )
    
    try:
        with DatabaseConnection() as db_conn:
            # Get job description
            try:
                job_desc = JobDataAccess.get_job_description(job_id)
                if not job_desc:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Job description not found for job_id {job_id}",
                    )
            except HTTPException as he:
                # Re-raise HTTPException to preserve status code and detail
                raise he
            except Exception as e:
                logging.error(f"Error retrieving job description: {str(e)}")
                logging.error(traceback.format_exc())
                raise HTTPException(
                    status_code=500, 
                    detail=f"Error retrieving job description: {str(e)}"
                )

            # Get shortlisted profiles
            try:
                shortlisted_profiles = ShortlistDataAccess.get_shortlisted_profiles(
                    db_conn, job_id
                )
                logging.info(f"Found {len(shortlisted_profiles)} shortlisted profiles for job_id {job_id}")
                if not shortlisted_profiles:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No shortlisted candidates found for job_id {job_id}. Please ensure candidates have been shortlisted for this job.",
                    )
            except HTTPException as he:
                # Re-raise HTTPException to preserve status code and detail
                raise he
            except Exception as e:
                logging.error(f"Error retrieving shortlisted profiles: {str(e)}")
                logging.error(traceback.format_exc())
                raise HTTPException(
                    status_code=500, 
                    detail=f"Error retrieving shortlisted profiles: {str(e)}"
                )

            # Initialize analyzers
            try:
                skills_fetcher = SkillsFetcher()
                skills_fetcher.fetch_skills(job_id)
                required_skills = skills_fetcher.get_skills_dict()
                logging.info(f"Found {len(required_skills)} required skills for job_id {job_id}")

                if not required_skills:
                    logging.warning(f"No required skills found for job_id {job_id}")
                    raise HTTPException(
                        status_code=404, 
                        detail=f"No required skills found for job_id {job_id}"
                    )
            except HTTPException as he:
                raise he
            except Exception as e:
                logging.error(f"Error fetching required skills: {str(e)}")
                logging.error(traceback.format_exc())
                raise HTTPException(
                    status_code=500, 
                    detail=f"Error fetching required skills: {str(e)}"
                )

            resume_analyzer = ResumeAnalyzer(api_key)

            # Create/check resume directory
            resume_directory = "RESUME"
            if not os.path.exists(resume_directory):
                os.makedirs(resume_directory)
                logging.info(f"Created resume directory: {resume_directory}")

            # Process each candidate
            evaluation_results = []
            final_scores = []
            errors = []

            for profile in shortlisted_profiles:
                candidate_id = profile["candidate_id"]
                logging.info(f"Processing candidate ID: {candidate_id}")
                local_resume_path = None

                try:
                    # Get and process resume
                    candidates = CandidateDataAccess.get_candidate_details(
                        db_conn, candidate_id
                    )
                    if not candidates or not candidates[0].get("s3_key_resume"):
                        error_msg = f"No resume found for candidate_id {candidate_id}"
                        logging.warning(error_msg)
                        errors.append(error_msg)
                        continue

                    s3_key_resume = candidates[0]["s3_key_resume"]
                    local_resume_path = os.path.join(
                        resume_directory,
                        f"{candidate_id}_resume{os.path.splitext(s3_key_resume)[1]}",
                    )

                    # Download and read resume
                    try:
                        logging.info(f"Downloading resume from S3: {s3_key_resume}")
                        S3FileDownload.download_s3_file(s3_key_resume, local_resume_path)
                    except Exception as e:
                        error_msg = f"Error downloading resume for candidate {candidate_id}: {str(e)}"
                        logging.error(error_msg)
                        logging.error(traceback.format_exc())
                        errors.append(error_msg)
                        continue

                    resume_text = DocumentParser.read_file(local_resume_path)
                    if not resume_text:
                        error_msg = f"Could not extract text from resume for candidate_id {candidate_id}"
                        logging.warning(error_msg)
                        errors.append(error_msg)
                        continue

                    # Skills Analysis with graceful handling of fewer skills
                    try:
                        skills_scores = resume_analyzer.analyze_resume_skills(
                            resume_text, required_skills
                        )
                        
                        if not isinstance(skills_scores, dict):
                            error_msg = f"Skills analysis failed for candidate_id {candidate_id}: {skills_scores}"
                            logging.warning(error_msg)
                            errors.append(error_msg)
                            continue
                            
                        # Calculate average skill score using only non-zero scores
                        non_zero_scores = [s["score"] for s in skills_scores.values() if s["score"] > 0]
                        if non_zero_scores:
                            skills_avg = sum(non_zero_scores) / len(non_zero_scores)
                        else:
                            skills_avg = 0
                            
                        logging.info(f"Completed skills analysis for candidate {candidate_id} with avg score: {skills_avg}")
                    except Exception as e:
                        error_msg = f"Error in skills analysis for candidate {candidate_id}: {str(e)}"
                        logging.error(error_msg)
                        logging.error(traceback.format_exc())
                        errors.append(error_msg)
                        continue

                    # General Analysis
                    try:
                        general_analysis = resume_analyzer.general_analyze_resume(
                            resume_text, job_desc
                        )
                        
                        if not isinstance(general_analysis, dict):
                            error_msg = f"General analysis failed for candidate_id {candidate_id}: {general_analysis}"
                            logging.warning(error_msg)
                            errors.append(error_msg)
                            continue
                            
                        detailed_scores = general_analysis.get("detailed_scores", {})
                        general_avg = general_analysis.get("overall_score", 0)
                        logging.info(f"Completed general analysis for candidate {candidate_id} with avg score: {general_avg}")
                    except Exception as e:
                        error_msg = f"Error in general analysis for candidate {candidate_id}: {str(e)}"
                        logging.error(error_msg)
                        logging.error(traceback.format_exc())
                        errors.append(error_msg)
                        continue

                    # Calculate final score
                    final_score = (skills_avg + general_avg) / 2

                    # Store evaluation results
                    result = {
                        "candidate_id": candidate_id,
                        "final_score": final_score,
                        "skills_score": skills_avg,
                        "general_score": general_avg,
                        "skills_breakdown": skills_scores,
                        "general_breakdown": detailed_scores,
                        "manager_id": profile["manager_id"],
                    }
                    evaluation_results.append(result)
                    logging.info(f"Evaluation complete for candidate {candidate_id} with final score: {final_score}")

                    # Add to final scores list
                    final_scores.append(
                        {"candidate_id": candidate_id, "final_score": final_score}
                    )

                except Exception as e:
                    error_msg = f"Error processing candidate {candidate_id}: {str(e)}"
                    logging.error(error_msg)
                    logging.error(traceback.format_exc())
                    errors.append(error_msg)
                    continue
                finally:
                    # Cleanup downloaded resume
                    if local_resume_path and os.path.exists(local_resume_path):
                        try:
                            os.remove(local_resume_path)
                            logging.info(f"Removed temporary file: {local_resume_path}")
                        except Exception as e:
                            logging.warning(f"Failed to remove temporary file {local_resume_path}: {str(e)}")

            # Update scores in database
            if evaluation_results:
                try:
                    logging.info(f"Updating database with scores for {len(evaluation_results)} candidates")
                    ResumeScoreUpdater.update_resume_scores(db_conn, evaluation_results)
                except Exception as e:
                    error_msg = f"Error updating scores in database: {str(e)}"
                    logging.error(error_msg)
                    logging.error(traceback.format_exc())
                    errors.append(error_msg)
                    # Continue despite database update errors

            if not final_scores:
                if errors:
                    error_summary = "; ".join(errors[:5])
                    if len(errors) > 5:
                        error_summary += f"; and {len(errors) - 5} more errors"
                    logging.error(f"No candidates were successfully evaluated: {error_summary}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to evaluate any candidates: {error_summary}"
                    )
                else:
                    logging.error(f"No candidates were successfully evaluated for job_id {job_id}")
                    raise HTTPException(
                        status_code=404,
                        detail=f"No candidates were successfully evaluated for job_id {job_id}"
                    )

            logging.info(f"Successfully evaluated {len(final_scores)} candidates for job_id {job_id}")
            return final_scores

    except HTTPException as he:
        # Re-raise HTTPExceptions to preserve their status code and detail
        raise he
    except Exception as e:
        # Convert generic exceptions to HTTPExceptions with detail
        error_message = str(e)
        logging.error(f"Evaluation failed: {error_message}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_message)