from uuid import uuid4

"""
The workout class contains meta information about a particular workout 
(such as the workout creator, average length, difficulty level)
as well as a list of exercises.
"""


class Workout:
	def __init__(self, title="", created_by=""):
		self.id = str(uuid4())
		# for completed workouts, the template_id property specifies the original saved workout
		# that the completed workout was based on.
		# Since saved workouts are the template, they do not a template_id
		self.template_id = ""
		self.title = title
		self.created_by = created_by
		self.duration = 0
		self.running = False
		self.saves = 0
		self.exercises = []
		self.running = False

	def __str__(self):
		title_string = f"*{self.title}*\n\n"
		length_string = f"_Duration: \\~ {self.duration} minutes_\n"
		exercises_string = ""
		if self.exercises:
			exercises_string = f"\nExercises:\n\n"
			for exercise in self.exercises:
				exercises_string += str(exercise) + "\n\n"
		return f"{title_string}{length_string}{exercises_string}"
