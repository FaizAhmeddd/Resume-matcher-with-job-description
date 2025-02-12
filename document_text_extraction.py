import os
import re
import pathlib
from datetime import datetime
import fitz  # PyMuPDF for PDF extraction
from docx import Document
from typing import List, Optional

class DocumentParser:
    def __init__(self):
        # Common skill-related keywords and their variations
        self.skill_indicators = [
            r'skills?',
            r'technologies?',
            r'proficien(?:t|cy)',
            r'expertise',
            r'competenc(?:y|ies)',
            r'capabilities',
            r'technical\s*knowledge'
        ]
        
        # Common skill section markers
        self.section_markers = [
            r'technical\s*skills?',
            r'core\s*competenc(?:y|ies)',
            r'professional\s*skills?',
            r'key\s*skills?',
            r'areas?\s*of\s*expertise'
        ]

    def create_flexible_skill_pattern(self, skill_name: str) -> str:
        """
        Creates a flexible regex pattern for a given skill name that matches:
        - Case-insensitive variations
        - Optional spaces between words
        - Common variations and abbreviations
        - Special characters and their text equivalents
        
        Args:
            skill_name (str): The base skill name to create pattern for
            
        Returns:
            str: Flexible regex pattern for the skill
        """
        # Replace special characters with optional patterns
        pattern = skill_name.replace('+', r'(?:\+|plus)')
        pattern = pattern.replace('#', r'(?:#|sharp)')
        pattern = pattern.replace('.', r'[\.\s]?')
        
        # Make spaces optional and handle multiple word skills
        pattern = r'\s*'.join(re.split(r'\s+', pattern))
        
        # Add word boundaries and make case-insensitive
        pattern = fr'\b(?i){pattern}\b'
        
        return pattern

    def create_skill_variations(self, base_skills: List[str]) -> List[str]:
        """
        Generate common variations of skill names
        
        Args:
            base_skills (List[str]): List of base skill names
            
        Returns:
            List[str]: Extended list with skill variations
        """
        variations = []
        for skill in base_skills:
            # Add base skill
            variations.append(self.create_flexible_skill_pattern(skill))
            
            # Add common prefixes/suffixes
            prefixes = [r'ms\s*', r'microsoft\s*', r'apache\s*', r'adobe\s*']
            suffixes = [
                r'\s*language',
                r'\s*framework',
                r'\s*library',
                r'\s*platform',
                r'\s*development'
            ]
            
            for prefix in prefixes:
                variations.append(fr'{prefix}{self.create_flexible_skill_pattern(skill)}')
            for suffix in suffixes:
                variations.append(fr'{self.create_flexible_skill_pattern(skill)}{suffix}')
        
        return variations

    def extract_skills(self, text: str, skill_patterns: List[str]) -> List[str]:
        """
        Extract skills from text using flexible patterns
        
        Args:
            text (str): Input text to search for skills
            skill_patterns (List[str]): List of regex patterns for skills
            
        Returns:
            List[str]: List of found unique skills
        """
        found_skills = set()
        
        # First try to identify skill sections
        section_pattern = '|'.join(self.section_markers)
        sections = re.split(f'(?i){section_pattern}', text)
        
        # If we found sections, prioritize searching in them
        if len(sections) > 1:
            # Search in sections after skill headers
            for section in sections[1:]:
                # Limit search to next likely section boundary
                section_end = re.search(r'\n\s*[A-Z][A-Za-z\s]{10,}:', section)
                if section_end:
                    section = section[:section_end.start()]
                
                self._search_skills(section, skill_patterns, found_skills)
        else:
            # If no clear sections, search whole text
            self._search_skills(text, skill_patterns, found_skills)
        
        return sorted(list(found_skills))

    def _search_skills(self, text: str, patterns: List[str], found_skills: set) -> None:
        """
        Helper method to search for skills in text
        
        Args:
            text (str): Text to search in
            patterns (List[str]): Skill patterns to search for
            found_skills (set): Set to store found skills
        """
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Clean up the found skill
                skill = match.group(0).strip()
                skill = re.sub(r'\s+', ' ', skill)  # Normalize spaces
                found_skills.add(skill)

    @staticmethod
    def read_file(file_path: str) -> Optional[str]:
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
    def read_pdf(file_path: str) -> Optional[str]:
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
    def read_docx(file_path: str) -> Optional[str]:
        """Extract text from a DOCX/DOC/DOCS file"""
        try:
            doc = Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text.strip()
        except Exception as e:
            print(f"Error reading DOCX file: {str(e)}")
            return None

    @staticmethod
    def read_txt(file_path: str) -> Optional[str]:
        """Read text from a TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except Exception as e:
            print(f"Error reading TXT file: {str(e)}")
            return None