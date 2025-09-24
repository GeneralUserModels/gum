"""Segment trajectory into (raw) nodes based on state similarity.
 - Use MSE to measure state similarity, split if beyond a threshold.
 - If specified, use neural similarity to re-merge nodes if the software is the same.
"""

import os
import cv2
import argparse
import numpy as np
from utils import encode_image, call_openai
from language import (
    ActionNode, SequenceNode, get_new_node, merge_nodes, 
    get_first_action, get_last_action, viz_node,
)

# %% State Similarity
MAX_DIFF = 100000.0

def mse(image_path1: str | None, image_path2: str | None) -> float:
    """Calculate the mean squared error between two images."""
    # print(f"Calculating MSE between {image_path1} and {image_path2}")
    if image_path1 is None or image_path2 is None:
        return MAX_DIFF
    image1 = cv2.imread(image_path1)
    image2 = cv2.imread(image_path2)
    if image1.shape != image2.shape:
        # print(f"Image shapes do not match: {image1.shape} != {image2.shape}")
        return MAX_DIFF
    err = np.sum((image1.astype("float") - image2.astype("float")) ** 2)
    err /= float(image1.shape[0] * image1.shape[1])
    return err


PROMPT = """Your task is to determine if the two computer screens focus on the same software.
For each screen, first identify the software it is focused on in the front, e.g., Google Chrome, VSCode, Finder, etc.
Then, compare the software on the two screens. If they are the same, output 'YES'. Otherwise, output 'NO'."""

def neural(image1: str | None, image2: str | None) -> float:
    """Calculate the similarity between two images using LLM."""
    if image1 is None or image2 is None:
        return MAX_DIFF
    image1_url = encode_image(image1, return_url=True)
    image2_url = encode_image(image2, return_url=True)
    content = [
        {"type": "image_url", "image_url": {"url": image1_url},},
        {"type": "image_url", "image_url": {"url": image2_url},}
    ]
    response = call_openai(PROMPT, content)
    return 0.0 if "YES" in response else 1.0


SIM_FUNC = {"mse": mse, "neural": neural}

def get_state_similarity(
    curr_node: ActionNode | SequenceNode,
    last_node: ActionNode | SequenceNode,
    method: str = "mse",
) -> float:
    """Calculate the similarity between the current and last state of the trajectory."""
    curr_action = get_first_action(curr_node)
    curr_state_path = curr_action.state.get_state(reverse=True)
    last_action = get_last_action(last_node)
    last_state_path = last_action.state.get_state(reverse=True)
    diff_score = SIM_FUNC[method](curr_state_path, last_state_path)
    if diff_score is None:
        print(f"Diff score is None for {curr_state_path} and {last_state_path}")
    return diff_score


def measure_state_diffs(path: str, verbose: bool = False) -> SequenceNode:
    """Measure the state similarity between consecutive action nodes in the trajectory."""
    output_path = path.replace(".json", "_mse.json")
    if os.path.exists(output_path):
        root_node = SequenceNode.from_json(output_path)
        if verbose:
            print(f"Loaded trajectory with mse diff scores from {output_path}")
        return root_node

    # measure similarity scores
    print(f"Measuring state diffs for {path}...")
    root_node = SequenceNode.from_json(path)
    root_node.nodes[0].state.diff_score = 0.0
    for i, action_node in enumerate(root_node.nodes[1:]):
        diff_score = get_state_similarity(
            curr_node=action_node,
            last_node=root_node.nodes[i-1],
            method="mse",
        )
        root_node.nodes[i+1].state.diff_score = diff_score

    # save the trajectory with diff scores
    root_node.to_json(output_path)
    if verbose:
        print(f"Saved trajectory with mse diff scores to {output_path}")
    return root_node


# %% Segmentation

def segment_per_step(
    root_node: SequenceNode,
    threshold: float = 10000.0,
    verbose: bool = False
) -> list[SequenceNode | ActionNode]:
    """Segment the trajectory at actions with above-threshold state differences."""
    segments, curr_segment = [], []
    for i, action_node in enumerate(root_node.nodes):
        # clean the current segment if a new high-diff step is found
        if (action_node.state.diff_score > threshold) and len(curr_segment) > 0:
            segments.append(get_new_node(curr_segment))
            curr_segment = []
        # otherwise, add the step to the current segment
        curr_segment.append(action_node)

    # add the last segment if it exists
    if curr_segment: segments.append(get_new_node(curr_segment))
    if verbose:
        print(f"Found {len(segments)} segments via mse diff threshold {threshold}.")
    return segments


