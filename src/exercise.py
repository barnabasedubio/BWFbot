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

	#  string representation of class (formatted as MarkdownV2)
	def __str__(self):
		name_string = f"*{self.name.capitalize()}*\n"
		video_link_string = f"\n[Video demonstration]({self.video_link})\n" if self.video_link else ""
		muscles_worked_string = ""
		if self.muscles_worked:
			muscles_worked_string = "\nTargets:\n"

		for muscle in self.muscles_worked:
			muscles_worked_string += "▫️ " + muscle + "\n"
		return f"{name_string}{video_link_string}{muscles_worked_string}"
