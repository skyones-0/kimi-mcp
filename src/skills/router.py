"""
Skill Router for Kimi-PIMCP
Routes queries to appropriate skills using intent classification.
"""

import os
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.svm import SVC
from sklearn.feature_extraction.text import TfidfVectorizer

from .base import (
    BaseSkill, SkillType, SkillContext, SkillConfig,
    DebuggerSkill, ArchitectSkill, ExplainerSkill, TesterSkill, CavemanSkill
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class RoutingResult:
    """Result of skill routing."""
    skill_type: SkillType
    skill: BaseSkill
    confidence: float
    all_scores: Dict[SkillType, float]


class IntentClassifier:
    """
    Intent classifier using embeddings + similarity or SVM.
    Lightweight ML for skill classification.
    """
    
    def __init__(
        self,
        model_name: str = 'sentence-transformers/all-MiniLM-L6-v2',
        use_svm: bool = True
    ):
        """
        Initialize intent classifier.
        
        Args:
            model_name: Name of the embedding model
            use_svm: Whether to use SVM (True) or pure similarity (False)
        """
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        self.use_svm = use_svm
        self.svm: Optional[SVC] = None
        self.tfidf: Optional[TfidfVectorizer] = None
        
        # Training data
        self.training_queries: List[str] = []
        self.training_labels: List[str] = []
        
        # Embeddings cache for similarity-based classification
        self.skill_prototypes: Dict[SkillType, np.ndarray] = {}
    
    def _load_model(self):
        """Lazy load the embedding model."""
        if self.model is None:
            logger.info(f"Loading embedding model for intent classification: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
    
    def load_training_data(self, dataset_path: str):
        """Load training data from dataset file."""
        if not os.path.exists(dataset_path):
            logger.warning(f"Training data not found: {dataset_path}")
            return
        
        with open(dataset_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.training_queries = []
        self.training_labels = []
        
        for item in data:
            self.training_queries.append(item['query'])
            self.training_labels.append(item['skill'])
        
        logger.info(f"Loaded {len(self.training_queries)} training examples")
        
        # Train SVM if enabled
        if self.use_svm and len(self.training_queries) > 10:
            self._train_svm()
        else:
            self._build_prototypes()
    
    def _train_svm(self):
        """Train SVM classifier on training data."""
        self._load_model()
        
        # Generate embeddings
        embeddings = self.model.encode(self.training_queries)
        
        # Train SVM
        self.svm = SVC(kernel='linear', probability=True)
        self.svm.fit(embeddings, self.training_labels)
        
        logger.info(f"SVM trained with {len(self.training_queries)} examples")
    
    def _build_prototypes(self):
        """Build prototype embeddings for each skill."""
        self._load_model()
        
        # Group queries by skill
        skill_queries: Dict[str, List[str]] = {}
        for query, label in zip(self.training_queries, self.training_labels):
            if label not in skill_queries:
                skill_queries[label] = []
            skill_queries[label].append(query)
        
        # Build prototypes (mean embedding for each skill)
        for skill_name, queries in skill_queries.items():
            try:
                skill_type = SkillType(skill_name)
                embeddings = self.model.encode(queries)
                prototype = np.mean(embeddings, axis=0)
                self.skill_prototypes[skill_type] = prototype
            except ValueError:
                logger.warning(f"Unknown skill type: {skill_name}")
        
        logger.info(f"Built prototypes for {len(self.skill_prototypes)} skills")
    
    def classify(self, query: str) -> Dict[SkillType, float]:
        """
        Classify query intent.
        
        Returns:
            Dictionary mapping skill types to confidence scores
        """
        self._load_model()
        
        # Get query embedding
        query_embedding = self.model.encode([query])[0]
        
        if self.use_svm and self.svm is not None:
            # Use SVM for classification
            probabilities = self.svm.predict_proba([query_embedding])[0]
            classes = self.svm.classes_
            
            scores = {}
            for skill_name, prob in zip(classes, probabilities):
                try:
                    skill_type = SkillType(skill_name)
                    scores[skill_type] = float(prob)
                except ValueError:
                    pass
            
            return scores
        else:
            # Use similarity to prototypes
            scores = {}
            for skill_type, prototype in self.skill_prototypes.items():
                similarity = np.dot(query_embedding, prototype) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(prototype)
                )
                scores[skill_type] = float(similarity)
            
            # Normalize scores to sum to 1
            total = sum(scores.values())
            if total > 0:
                scores = {k: v / total for k, v in scores.items()}
            
            return scores


class SkillRouter:
    """
    Main router for selecting appropriate skills.
    Combines intent classification with skill confidence scores.
    """
    
    def __init__(
        self,
        model_name: str = 'sentence-transformers/all-MiniLM-L6-v2',
        use_svm: bool = True,
        dataset_path: str = None
    ):
        """
        Initialize skill router.
        
        Args:
            model_name: Name of the embedding model
            use_svm: Whether to use SVM for classification
            dataset_path: Path to training dataset
        """
        self.classifier = IntentClassifier(model_name, use_svm)
        
        # Initialize all skills
        self.skills: Dict[SkillType, BaseSkill] = {
            SkillType.DEBUGGER: DebuggerSkill(),
            SkillType.ARCHITECT: ArchitectSkill(),
            SkillType.EXPLAINER: ExplainerSkill(),
            SkillType.TESTER: TesterSkill(),
            SkillType.CAVEMAN: CavemanSkill(),
        }
        
        self.stats = {
            'queries_routed': 0,
            'classification_time_ms': 0,
        }
        
        # Load training data
        if dataset_path is None:
            dataset_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'data', 'datasets', 'skill_queries.json'
            )
        self.classifier.load_training_data(dataset_path)
    
    def select_skill(
        self,
        query: str,
        retrieved_files: List[Dict[str, Any]] = None,
        project_path: str = ""
    ) -> RoutingResult:
        """
        Select the best skill for a query.
        
        Args:
            query: User query
            retrieved_files: List of retrieved file information
            project_path: Path to the project
        
        Returns:
            Routing result with selected skill and confidence
        """
        import time
        start_time = time.time()
        
        retrieved_files = retrieved_files or []
        
        # Create skill context
        context = SkillContext(
            query=query,
            retrieved_files=retrieved_files,
            project_path=project_path,
            metadata={}
        )
        
        # Get intent classification scores
        intent_scores = self.classifier.classify(query)
        
        # Get skill confidence scores
        skill_scores: Dict[SkillType, float] = {}
        for skill_type, skill in self.skills.items():
            skill_confidence = skill.can_handle(context)
            intent_confidence = intent_scores.get(skill_type, 0.0)
            
            # Combine scores (weighted average)
            combined_score = 0.4 * intent_confidence + 0.6 * skill_confidence
            skill_scores[skill_type] = combined_score
        
        # Select best skill
        best_skill_type = max(skill_scores, key=skill_scores.get)
        best_confidence = skill_scores[best_skill_type]
        
        # Update stats
        classification_time = int((time.time() - start_time) * 1000)
        self.stats['queries_routed'] += 1
        self.stats['classification_time_ms'] += classification_time
        
        logger.debug(f"Selected skill: {best_skill_type.value} (confidence: {best_confidence:.3f})")
        
        return RoutingResult(
            skill_type=best_skill_type,
            skill=self.skills[best_skill_type],
            confidence=best_confidence,
            all_scores=skill_scores
        )
    
    def execute_skill(
        self,
        query: str,
        retrieved_files: List[Dict[str, Any]] = None,
        project_path: str = ""
    ) -> Dict[str, Any]:
        """
        Select and execute the best skill.
        
        Args:
            query: User query
            retrieved_files: List of retrieved file information
            project_path: Path to the project
        
        Returns:
            Skill execution result
        """
        routing = self.select_skill(query, retrieved_files, project_path)
        
        context = SkillContext(
            query=query,
            retrieved_files=retrieved_files or [],
            project_path=project_path,
            metadata={'routing_confidence': routing.confidence}
        )
        
        result = routing.skill.execute(context)
        result['routing'] = {
            'skill': routing.skill_type.value,
            'confidence': routing.confidence,
            'all_scores': {k.value: v for k, v in routing.all_scores.items()}
        }
        
        return result
    
    def get_skill(self, skill_type: SkillType) -> Optional[BaseSkill]:
        """Get a specific skill by type."""
        return self.skills.get(skill_type)
    
    def list_skills(self) -> List[str]:
        """List all available skill names."""
        return [s.value for s in self.skills.keys()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        avg_time = 0
        if self.stats['queries_routed'] > 0:
            avg_time = self.stats['classification_time_ms'] // self.stats['queries_routed']
        
        return {
            'queries_routed': self.stats['queries_routed'],
            'avg_classification_time_ms': avg_time,
            'available_skills': self.list_skills()
        }


# Singleton instance
_router_instance: Optional[SkillRouter] = None


def get_router(**kwargs) -> SkillRouter:
    """Get or create singleton router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = SkillRouter(**kwargs)
    return _router_instance


if __name__ == '__main__':
    import sys
    
    router = SkillRouter()
    
    # Test queries
    test_queries = [
        "fix login bug - getting 401 error",
        "how should I structure my microservices",
        "explain what this function does",
        "generate unit tests for payment service",
        "refactor this monolithic codebase",
    ]
    
    print("Skill Router Test")
    print("=" * 60)
    
    for query in test_queries:
        result = router.select_skill(query)
        print(f"\nQuery: {query}")
        print(f"Selected: {result.skill_type.value} (confidence: {result.confidence:.3f})")
        print("All scores:")
        for skill, score in sorted(result.all_scores.items(), key=lambda x: -x[1]):
            print(f"  {skill.value}: {score:.3f}")