def find_below_threshold_ranges(scores: list[float], threshold: float = 8000.0, min_steps: int = 3) -> list[tuple[int, int]]:
    """
    Find all ranges (start_index, end_index) where all scores are below threshold.
    
    Args:
        scores: List of numeric scores
        threshold: Threshold value to compare against
        
    Returns:
        List of tuples (start_index, end_index) where all scores in the range
        [start_index, end_index] are below threshold
    """
    ranges = []
    start = None
    
    for i, score in enumerate(scores):
        if score < threshold:
            if start is None:
                start = i
        else:
            if start is not None:
                ranges.append((start, i - 1))
                start = None
    
    # Handle case where the last range extends to the end
    if start is not None:
        ranges.append((start, len(scores) - 1))
    
    ranges = [r for r in ranges if (r[1] - r[0] + 1)>= min_steps]
    return ranges

def get_intervals(
    ranges: list[tuple[int, int]],
    root_node: SequenceNode, 
    threshold: float = 10000.0, 
    min_steps: int = 5,
    verbose: bool = False
) -> list[tuple[int, int]]:
    intervals = []

    # add the first range
    s, e = ranges[0]
    if s <= min_steps:
        ranges = [(0, e)] + ranges[1: ]
    else:
        intervals.append((0, s-1))
    if verbose:
        print(f"Found {len(ranges)} ranges: ", ranges)
        # cont = input("Continue? (Y/n)")

    # add the rest of the ranges
    i, L = 0, len(ranges)
    while i < (L - 1):
        # calculate gap with next range
        curr_range = ranges[i]
        gap = (ranges[i][1]+1, ranges[i+1][0]-1)  # both sides inclusive
        step_diff = gap[1] - curr_range[1]
        if step_diff >= min_steps: # add as two ranges
            intervals.append(curr_range)
            intervals.append(gap)
            if verbose:
                print(f"Added range {curr_range} and gap {gap} (step_diff: {step_diff})")
                # cont = input("Continue? (Y/n)")
        else:  # merge as one range
            intervals.append((curr_range[0], gap[1]))
            if verbose:
                print(f"Added merged range {intervals[-1]} (curr_range: {curr_range}) (gap: {gap}) (step_diff: {step_diff})")
                # cont = input("Continue? (Y/n)")
        i += 1
    
    # after the loop
    if i != L - 1:
        print("Suggestion: use `--default_segment` to use the default segmentation method. Do you want to run it now? (y/n)")
        cont = input()
        if cont == "y":
            segments = segment_per_step(root_node, threshold, verbose)
            return segments
        else:
            raise ValueError("i != L - 1" + f"(i: {i}, L-1: {L-1})")

    if ranges[i][1] < root_node.length-1:
        curr_range = ranges[i]
        gap = (ranges[i][1]+1, root_node.length-1)
        step_diff = gap[0] - curr_range[1]
        if step_diff >= min_steps:
            intervals.append(curr_range)
            intervals.append(gap)
        else:
            intervals.append((curr_range[0], gap[1]))
    else:
        assert ranges[i][1] == root_node.length-1
        intervals.append(ranges[i])
    return intervals


def segment_by_ranges(
    root_node: SequenceNode, 
    threshold: float = 10000.0, 
    min_steps: int = 5,
    verbose: bool = False,
) -> list[ActionNode | SequenceNode]:
    scores = [a.state.diff_score for a in root_node.nodes]
    ranges = find_below_threshold_ranges(scores, threshold, min_steps)  # inclusive at both ends
    intervals = get_intervals(ranges, root_node, threshold, min_steps, verbose)
    if verbose:
        print(f"Found {len(intervals)} segments via mse diff threshold {threshold}: {intervals}")
    if min_steps == 1:
        split_intervals = []
        for (s, e) in intervals:
            if all([root_node.nodes[i].state.diff_score == MAX_DIFF for i in range(s, e+1)]):
                split_intervals.extend([(m, m) for m in range(s, e+1)])
            else:
                split_intervals.append((s, e))
        if verbose:
            print(f"Split {len(intervals)} segments via MaxDiff into: {len(split_intervals)}")
        intervals = split_intervals

    segments = [
        get_new_node(root_node.nodes[i1:i2+1])
        for (i1, i2) in intervals
    ]
    return segments


def get_ipython_segments_0(nodes: list[ActionNode]) -> list[ActionNode | SequenceNode]:
    """Get the ipython segments from the nodes."""
    ipython_segments = []
    curr_segment = []
    for node in nodes:
        assert isinstance(node, ActionNode)
        if ("run_ipython" in node.action) and (len(curr_segment) > 0):
            ipython_segments.append(get_new_node(curr_segment))
            curr_segment = []
        curr_segment.append(node)
    if len(curr_segment) > 0:
        ipython_segments.append(get_new_node(curr_segment))
    return ipython_segments

