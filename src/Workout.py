"""
The workout class contains meta information about a particular workout 
(such as the workout creator, average length, difficulty level)
as well as a list of exercises.
"""


class Workout:
	def __init__(self, title="", created_by=""):
		self.title = title
		self.created_by = created_by
		self.length = 0
		self.running = False
		self.saves = 0
		self.exercises = []
		self.started = False

	def __str__(self):
		title_string = f"\nTitle: {self.title}"
		created_by_string = f"\nCreated By: {self.created_by}"
		length_string = f"\nLength: ~ {self.length} minutes"
		exercises_string = f"\nExercises: {self.exercises}"
		return f"{title_string}{created_by_string}{length_string}{exercises_string}"

	def display_summary(self):
		summary = ""
		for exercise in self.exercises:
			summary += f"You did {sum(exercise.reps)} {exercise.name}!"
		summary += "\n"
		return summary
