"""
The exercise class contains the name of the exercise, a brief description,
a youtube link to a demonstration, a list of muscles worked, and a difficulty level.
"""


class Exercise:
	def __init__(self, name="Nameless"):
		self.name = name
		self.video_link = ""
		self.target_rep_range = []
		self.muscles_worked = []
		self.reps = []