def get_ipython_segments(nodes: list[ActionNode]) -> list[ActionNode | SequenceNode]:
    """Get the ipython segments from the nodes."""
    ipython_indices = [i for i, node in enumerate(nodes) if ("run_ipython" in node.action)]
    if len(ipython_indices) == 0:
        return [get_new_node(nodes)]
    ipython_segments = []
    if ipython_indices[0] > 0:
        ipython_segments.append(get_new_node(nodes[:ipython_indices[0]]))
    for i in range(len(ipython_indices)-1):
        ipython_segments.append(nodes[ipython_indices[i]])
        if ipython_indices[i]+1 < ipython_indices[i+1]:
            ipython_segments.append(get_new_node(nodes[ipython_indices[i]+1:ipython_indices[i+1]]))
    ipython_segments.append(nodes[ipython_indices[-1]])
    if ipython_indices[-1] < len(nodes)-1:
        ipython_segments.append(get_new_node(nodes[ipython_indices[-1]+1:]))
    return ipython_segments

def segment_at_ipython(segments: list[ActionNode | SequenceNode], verbose: bool = False) -> list[ActionNode | SequenceNode]:
    """Segment the trajectory at actions with above-threshold state differences."""
    ipython_segments = []
    for seg in segments:
        if isinstance(seg, ActionNode):
            ipython_segments.append(seg)
        elif isinstance(seg, SequenceNode):
            ipython_segments.extend(get_ipython_segments(seg.nodes))
        else:
            raise ValueError(f"Unknown segment type: {type(seg)}")
    if verbose:
        print(f"Found {len(ipython_segments)} ipython segments from {len(segments)} segments.")
    return ipython_segments

# %% Remerge with LLM

def remerge_segments(
    segments: list[ActionNode | SequenceNode],
    threshold: float = 3.0,
    verbose: bool = False
) -> list[ActionNode | SequenceNode]:
    merged_segments = []
    i, L = 0, len(segments)
    while i < (L-1):
        seg, next_seg = segments[i], segments[i+1]
        if min(seg.length, next_seg.length) < threshold:
            diff_score = get_state_similarity(
                curr_node=next_seg,
                last_node=seg,
                method="neural",
            )
            if diff_score == 0.0: # same software
                merged_segments.append(merge_nodes([seg, next_seg]))
                i += 2
                if verbose:
                    print(f"Merged segment #{i-1} and #{i} with {len(seg) + len(next_seg)} steps.")
                continue
        merged_segments.append(seg)
        i += 1
    if i == L-1:
        merged_segments.append(segments[i])
    return merged_segments


def remerge_segments_iterative(
    segments: list[ActionNode | SequenceNode],
    threshold: float = 3.0,
    verbose: bool = False,
) -> list[ActionNode | SequenceNode]:
    segment_lengths = [seg.length for seg in segments]
    while min(segment_lengths) < threshold:
        segments = remerge_segments(segments, threshold, verbose)
        if segment_lengths == [seg.length for seg in segments]:
            break
        segment_lengths = [seg.length for seg in segments]
    return segments


# %% Split Sequence Nodes

def split_sequence_node(node: SequenceNode) -> list[ActionNode | SequenceNode]:
    """Split the sequence node into multiple nodes."""
    subgoals = [n.goal for n in node.nodes]
    if len(subgoals) == 1: 
        # assert node.goal == subgoals[0], f"Node goal: {node.goal} != Subgoal: {subgoals[0]}"
        return node.nodes
    if len(subgoals) > 20:
        return [node]
    response = call_openai(
        prompt="Is the goal a simple composition of subgoals? Only output 'YES' or 'NO'.",
        content=f"Goal: {node.goal}\n\nSubgoals:\n" + "\n".join(subgoals)
    )
    if "YES" in response:
        print(f"Split sequence node {node.goal} into {len(node.nodes)} nodes:", subgoals)
        # cont = input("Continue? (Y/n)")
        return node.nodes
    else:
        print(f"Not splitting sequence node {node.goal} into {len(node.nodes)} nodes:", subgoals)
        # cont = input("Continue? (y/N)")
        return [node]
    if cont.strip().lower() == "y":
        return node.nodes
    else:
        return [node]


# %% Main

