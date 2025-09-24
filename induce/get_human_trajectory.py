"""Load the process human trajectory from the database."""

import os
import shutil
import argparse

import pandas as pd
from sqlalchemy import create_engine, text
from utils import (
	is_click_action, is_keyboard_action, is_scroll_action,
	get_key_input, compose_key_input
)
from language import ActionNode, SequenceNode

# %% Action Processing

def load_actions_from_db(log_dir: str, db_path: str) -> list[str]:
	"""Load the actions from the database. """
	db_path = os.path.expanduser(os.path.join(log_dir, db_path))
	engine = create_engine(f"sqlite:///{db_path}")

	with engine.connect() as connection:
		query = text("SELECT * from observations")
		df = pd.read_sql_query(query, connection)
	return df["content"].to_list()

def hotkey_in_action(action: str) -> bool:
	"""Check if the action contains a hotkey."""
	return any(hotkey in action for hotkey in [".cmd", ".enter", ".tab", ".up", ".down"])


def trigger_close_buffer(action: str, buffer_actions: list[str], enable_hotkey: bool = False) -> bool:
	"""Time to close the buffer: 
	- Current buffer is non-empty
	- Next new key/scroll action is different from the last action in the buffer.
	"""
	if len(buffer_actions) == 0:
		return False
	if is_keyboard_action(buffer_actions[-1]) and (not is_keyboard_action(action)):
		return True
	if is_scroll_action(buffer_actions[-1]) and (not is_scroll_action(action)):
		return True
	if enable_hotkey and is_keyboard_action(action) and hotkey_in_action(action):
		return True
	return False


def trigger_add_buffer(action: str, buffer_actions: list[str]) -> bool:
	"""Should add the new action to the buffer.
	- Is keyboard or scroll action
	- (i) buffer is empty; (ii) last action in buffer is the same type as the new action.
	"""
	if not (is_keyboard_action(action) or is_scroll_action(action)):
		return False
	if len(buffer_actions) == 0:
		return True
	if is_keyboard_action(action) and is_keyboard_action(buffer_actions[-1]):
		# print(f"Event 1: {action} | {buffer_actions[-1]}")
		return True
	if is_scroll_action(action) and is_scroll_action(buffer_actions[-1]):
		return True
	return False


def merge_actions(actions: list[str], enable_hotkey: bool = False) -> list[str]:
	"""Merge adjacent keyboard and scrolling actions into a single action."""
	original_actions, merged_actions = [], []
	buffer_actions = []
	for action in actions:
		close_buffer_flag = trigger_close_buffer(action, buffer_actions, enable_hotkey=enable_hotkey)
		if close_buffer_flag:
			if buffer_actions and is_keyboard_action(buffer_actions[0]):  # keypress buffer
				assert all([is_keyboard_action(action) for action in buffer_actions])
				original_actions.append({"before": buffer_actions[0], "after": buffer_actions[-1]})
				
				buffer_values = [get_key_input(action) for action in buffer_actions]
				keyboard_input = compose_key_input(buffer_values)
				merged_actions.append(f"key_press('{keyboard_input}')")
				# print("[KeyPress] :", merged_actions[-1])
			elif buffer_actions and is_scroll_action(buffer_actions[0]):  # scroll buffer
				assert all([is_scroll_action(action) for action in buffer_actions])
				for ba in buffer_actions:
					if len(merged_actions) == 0 or ba != merged_actions[-1]:
						original_actions.append({"before": ba, "after": ba})
						merged_actions.append(ba)
						# print("[Scroll] :", merged_actions[-1])
			buffer_actions = []

		add_buffer_flag = trigger_add_buffer(action, buffer_actions)
		if add_buffer_flag:
			buffer_actions.append(action)
		else:
			merged_actions.append(action)
			original_actions.append({"before": action, "after": action})

	return original_actions, merged_actions


# %% State

def find_screenshot(screenshot_paths: list[str], action: str, suffix: str) -> tuple[str, list[str]]:
	"""Find the screenshot path for the given action and suffix.
	Return the screenshot path and the remaining screenshot paths."""
	for i, sp in enumerate(screenshot_paths):
		if action in sp and sp.endswith(suffix):
			return screenshot_paths[i], screenshot_paths[: i] + screenshot_paths[i+1:]
	return None, screenshot_paths


