import os
import enum
import json
from utils import is_keyboard_action, encode_image, call_openai

from openai import OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


MAX_DIFF = 100000.0

class NodeType(enum.Enum):
    ACTION = "action"
    SEQUENCE = "sequence"

# %% Action Node

class Time:
    def __init__(self, before: str, after: str, range: float = None, diff: float = None):
        """Initialize the time object associated with an action.
        """
        self.before = before
        self.after = after
        self.range = range
        self.diff = diff

    @classmethod
    def from_json(cls, path: str = None, data: dict = None):
        if path is not None:
            data = json.load(open(path))
        elif data is None:
            return None
        return cls(**data)
    
    def to_json(self, path: str = None):
        data = {
            "before": self.before, "after": self.after,
            "range": self.range, "diff": self.diff
        }
        if path is not None:
            json.dump(data, open(path, 'w'))
        return data

    def get_time(self, reverse: bool = False) -> str:
        if reverse: return self.after if (self.after is not None) else self.before
        else: return self.before if (self.before is not None) else self.after
    

class State:
    def __init__(self, before: str, after: str, diff_score: float = None):
        """Initialize the state object associated with an action.
        Args:
            before: The screenshot path of the state before the action.
            after: The screenshot path of the state after the action.
            diff_score: The MSE difference score between the before and after states.
        """
        self.before = before
        self.after = after
        self.diff_score = diff_score

    @classmethod
    def from_json(cls, path: str = None, data: dict = None):
        if path is not None:
            data = json.load(open(path))
        elif data is None:
            raise ValueError("Either path or data must be provided.")
        return cls(before=data["before"], after=data["after"], diff_score=data.get("diff_score", None))
    
    def to_json(self, path: str = None):
        data = {"before": self.before, "after": self.after, "diff_score": self.diff_score}
        if path is not None:
            json.dump(data, open(path, 'w'))
        return data
    
    def get_state(self, reverse: bool = False) -> str:
        if reverse: return self.after if (self.after is not None) else self.before
        else: return self.before if (self.before is not None) else self.after


class ActionNode:
    def __init__(self, action: str, state: dict | State, goal: str = None, time: dict | Time = None):
        self.node_type = NodeType.ACTION
        self.length = 1
        self.action = action
        self.state = state if isinstance(state, State) else State(**state)
        self.goal = goal
        if time is None:
            self.time = None
        else:
            self.time = time if isinstance(time, Time) else Time(**time)
        self.status = SequenceStatus.SUCCESS

    def __str__(self):
        return f"ActionNode(action={self.action}, state={self.state}, description={self.description})"
    
    def get_semantic_repr(self):
        if self.goal is not None: return self.goal
        else: self.action
    
    def get_num_actions(self):
        return 1

    def get_goal(self, model_name: str = None):
        """Verbalize the `goal` of the `action`."""
        content = get_action_content(self, add_state=False)
        prompt = "Your task is to summarize the goal in a short sentence, given the action and the state." + \
            "Do not include prefix like 'the goal is'. Do not include action-specific details like the coordinates."
        goal = call_openai(prompt=prompt, content=content)
        self.goal = goal
    
    @classmethod
    def from_json(cls, path: str = None, data: dict = None):
        if path is not None:
            data = json.load(open(path))
        elif data is None:
            raise ValueError("Either path or data must be provided.")
        state = State.from_json(data=data["state"])
        time = Time.from_json(data=data.get("time", None))
        return cls(action=data["action"], state=state, goal=data.get("goal", None), time=time)

    def to_json(self, path: str = None):
        """Save the action node to a JSON file.
        Args:
            path: The path to save the action node.
        """
        data = {
            "node_type": self.node_type.value,
            "action": self.action,
            "state": self.state.to_json(),
            "goal": self.goal,
            "time": self.time.to_json() if self.time is not None else None
        }
        if path is not None:
            json.dump(data, open(path, 'w'))
        return data

# %% Sequence Node

