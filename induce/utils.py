import time
import base64

def encode_image(img_path: str, return_url: bool = False) -> str:
	"""Encode the image to base64."""
	with open(img_path, "rb") as fh:
		img = base64.b64encode(fh.read()).decode()
	if return_url:
		return f"data:image/jpeg;base64,{img}"
	return img


def is_keyboard_action(action: str) -> bool:
	"""Check if the action is a keyboard action."""
	return "press" in action

def is_click_action(action: str) -> bool:
	return "click" in action

def is_scroll_action(action: str) -> bool:
	return "scroll" in action

# %% Keyboard Input
def get_key_input(action: str) -> str:
	"""Parse the key input from the action."""
	if '(' in action and ')' in action:
		kin = action.split('(')[1].split(')')[0]
	else:
		kin = action
	kin = kin.replace("'", "").strip()

	if kin == "Key.space":
		return " "
	elif kin == "Key.shift":
		return ""  # upper/lower case already applied to characters
	elif kin == "Key.backspace":
		return kin
	elif kin.startswith("Key."):  # shift/ctrl/alt/cmd
		return kin + '+'
	else:
		return kin

def compose_key_input(input_list: list[str]) -> str:
	"""Compose the key input from the actions."""
	composed_input_list = []
	for il in input_list:
		if il == "Key.backspace" and len(composed_input_list) > 0:
			composed_input_list[-1] = composed_input_list[-1][:-1]
		else:
			composed_input_list.append(il)
	return "".join(composed_input_list)


# %% LLM
import os
import openai
from openai import OpenAI

def call_openai(prompt: str, content = None, model_name: str = "gpt-4o") -> str:
	client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
	try:
		response = client.chat.completions.create(
			model=model_name,
			messages=[
				{"role": "system", "content": prompt},
				{"role": "user", "content": content},
			],
			temperature=0.0,
		)
		return response.choices[0].message.content
	except Exception as e:
		print(f"Error calling {model_name}: {type(e)}")
		return ""