def get_states(actions: list[str], screenshot_dir: str, is_windows: bool = False) -> list[dict[str, str]]:
	"""Get before/after states (screenshots) associate with each action.
	"""
	screenshot_paths = sorted(os.listdir(screenshot_dir), key=lambda x: x.split('_')[0]) # sort by timestamp
	screenshot_paths = [os.path.join(screenshot_dir, p) for p in screenshot_paths]

	states = []
	for action_dict in actions:
		# print(action_dict)
		suffix_before = "_first.jpg" if is_keyboard_action(action_dict["before"]) else "_before.jpg"
		before_path, screenshot_paths = find_screenshot(screenshot_paths, action_dict["before"], suffix_before)
		
		suffix_after = "_final.jpg" if is_keyboard_action(action_dict["after"]) else "_after.jpg"
		after_path, screenshot_paths = find_screenshot(screenshot_paths, action_dict["after"], suffix_after)
		state = {"before": before_path, "after": after_path}
		states.append(state)
		print(state)
		print('-'*20)

	return states


def adjust_states(actions: list[str], states: list[dict]) -> list[dict]:
	"""Adjust the states to reflect more accurate changes."""
	adjusted_states = []
	for i, (action, state) in enumerate(zip(actions, states)):
		if (i == 0) or is_keyboard_action(action):
			before_state = state["before"]
		else: 
			before_state = states[i-1]["after"]

		if is_keyboard_action(action) and (i < len(actions) - 1):
			after_state = states[i+1]["before"]
		else:
			after_state = state.get("after", state["before"])

		adjusted_states.append({"before": before_state, "after": after_state})

	return adjusted_states


# %% Time

def parse_screenshot_path(path: str) -> tuple[str, str]:
    """Parse the screenshot path into action and timestamp."""
    parts = path.split('/')[-1].split('_')
    timestamp = parts[0]
    if "key" in parts:
        action = '_'.join(parts[1:]).rstrip(".jpg")
        tag = "before"
    else:
        action = '_'.join(parts[1:-1])
        tag = parts[-1].split('.')[0]
    return {"timestamp": timestamp, "action": action, "tag": tag}


# %% Merge Click Actions

def parse_click_coords(action: str) -> tuple[float, float]:
	"""Parse the coordinates from the action."""
	x, y = action.split('(')[1].split(')')[0].split(',')
	return float(x), float(y)

def is_double_click(step_1: ActionNode, step_2: ActionNode, time_threshold: float = 0.5, distance_threshold: float = 10) -> bool:
	"""Check if the two click actions constitute a double click."""
	if not (is_click_action(step_1.action) and is_click_action(step_2.action)):
		return False
	if step_2.time.diff > time_threshold:
		return False

	x1, y1 = parse_click_coords(step_1.action)
	x2, y2 = parse_click_coords(step_2.action)
	dx, dy = x2 - x1, y2 - y1
	distance = (dx * dx + dy * dy) ** 0.5
	return distance < distance_threshold

def merge_double_clicks(node_list: list[ActionNode]) -> list[ActionNode]:
	"""Merge double clicks into a single click."""
	merged_node_list = []
	i, N = 0, len(node_list) - 1
	while i < N:
		step, next_step = node_list[i], node_list[i+1]
		if is_double_click(step, next_step):
			coords_str = '(' + step.action.split('(')[1]
			merged_action = "double_click" + coords_str

			data = {
				"action": merged_action,
				"state": {
					"before": step.state.before,
					"after": next_step.state.after,
				},
				"time": {
					"before": step.time.before,
					"after": next_step.time.after,
					"range": step.time.range + next_step.time.range,
					"diff": step.time.diff + next_step.time.diff
				}
			}
			merged_node_list.append(ActionNode.from_json(data=data))
			i += 2
		else:
			merged_node_list.append(step)
			i += 1
	print(f"Double clicks merged: #{len(node_list)} -> #{len(merged_node_list)} steps.")
	return merged_node_list


# %% Time

def parse_time_from_path(path: str) -> float:
	"""Parse the time from the path."""
	return float(path.split('/')[-1].split('_')[0])


def measure_time_from_states(states: list[dict]) -> list[dict]:
	"""Measure the time from the states."""
	time_list = []
	for i, state in enumerate(states):
		# calculate time range
		try:
			before_time = parse_time_from_path(state["before"])
			after_time = parse_time_from_path(state.get("after", state["before"]))
		except:
			print(f"Error parsing time from path: {state}")
			before_time = 0
			after_time = 0
		time_range = after_time - before_time

		# calculate time diff
		if i == 0:
			time_diff = 0
		else:
			try:
				last_time = parse_time_from_path(states[i-1].get("after", states[i-1]["before"]))
				time_diff = before_time - last_time
			except:
				print(f"Error parsing time from path: {states[i-1]}")
				time_diff = 0

		time_list.append({
			"before": before_time, "after": after_time,
			"range": time_range, "diff": time_diff,
		})
	return time_list