class SequenceStatus(enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


class SequenceNode:
    def __init__(
        self, 
        nodes: list, 
        goal: str = None, 
        status: SequenceStatus = None,
    ):
        self.node_type = NodeType.SEQUENCE
        self.nodes = nodes
        self.length = len(self.nodes)

        self.goal = goal
        if status is None:
            self.status = SequenceStatus.UNKNOWN
        else:
            for v in SequenceStatus:
                if v.value == status:
                    self.status = v
            else:
                self.status = SequenceStatus.UNKNOWN
    
    def __str__(self):
        return f"SequenceNode(goal={self.goal}, nnodes={len(self.nodes)}, status={self.status})"
    
    def get_semantic_repr(self):
        if self.goal is not None: return self.goal
        else:
            subgoals = [n.get_semantic_repr() for n in self.nodes]
            return '\n'.join([sg for sg in subgoals if sg is not None])
    
    def get_num_actions(self):
        num_actions = 0
        for n in self.nodes:
            num_actions += n.get_num_actions()
        return num_actions

    def annotate(
        self,
        prompt_path: str = "prompts/annotate_node.txt",
        model_name: str = "litellm/neulab/claude-3-5-sonnet-20241022",
        bucket_size: int = 20,
        verbose: bool = True,
    ):
        """Group adjacent `nodes` into a `SequenceNode`."""
        total_nodes = len(self.nodes)
        num_buckets = (total_nodes + bucket_size - 1) // bucket_size
        if verbose: print(f"Total nodes: {total_nodes} | Num buckets: {num_buckets}")

        prompt = open(prompt_path).read()

        new_nodes = []
        for i in range(num_buckets):
            print(f"Bucket {i}...")
            nodes = self.nodes[i*bucket_size:(i+1)*bucket_size]
            content = get_nodes_content(nodes, add_state=True)
            response = call_openai(prompt=prompt, content=content)
            chunks = parse_annotation(response, nodes)
            while chunks is None:
                print("Failed to parse annotation. Please try again.")
                response = call_openai(prompt=prompt, content=content)
                chunks = parse_annotation(response, nodes)
            # print("Chunks: ", chunks)
            chunks = validate_chunks(chunks, nodes)
            
            for c in chunks:
                new_node = get_new_node(nodes[c["start"]:c["end"]+1])
                new_node.goal = c["goal"]
                new_nodes.append(new_node)
            if verbose: print(f"Bucket {i} done: {len(new_nodes)} new nodes..")

        self.nodes = new_nodes

        # update the goal and status
        self.get_goal(model_name=model_name)
        self.get_status(model_name=model_name)
    
    def get_goal(self, prompt_path: str = "prompts/get_node_goal.txt", model_name: str = "litellm/neulab/claude-3-5-sonnet-20241022"):
        """Summarize the `goal` from the `nodes`."""
        subgoals = [f"[{i}] {n.get_semantic_repr()}" for i, n in enumerate(self.nodes)]
        content = [{"type": "text", "text": '\n'.join(subgoals)}]
        prompt = open(prompt_path).read()
        goal = call_openai(prompt=prompt, content=content)
        self.goal = goal
    
    def get_status(self, prompt_path: str = "prompts/get_node_status.txt", model_name: str = "litellm/neulab/claude-3-5-sonnet-20241022"):
        """Get the success/failure status of the `nodes` in achieving the `goal`."""
        prompt = open(prompt_path).read()
        content = get_nodes_content(self.nodes, add_state=True)
        response = call_openai(prompt=prompt, content=content)
        self.status = SequenceStatus.SUCCESS if "YES" in response else SequenceStatus.FAILURE
    
    @classmethod
    def from_json(cls, path: str = None, data: dict = None):
        if path is not None:
            # print(f"Loading sequence node from {type(path)} | {path}...")
            data = json.load(open(path, 'r'))
        elif data is None:
            raise ValueError("Either path or data must be provided.")
        
        nodes = []
        for node in data["nodes"]:
            if node["node_type"] == NodeType.ACTION.value:
                nodes.append(ActionNode.from_json(data=node))
            elif node["node_type"] == NodeType.SEQUENCE.value:
                nodes.append(cls.from_json(data=node))
        return cls(nodes=nodes, goal=data.get("goal", None), status=data.get("status", None))

    def to_json(self, path: str = None):
        """Save the sequence node to a JSON file.
        Args:
            path: The path to save the sequence node.
        """
        data = {
            "node_type": self.node_type.value,
            "nodes": [node.to_json() for node in self.nodes],
            "goal": self.goal,
            "status": self.status.value
        }
        if path is not None:
            json.dump(data, open(path, 'w'))
        return data

# %% Utility functions

def get_new_node(action_node_list: list[ActionNode]) -> ActionNode | SequenceNode:
    """Get a new node from a segment."""
    if len(action_node_list) == 1:
        return action_node_list[0]
    else:
        assert len(action_node_list) > 1, f"Length is {len(action_node_list)}"
        return SequenceNode(nodes=action_node_list)

def merge_nodes(node_list: list[ActionNode | SequenceNode]) -> SequenceNode:
    merged_nodes = []
    for i, node in enumerate(node_list):
        if isinstance(node, ActionNode):
            merged_nodes.append(node)
        elif isinstance(node, SequenceNode):
            merged_nodes.extend(node.nodes)
    return SequenceNode(nodes=merged_nodes)


# %% Annotate Sequence Node
def parse_chunk(chunk: str) -> dict:
	"""Parse chunk info dict from string."""
	s = chunk.index('[')
	e = chunk.index(']', s+1)
	text = chunk[e+1:].strip()
	print(chunk[s+1:e])
	if '-' not in chunk[s+1:e]:
		s, e = chunk[s+1:e], chunk[s+1:e]
	else:
		s, e = chunk[s+1:e].split('-')
	s, e = int(s.strip()), int(e.strip())
	return {"start": s, "end": e, "length": e - s + 1, "goal": text}

def parse_annotation(annotation: str, node_list: list[ActionNode]) -> list[ActionNode | SequenceNode]:
    print("Annotation: ", annotation)
    index = annotation.find('[')
    chunks = [s.strip() for s in annotation[index:].split('\n') if s.strip()]
    chunks = [c for c in chunks if c.startswith('[')]
    parsed_chunks = []
    for c in chunks:
        try:
            cp = parse_chunk(c)
            parsed_chunks.append(cp)
        except: 
            print(f"Failed to parse chunk: {c}")
    return parsed_chunks


# %% Validate Chunks

def remove_empty_chunks(chunks: list[dict], node_list: list[ActionNode]) -> list[dict]:
    """Remove chunks with no steps."""
    chunk_index = None
    for i, c in enumerate(chunks):
        actions = node_list[c["start"]:c["end"]+1]
        if len(actions) == 0:
            chunk_index = i
            break
        if len(actions) < c["length"]:
            chunks[i]["end"] = c["start"] + len(actions) - 1
            chunks[i]["length"] = len(actions)
    if chunk_index is not None:
        chunks = chunks[:chunk_index]
        print(f"Removed chunk {chunk_index} because it has no steps.")
    return chunks

def validate_chunks(chunks: list[dict], node_list: list[ActionNode]) -> list[dict]:
    """Validate the chunks contain the same number of ActionNodes."""
    chunks = remove_empty_chunks(chunks, node_list)
    print("Non-Empty Chunks: ", chunks)
    total_steps = sum([c["length"] for c in chunks])
    print(f"Total Chunk Steps: {total_steps} vs Trajectory Length:{len(node_list)}")
    if total_steps < len(node_list): # add the remaining steps to the last chunk
        if len(chunks) == 0:
            chunks.append({"start": 0, "end": len(node_list) - 1, "length": len(node_list), "goal": None})
        else:
            chunks[-1]["end"] = len(node_list) - 1
            chunks[-1]["length"] = len(node_list) - chunks[-1]["start"]
        total_steps = sum([c["length"] for c in chunks])
        if total_steps != len(node_list):
            print(f"[WARNING] Total Chunk Steps: {chunks} vs Trajectory Length:{len(node_list)}")
    return chunks

# %% Input Node to LLM

def get_action_content(action_node: ActionNode, add_state: bool = False) -> list[dict]:
	"""Get the content of the step."""
	content = []
	if add_state:
		if is_keyboard_action(action_node.action):
			image_path = action_node.state.get_state()
			if image_path is not None:
				image_url = encode_image(image_path, return_url=True)
				content.append({"type": "image_url", "image_url": {"url": image_url}})
		else:
			image_path = action_node.state.get_state()
			if image_path is not None:
				image_url = encode_image(image_path, return_url=True)
				content.append({"type": "image_url", "image_url": {"url": image_url}})
	
	text = action_node.action
	if action_node.goal is not None:
		text += f" ({action_node.goal})"
	content.append({"type": "text", "text": text})
	return content

def get_nodes_content(node_list: list[ActionNode | SequenceNode], add_state: bool = False) -> list[dict]:
	"""Get the content of the sequence. Only add state for the last action, if set up."""
	content = []
	for n in node_list[:-1]:
		if isinstance(n, ActionNode):
			content.extend(get_action_content(n, add_state=False))
		else:
			content.extend(get_nodes_content(n.nodes, add_state=False))
	
	if isinstance(node_list[-1], ActionNode):
		content.extend(get_action_content(node_list[-1], add_state=add_state))
	else:
		content.extend(get_nodes_content(node_list[-1].nodes, add_state=add_state))
	return content


# %% Get First/Last Action

def get_first_action(node: ActionNode | SequenceNode) -> ActionNode:
    if isinstance(node, ActionNode):
        return node
    else:
        return get_first_action(node.nodes[0])

def get_last_action(node: ActionNode | SequenceNode) -> ActionNode:
    if isinstance(node, ActionNode):
        return node
    else:
        return get_last_action(node.nodes[-1])



def viz_node(node, indent_level: int = 0):
    content = f"[{indent_level}]" + " " * indent_level + "Type: " + node.node_type.value + " | "
    if isinstance(node, ActionNode) and node.action is not None:
        content += "Action: " + node.action + " | "
    else:
        content += "Action: None | "
    if node.goal is not None:
        content += "Goal: " + node.goal.split("\n")[0]
    else:
        content += "Goal: None"
    print(content)
    if node.node_type == NodeType.SEQUENCE:
        for child in node.nodes:
            viz_node(child, indent_level + 1)