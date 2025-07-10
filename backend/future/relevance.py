import re
from typing import List, Dict, Any, Tuple
import numpy as np
from loguru import logger
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import torch

from core.config import settings


class RelevanceClassifier:
    """Classify content relevance for medical data"""
    
    def __init__(self, model_name: str = None):
        """
        Initialize relevance classifier
        
        Args:
            model_name: Name of sentence transformer model to use
        """
        self.model_name = model_name or settings.embedding_model
        self.model = None
        self.medical_terms = self._load_medical_terms()
        self.relevance_threshold = settings.relevance_threshold
        
        # Lazy load model
        self._model_loaded = False
    
    def _load_model(self):
        """Lazy load the sentence transformer model"""
        if not self._model_loaded:
            logger.info(f"Loading relevance model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            self._model_loaded = True
    
    def _load_medical_terms(self) -> Dict[str, List[str]]:
        """TODO: make this not retarded"""
    
    def calculate_keyword_score(self, text: str) -> Tuple[float, Dict[str, int]]:
        """
        Calculate relevance score based on medical keyword presence
        
        Returns:
            Tuple of (score, keyword_counts)
        """
        text_lower = text.lower()
        keyword_counts = {}
        total_keywords = 0
        
        for category, keywords in self.medical_terms.items():
            category_count = 0
            for keyword in keywords:
                # Use word boundaries to avoid partial matches
                pattern = r'\b' + re.escape(keyword) + r'\b'
                matches = len(re.findall(pattern, text_lower))
                if matches > 0:
                    category_count += matches
                    total_keywords += matches
            
            if category_count > 0:
                keyword_counts[category] = category_count
        
        # Calculate score based on keyword density
        word_count = len(text.split())
        if word_count == 0:
            return 0.0, keyword_counts
        
        # Score is based on keyword density with diminishing returns
        keyword_density = total_keywords / word_count
        score = min(1.0, keyword_density * 10)  # Cap at 1.0
        
        # Boost score if multiple categories are present
        category_diversity = len(keyword_counts) / len(self.medical_terms)
        score = score * (1 + category_diversity * 0.5)
        
        return min(1.0, score), keyword_counts
    
    def calculate_semantic_score(self, text: str, query: str = None) -> float:
        """
        Calculate semantic relevance using sentence embeddings
        
        Args:
            text: Text to evaluate
            query: Optional query to compare against
        
        Returns:
            Semantic similarity score (0-1)
        """
        self._load_model()
        
        # If no query, use general medical relevance phrases
        if not query:
            medical_queries = [
                "medical condition disease treatment symptoms",
                "patient health diagnosis medication therapy",
                "clinical trial research study outcome",
                "side effects adverse events efficacy",
                "chronic illness pain management recovery"
            ]
        else:
            medical_queries = [query]
        
        # Encode text and queries
        text_embedding = self.model.encode([text])
        query_embeddings = self.model.encode(medical_queries)
        
        # Calculate similarities
        similarities = cosine_similarity(text_embedding, query_embeddings)[0]
        
        # Return max similarity
        return float(np.max(similarities))
    
    def classify(self, text: str, query: str = None, 
                use_semantic: bool = True) -> Dict[str, Any]:
        """
        Classify text relevance for medical data
        
        Args:
            text: Text to classify
            query: Optional search query for context
            use_semantic: Whether to use semantic similarity
        
        Returns:
            Dictionary with classification results
        """
        # Calculate keyword score
        keyword_score, keyword_counts = self.calculate_keyword_score(text)
        
        # Calculate semantic score if enabled
        semantic_score = 0.0
        if use_semantic and len(text) > 50:  # Only for substantial text
            try:
                semantic_score = self.calculate_semantic_score(text, query)
            except Exception as e:
                logger.error(f"Error calculating semantic score: {e}")
        
        # Combine scores (weighted average)
        if use_semantic:
            final_score = 0.6 * keyword_score + 0.4 * semantic_score
        else:
            final_score = keyword_score
        
        # Determine relevance
        is_relevant = final_score >= self.relevance_threshold
        
        # Explain decision
        explanation = []
        if keyword_counts:
            explanation.append(f"Found medical keywords: {keyword_counts}")
        if semantic_score > 0:
            explanation.append(f"Semantic similarity: {semantic_score:.2f}")
        
        return {
            'is_relevant': is_relevant,
            'relevance_score': float(final_score),
            'keyword_score': float(keyword_score),
            'semantic_score': float(semantic_score),
            'keyword_counts': keyword_counts,
            'explanation': '; '.join(explanation)
        }
    
    def batch_classify(self, texts: List[str], query: str = None,
                      use_semantic: bool = True) -> List[Dict[str, Any]]:
        """Classify multiple texts efficiently"""
        results = []
        
        # Process semantic scores in batch if needed
        if use_semantic and any(len(text) > 50 for text in texts):
            self._load_model()
            
            # Filter texts for semantic processing
            texts_for_semantic = [(i, text) for i, text in enumerate(texts) 
                                if len(text) > 50]
            
            if texts_for_semantic:
                indices, filtered_texts = zip(*texts_for_semantic)
                
                # Batch encode
                text_embeddings = self.model.encode(filtered_texts)
                
                # Create query embeddings
                if not query:
                    query = "medical condition disease treatment symptoms patient health"
                query_embedding = self.model.encode([query])
                
                # Calculate similarities
                similarities = cosine_similarity(text_embeddings, query_embedding)
                
                # Store results
                semantic_scores = {indices[i]: float(similarities[i][0]) 
                                 for i in range(len(indices))}
            else:
                semantic_scores = {}
        else:
            semantic_scores = {}
        
        # Process each text
        for i, text in enumerate(texts):
            # Get keyword score
            keyword_score, keyword_counts = self.calculate_keyword_score(text)
            
            # Get semantic score if available
            semantic_score = semantic_scores.get(i, 0.0)
            
            # Combine scores
            if use_semantic and i in semantic_scores:
                final_score = 0.6 * keyword_score + 0.4 * semantic_score
            else:
                final_score = keyword_score
            
            results.append({
                'is_relevant': final_score >= self.relevance_threshold,
                'relevance_score': float(final_score),
                'keyword_score': float(keyword_score),
                'semantic_score': float(semantic_score),
                'keyword_counts': keyword_counts
            })
        
        return results
    
    def extract_medical_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract medical entities from text"""
        text_lower = text.lower()
        entities = {}
        
        for category, terms in self.medical_terms.items():
            found_terms = []
            for term in terms:
                pattern = r'\b' + re.escape(term) + r'\b'
                if re.search(pattern, text_lower):
                    found_terms.append(term)
            
            if found_terms:
                entities[category] = found_terms
        
        return entities