import os
import re
import pathlib
from typing import List, Optional, Dict, Tuple, Set
import fitz  # PyMuPDF for PDF extraction
from docx import Document

class DocumentParser:
    def __init__(self):
        # Skill indicators to identify sections containing skills
        self.skill_indicators = [
            r'skills?',
            r'technologies?',
            r'proficien(?:t|cy)',
            r'expertise',
            r'competenc(?:y|ies)',
            r'capabilities',
            r'technical\s*knowledge',
            r'tools?',
            r'programming\s*languages?',
            r'frameworks?',
            r'platforms?',
            r'software',
            r'systems?',
            r'applications?'
        ]
        
        # Section markers to identify key sections in job descriptions
        self.section_markers = [
            r'technical\s*skills?',
            r'core\s*competenc(?:y|ies)',
            r'professional\s*skills?',
            r'key\s*skills?',
            r'areas?\s*of\s*expertise',
            r'technical\s*requirements?',
            r'required\s*skills?',
            r'qualifications?',
            r'requirements?',
            r'what\s*you\'ll?\s*need',
            r'what\s*we\'?re?\s*looking\s*for',
            r'must\s*have',
            r'essential\s*skills?',
            r'preferred\s*skills?',
            r'minimum\s*requirements?',
            r'basic\s*qualifications?',
            r'preferred\s*qualifications?'
        ]

        # Patterns to identify required and preferred skills
        self.requirement_levels = {
            'required': [
                r'required',
                r'must\s*have',
                r'essential',
                r'necessary',
                r'mandatory',
                r'minimum'
            ],
            'preferred': [
                r'preferred',
                r'desired',
                r'nice\s*to\s*have',
                r'plus',
                r'bonus',
                r'advantageous'
            ]
        }

        # Patterns to extract experience requirements
        self.experience_patterns = [
            (r'(\d+)\+?\s*(?:or more)?\s*years?(?:\s*of)?\s*experience', lambda x: (int(x), None)),
            (r'(\d+)\s*-\s*(\d+)\s*years?(?:\s*of)?\s*experience', lambda x, y: (int(x), int(y))),
            (r'minimum\s*(?:of\s*)?(\d+)\s*years?', lambda x: (int(x), None)),
            (r'at\s*least\s*(\d+)\s*years?', lambda x: (int(x), None))
        ]

        # Patterns to extract education requirements
        self.education_patterns = [
            r'bachelor\'?s?\s*degree',
            r'master\'?s?\s*degree',
            r'ph\.?d',
            r'high\s*school\s*diploma',
            r'associate\'?s?\s*degree',
            r'degree\s*in\s*[a-zA-Z]+',
            r'education\s*level\s*:\s*[a-zA-Z]+'
        ]

        # Patterns to extract certifications
        self.certification_patterns = [
            r'certifications?',
            r'certified\s*in\s*[a-zA-Z]+',
            r'[a-zA-Z]+\s*certification',
            r'[a-zA-Z]+\s*certificate'
        ]

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
            if file_extension == '.pdf':
                return DocumentParser.read_pdf(file_path)
            elif file_extension in ['.docx', '.doc']:
                return DocumentParser.read_docx(file_path)
            elif file_extension == '.txt':
                return DocumentParser.read_txt(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
        except Exception as e:
            print(f"Error reading file: {str(e)}")
            return None

    @staticmethod
    def read_pdf(file_path: str) -> Optional[str]:
        """
        Extract text from a PDF file using PyMuPDF (fitz).
        
        Args:
            file_path (str): Path to the PDF file.
            
        Returns:
            Optional[str]: Extracted text or None if an error occurs.
        """
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
    def read_docx(file_path: str) -> Optional[str]:
        """
        Extract text from a DOCX/DOC file.
        
        Args:
            file_path (str): Path to the Word document.
            
        Returns:
            Optional[str]: Extracted text or None if an error occurs.
        """
        try:
            doc = Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text.strip()
        except Exception as e:
            print(f"Error reading DOCX file: {str(e)}")
            return None

    @staticmethod
    def read_txt(file_path: str) -> Optional[str]:
        """
        Read text from a TXT file.
        
        Args:
            file_path (str): Path to the text file.
            
        Returns:
            Optional[str]: File contents or None if an error occurs.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except Exception as e:
            print(f"Error reading TXT file: {str(e)}")
            return None

    def parse_job_description(self, text: str) -> Dict:
        """
        Parse job description comprehensively.
        
        Args:
            text (str): Text content of the job description.
            
        Returns:
            Dict: Parsed job description with required skills, preferred skills,
                  experience requirements, education requirements, certifications,
                  and sections.
        """
        result = {
            'required_skills': set(),
            'preferred_skills': set(),
            'experience_requirements': [],
            'education_requirements': set(),
            'certifications': set(),
            'sections': {}
        }
        
        # Split text into sections
        sections = self._split_into_sections(text)
        result['sections'] = sections
        
        # Extract information from each section
        for section_name, section_text in sections.items():
            required, preferred = self._extract_skills_with_requirements(section_text)
            result['required_skills'].update(required)
            result['preferred_skills'].update(preferred)
            
            experience_reqs = self._extract_experience_requirements(section_text)
            if experience_reqs:
                result['experience_requirements'].extend(experience_reqs)
            
            education = self._extract_education_requirements(section_text)
            if education:
                result['education_requirements'].update(education)
            
            certs = self._extract_certifications(section_text)
            if certs:
                result['certifications'].update(certs)
        
        # Convert sets to sorted lists
        result['required_skills'] = sorted(list(result['required_skills']))
        result['preferred_skills'] = sorted(list(result['preferred_skills']))
        result['education_requirements'] = sorted(list(result['education_requirements']))
        result['certifications'] = sorted(list(result['certifications']))
        
        return result

    def _split_into_sections(self, text: str) -> Dict[str, str]:
        """
        Split job description into logical sections.
        
        Args:
            text (str): Text content of the job description.
            
        Returns:
            Dict[str, str]: Dictionary of section names and their corresponding text.
        """
        sections = {}
        current_section = 'general'
        current_text = []
        
        section_headers = [
            r'about\s*(?:the\s*)?(?:role|position|job)',
            r'responsibilities',
            r'requirements',
            r'qualifications',
            r'skills(?:\s*&\s*experience)?',
            r'what\s*you\'ll?\s*(?:do|need)',
            r'about\s*you',
            r'we\s*offer',
            r'benefits',
            r'about\s*(?:us|the\s*company)',
            r'education(?:\s*&\s*experience)?'
        ]
        
        header_pattern = '|'.join(f'({h})' for h in section_headers)
        
        lines = text.split('\n')
        for line in lines:
            header_match = re.match(fr'^(?i)\s*(?:{header_pattern})\s*:?\s*$', line.strip())
            if header_match:
                if current_text:
                    sections[current_section] = '\n'.join(current_text)
                current_section = next(h for h in header_match.groups() if h is not None)
                current_text = []
            else:
                current_text.append(line)
        
        if current_text:
            sections[current_section] = '\n'.join(current_text)
        
        return sections

    def _extract_skills_with_requirements(self, text: str) -> Tuple[Set[str], Set[str]]:
        """
        Extract skills and determine if they are required or preferred.
        
        Args:
            text (str): Text content of a section.
            
        Returns:
            Tuple[Set[str], Set[str]]: Tuple of required skills and preferred skills.
        """
        required_skills = set()
        preferred_skills = set()
        
        # Extract skills based on context
        for skill_indicator in self.skill_indicators:
            skill_matches = re.finditer(fr'(?i)\b{skill_indicator}\b', text)
            for match in skill_matches:
                context = self._get_context(text, match.start(), match.end())
                if self._is_required(context):
                    required_skills.update(self._extract_skills_from_context(context))
                elif self._is_preferred(context):
                    preferred_skills.update(self._extract_skills_from_context(context))
        
        return required_skills, preferred_skills

    def _get_context(self, text: str, start: int, end: int, window: int = 100) -> str:
        """
        Get context around a match in the text.
        
        Args:
            text (str): Text content.
            start (int): Start index of the match.
            end (int): End index of the match.
            window (int): Number of characters to include before and after the match.
            
        Returns:
            str: Context around the match.
        """
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end]

    def _is_required(self, text: str) -> bool:
        """
        Determine if the context indicates a required skill.
        
        Args:
            text (str): Context text.
            
        Returns:
            bool: True if the context indicates a required skill, False otherwise.
        """
        for pattern in self.requirement_levels['required']:
            if re.search(fr'(?i)\b{pattern}\b', text):
                return True
        return False

    def _is_preferred(self, text: str) -> bool:
        """
        Determine if the context indicates a preferred skill.
        
        Args:
            text (str): Context text.
            
        Returns:
            bool: True if the context indicates a preferred skill, False otherwise.
        """
        for pattern in self.requirement_levels['preferred']:
            if re.search(fr'(?i)\b{pattern}\b', text):
                return True
        return False

    def _extract_skills_from_context(self, context: str) -> List[str]:
        """
        Extract skills from the given context.
        
        Args:
            context (str): Context text.
            
        Returns:
            List[str]: List of extracted skills.
        """
        skills = []
        # Example: Extract skills mentioned after colons or in lists
        skill_matches = re.finditer(r'(?i)(?:skills?|proficien(?:t|cy)|expertise):?\s*([\w\s,]+)', context)
        for match in skill_matches:
            skills.extend([s.strip() for s in match.group(1).split(',')])
        return skills

    def _extract_experience_requirements(self, text: str) -> List[Tuple[int, Optional[int]]]:
        """
        Extract experience requirements from the text.
        
        Args:
            text (str): Text content.
            
        Returns:
            List[Tuple[int, Optional[int]]]: List of experience requirements.
        """
        experience_reqs = []
        for pattern, func in self.experience_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                experience_reqs.append(func(*match.groups()))
        return experience_reqs

    def _extract_education_requirements(self, text: str) -> Set[str]:
        """
        Extract education requirements from the text.
        
        Args:
            text (str): Text content.
            
        Returns:
            Set[str]: Set of education requirements.
        """
        education_reqs = set()
        for pattern in self.education_patterns:
            matches = re.finditer(fr'(?i)\b{pattern}\b', text)
            for match in matches:
                education_reqs.add(match.group(0).strip())
        return education_reqs

    def _extract_certifications(self, text: str) -> Set[str]:
        """
        Extract certifications from the text.
        
        Args:
            text (str): Text content.
            
        Returns:
            Set[str]: Set of certifications.
        """
        certifications = set()
        for pattern in self.certification_patterns:
            matches = re.finditer(fr'(?i)\b{pattern}\b', text)
            for match in matches:
                certifications.add(match.group(0).strip())
        return certifications