def main():
    # measure state diffs
    root_node = measure_state_diffs(args.trajectory_path, args.verbose)
    # segment the trajectory
    if args.default_segment:
        segments = segment_per_step(root_node, args.threshold, args.verbose)
    else:
        segments = segment_by_ranges(root_node, args.threshold, min_steps=args.min_steps, verbose=args.verbose)

    segments = segment_at_ipython(segments, args.verbose)
    if len(segments) == 0: segments = [root_node]
   
    # semantically re-merge the segments if specified (based on semantic adjacent state similarity)
    if args.do_remerge:  # list[ActionNode | SequenceNode]
        segments = remerge_segments_iterative(segments, args.remerge_threshold, args.verbose)

    segments = segments[1:]
    print(f"Found {len(segments)} segments: ", [s.get_num_actions() for s in segments])  # each segment is a ActionNode or list[ActionNode]
    # cont = input("Continue? (Y/n)")
    # segment sequence nodes with compositional goals (based on LLM-annotated goals)
    def process_and_save_node(node: ActionNode | SequenceNode, i: int, save: bool = True) -> tuple[list[ActionNode | SequenceNode], int]:
        if isinstance(node, ActionNode):
            node.get_goal()
            print(f"[{node.node_type.value}] Goal: {node.goal}")
            if save:
                node_path = os.path.join(args.output_dir, f"{i}.json")
                node.to_json(node_path)
            return [node], i+1
        elif isinstance(node, SequenceNode):
            node.annotate(model_name="gpt-4o", verbose=args.verbose)
            split_nodes = split_sequence_node(node)
            for n in split_nodes:
                print(f"[{n.node_type.value}] Goal: {n.goal}")
                if save:
                    node_path = os.path.join(args.output_dir, f"{i}.json")
                    n.to_json(node_path)
                i += 1
            return split_nodes, i


    node_list = []
    for node in segments[: 2]:
        nodes, i = process_and_save_node(node, 0, save=False)
        node_list.extend(nodes)
    
    def merge_nodes_keep_goal(node1: ActionNode | SequenceNode, node2: ActionNode | SequenceNode) -> SequenceNode:
        if node1.node_type.value == "action":
            if node2.node_type.value == "action":
                node = get_new_node([node1, node2])
                return [node]
            else:
                node2.nodes = [node1] + node2.nodes
                return [node2]
        elif node1.node_type.value == "sequence":
            node2.nodes = node1.nodes + node2.nodes
            return [node2]
        else:
            raise ValueError(f"Unknown node type: {node1.node_type.value}")
    
    if node_list[0].get_num_actions() == 1:
        node_list = merge_nodes_keep_goal(node_list[0], node_list[1])
    for i, n in enumerate(node_list):
        print(f"[{n.node_type.value}] Goal: {n.goal}")
        node_path = os.path.join(args.output_dir, f"{i}.json")
        n.to_json(node_path)
    
    i += 1
    print("Resume node processing from index", i)
    for node in segments[2:]:
        nodes, i = process_and_save_node(node, i, save=True)
        node_list.extend(nodes)

    # examine the segments
    if args.verbose:
        viz_idx = int(input(f"Enter the index of the node to visualize (0-{len(node_list)-1}): "))
        while 0 <= viz_idx < len(node_list):
            viz_node(node_list[viz_idx])
            viz_idx = int(input(f"Enter the index of the node to visualize (0-{len(node_list)-1}): "))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=str, required=True,
                        help="The directory containing the trajectory data.")
    parser.add_argument("--trajectory_name", type=str, default="processed_trajectory.json",
                        help="The name of the trajectory data file.")
    parser.add_argument("--output_dir", type=str, default="nodes",
                        help="The directory to save the segmented nodes.")

    # mse
    parser.add_argument("--threshold", type=float, default=8000.0, 
                        help="State MSE difference threshold for segmentation.")
    parser.add_argument("--min_steps", type=int, default=5, help="Minimum number of steps for a segment.")
    parser.add_argument("--default_segment", action="store_true", 
                        help="If use default segmentation method: split at high-diff steps; otherwise, identify low-diff ranges.")

    # neural
    parser.add_argument("--do_remerge", action="store_true", 
                        help="If re-merge segments via neural similarity.")
    parser.add_argument("--remerge_threshold", type=float, default=3.0,
                        help="Maximum number of steps for triggering re-merging via neural similarity.")
    
    # debug
    parser.add_argument("--verbose", action="store_true", help="Print details.")

    args = parser.parse_args()

    args.trajectory_path = os.path.join(args.data_dir, args.trajectory_name)
    args.output_dir = os.path.join(args.data_dir, args.output_dir)
    os.makedirs(args.output_dir, exist_ok=True)

    main()
