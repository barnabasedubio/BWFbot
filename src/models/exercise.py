from uuid import uuid4

"""
The exercise class contains the name of the exercise, a brief description,
a youtube link to a demonstration, a list of muscles worked, and a difficulty level.
"""


class Exercise:
	def __init__(self, name="Nameless"):
		self.id = str(uuid4())
		self.name = name
		self.video_link = ""
		self.muscles_worked = []
		self.reps = []
		self.information = ""  # custom information related to the exercise