def transfer_valid_states(node_list: list[ActionNode], src_suffix: str, dst_suffix: str):
	"""Trasfer valid states to the new directory."""
	for i, node in enumerate(node_list):
		before_path, after_path = node.state.before, node.state.after
		if before_path is not None:
			dst_before_path = before_path.replace(src_suffix, dst_suffix)
			if os.path.exists(before_path):
				shutil.move(before_path, dst_before_path)
			node_list[i].state.before = dst_before_path
		
		if after_path is not None:
			dst_after_path = after_path.replace(src_suffix, dst_suffix)
			if os.path.exists(after_path):
				shutil.move(after_path, dst_after_path)
			node_list[i].state.after = dst_after_path

	return node_list


# %% Main
def main():
	actions = load_actions_from_db(args.data_dir, args.db_path)
	print(f"Loaded {len(actions)} actions from the database.")
	original_actions, actions = merge_actions(actions, enable_hotkey=args.enable_hotkey)
	states = get_states(original_actions, args.screenshot_dir)
	time_list = measure_time_from_states(states)
	assert len(actions) == len(states) == len(time_list)
	# trajectory = [{"action": a, "time": t, "state": s} for a,s,t in zip(actions, states, time_list)]
	print(f"Original trajectory: #{len(actions)} steps.")

	# prune the consecutive actions without before+after states, in the beginning and end of the trajectory
	# find the first action with not-None before+after states
	first_idx = 0
	for i, (a, s, t) in enumerate(zip(actions, states, time_list)):
		if s["before"] is not None and s["after"] is not None:
			if states[i+1]["before"] is None or states[i+1]["after"] is None:
				first_idx = i
				break
	actions = actions[first_idx:]
	states = states[first_idx:]
	time_list = time_list[first_idx:]
	# find the last action with not-None before+after states
	last_idx = len(actions) - 1
	for i in range(len(actions)-1, -1, -1):
		if states[i]["before"] is not None and states[i]["after"] is not None:
			if states[i-1]["before"] is None or states[i-1]["after"] is None:
				last_idx = i
				break
	actions = actions[:last_idx+1]
	states = states[:last_idx+1]
	time_list = time_list[:last_idx+1]
	print(f"Pruned trajectory: #{last_idx+1-first_idx} steps.")

	if args.adjust_states:
		states = adjust_states(actions, states)
		adjusted_time_list = measure_time_from_states(states)
		for time_dict, adjusted in zip(time_list, adjusted_time_list):
			time_dict["range"] = adjusted["range"]
	assert len(actions) == len(states) == len(time_list)

	node_list = [ActionNode(action=a, state=s, time=t) for a, s, t in zip(actions, states, time_list)]

    # organize trajectory
	if args.merge_double_clicks:
		node_list = merge_double_clicks(node_list)

	if args.transfer_valid_states:
		src_suffix = args.screenshot_dir.split('/')[-1]
		dst_suffix = args.state_dir.split('/')[-1]
		node_list = transfer_valid_states(node_list, src_suffix, dst_suffix)

	print(f"Saving trajectory of #{len(node_list)} steps to {args.data_dir}...")
	traj_dir = args.data_dir.replace("/records", "")
	traj_path = os.path.join(traj_dir, "processed_trajectory.json")
	root = SequenceNode(nodes=node_list)
	root.to_json(traj_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=str, required=True,
                        help="The directory containing the raw trajectory data.")
    parser.add_argument("--db_path", type=str, default="actions.db")
    parser.add_argument("--screenshot_dir", type=str, default="screenshots")

    parser.add_argument("--enable_hotkey", action="store_true", help="Enable hotkey in the action.")
    parser.add_argument("--adjust_states", action="store_true", help="Adjust the states to reflect more accurate changes.")
    parser.add_argument("--merge_double_clicks", action="store_true", help="Identify double clicks and merge them into a single action.")
    parser.add_argument("--transfer_valid_states", action="store_true", help="Transfer valid states to the new directory.")
    parser.add_argument("--state_dir", type=str, default="states")
    parser.add_argument("--verbose", action="store_true")
    
    args = parser.parse_args()

    args.data_dir = os.path.join(args.data_dir, "records")
    args.screenshot_dir = os.path.join(args.data_dir, args.screenshot_dir)

    args.adjust_states, args.merge_double_clicks = True, True

    main()
