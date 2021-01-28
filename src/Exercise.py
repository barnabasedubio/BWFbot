"""
The exercise class contains the name of the exercise, a brief description,
a youtube link to a demonstration, a list of muscles worked, and a difficulty level.
"""

class Exercise:
	def __init__(self, name, description="", video_link="", muscles_worked=[]):
		self.name = name
		self.description = description
		self.video_link = video_link
		self.muscles_worked = muscles_worked
		self.reps = []