import os
import json
import argparse
from utils import call_openai
from language import ActionNode, SequenceNode


def get_node_list(data_dir: str) -> list[ActionNode | SequenceNode]:
    node_paths = [f for f in os.listdir(data_dir) if f.endswith(".json")]
    node_paths.sort(key=lambda x: int(x.split('.')[0]))
    node_paths = [os.path.join(data_dir, f) for f in node_paths]
    assert len(node_paths) > 0, f"No node files found in {data_dir}"
    node_list = []
    for np in node_paths:
        np_data = json.load(open(np))
        if np_data["node_type"] == "action":
            node_list.append(ActionNode.from_json(data=np_data))
        elif np_data["node_type"] == "sequence":
            node_list.append(SequenceNode.from_json(data=np_data))
        else:
            raise ValueError(f"Unknown node type: {np_data['node_type']}")
    return node_list

def get_step_goals(node_list: list[ActionNode | SequenceNode]) -> str:
    goals = []
    for i, node in enumerate(node_list):
        if node.status.value == "failure":
            goals.append(f"[{i}] (Attempted Failure) {node.goal}")
        elif node.goal is None:
            continue
        else:
            goals.append(f"[{i}] {node.goal}")
    return '\n'.join(goals)


# %% Induce and Parse Workflow

def get_workflow(text: str, verbose: bool = True) -> list[str]:
    """Induce the workflow from the step goals, by adopting or merging the steps.
    Args:
        text: The step goals.
        verbose: Whether to print the workflow.
    Returns:
        The workflow steps.
    """
    prompt = open(os.path.join(args.prompt_dir, "induce.txt")).read()
    workflow = call_openai(prompt=prompt, content=text)
    workflow = workflow.strip('```').strip('\n').strip()
    if verbose: print(workflow)
    workflow_steps = workflow.split('\n')
    workflow_steps = [ws for ws in workflow_steps if ws.startswith('[')]
    return workflow_steps


def parse_step(step: str) -> dict:
    index_text, desc_text = step.split(']')
    index_text = index_text.strip().lstrip('[').rstrip(']')
    if '-' in index_text:
        s, e = index_text.split('-')
        s = int(s.strip())
        e = int(e.strip())
    else:
        s = e = int(index_text.strip())
    
    desc_text = desc_text.strip()
    return {"index": (s, e), "goal": desc_text}


def parse_workflow(workflow_steps: list[str], node_list: list[ActionNode | SequenceNode], verbose: bool = True) -> SequenceNode:
    workflow_root = SequenceNode(nodes=[])
    if verbose: print("Parsing workflow steps...")
    for step in workflow_steps:
        wdict = parse_step(step)
        s, e = wdict["index"]  # inclusive at both ends
        if s == e: # a single action/sequence node
            w_node = node_list[s]
            if w_node.node_type.value == "sequence":
                w_node.get_status()
        else: # sequence node
            w_node = SequenceNode(nodes=node_list[s:e+1])
            w_node.goal = wdict["goal"]
            w_node.get_status()
        if w_node.status.value == "failure":
            w_node.goal = w_node.goal
        workflow_root.nodes.append(w_node)
        if verbose:
            print(f"{w_node.node_type} | {w_node.goal} | {w_node.status}")
    
    return workflow_root


# %% Main

def one_pass(input_dir: str, output_dir: str):
    input_dir = os.path.join(args.data_dir, input_dir)
    output_dir = os.path.join(args.data_dir, output_dir)
    os.makedirs(output_dir, exist_ok=True)

    node_list = get_node_list(input_dir)
    step_goals = get_step_goals(node_list)
    if args.verbose: print("Original step goals:\n", step_goals)

    workflow_steps = get_workflow(step_goals)

    # save workflow plain text
    output_path = os.path.join(output_dir, f"workflow.txt")
    with open(output_path, 'w') as fw:
        fw.write('\n'.join(workflow_steps))

    # save workflow json
    workflow_root = None
    while workflow_root is None:
        try:
            workflow_root = parse_workflow(workflow_steps, node_list, args.verbose)
            print(f"Parsed workflow: {len(workflow_root.nodes)}")
        except Exception as e:
            print(f"Error parsing workflow: {e}")
            print("Please try again.")
            workflow_steps = get_workflow(step_goals)
    
    for i, node in enumerate(workflow_root.nodes):
        output_path = os.path.join(output_dir, f"{i}.json")
        node.to_json(output_path)

    final = input("Output the final workflow? (Y/n)")
    if final.lower() != "n":
        output_path = os.path.join(args.data_dir, f"workflow.json")
        print(f"Outputting the final workflow to {output_path} ...")
        workflow_root.to_json(output_path)
    
    return workflow_root
    

def decide_next_dir(input_dir: str, output_dir: str) -> tuple[str, str]:
    input_index = input_dir.lstrip('nodes').rstrip('/')
    if input_index == '': input_index = 0
    else: input_index = int(input_index)
    output_index = output_dir.lstrip('nodes').rstrip('/')
    output_index = int(output_index)
    print(f"Input index: {input_index}, Output index: {output_index}")
    return f"nodes{input_index + 1}", f"nodes{output_index + 1}"

def is_close_enough(last_root: SequenceNode, curr_root: SequenceNode) -> bool:
    return len(last_root.nodes) <= (len(curr_root.nodes) + 2)
    

def auto_iterate():
    node_list = get_node_list(os.path.join(args.data_dir, args.input_dir))
    last_root = SequenceNode(nodes=node_list)
    close_enough = False
    i_iter, max_iter = 0, 5
    while i_iter < max_iter:
        curr_root = one_pass(args.input_dir, args.output_dir)
        close_enough = is_close_enough(last_root, curr_root)
        if close_enough: break
        last_root = curr_root
        i_iter += 1
        args.input_dir, args.output_dir = decide_next_dir(args.input_dir, args.output_dir)
    
    output_path = os.path.join(args.data_dir, f"workflow.json")
    curr_root.to_json(output_path)



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=str, required=True,
                        help="The directory containing the nodes folder.")
    parser.add_argument("--input_dir", type=str, default="nodes",
                        help="The directory containing the input nodes.")
    parser.add_argument("--output_dir", type=str, default="nodes1",
                        help="The directory to save the merged nodes.")

    parser.add_argument("--model_name", type=str, 
                        default="litellm/neulab/claude-3-5-sonnet-20241022",
                        help="The model name to use for the LLM.")
    parser.add_argument("--prompt_dir", type=str, default="prompts",
                        help="The directory containing the prompts.")
    
    parser.add_argument("--auto", action="store_true", help="If automatically iterate and terminate workflow induction.")
    parser.add_argument("--verbose", action="store_true", help="Print details.")
    
    args = parser.parse_args()

    if args.auto:
        auto_iterate()
    else:
        one_pass(args.input_dir, args.output_dir)
