"""
The exercise class contains the name of the exercise, a brief description,
a youtube link to a demonstration, a list of muscles worked, and a difficulty level.
"""


class Exercise:
	def __init__(self, name="Nameless"):
		self.name = name
		self.video_link = ""
		self.muscles_worked = []
		self.target_rep_range = []
		self.reps = []

	def __str__(self):
		name_string = f"\nName: {self.name}"
		video_link_string = f"\nVideo: {self.video_link}" if self.video_link else ""
		muscles_worked_string = f"\nMuscled worked: {self.muscles_worked[0]}" if self.muscles_worked else ""
		target_rep_range_string = f"\nTarget rep range: {self.target_rep_range[0] + '-' + self.target_rep_range[1]}" if self.target_rep_range else ""
		return f"{name_string}{video_link_string}{muscles_worked_string}{target_rep_range_string}"
