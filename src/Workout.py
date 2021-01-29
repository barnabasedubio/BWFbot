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
