import networkx as nx
from typing import List, Dict, Any

def generate_knowledge_graph(modules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deterministically builds a prerequisite graph for a linear course.
    Earlier modules are prerequisites for later ones.
    Within a module, earlier topics are prerequisites for later ones.
    This saves LLM calls by algorithmically generating the DAG.
    """
    G = nx.DiGraph()
    
    prev_module_last_topic = None
    topic_id_map = {}
    
    for mod_idx, mod in enumerate(modules):
        prev_topic = None
        for top_idx, top in enumerate(mod.get("lessons", [])):
            topic_title = top.get("title", f"Topic {mod_idx}-{top_idx}")
            node_id = f"m{mod_idx}_t{top_idx}"
            
            G.add_node(node_id, label=topic_title, module=mod.get("title"))
            topic_id_map[topic_title] = node_id
            
            # Link to previous topic in the same module
            if prev_topic:
                G.add_edge(prev_topic, node_id, type="sequential")
            # If it's the first topic in a module, link to the last topic of the previous module
            elif prev_module_last_topic:
                G.add_edge(prev_module_last_topic, node_id, type="module_transition")
                
            prev_topic = node_id
            
        if prev_topic:
            prev_module_last_topic = prev_topic
            
    # Export to JSON-friendly node-link format
    return nx.node_link_data(G)
