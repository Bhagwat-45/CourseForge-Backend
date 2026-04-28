import networkx as nx
from sqlalchemy.orm import Session
from typing import Dict, Any
from app.models.models import Topic, CourseProgress, Course
import logging

logger = logging.getLogger(__name__)

class MasteryEngine:
    @staticmethod
    def calculate_bayesian_update(current_mastery: float, is_correct: bool, difficulty_weight: float = 1.0) -> float:
        """
        Updates the mastery score (0.0 to 1.0) based on an interaction.
        A correct answer increases mastery, but with diminishing returns as you get closer to 1.0.
        An incorrect answer drops mastery, with a larger drop if mastery was previously high.
        """
        learning_rate = 0.15 * difficulty_weight
        
        if is_correct:
            # Asymptotically approach 1.0
            new_mastery = current_mastery + (1.0 - current_mastery) * learning_rate
        else:
            # Drop score based on how confident we thought they were
            drop = current_mastery * learning_rate * 1.5
            new_mastery = max(0.0, current_mastery - drop)
            
        return round(new_mastery, 3)

    @staticmethod
    def propagate_mastery_graph(db: Session, course_id: int, user_id: int):
        """
        Recalculates the mastery_heatmap for a user's course based on graph dependencies.
        If a prerequisite has a very low score, dependent topics suffer a confidence penalty.
        """
        course = db.query(Course).filter(Course.id == course_id).first()
        progress = db.query(CourseProgress).filter(
            CourseProgress.course_id == course_id, 
            CourseProgress.user_id == user_id
        ).first()
        
        if not course or not progress or not course.knowledge_graph:
            return
            
        try:
            # Reconstruct NetworkX DiGraph from JSON
            from networkx.readwrite import json_graph
            G = json_graph.node_link_graph(course.knowledge_graph)
            
            heatmap = progress.mastery_heatmap or {}
            
            # For each node, if its predecessors (prerequisites) have low scores, apply a penalty
            # Using topological sort ensures we propagate penalties correctly downstream
            for node in nx.topological_sort(G):
                preds = list(G.predecessors(node))
                if not preds:
                    continue
                    
                # Calculate average prerequisite mastery
                pred_scores = [heatmap.get(p, 0.0) for p in preds]
                avg_pred_score = sum(pred_scores) / len(pred_scores) if pred_scores else 1.0
                
                # If prerequisites are failing (< 0.4), apply a decay to the current node
                if avg_pred_score < 0.4:
                    current_node_score = heatmap.get(node, 0.0)
                    penalized_score = current_node_score * 0.9 # 10% confidence decay
                    heatmap[node] = round(penalized_score, 3)
            
            # Save updated heatmap
            progress.mastery_heatmap = heatmap
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to propagate mastery graph: {e}")

    @staticmethod
    def register_interaction(db: Session, topic_id: int, user_id: int, is_correct: bool):
        """
        Registers a quiz or SRS interaction and updates local topic mastery.
        """
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            return None
            
        # Update raw topic score
        current_score = topic.mastery_score or 0.0
        new_score = MasteryEngine.calculate_bayesian_update(current_score, is_correct)
        topic.mastery_score = new_score
        
        if not is_correct:
            topic.struggle_count = (topic.struggle_count or 0) + 1
            
        # Update user heatmap
        progress = db.query(CourseProgress).filter(
            CourseProgress.course_id == topic.module.course_id,
            CourseProgress.user_id == user_id
        ).first()
        
        if progress:
            heatmap = progress.mastery_heatmap or {}
            
            # In knowledge_graph nodes are labelled m{x}_t{y}, but we map it via title
            # In a full prod system we'd map topic.id directly to node_id.
            # We'll use topic.title as the lookup key since we added label=title in graph_engine.
            node_key = topic.title 
            
            # Find the actual node ID from graph
            course = db.query(Course).filter(Course.id == topic.module.course_id).first()
            if course and course.knowledge_graph:
                for node in course.knowledge_graph.get("nodes", []):
                    if node.get("label") == topic.title:
                        node_key = node.get("id")
                        break
                        
            heatmap[node_key] = new_score
            progress.mastery_heatmap = heatmap
            db.commit()
            
            # Propagate changes downstream
            MasteryEngine.propagate_mastery_graph(db, topic.module.course_id, user_id)
        
        return new_score
