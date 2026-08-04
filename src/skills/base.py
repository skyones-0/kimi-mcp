"""
Base Skill Class for Kimi-PIMCP
Defines the interface for all skills.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import os


class SkillType(Enum):
    """Types of skills available."""
    DEBUGGER = "debugger"
    ARCHITECT = "architect"
    EXPLAINER = "explainer"
    TESTER = "tester"
    CAVEMAN = "caveman"


@dataclass
class SkillConfig:
    """Configuration for a skill."""
    name: str
    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0


@dataclass
class SkillContext:
    """Context passed to skills during execution."""
    query: str
    retrieved_files: List[Dict[str, Any]]
    project_path: str
    metadata: Dict[str, Any]


class BaseSkill(ABC):
    """Base class for all skills."""
    
    SKILL_TYPE: SkillType = None
    DEFAULT_PROMPT_PATH: str = None
    
    def __init__(self, config: Optional[SkillConfig] = None):
        """Initialize skill with configuration."""
        if config is None:
            config = self._load_default_config()
        self.config = config
    
    def _load_default_config(self) -> SkillConfig:
        """Load default configuration for this skill."""
        prompt = self._load_default_prompt()
        return SkillConfig(
            name=self.SKILL_TYPE.value if self.SKILL_TYPE else "unknown",
            system_prompt=prompt,
            temperature=0.7,
            max_tokens=4096
        )
    
    def _load_default_prompt(self) -> str:
        """Load default system prompt from file."""
        if self.DEFAULT_PROMPT_PATH and os.path.exists(self.DEFAULT_PROMPT_PATH):
            with open(self.DEFAULT_PROMPT_PATH, 'r', encoding='utf-8') as f:
                return f.read()
        return "You are a helpful assistant."
    
    @abstractmethod
    def can_handle(self, context: SkillContext) -> float:
        """
        Determine if this skill can handle the given context.
        
        Returns:
            Confidence score between 0 and 1
        """
        pass
    
    @abstractmethod
    def execute(self, context: SkillContext) -> Dict[str, Any]:
        """
        Execute the skill with the given context.
        
        Returns:
            Response dictionary with 'content' and optional metadata
        """
        pass
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for this skill."""
        return self.config.system_prompt
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get generation parameters for this skill."""
        return {
            'temperature': self.config.temperature,
            'max_tokens': self.config.max_tokens,
            'top_p': self.config.top_p,
            'frequency_penalty': self.config.frequency_penalty,
            'presence_penalty': self.config.presence_penalty,
        }


class DebuggerSkill(BaseSkill):
    """Skill for debugging code issues."""
    
    SKILL_TYPE = SkillType.DEBUGGER
    
    DEBUG_INDICATORS = [
        'bug', 'error', 'exception', 'crash', 'fail', 'broken',
        'not working', 'doesn\'t work', 'issue', 'problem',
        'debug', 'fix', 'traceback', 'stack trace', 'log',
        'null', 'undefined', 'none', 'nan', 'infinity',
        'timeout', 'hang', 'freeze', 'slow', 'memory leak',
        '401', '403', '404', '500', '502', '503',
        'syntax error', 'runtime error', 'type error',
    ]
    
    def __init__(self, config: Optional[SkillConfig] = None):
        """Initialize debugger skill."""
        super().__init__(config)
        self.DEFAULT_PROMPT_PATH = os.path.join(
            os.path.dirname(__file__), 'prompts', 'debugger.txt'
        )
        # Reload with correct prompt
        if config is None:
            self.config = self._load_default_config()
    
    def can_handle(self, context: SkillContext) -> float:
        """Check if query indicates a debugging scenario."""
        query_lower = context.query.lower()
        
        # Check for debug indicators
        score = 0.0
        for indicator in self.DEBUG_INDICATORS:
            if indicator in query_lower:
                score += 0.2
        
        # Check if retrieved files are test files
        for file_info in context.retrieved_files:
            filepath = file_info.get('filepath', '').lower()
            if any(x in filepath for x in ['test', 'spec', 'debug']):
                score += 0.15
        
        # Check for error patterns in query
        if any(x in query_lower for x in ['traceback', 'stack trace', 'exception']):
            score += 0.3
        
        return min(score, 1.0)
    
    def execute(self, context: SkillContext) -> Dict[str, Any]:
        """Execute debugging assistance."""
        return {
            'skill': self.SKILL_TYPE.value,
            'system_prompt': self.get_system_prompt(),
            'parameters': self.get_parameters(),
            'context': {
                'query': context.query,
                'files': context.retrieved_files,
                'suggestions': self._generate_suggestions(context)
            }
        }
    
    def _generate_suggestions(self, context: SkillContext) -> List[str]:
        """Generate debugging suggestions based on context."""
        suggestions = []
        query_lower = context.query.lower()
        
        if 'error' in query_lower or 'exception' in query_lower:
            suggestions.append("Check the error message and stack trace carefully")
            suggestions.append("Look for line numbers mentioned in the error")
        
        if 'test' in query_lower:
            suggestions.append("Run tests with verbose output: pytest -v or npm test -- --verbose")
        
        if '401' in query_lower or '403' in query_lower:
            suggestions.append("Verify authentication tokens and permissions")
        
        if 'timeout' in query_lower:
            suggestions.append("Check network connectivity and API response times")
        
        return suggestions


class ArchitectSkill(BaseSkill):
    """Skill for system design and architecture."""
    
    SKILL_TYPE = SkillType.ARCHITECT
    
    ARCHITECT_INDICATORS = [
        'architecture', 'design', 'structure', 'pattern',
        'microservice', 'monolith', 'scalable', 'scale',
        'database schema', 'data model', 'entity relationship',
        'refactor', 'restructure', 'reorganize', 'modularize',
        'best practice', 'convention', 'standard',
        'performance', 'optimization', 'efficient',
        'security', 'authentication', 'authorization',
    ]
    
    def __init__(self, config: Optional[SkillConfig] = None):
        """Initialize architect skill."""
        super().__init__(config)
        self.DEFAULT_PROMPT_PATH = os.path.join(
            os.path.dirname(__file__), 'prompts', 'architect.txt'
        )
        if config is None:
            self.config = self._load_default_config()
    
    def can_handle(self, context: SkillContext) -> float:
        """Check if query indicates an architecture scenario."""
        query_lower = context.query.lower()
        
        score = 0.0
        for indicator in self.ARCHITECT_INDICATORS:
            if indicator in query_lower:
                score += 0.2
        
        # Higher score for design questions
        if any(x in query_lower for x in ['how should', 'best way', 'recommend']):
            score += 0.15
        
        return min(score, 1.0)
    
    def execute(self, context: SkillContext) -> Dict[str, Any]:
        """Execute architecture assistance."""
        return {
            'skill': self.SKILL_TYPE.value,
            'system_prompt': self.get_system_prompt(),
            'parameters': self.get_parameters(),
            'context': {
                'query': context.query,
                'files': context.retrieved_files,
            }
        }


class ExplainerSkill(BaseSkill):
    """Skill for explaining code and concepts."""
    
    SKILL_TYPE = SkillType.EXPLAINER
    
    EXPLAIN_INDICATORS = [
        'explain', 'what is', 'how does', 'what does',
        'documentation', 'document', 'describe',
        'understand', 'meaning', 'purpose',
        'why', 'when', 'where',
        'tutorial', 'guide', 'example',
        'walkthrough', 'overview', 'summary',
    ]
    
    def __init__(self, config: Optional[SkillConfig] = None):
        """Initialize explainer skill."""
        super().__init__(config)
        self.DEFAULT_PROMPT_PATH = os.path.join(
            os.path.dirname(__file__), 'prompts', 'explainer.txt'
        )
        if config is None:
            self.config = self._load_default_config()
    
    def can_handle(self, context: SkillContext) -> float:
        """Check if query indicates an explanation scenario."""
        query_lower = context.query.lower()
        
        score = 0.0
        for indicator in self.EXPLAIN_INDICATORS:
            if indicator in query_lower:
                score += 0.25
        
        # Question marks indicate explanation requests
        if '?' in context.query:
            score += 0.1
        
        return min(score, 1.0)
    
    def execute(self, context: SkillContext) -> Dict[str, Any]:
        """Execute explanation assistance."""
        return {
            'skill': self.SKILL_TYPE.value,
            'system_prompt': self.get_system_prompt(),
            'parameters': self.get_parameters(),
            'context': {
                'query': context.query,
                'files': context.retrieved_files,
            }
        }


class TesterSkill(BaseSkill):
    """Skill for testing and quality assurance."""
    
    SKILL_TYPE = SkillType.TESTER
    
    TEST_INDICATORS = [
        'test', 'spec', 'coverage', 'unit test',
        'integration test', 'e2e', 'end to end',
        'jest', 'pytest', 'mocha', 'cypress',
        'mock', 'stub', 'fixture', 'assert',
        'expect', 'should', 'verify',
        'tdd', 'bdd', 'quality', 'qa',
        'edge case', 'boundary', 'scenario',
    ]
    
    def __init__(self, config: Optional[SkillConfig] = None):
        """Initialize tester skill."""
        super().__init__(config)
        self.DEFAULT_PROMPT_PATH = os.path.join(
            os.path.dirname(__file__), 'prompts', 'tester.txt'
        )
        if config is None:
            self.config = self._load_default_config()
    
    def can_handle(self, context: SkillContext) -> float:
        """Check if query indicates a testing scenario."""
        query_lower = context.query.lower()
        
        score = 0.0
        for indicator in self.TEST_INDICATORS:
            if indicator in query_lower:
                score += 0.25
        
        # Check if retrieved files are test files
        for file_info in context.retrieved_files:
            filepath = file_info.get('filepath', '').lower()
            if any(x in filepath for x in ['test', 'spec', '__tests__']):
                score += 0.2
        
        return min(score, 1.0)
    
    def execute(self, context: SkillContext) -> Dict[str, Any]:
        """Execute testing assistance."""
        return {
            'skill': self.SKILL_TYPE.value,
            'system_prompt': self.get_system_prompt(),
            'parameters': self.get_parameters(),
            'context': {
                'query': context.query,
                'files': context.retrieved_files,
                'test_framework': self._detect_test_framework(context)
            }
        }
    
    def _detect_test_framework(self, context: SkillContext) -> Optional[str]:
        """Detect the testing framework being used."""
        for file_info in context.retrieved_files:
            filepath = file_info.get('filepath', '').lower()
            content = file_info.get('content', '').lower()
            
            if 'jest' in filepath or 'jest' in content:
                return 'jest'
            elif 'pytest' in filepath or 'pytest' in content:
                return 'pytest'
            elif 'mocha' in filepath or 'mocha' in content:
                return 'mocha'
            elif 'cypress' in filepath:
                return 'cypress'
            elif 'unittest' in content:
                return 'unittest'
        
        return None


class CavemanSkill(BaseSkill):
    """Default skill with caveman compression."""
    
    SKILL_TYPE = SkillType.CAVEMAN
    
    def __init__(self, config: Optional[SkillConfig] = None):
        """Initialize caveman skill."""
        super().__init__(config)
        self.DEFAULT_PROMPT_PATH = os.path.join(
            os.path.dirname(__file__), 'prompts', 'caveman.txt'
        )
        if config is None:
            self.config = self._load_default_config()
        # Lower temperature for more concise responses
        self.config.temperature = 0.3
    
    def can_handle(self, context: SkillContext) -> float:
        """Default skill - always available with low confidence."""
        return 0.3
    
    def execute(self, context: SkillContext) -> Dict[str, Any]:
        """Execute with caveman compression."""
        return {
            'skill': self.SKILL_TYPE.value,
            'system_prompt': self.get_system_prompt(),
            'parameters': self.get_parameters(),
            'context': {
                'query': context.query,
                'files': context.retrieved_files,
            }
        }
